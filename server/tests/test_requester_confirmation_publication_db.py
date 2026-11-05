from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ClosurePolicy, Ticket, TicketEvent
from auth.context import AuthContext, AuthType
from scripts.helpdesk_requester_confirmation import publish_confirmation
from tickets.closure_policy import requires_requester_confirmation
from tickets.requester_policy import requester_ticket_actions

pytestmark = [pytest.mark.asyncio, pytest.mark.db_cleanup("full")]


async def test_confirmation_publication_is_versioned_idempotent_and_updates_effective_old_ticket_policy(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    auth = AuthContext(actor_id="admin-test", actor_role="admin", auth_type=AuthType.UI_TOKEN)
    code = "guided_studio_20261011_closure"
    async with maker() as session:
        session.add(ClosurePolicy(code=code, version="1.0.2", title="Ordinary closure", is_active=True,
            config_json={"require_public_summary": True, "require_resolution_code": False, "requester_confirmation": {"required": False}}, published_at=datetime.now(timezone.utc)))
        session.add(ClosurePolicy(code="special", version="1.0.1", title="Special", is_active=True,
            config_json={"require_worklog": True}, published_at=datetime.now(timezone.utc)))
        session.add(Ticket(ticket_id="resolved-before-publication", title="Previously prepared result", description="Synthetic fixture", status="resolved",
            requester_id="prior-owner", requester_resolution_summary="Проверьте результат", resolved_at=datetime.now(timezone.utc),
            custom_fields={"request_template": {"policy_refs": {"closure": {"code": code, "version": "1.0.2"}}},
                           "resolution_confirmation_policy": {"required": False}}))
        session.add(Ticket(ticket_id="pending-before-publication", title="Pending result", description="Synthetic fixture", status="resolved",
            requester_id="prior-owner", requester_resolution_summary="Проверьте результат", resolved_at=datetime.now(timezone.utc),
            custom_fields={"request_template": {"policy_refs": {"closure": {"code": code, "version": "1.0.2"}}},
                "resolution_confirmation": {"pending": True, "request_id": "keep-original-request"},
                "resolution_confirmation_policy": {"required": True, "auto_close_after_days": 3}}))
        session.add(Ticket(ticket_id="special-pending", title="Special pending result", description="Synthetic fixture", status="resolved",
            requester_id="prior-owner", custom_fields={"request_template": {"policy_refs": {"closure": {"code": "special"}}},
                "resolution_confirmation": {"pending": True, "request_id": "special-request"},
                "resolution_confirmation_policy": {"required": True, "auto_close_after_days": 3}}))
        await session.commit()
    plan = await publish_confirmation(maker, auth, isolated_test=True)
    with pytest.raises(ValueError, match="fresh plan"):
        await publish_confirmation(maker, auth, apply=True, expected_fingerprint="stale", isolated_test=True)
    result = await publish_confirmation(maker, auth, apply=True, expected_fingerprint=plan["fingerprint"], isolated_test=True)
    assert result["changed"] is True
    assert result["reconciled_tickets"] == ["resolved-before-publication"]
    assert result["expiry_cleared_tickets"] == ["pending-before-publication"]
    async with maker() as session:
        rows = list((await session.execute(select(ClosurePolicy).where(ClosurePolicy.code == code))).scalars())
        assert len(rows) == 2 and [r.version for r in rows if r.is_active] == ["1.0.3"]
        special = await session.scalar(select(ClosurePolicy).where(ClosurePolicy.code == "special"))
        assert special.is_active and special.config_json == {"require_worklog": True}
        old_ticket = SimpleNamespace(custom_fields={"request_template": {"policy_refs": {"closure": {"code": code, "version": "1.0.2"}},
            "closure_policy": {"requester_confirmation": {"required": False}}}})
        assert await requires_requester_confirmation(session, old_ticket)
        previously_resolved = await session.get(Ticket, "resolved-before-publication")
        assert previously_resolved.status == "resolved" and previously_resolved.closed_at is None
        assert requester_ticket_actions(previously_resolved)["can_confirm_solution"]
        assert previously_resolved.custom_fields["resolution_confirmation_policy"]["auto_close_after_days"] is None
        events = list((await session.execute(select(TicketEvent).where(TicketEvent.ticket_id == previously_resolved.ticket_id))).scalars())
        assert len(events) == 1 and events[0].event_type == "closure_confirmation_requested"
        pending = await session.get(Ticket, "pending-before-publication")
        assert pending.custom_fields["resolution_confirmation"] == {"pending": True, "request_id": "keep-original-request"}
        assert pending.custom_fields["resolution_confirmation_policy"]["auto_close_after_days"] is None
        assert pending.status == "resolved" and pending.closed_at is None
        special_ticket = await session.get(Ticket, "special-pending")
        assert special_ticket.custom_fields["resolution_confirmation_policy"]["auto_close_after_days"] == 3
        assert special_ticket.custom_fields["resolution_confirmation"]["request_id"] == "special-request"
    again = await publish_confirmation(maker, auth, isolated_test=True)
    assert again["already_published"]
    assert not (await publish_confirmation(maker, auth, apply=True, expected_fingerprint=again["fingerprint"], isolated_test=True))["changed"]
