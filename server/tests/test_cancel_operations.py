"""Integration tests for cancel operations functionality."""

import asyncio

import pytest
from app.db.engine import async_sessionmaker
from app.repos.operations_repo import OperationsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from tests.test_helpers import (
    TEST_ECHO_TOOL,
    TEST_SLOW_ECHO_TOOL,
    create_test_ticket,
    start_tool_operation,
    wait_for_operation_status,
    wait_for_operation_terminal,
)


@pytest.mark.asyncio
async def test_cancel_running_operation(test_client, test_agent, test_engine):
    """T1: Cancel running operation -> canceled."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_SLOW_ECHO_TOOL,
        params={"message": "hi", "delay": 2},
    )

    await wait_for_operation_status(test_engine, operation_id, ["accepted", "running"], timeout=5)

    cancel_resp = await test_client.post(
        f"/api/operations/{operation_id}/cancel",
        json={"reason": "User requested", "actor_role": "user"},
    )
    assert cancel_resp.status == 200
    cancel_data = await cancel_resp.json()
    assert cancel_data["status"] == "ok"
    cancel_operation_id = cancel_data["cancel_operation_id"]

    target_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert target_status == "canceled"

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        target_op = await op_repo.get_by_operation_id(operation_id)
        cancel_op = await op_repo.get_by_operation_id(cancel_operation_id)

        assert target_op.status == "canceled"
        assert target_op.status_before_cancel is None
        assert target_op.canceled_at is not None

        assert cancel_op.status == "succeeded"
        assert cancel_op.kind == "cancel_operation"
        assert cancel_op.cancel_target_operation_id == operation_id

        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        event_types = [e.event_type for e in events]
        assert "op_cancel_requested" in event_types
        assert "op_canceled" in event_types


@pytest.mark.asyncio
async def test_cancel_idempotent(test_client, test_agent, test_engine):
    """T3: Cancel idempotent on cancel_requested."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_SLOW_ECHO_TOOL,
        params={"message": "hi", "delay": 2},
    )

    await wait_for_operation_status(test_engine, operation_id, ["accepted", "running"], timeout=5)

    cancel_resp1 = await test_client.post(
        f"/api/operations/{operation_id}/cancel",
        json={"reason": "First cancel", "actor_role": "user"},
    )
    assert cancel_resp1.status == 200
    cancel_data1 = await cancel_resp1.json()
    cancel_operation_id1 = cancel_data1["cancel_operation_id"]

    cancel_resp2 = await test_client.post(
        f"/api/operations/{operation_id}/cancel",
        json={"reason": "Second cancel", "actor_role": "user"},
    )
    assert cancel_resp2.status == 200
    cancel_data2 = await cancel_resp2.json()
    assert cancel_data2["status"] == "ok"
    assert cancel_data2["cancel_operation_id"] == cancel_operation_id1

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        target_op = await op_repo.get_by_operation_id(operation_id)
        assert target_op.status == "cancel_requested"
        assert target_op.active_cancel_operation_id == cancel_operation_id1


@pytest.mark.asyncio
async def test_cancel_terminal_operation(test_client, test_agent, test_engine):
    """T4: Cancel terminal operation -> 409/no-op."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_ECHO_TOOL,
        params={"message": "hi"},
    )

    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status == "succeeded"

    cancel_resp = await test_client.post(
        f"/api/operations/{operation_id}/cancel",
        json={"reason": "Too late", "actor_role": "user"},
    )
    assert cancel_resp.status == 409
    cancel_data = await cancel_resp.json()
    assert cancel_data["status"] == "noop"
    assert cancel_data["reason"] == "already_terminal"

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        operation = await op_repo.get_by_operation_id(operation_id)
        assert operation.status == "succeeded"


@pytest.mark.asyncio
async def test_cancel_request_race(test_client, test_agent, test_engine):
    """T5: Two parallel cancel requests -> one cancel-op (idempotency)."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_SLOW_ECHO_TOOL,
        params={"message": "hi", "delay": 2},
    )

    await wait_for_operation_status(test_engine, operation_id, ["accepted", "running"], timeout=5)

    async def cancel_request():
        resp = await test_client.post(
            f"/api/operations/{operation_id}/cancel",
            json={"reason": "Race test", "actor_role": "user"},
        )
        return await resp.json()

    results = await asyncio.gather(cancel_request(), cancel_request())

    cancel_op_ids = [result.get("cancel_operation_id") for result in results if result.get("status") == "ok"]
    assert cancel_op_ids
    assert len(set(cancel_op_ids)) == 1, f"Expected single cancel_op_id, got: {cancel_op_ids}"

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        target_op = await op_repo.get_by_operation_id(operation_id)
        assert target_op.active_cancel_operation_id == cancel_op_ids[0]


@pytest.mark.asyncio
async def test_cancel_after_completion_race(test_client, test_agent, test_engine):
    """T6: Cancel after operation completes -> no rollback to incorrect status."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_ECHO_TOOL,
        params={"message": "hi"},
    )

    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status == "succeeded"

    cancel_resp = await test_client.post(
        f"/api/operations/{operation_id}/cancel",
        json={"reason": "Too late", "actor_role": "user"},
    )
    assert cancel_resp.status == 409

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        target_op = await op_repo.get_by_operation_id(operation_id)
        assert target_op.status == "succeeded"
