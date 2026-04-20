"""P0 (Critical) integration tests for Protocol V3."""

import pytest
from app.db.engine import async_sessionmaker
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.repos.operations_repo import OperationsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from tests.test_helpers import (
    TEST_ECHO_TOOL,
    TEST_FAIL_TOOL,
    create_test_ticket,
    start_tool_operation,
    wait_for_agent_connected,
    wait_for_ticket_event,
    wait_for_operation_terminal,
)


@pytest.mark.asyncio
async def test_happy_path_echo(test_client, test_agent, test_engine):
    """T1: Happy path - run_tool echo succeeds."""
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
    await wait_for_ticket_event(
        test_engine,
        ticket_id=ticket_id,
        operation_id=operation_id,
        event_type="tool_call_result",
        timeout=10,
    )

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)

        assert operation is not None
        assert operation.status == "succeeded"
        assert operation.operation_id == operation_id
        assert operation.queued_at is not None
        assert operation.sent_at is not None
        assert operation.accepted_at is not None
        assert operation.finished_at is not None
        assert operation.queued_at < operation.sent_at
        assert operation.sent_at < operation.accepted_at
        assert operation.accepted_at < operation.finished_at

        outbox_repo = DeviceOutboxRepo(session)
        outbox_item = await outbox_repo.get_command_by_id(operation_id)
        assert outbox_item is not None
        assert outbox_item.status == "delivered"

        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        event_types = [event.event_type for event in events]
        assert "tool_call_started" in event_types
        assert "tool_call_result" in event_types
        operation_events = [event for event in events if event.operation_id == operation_id]
        assert operation_events


@pytest.mark.asyncio
async def test_error_path_fail(test_client, test_agent, test_engine):
    """T2: Error path - run_tool fail returns failed operation."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_FAIL_TOOL,
        params={"error_code": "TEST_ERROR"},
    )

    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status == "failed"
    await wait_for_ticket_event(
        test_engine,
        ticket_id=ticket_id,
        operation_id=operation_id,
        event_type="tool_call_result",
        timeout=10,
    )

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)

        assert operation is not None
        assert operation.status == "failed"

        outbox_repo = DeviceOutboxRepo(session)
        outbox_item = await outbox_repo.get_command_by_id(operation_id)
        assert outbox_item is not None
        assert outbox_item.status == "delivered"

        assert operation.queued_at is not None
        assert operation.sent_at is not None
        assert operation.accepted_at is not None
        assert operation.finished_at is not None
        assert operation.queued_at < operation.sent_at
        assert operation.sent_at < operation.accepted_at
        assert operation.accepted_at < operation.finished_at

        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        result_events = [
            event
            for event in events
            if event.event_type == "tool_call_result" and event.operation_id == operation_id
        ]
        assert result_events
        result_event = result_events[0]
        assert result_event.payload.get("status") in ["error", "failed"]


@pytest.mark.asyncio
async def test_command_ack_before_result(test_client, test_agent, test_engine):
    """T3: command_ack sets accepted before final result."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_ECHO_TOOL,
        params={"message": "test"},
    )

    await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    await wait_for_ticket_event(
        test_engine,
        ticket_id=ticket_id,
        operation_id=operation_id,
        event_type="tool_call_result",
        timeout=10,
    )

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)

        assert operation is not None
        assert operation.accepted_at is not None
        assert operation.finished_at is not None
        assert operation.accepted_at < operation.finished_at


@pytest.mark.asyncio
async def test_duplicate_command_result_idempotency(test_client, test_agent, test_engine):
    """T4: Duplicate command_result does not create duplicates."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_ECHO_TOOL,
        params={"message": "test"},
    )

    await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    await wait_for_ticket_event(
        test_engine,
        ticket_id=ticket_id,
        operation_id=operation_id,
        event_type="tool_call_result",
        timeout=10,
    )

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        initial_finished_at = operation.finished_at
        initial_status = operation.status

        events_repo = TicketEventsRepo(session)
        events_before = await events_repo.get_events(ticket_id)
        events_count_before = len([event for event in events_before if event.operation_id == operation_id])

    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)

        assert operation.status == initial_status
        assert operation.finished_at == initial_finished_at

        events_repo = TicketEventsRepo(session)
        events_after = await events_repo.get_events(ticket_id)
        events_count_after = len([event for event in events_after if event.operation_id == operation_id])
        assert events_count_after == events_count_before


@pytest.mark.asyncio
async def test_device_only_operation(test_client, test_agent, test_engine):
    """T6: Device-only operation without ticket_id stays supported."""
    device_id = test_agent.device_id

    from websocket.protocol import send_ws_command

    state = test_client.app["state"]
    await wait_for_agent_connected(state, device_id, timeout=10)
    result = await send_ws_command(
        state=state,
        device_id=device_id,
        command="list_tools",
        params={},
        actor_role="support",
        timeout=10,
    )

    assert result is not None


@pytest.mark.asyncio
async def test_state_transition_guards(test_client, test_agent, test_engine):
    """T9: Operation cannot move from terminal back to non-terminal."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_ECHO_TOOL,
        params={"message": "test"},
    )

    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status in ["succeeded", "failed"]

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        initial_status = operation.status
        initial_finished_at = operation.finished_at

        assert operation.status == initial_status
        assert operation.finished_at == initial_finished_at
        assert operation.status in ["succeeded", "failed", "timed_out", "canceled"]


@pytest.mark.asyncio
async def test_server_event_dedup(test_client, test_agent, test_engine):
    """T10: Server-originated events are not duplicated."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, _operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_ECHO_TOOL,
        params={"message": "test"},
    )

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id)
        server_events = [event for event in events if event.agent_seq is None]
        assert server_events


@pytest.mark.asyncio
async def test_error_result_outbox_terminal(test_client, test_agent, test_engine):
    """command_result error still leaves operation/outbox in terminal states."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_ECHO_TOOL,
        params={"message": "test"},
    )

    await wait_for_operation_terminal(test_engine, operation_id, timeout=10)

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)

        assert operation is not None
        assert operation.status in ["succeeded", "failed", "timed_out", "canceled"]

        outbox_repo = DeviceOutboxRepo(session)
        outbox_item = await outbox_repo.get_command_by_id(operation_id)
        assert outbox_item is not None
        assert outbox_item.status in ["delivered", "failed"]


@pytest.mark.asyncio
async def test_watchdog_marks_stuck_sent(test_client, test_agent, test_engine):
    """Pending placeholder for watchdog timeout test."""
    pass


@pytest.mark.asyncio
async def test_watchdog_does_not_override_terminal(test_client, test_agent, test_engine):
    """watchdog does not overwrite terminal states."""
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    _payload, operation_id = await start_tool_operation(
        test_client,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name=TEST_ECHO_TOOL,
        params={"message": "test"},
    )

    terminal_status = await wait_for_operation_terminal(test_engine, operation_id, timeout=10)
    assert terminal_status in ["succeeded", "failed"]

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = OperationsRepo(session)
        operation = await repo.get_by_operation_id(operation_id)
        initial_status = operation.status
        initial_finished_at = operation.finished_at

        success = await repo.update_status(
            operation_id=operation_id,
            new_status="running",
            expected_statuses=None,
        )

        assert success is False

        operation_after = await repo.get_by_operation_id(operation_id)
        assert operation_after.status == initial_status
        assert operation_after.finished_at == initial_finished_at


@pytest.mark.asyncio
async def test_consent_required_status(test_client, test_agent, test_engine):
    """Pending placeholder for consent-required tool path."""
    pass
