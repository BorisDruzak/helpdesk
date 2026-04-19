from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

from sqlalchemy import select

import pytest

from app.db import get_session
from app.db.models import Operation, TicketEvent
from auth.context import AuthContext, AuthType
from tests.test_helpers import TEST_ECHO_TOOL, create_test_ticket
from websocket.protocol import send_ws_command
from websocket.protocol import WsCommandQueueFullError


ADMIN_TOKEN = "test-ui-admin-token"


def _auth(token: str = ADMIN_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_send_ws_command_async_releases_run_tool_slot(monkeypatch):
    class _FakeSession:
        async def commit(self):
            return None

    @asynccontextmanager
    async def _fake_get_session():
        yield _FakeSession()

    class _FakeDeviceOutboxRepo:
        def __init__(self, session):
            self.session = session

        async def enqueue_command(
            self,
            *,
            device_id,
            command_id,
            command,
            params,
            request_id,
            trace_id,
            actor_role,
            operation_id,
        ):
            return f"outbox-{command_id}"

    class _FakeOperationsRepo:
        def __init__(self, session):
            self.session = session

        async def get_by_operation_id(self, operation_id):
            return None

    class _FakeOperationService:
        def __init__(self, session, publisher=None):
            self.session = session
            self.publisher = publisher

        async def enqueue_operation(
            self,
            *,
            operation_id,
            device_id,
            kind,
            actor_role,
            trace_id,
            ticket_id=None,
            job_id=None,
            tool_name=None,
            command_name=None,
            timeout_override_sec=None,
            playbook_run_id=None,
            max_retries=3,
            initial_status="queued",
        ):
            return SimpleNamespace(
                operation_id=operation_id,
                device_id=device_id,
                kind=kind,
                actor_role=actor_role,
                trace_id=trace_id,
                ticket_id=ticket_id,
                job_id=job_id,
                tool_name=tool_name,
                status=initial_status,
            )

    class _FakeState:
        def __init__(self):
            self.connected_agents = {
                "device-async-1": {
                    "metadata": {"device_id": "device-async-1"},
                }
            }

        def get_agent(self, device_id):
            return self.connected_agents.get(device_id)

    monkeypatch.setattr("app.db.get_session", _fake_get_session)
    monkeypatch.setattr("app.repos.DeviceOutboxRepo", _FakeDeviceOutboxRepo)
    monkeypatch.setattr("app.repos.OperationsRepo", _FakeOperationsRepo)
    monkeypatch.setattr("app.services.OperationService", _FakeOperationService)

    state = _FakeState()
    auth_context = AuthContext(
        actor_id="support-test",
        actor_role="support",
        auth_type=AuthType.UI_TOKEN,
        token="test-token",
    )

    first_result = await send_ws_command(
        state=state,
        device_id="device-async-1",
        command="run_tool",
        params={
            "ticket_id": "ticket-async-1",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "first"},
        },
        auth_context=auth_context,
        wait_for_result=False,
    )
    second_result = await send_ws_command(
        state=state,
        device_id="device-async-1",
        command="run_tool",
        params={
            "ticket_id": "ticket-async-1",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "second"},
        },
        auth_context=auth_context,
        wait_for_result=False,
    )

    assert first_result["status"] == "accepted"
    assert second_result["status"] == "accepted"
    assert first_result["operation_id"] != second_result["operation_id"]


@pytest.mark.asyncio
async def test_dispatch_failure_materializes_failed_operation_and_trace(test_client, test_agent, monkeypatch):
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _queue_full(*args, **kwargs):
        raise WsCommandQueueFullError("WS command queue full")

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("websocket.protocol.send_ws_command", _queue_full)

    response = await test_client.post(
        "/api/tools/run",
        json={
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "dispatch-failure"},
            "device_id": device_id,
            "ticket_id": ticket_id,
        },
    )

    assert response.status == 429, await response.text()
    payload = await response.json()
    operation_id = payload["operation_id"]
    trace_id = payload["trace_id"]

    assert payload["status"] == "error"
    assert payload["error_code"] == "WS_COMMAND_QUEUE_FULL"
    assert payload["poll_url"] == f"/api/operations/{operation_id}"

    async with get_session() as session:
        operation = (
            await session.execute(
                select(Operation).where(Operation.operation_id == operation_id)
            )
        ).scalar_one()
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id, TicketEvent.operation_id == operation_id)
                .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
            )
        ).scalars().all()

    assert operation.trace_id == trace_id
    assert operation.status == "failed"
    assert operation.error_code == "WS_COMMAND_QUEUE_FULL"
    assert operation.error_message == "WS command queue full"

    started_events = [event for event in events if event.event_type == "tool_call_started"]
    result_events = [event for event in events if event.event_type == "tool_call_result"]
    assert len(started_events) == 1
    assert len(result_events) == 1
    assert result_events[0].payload["status"] == "error"
    assert result_events[0].payload["error_code"] == "WS_COMMAND_QUEUE_FULL"

    rebuild_resp = await test_client.post(
        f"/api/admin/tech/traces/rebuild?operation_id={operation_id}",
        headers=_auth(),
    )
    assert rebuild_resp.status == 200
    rebuild_payload = await rebuild_resp.json()
    assert trace_id in rebuild_payload["trace_ids"]

    trace_search_resp = await test_client.get(
        f"/api/admin/tech/traces?trace_id={trace_id}",
        headers=_auth(),
    )
    assert trace_search_resp.status == 200
    trace_search_payload = await trace_search_resp.json()
    assert trace_search_payload["status"] == "ok"
    assert trace_search_payload["count"] == 1
    assert trace_search_payload["traces"][0]["trace_id"] == trace_id
    assert trace_search_payload["traces"][0]["error_count"] >= 1

    detail_resp = await test_client.get(
        f"/api/admin/tech/traces/{trace_id}",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    assert detail_payload["status"] == "ok"
    assert detail_payload["trace"]["trace_id"] == trace_id
    assert detail_payload["error_occurrences"]
    assert any(
        occurrence["error_signature"].startswith("ws_command_queue_full")
        for occurrence in detail_payload["error_occurrences"]
    )
