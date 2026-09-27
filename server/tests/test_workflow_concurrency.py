import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent
from app.repos.ticket_events_repo import TicketEventsRepo
from tests.test_ticket_queue_routing_contracts import _seed_queue
from tickets.workflow_service import TicketWorkflowService, WorkflowTransitionConflict

pytestmark = pytest.mark.db_cleanup("tickets")


@pytest.mark.asyncio
@pytest.mark.parametrize("losing_target", ["canceled", "queued"])
async def test_competing_transitions_have_one_winner_and_refresh_stale_identity(test_engine, losing_target):
    maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    ticket_id = str(uuid.uuid4())
    async with maker() as seed:
        seed.add(Ticket(ticket_id=ticket_id, device_id=None, title="Concurrent workflow",
                        description="Isolated acceptance", requester_id="test-requester", status="new",
                        assignee_id=None, custom_fields={}))
        await seed.commit()

    async with maker() as first, maker() as second:
        stale = await TicketEventsRepo(second).get_ticket(ticket_id)
        assert stale.status == "new"
        await TicketWorkflowService(first, TicketEventsRepo(first)).apply_status_transition(
            ticket_id, "new", "queued", "first", "support")
        started = asyncio.Event()

        async def competing_transition():
            started.set()
            try:
                await TicketWorkflowService(second, TicketEventsRepo(second)).apply_status_transition(
                    ticket_id, "new", losing_target, "second", "support")
                await second.commit()
            except BaseException:
                await second.rollback()
                raise

        task = asyncio.create_task(competing_transition())
        try:
            await asyncio.wait_for(started.wait(), 5)
            try:
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(asyncio.shield(task), 0.2)
            finally:
                await first.commit()
            with pytest.raises(WorkflowTransitionConflict):
                await asyncio.wait_for(task, 10)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async with maker() as verification:
        ticket = await verification.get(Ticket, ticket_id)
        assert ticket.status == "queued"
        events = (await verification.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id))).scalars().all()
        assert len(events) == 1
        assert events[0].event_type == "status_changed"
        assert events[0].payload["actor_id"] == "first"
        assert events[0].payload["from_status"] == "new"
        assert events[0].payload["to_status"] == "queued"


@pytest.mark.asyncio
async def test_locked_transition_preserves_pending_assignment_without_autoflush(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    ticket_id = str(uuid.uuid4())
    async with maker() as session:
        queue = await _seed_queue(session, code="pending_" + uuid.uuid4().hex,
                                  name="Pending assignment", members=[], auto_assign_enabled=False)
        session.add(Ticket(ticket_id=ticket_id, device_id=None, title="Pending assignment",
                           description="Isolated acceptance", requester_id="test-requester", status="new",
                           queue_id=queue.id, assignee_id=None, custom_fields={}))
        await session.commit()
        repo = TicketEventsRepo(session)
        await repo.update_ticket(ticket_id, assignee_id="test-operator")
        await TicketWorkflowService(session, repo).apply_status_transition(
            ticket_id, "new", "assigned", "test", "support")
        await session.commit()
    async with maker() as verification:
        ticket = await verification.get(Ticket, ticket_id)
        assert ticket.status == "assigned"
        assert ticket.assignee_id == "test-operator"
