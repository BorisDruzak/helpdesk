import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
import config
from app.db.models import Ticket, TicketSlaPolicy
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.routing_service import TicketRoutingService
from tests.test_ticket_queue_routing_contracts import _seed_queue

pytestmark = pytest.mark.db_cleanup("tickets")


@pytest.mark.asyncio
async def test_unified_routing_persists_priority_sla_and_approval_for_new_and_existing_tickets(test_engine, monkeypatch):
    import uuid
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified")
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        common = await _seed_queue(session, code=config.TICKET_TAKE_QUEUE_COMMON_CODE, name="Synthetic common")
        legacy = await _seed_queue(session, code="legacy_" + uuid.uuid4().hex[:8], name="Synthetic legacy")
        sla = TicketSlaPolicy(name="Synthetic routing SLA")
        session.add(sla)
        await session.flush()
        approval = {"require_comment_on_reject": True}
        for initial_queue in (None, legacy.id):
            fields = {"priority_class": "P3", "request_template": {"routing_policy": {"rules": [{"when": {}, "then": {"queue_id": legacy.id, "minimum_priority": "P1", "sla_policy_id": sla.id, "approval_policy": approval}}]}}}
            ticket = Ticket(ticket_id=str(uuid.uuid4()), device_id=None, title="Synthetic policy", description="Isolated DB only", requester_id="synthetic", status="new", queue_id=initial_queue, custom_fields=fields)
            session.add(ticket)
            await session.flush()
            repo = TicketEventsRepo(session)
            await TicketRoutingService(session, repo, None).apply_routing(ticket.ticket_id, None)
            await session.commit()
            await session.refresh(ticket)
            assert ticket.queue_id == (common.id if initial_queue is None else legacy.id)
            assert ticket.sla_policy_id == sla.id
            assert ticket.custom_fields["priority_class"] == "P1"
            assert ticket.custom_fields["request_template"]["approval_policy"] == approval

