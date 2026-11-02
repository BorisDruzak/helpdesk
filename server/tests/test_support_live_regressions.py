"""Regressions from administrator support-mode acceptance on old tickets."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent
from tests.test_support_work import work_client, seed_work

pytestmark = pytest.mark.db_cleanup("web_support")


@pytest.mark.asyncio
async def test_old_noisy_ticket_keeps_latest_public_reply_and_separate_private_notes(work_client, test_engine):
    ticket_id = await seed_work(test_engine, status="in_progress", assignee="support1")
    start = datetime.now(timezone.utc) - timedelta(days=2)
    async with async_sessionmaker(test_engine)() as session:
        session.add_all([TicketEvent(ticket_id=ticket_id, event_type="sla_reminder_sent",
            payload={"summary": "Historical SLA reminder"}, created_at=start + timedelta(seconds=i)) for i in range(700)])
        await session.commit()
    base = f"/api/web/support/tickets/{ticket_id}"
    reply = await work_client.post(base + "/messages", json={"text": "Latest public reply"})
    assert reply.status == 200, await reply.text()
    # A busy private stream must not evict the public conversation.
    async with async_sessionmaker(test_engine)() as session:
        session.add_all([TicketEvent(ticket_id=ticket_id, event_type="chat_message",
            payload={"text": f"Private note {i}", "visibility": "internal", "from_role": "support"},
            created_at=datetime.now(timezone.utc) + timedelta(seconds=i)) for i in range(300)])
        await session.commit()
    for filter_name, expected in (("messages", "Latest public reply"), ("internal", "Private note 299")):
        response = await work_client.get(base + "/timeline", params={"filter": filter_name})
        assert response.status == 200, await response.text()
        items = (await response.json())["data"]["items"]
        assert expected in [item["text"] for item in items]
        assert len(items) <= 80
        assert [item["ts"] for item in items] == sorted(item["ts"] for item in items)
        assert all((item["visibility"] == "internal") == (filter_name == "internal") for item in items)


@pytest.mark.asyncio
async def test_admin_must_claim_legacy_in_progress_ticket_before_resolution(work_client, test_engine):
    ticket_id = await seed_work(test_engine, status="in_progress", assignee=None)
    base = f"/api/web/support/tickets/{ticket_id}"
    headers = {"X-Test-Actor": "admin"}
    response = await work_client.get(base, headers=headers)
    actions = (await response.json())["data"]["actions"]
    assert actions["take_in_work"]["allowed"] is True
    assert "resolved" not in [option["value"] for option in actions["status_options"]]
    rejected = await work_client.post(base + "/status", headers=headers,
        json={"to_status": "resolved", "requester_resolution_summary": "Premature result"})
    assert rejected.status == 409, await rejected.text()
    assert (await rejected.json())["error_code"] == "TICKET_NOT_IN_WORK"
    claimed = await work_client.post(base + "/assign", headers=headers,
        json={"assignee_id": "admin", "claim": True, "expected_assignee_id": None, "reason": "Explicitly take legacy ticket"})
    assert claimed.status == 200, await claimed.text()
    response = await work_client.get(base, headers=headers)
    actions = (await response.json())["data"]["actions"]
    assert "resolved" in [option["value"] for option in actions["status_options"]]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "in_progress" and ticket.assignee_id == "admin"
        events = (await session.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id))).scalars().all()
        assert any(event.event_type == "assignee_changed" for event in events)
        assert not any(event.event_type == "status_changed" for event in events)


@pytest.mark.asyncio
async def test_competing_legacy_claims_do_not_replace_the_first_owner(work_client, test_engine):
    ticket_id = await seed_work(test_engine, status="in_progress", assignee=None)
    base = f"/api/web/support/tickets/{ticket_id}/assign"
    responses = await asyncio.gather(*(work_client.post(base, headers={"X-Test-Actor": actor},
        json={"assignee_id": actor, "claim": True, "expected_assignee_id": None}) for actor in ("support1", "support2")))
    assert sorted(response.status for response in responses) == [200, 409], [await response.text() for response in responses]
    winner = ("support1", "support2")[next(i for i, response in enumerate(responses) if response.status == 200)]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "in_progress" and ticket.assignee_id == winner
        events = (await session.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "assignee_changed"))).scalars().all()
        assert len(events) == 1
