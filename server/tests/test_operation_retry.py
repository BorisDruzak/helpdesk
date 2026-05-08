"""Integration tests for policy-aware operation retry."""

import uuid

import pytest
from sqlalchemy import func, select, update

from app.db.engine import async_sessionmaker
from app.db.models import DeviceOutbox, Operation, Ticket, TicketEvent
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.repos.operations_repo import OperationsRepo
from tests.test_helpers import TEST_ECHO_TOOL
from tests.test_ticket_queue_routing_contracts import _seed_queue


async def _seed_retry_ticket(test_engine, *, device_id: str) -> str:
    ticket_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        queue = await _seed_queue(
            session,
            code=f"retry_{uuid.uuid4().hex[:8]}",
            name="Retry tests",
            members=["support-test"],
            auto_assign_enabled=False,
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Retry operation ticket",
                description="Ticket with explicit queue for operation retry tests.",
                status="in_progress",
                requester_id="retry-user",
                queue_id=queue.id,
                observer_root_trace_id=str(uuid.uuid4()),
            )
        )
        await session.commit()
    return ticket_id


async def _seed_failed_tool_operation(
    test_engine,
    *,
    device_id: str,
    ticket_id: str,
    tool_name: str = TEST_ECHO_TOOL,
    params: dict | None = None,
    retry_count: int = 0,
    max_retries: int = 2,
) -> str:
    operation_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        await op_repo.create_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="tool_call",
            tool_name=tool_name,
            actor_role="support",
            trace_id=trace_id,
            ticket_id=ticket_id,
            status="failed",
            max_retries=max_retries,
        )
        if retry_count:
            await op_repo.update_status(
                operation_id=operation_id,
                new_status="failed",
                expected_statuses=["failed"],
                retry_count=retry_count,
            )
        outbox_repo = DeviceOutboxRepo(session)
        outbox_id = await outbox_repo.enqueue_command(
            device_id=device_id,
            command_id=operation_id,
            command="run_tool",
            params={
                "tool_name": tool_name,
                "ticket_id": ticket_id,
                "params": params if params is not None else {"message": "retry me"},
                "call_id": "old-call-id",
            },
            request_id=operation_id,
            trace_id=trace_id,
            actor_role="support",
            operation_id=operation_id,
        )
        await session.execute(
            update(DeviceOutbox)
            .where(DeviceOutbox.id == outbox_id)
            .values(status="failed", error_code="TEST_FAILED", error_message="seeded failure")
        )
        await session.commit()
    return operation_id


@pytest.mark.asyncio
async def test_retry_failed_operation_revalidates_and_creates_new_operation(test_client, test_agent, test_engine):
    device_id = test_agent.device_id
    ticket_id = await _seed_retry_ticket(test_engine, device_id=device_id)
    original_operation_id = await _seed_failed_tool_operation(
        test_engine,
        device_id=device_id,
        ticket_id=ticket_id,
        params={"message": "retry me", "_operation_id": "must-not-replay"},
    )

    response = await test_client.post(
        f"/api/operations/{original_operation_id}/retry",
        json={"reason": "operator requested retry"},
    )

    assert response.status == 202, await response.text()
    payload = await response.json()
    assert payload["status"] == "accepted"
    retry_operation_id = payload["operation_id"]
    assert retry_operation_id != original_operation_id
    assert payload["retry_of_operation_id"] == original_operation_id
    assert payload["ticket_id"] == ticket_id
    assert payload["device_id"] == device_id

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        original = await op_repo.get_by_operation_id(original_operation_id)
        retried = await op_repo.get_by_operation_id(retry_operation_id)

        assert original.retry_count == 1
        assert retried is not None
        assert retried.kind == "tool_call"
        assert retried.tool_name == TEST_ECHO_TOOL
        assert retried.ticket_id == ticket_id
        assert retried.device_id == device_id
        assert retried.retry_of_operation_id == original_operation_id

        outbox_result = await session.execute(
            select(DeviceOutbox).where(DeviceOutbox.operation_id == retry_operation_id)
        )
        outbox = outbox_result.scalar_one_or_none()
        assert outbox is not None
        assert outbox.command == "run_tool"
        assert outbox.params["tool_name"] == TEST_ECHO_TOOL
        assert outbox.params["ticket_id"] == ticket_id
        assert outbox.params["params"]["message"] == "retry me"
        assert "_operation_id" not in outbox.params["params"]

        event_result = await session.execute(
            select(TicketEvent).where(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.operation_id == retry_operation_id,
                TicketEvent.event_type == "operation_retried",
            )
        )
        event = event_result.scalar_one_or_none()
        assert event is not None
        assert event.payload["retry_of_operation_id"] == original_operation_id
        assert event.payload["retry_operation_id"] == retry_operation_id

        retry_operation_trace_id = (
            await session.execute(select(Operation.trace_id).where(Operation.operation_id == retry_operation_id))
        ).scalar_one()
        assert event.trace_id == retry_operation_trace_id


@pytest.mark.asyncio
async def test_retry_consent_required_operation_creates_waiting_consent_without_dispatch(
    test_client,
    test_agent,
    test_engine,
    monkeypatch,
):
    device_id = test_agent.device_id
    ticket_id = await _seed_retry_ticket(test_engine, device_id=device_id)
    original_operation_id = await _seed_failed_tool_operation(
        test_engine,
        device_id=device_id,
        ticket_id=ticket_id,
        tool_name="observer_canary.consent_probe",
        params={"label": "retry-consent"},
    )

    class ConsentRetryToolService:
        def __init__(self, _state):
            pass

        async def get_tools_list(self, device_id_arg):
            assert device_id_arg == device_id
            return [
                {
                    "tool": "observer_canary.consent_probe",
                    "spec": {
                        "risk_level": "safe_read",
                        "metadata": {"requires_consent": True, "risk_level": "safe_read"},
                    },
                }
            ]

        async def get_tools_from_server(self, device_id_arg):
            assert device_id_arg == device_id
            return []

        async def run_tool(self, **_kwargs):
            raise AssertionError("consent-required retry must not dispatch before approval")

    monkeypatch.setattr("api.operations.ToolExecutionService", ConsentRetryToolService)

    response = await test_client.post(
        f"/api/operations/{original_operation_id}/retry",
        json={"reason": "operator requested consent retry"},
    )

    assert response.status == 202, await response.text()
    payload = await response.json()
    assert payload["status"] == "waiting_consent"
    retry_operation_id = payload["operation_id"]
    assert retry_operation_id != original_operation_id
    assert payload["retry_of_operation_id"] == original_operation_id
    assert payload["retry_requires_consent"] is True
    assert payload["consent_state"] == "waiting_consent"
    assert payload["consent_action_url"] == f"/api/operations/{retry_operation_id}/approve"

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        original = await OperationsRepo(session).get_by_operation_id(original_operation_id)
        retried = await OperationsRepo(session).get_by_operation_id(retry_operation_id)
        assert original.retry_count == 1
        assert retried is not None
        assert retried.status == "waiting_consent"
        assert retried.retry_of_operation_id == original_operation_id
        assert retried.tool_name == "observer_canary.consent_probe"

        outbox_count = (
            await session.execute(
                select(func.count(DeviceOutbox.id)).where(DeviceOutbox.operation_id == retry_operation_id)
            )
        ).scalar_one()
        assert outbox_count == 0

        consent_event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.operation_id == retry_operation_id,
                    TicketEvent.event_type == "operation_retry_consent_requested",
                )
            )
        ).scalar_one_or_none()
        assert consent_event is not None
        assert consent_event.payload["retry_of_operation_id"] == original_operation_id
        assert consent_event.payload["params"]["label"] == "retry-consent"

        started_event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.operation_id == retry_operation_id,
                    TicketEvent.event_type == "tool_call_started",
                )
            )
        ).scalar_one_or_none()
        assert started_event is not None
        assert started_event.payload["params"]["label"] == "retry-consent"

    approve_response = await test_client.post(
        f"/api/operations/{retry_operation_id}/approve",
        json={"reason": "requester consent approved"},
    )
    assert approve_response.status == 200, await approve_response.text()

    async with session_maker() as session:
        retried = await OperationsRepo(session).get_by_operation_id(retry_operation_id)
        assert retried.status in {"queued", "sent", "accepted", "running", "failed", "succeeded"}
        outbox = (
            await session.execute(select(DeviceOutbox).where(DeviceOutbox.operation_id == retry_operation_id))
        ).scalar_one()
        assert outbox.command == "run_tool"
        assert outbox.params["tool_name"] == "observer_canary.consent_probe"
        assert outbox.params["ticket_id"] == ticket_id
        assert outbox.params["params"]["label"] == "retry-consent"


@pytest.mark.asyncio
async def test_retry_rejects_non_terminal_operation(test_client, test_agent, test_engine):
    device_id = test_agent.device_id
    ticket_id = await _seed_retry_ticket(test_engine, device_id=device_id)
    operation_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        await op_repo.create_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="tool_call",
            tool_name=TEST_ECHO_TOOL,
            actor_role="support",
            trace_id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            status="running",
            max_retries=2,
        )
        await session.commit()

    response = await test_client.post(f"/api/operations/{operation_id}/retry", json={})

    assert response.status == 409
    payload = await response.json()
    assert payload["error_code"] == "OPERATION_NOT_RETRYABLE"


@pytest.mark.asyncio
async def test_ticket_scoped_retry_rejects_ticket_mismatch(test_client, test_agent, test_engine):
    device_id = test_agent.device_id
    ticket_id = await _seed_retry_ticket(test_engine, device_id=device_id)
    other_ticket_id = await _seed_retry_ticket(test_engine, device_id=device_id)
    operation_id = await _seed_failed_tool_operation(
        test_engine,
        device_id=device_id,
        ticket_id=ticket_id,
    )

    response = await test_client.post(
        f"/api/tickets/{other_ticket_id}/operations/{operation_id}/retry",
        json={},
    )

    assert response.status == 403
    payload = await response.json()
    assert payload["error_code"] == "TICKET_CONTEXT_MISMATCH"


@pytest.mark.asyncio
async def test_retry_rejects_missing_replay_payload(test_client, test_agent, test_engine):
    device_id = test_agent.device_id
    ticket_id = await _seed_retry_ticket(test_engine, device_id=device_id)
    operation_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        await op_repo.create_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="tool_call",
            tool_name=TEST_ECHO_TOOL,
            actor_role="support",
            trace_id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            status="failed",
            max_retries=2,
        )
        await session.commit()

    response = await test_client.post(f"/api/operations/{operation_id}/retry", json={})

    assert response.status == 409
    payload = await response.json()
    assert payload["error_code"] == "RETRY_PARAMS_UNAVAILABLE"
