"""Real PostgreSQL acceptance for reversible unified queue mode."""
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import config
from app.db.models import Ticket, UiUser
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.assignment_service import TicketAssignmentService, TicketAssignmentError
from tests.test_support_work import seed_work, work_client

pytestmark = pytest.mark.db_cleanup("web_support")


@pytest.mark.asyncio
@pytest.mark.parametrize("unified", [False, True])
async def test_queue_mode_controls_scope_take_and_restores_partitioning(work_client, test_engine, monkeypatch, unified):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified" if unified else "partitioned")
    ticket_id = await seed_work(test_engine, members=["support2"])
    queue = await work_client.get("/api/web/support/queue")
    assert queue.status == 200, await queue.text()
    payload = (await queue.json())["data"]
    assert payload["queue_mode"] == ("unified" if unified else "partitioned")
    assert any(row["ticket_id"] == ticket_id for row in payload["tickets"]) is unified
    detail = await work_client.get(f"/api/web/support/tickets/{ticket_id}")
    assert detail.status == (200 if unified else 403), await detail.text()
    response = await work_client.post(f"/api/web/support/tickets/{ticket_id}/status", json={"to_status": "in_progress"})
    assert response.status == (200 if unified else 403), await response.text()
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.assignee_id == ("support1" if unified else None)
        assert ticket.first_response_at is None
        # The historical queue remains intact when the feature is switched back.
        assert ticket.queue_id is not None
        monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "partitioned")
        assert await TicketEventsRepo(session).is_actor_in_queue(ticket.queue_id, "support1") is False


@pytest.mark.asyncio
async def test_unified_assignment_still_requires_active_staff_and_capacity(work_client, test_engine, monkeypatch):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "unified")
    ticket_id = await seed_work(test_engine, members=["support2"])
    async with async_sessionmaker(test_engine)() as session:
        session.add(UiUser(user_login="requester", password_hash="!", actor_role="user", is_active=True))
        session.add(UiUser(user_login="inactive", password_hash="!", actor_role="support", is_active=False))
        await session.commit()
        repo = TicketEventsRepo(session)
        ticket = await session.get(Ticket, ticket_id)
        for actor in ("requester", "inactive", "unknown"):
            assert await repo.is_actor_in_queue(ticket.queue_id, actor) is False
            with pytest.raises(TicketAssignmentError):
                await TicketAssignmentService(repo).validate_manual_assignment(ticket, actor, activating=True)
        loads = await repo.list_assignable_users_with_load(queue_id=ticket.queue_id)
        assert {row["user_login"] for row in loads} == {"admin", "support1", "support2"}
        monkeypatch.setattr(repo, "count_active_tickets_for_assignee", AsyncMock(return_value=3))
        with pytest.raises(TicketAssignmentError) as exc:
            await TicketAssignmentService(repo).validate_manual_assignment(ticket, "support1", activating=True)
        assert exc.value.code == "ASSIGNEE_CAPACITY_REACHED"
