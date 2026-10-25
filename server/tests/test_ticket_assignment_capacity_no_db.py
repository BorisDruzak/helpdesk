"""Capacity regressions with deterministic transaction and row-lock doubles."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.assignment_service import TicketAssignmentError, TicketAssignmentService
from tests.test_web_support_api import web_support_client

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_concurrent_manual_activation_cannot_take_the_last_slot_twice(monkeypatch):
    import tickets.assignment_service as assignment

    monkeypatch.setattr(assignment, "unified_queue_enabled", lambda: False)
    row_lock = asyncio.Lock()
    unlocked_reads = asyncio.Barrier(2)
    load = 2

    class TransactionRepo:
        locked = False

        async def is_actor_in_queue(self, *_):
            return True

        async def lock_assignee_for_update(self, _assignee):
            await row_lock.acquire()
            self.locked = True
            return True

        async def count_active_tickets_for_assignee(self, _assignee):
            snapshot = load
            if not self.locked:
                # Both transactions observe the same committed load without a lock.
                await unlocked_reads.wait()
            return snapshot

    async def activate(ticket_id):
        nonlocal load
        repo = TransactionRepo()
        ticket = SimpleNamespace(ticket_id=ticket_id, status="new", queue_id=1, assignee_id=None)
        try:
            await TicketAssignmentService(repo).validate_manual_assignment(ticket, "operator", activating=True)
            load += 1  # Transaction's status/assignee update, then commit.
            return "accepted"
        except TicketAssignmentError as exc:
            return exc.code
        finally:
            if repo.locked:
                row_lock.release()

    results = await asyncio.wait_for(asyncio.gather(activate("first"), activate("second")), timeout=2)
    assert sorted(results) == ["ASSIGNEE_CAPACITY_REACHED", "accepted"]
    assert load == 3


@pytest.mark.asyncio
async def test_retained_assignee_reactivation_checks_capacity():
    repo = SimpleNamespace(is_actor_in_queue=AsyncMock(return_value=True),
                           lock_assignee_for_update=AsyncMock(return_value=True),
                           count_active_tickets_for_assignee=AsyncMock(return_value=3))
    ticket = SimpleNamespace(status="waiting_on_user", queue_id=1, assignee_id="operator")
    with pytest.raises(TicketAssignmentError) as exc:
        await TicketAssignmentService(repo).validate_manual_assignment(ticket, "operator", activating=True)
    assert exc.value.code == "ASSIGNEE_CAPACITY_REACHED"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,activating", [("assigned", True), ("in_progress", False), ("waiting_on_user", False)])
async def test_unchanged_assignment_without_increasing_load_is_allowed_at_capacity(status, activating):
    repo = SimpleNamespace(is_actor_in_queue=AsyncMock(return_value=True),
                           lock_assignee_for_update=AsyncMock(return_value=True),
                           count_active_tickets_for_assignee=AsyncMock(return_value=3))
    ticket = SimpleNamespace(status=status, queue_id=1, assignee_id="operator")
    await TicketAssignmentService(repo).validate_manual_assignment(ticket, "operator", activating=activating)
    repo.count_active_tickets_for_assignee.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_capacity_lock_is_the_same_user_row_as_auto_assignment():
    from sqlalchemy.dialects import postgresql

    statements = []

    class Session:
        async def execute(self, statement):
            statements.append(str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})))
            return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(user_login="operator"))

    repo = TicketEventsRepo(Session())
    assert await repo.lock_assignee_for_update("operator") is True
    assert "ui_users.user_login = 'operator'" in statements[0]
    assert statements[0].endswith("FOR UPDATE")


@pytest.mark.asyncio
@pytest.mark.parametrize("auto_assign", [False, True])
async def test_assignment_locks_and_refreshes_ticket_before_target_capacity(auto_assign, monkeypatch):
    import tickets.assignment_service as assignment

    monkeypatch.setattr(assignment, "unified_queue_enabled", lambda: False)
    stale = SimpleNamespace(ticket_id="ticket", queue_id=1, status="waiting_on_user", assignee_id="operator")
    current = SimpleNamespace(ticket_id="ticket", queue_id=1, status="in_progress", assignee_id="other")
    order = []

    async def get_ticket(ticket_id, *, for_update=False):
        assert ticket_id == "ticket" and for_update
        order.append("ticket")
        return current

    async def lock_target(*_, **__):
        order.append("target")
        return True

    async def select_target(*_, **__):
        await lock_target()
        raise TicketAssignmentError("full", code="ASSIGNEE_CAPACITY_REACHED")

    repo = SimpleNamespace(get_ticket=get_ticket, lock_assignee_for_update=lock_target,
                           select_assignee_for_update=select_target,
                           get_queue=AsyncMock(return_value=SimpleNamespace(auto_assign_enabled=True)),
                           is_actor_in_queue=AsyncMock(return_value=True),
                           count_active_tickets_for_assignee=AsyncMock(return_value=3))
    with pytest.raises(TicketAssignmentError) as exc:
        await TicketAssignmentService(repo).resolve_assignee(stale, requested_assignee_id="operator", auto_assign=auto_assign)
    assert exc.value.code == "ASSIGNEE_CAPACITY_REACHED"
    assert order == ["ticket", "target"]


@pytest.mark.asyncio
@pytest.mark.parametrize("target_status", ["assigned", "in_progress"])
async def test_canonical_workflow_blocks_retained_assignee_reactivation_at_capacity(target_status, monkeypatch):
    from tickets import workflow_service as workflow
    from tickets.workflow_profiles import get_workflow_profile

    ticket = SimpleNamespace(ticket_id="ticket", status="waiting_on_user", assignee_id="operator", device_id=None, queue_id=1)
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket), lock_assignee_for_update=AsyncMock(return_value=True),
                           count_active_tickets_for_assignee=AsyncMock(return_value=3), add_event=AsyncMock(return_value=(1, None)))
    monkeypatch.setattr(workflow, "load_ticket_workflow_profile", AsyncMock(return_value=get_workflow_profile("service_request")))
    monkeypatch.setattr(workflow, "_validate_transition_gate", AsyncMock(return_value={}))
    monkeypatch.setattr(workflow, "validate_approval_policy", AsyncMock(return_value={}))
    service = workflow.TicketWorkflowService(SimpleNamespace(), repo)
    for effect in ("_apply_waiting_effects", "_apply_gate_actions", "_persist_transition_and_finalize"):
        monkeypatch.setattr(service, effect, AsyncMock())
    with pytest.raises(TicketAssignmentError) as exc:
        await service.apply_status_transition(
            ticket_id="ticket", from_status="waiting_on_user", to_status=target_status, actor_id="operator", actor_role="support")
    assert exc.value.code == "ASSIGNEE_CAPACITY_REACHED"
    assert ticket.status == "waiting_on_user"


@pytest.mark.asyncio
@pytest.mark.parametrize("requested,processed", [(["b", "a"], ["b", "a"]), ([" b ", "a", "b"], ["b", "a"]),
                                                (["b", "closed", "missing"], ["b"])])
async def test_bulk_assignment_prelocks_unique_tickets_before_operator_lock(web_support_client, monkeypatch, requested, processed):
    import config
    from tickets import handlers
    from tickets import ola_service

    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", "partitioned")
    ticket_rows = {key: SimpleNamespace(ticket_id=key, device_id=None, queue_id=None, assignee_id=None,
                                       status="closed" if key == "closed" else "assigned") for key in ("a", "b", "closed")}
    acquired = set()
    operations = []
    assignments = []

    class Repo:
        async def get_ticket(self, ticket_id, *, for_update=False):
            if for_update and ticket_id not in acquired:
                acquired.add(ticket_id)
                operations.append(("ticket", ticket_id))
            return ticket_rows.get(ticket_id)

        async def lock_assignee_for_update(self, user_login):
            operations.append(("operator", user_login))
            return True

        async def count_active_tickets_for_assignee(self, user_login):
            return sum(row.assignee_id == user_login for row in ticket_rows.values())

        async def update_ticket(self, ticket_id, **updates):
            assignments.append(ticket_id)
            for key, value in updates.items():
                setattr(ticket_rows[ticket_id], key, value)

        add_event = AsyncMock(return_value=(1, None))
        touch_user_last_assignment = AsyncMock()

    session = SimpleNamespace(commit=AsyncMock())

    @asynccontextmanager
    async def transaction():
        yield session

    monkeypatch.setattr(handlers, "get_session", transaction)
    monkeypatch.setattr(handlers, "TicketEventsRepo", lambda _: Repo())
    monkeypatch.setattr(ola_service, "close_ola_ack", AsyncMock())
    response = await web_support_client.post("/api/tickets/bulk_assign", json={"ticket_ids": requested, "assignee_id": "operator"})
    assert response.status == 200
    body = await response.json()
    assert body["assigned"] == len(processed)
    expected_tickets = sorted({value.strip() for value in requested if value.strip()})
    assert operations[:len(expected_tickets)] == [("ticket", ticket_id) for ticket_id in expected_tickets]
    assert assignments == processed
