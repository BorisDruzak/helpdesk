"""Isolated PostgreSQL acceptance for the shared assignment capacity lock."""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

import config
from app.db.models import Ticket, UiUser
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.assignment_service import TicketAssignmentError, TicketAssignmentService
from tests.pg_lock_probe import wait_for_backend_blocker
from auth.context import AuthContext, AuthType
from tickets import handlers

pytestmark = pytest.mark.db_cleanup("web_support")


@pytest.mark.asyncio
async def test_parallel_manual_activations_share_the_operator_capacity_lock(test_engine, monkeypatch):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "partitioned")
    maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    operator = "capacity-" + uuid.uuid4().hex
    ticket_ids = [str(uuid.uuid4()) for _ in range(4)]
    async with maker() as seed:
        seed.add(UiUser(user_login=operator, password_hash="!", actor_role="support", is_active=True))
        for index, ticket_id in enumerate(ticket_ids):
            seed.add(Ticket(ticket_id=ticket_id, device_id=None, title="Capacity acceptance", description="Isolated test",
                            status="in_progress" if index < 2 else "new", assignee_id=operator if index < 2 else None))
        await seed.commit()

    async with maker() as first, maker() as second:
        first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
        second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
        repo = TicketEventsRepo(first)
        ticket = await repo.get_ticket(ticket_ids[2], for_update=True)
        await TicketAssignmentService(repo).validate_manual_assignment(ticket, operator, activating=True)
        await repo.update_ticket(ticket.ticket_id, status="in_progress", assignee_id=operator)

        async def second_activation():
            other_repo = TicketEventsRepo(second)
            other = await other_repo.get_ticket(ticket_ids[3], for_update=True)
            try:
                await TicketAssignmentService(other_repo).validate_manual_assignment(other, operator, activating=True)
                await other_repo.update_ticket(other.ticket_id, status="in_progress", assignee_id=operator)
                await second.commit()
            finally:
                await second.rollback()

        task = asyncio.create_task(second_activation())
        try:
            await wait_for_backend_blocker(test_engine, blocked_pid=second_pid, blocker_pid=first_pid, task=task)
            await first.commit()
            with pytest.raises(TicketAssignmentError) as exc:
                await asyncio.wait_for(task, 10)
            assert exc.value.code == "ASSIGNEE_CAPACITY_REACHED"
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async with maker() as verification:
        count = await verification.scalar(select(func.count()).select_from(Ticket).where(
            Ticket.assignee_id == operator, Ticket.status.in_(("assigned", "in_progress"))))
        assert count == 3
        assert (await verification.get(Ticket, ticket_ids[3])).status == "new"


@pytest.mark.asyncio
async def test_reversed_bulk_assignment_requests_wait_on_ticket_locks_before_capacity(test_engine, monkeypatch):
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "partitioned")
    maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    operator = "bulk-capacity-" + uuid.uuid4().hex
    ticket_ids = sorted(str(uuid.uuid4()) for _ in range(2))
    async with maker() as seed:
        seed.add(UiUser(user_login=operator, password_hash="!", actor_role="support", is_active=True))
        for ticket_id in ticket_ids:
            seed.add(Ticket(ticket_id=ticket_id, device_id=None, title="Bulk lock ordering", description="Isolated test",
                            status="in_progress", assignee_id=None))
        await seed.commit()

    async with maker() as first, maker() as second:
        first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
        second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
        current_session = ContextVar("bulk_assignment_test_session")
        capacity_reached = asyncio.Event()
        release_first = asyncio.Event()

        class PausedCapacityRepo(TicketEventsRepo):
            async def lock_assignee_for_update(self, user_login, *, skip_locked=False):
                if self.session is first and not capacity_reached.is_set():
                    # Pause exactly after the first command's ticket prelocks.
                    capacity_reached.set()
                    await release_first.wait()
                return await super().lock_assignee_for_update(user_login, skip_locked=skip_locked)

        @asynccontextmanager
        async def isolated_session():
            session = current_session.get()
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

        class Request(dict):
            async def json(self):
                return self.payload

        async def assign(session, requested_ids):
            marker = current_session.set(session)
            try:
                request = Request(auth_context=AuthContext(actor_id=operator, actor_role="support", auth_type=AuthType.UI_TOKEN))
                request.payload = {"ticket_ids": requested_ids, "assignee_id": operator}
                return await handlers.handle_tickets_bulk_assign(request)
            finally:
                current_session.reset(marker)

        monkeypatch.setattr(handlers, "get_session", isolated_session)
        monkeypatch.setattr(handlers, "TicketEventsRepo", PausedCapacityRepo)
        first_task = asyncio.create_task(assign(first, list(reversed(ticket_ids))))
        second_task = None
        try:
            await asyncio.wait_for(capacity_reached.wait(), 5)
            second_task = asyncio.create_task(assign(second, ticket_ids))
            await wait_for_backend_blocker(test_engine, blocked_pid=second_pid, blocker_pid=first_pid, task=second_task)
            release_first.set()
            responses = await asyncio.wait_for(asyncio.gather(first_task, second_task), 10)
            assert [response.status for response in responses] == [200, 200]
            assert [json.loads(response.text)["assigned"] for response in responses] == [2, 2]
        finally:
            release_first.set()
            tasks = [task for task in (first_task, second_task) if task is not None]
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async with maker() as verification:
        rows = (await verification.execute(select(Ticket).where(Ticket.ticket_id.in_(ticket_ids)))).scalars().all()
        assert len(rows) == 2
        assert all(ticket.assignee_id == operator and ticket.status == "in_progress" for ticket in rows)
