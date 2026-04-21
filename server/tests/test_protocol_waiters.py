from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from auth.context import AuthContext, AuthType
from websocket.protocol import send_ws_command


pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_send_ws_command_waiter_is_registered_in_state_registry(monkeypatch):
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
                "device-sync-1": {
                    "metadata": {
                        "device_id": "device-sync-1",
                        "connection_id": "conn-1",
                    },
                }
            }
            self.pending = {}

        def get_agent(self, device_id):
            return self.connected_agents.get(device_id)

        def register_pending_command_future(self, command_id, future, *, device_id=None, connection_id=None):
            self.pending[command_id] = {
                "future": future,
                "device_id": device_id,
                "connection_id": connection_id,
            }

        def resolve_pending_command_future(self, command_id, result_data):
            entry = self.pending.pop(command_id, None)
            if not entry:
                return False
            future = entry["future"]
            if future.done():
                return False
            future.set_result(result_data)
            return True

        def discard_pending_command_future(self, command_id):
            return self.pending.pop(command_id, None) is not None

    monkeypatch.setattr("app.db.get_session", _fake_get_session)
    monkeypatch.setattr("app.repos.DeviceOutboxRepo", _FakeDeviceOutboxRepo)
    monkeypatch.setattr("app.repos.OperationsRepo", _FakeOperationsRepo)
    monkeypatch.setattr("app.services.OperationService", _FakeOperationService)

    state = _FakeState()
    auth_context = AuthContext(
        actor_id="admin-test",
        actor_role="admin",
        auth_type=AuthType.UI_TOKEN,
        token="test-token",
    )

    task = asyncio.create_task(
        send_ws_command(
            state=state,
            device_id="device-sync-1",
            command="get_status",
            params={},
            auth_context=auth_context,
            wait_for_result=True,
            timeout=1.0,
        )
    )

    for _ in range(20):
        if state.pending:
            break
        await asyncio.sleep(0)

    assert state.pending
    command_id, entry = next(iter(state.pending.items()))
    assert entry["device_id"] == "device-sync-1"
    assert entry["connection_id"] == "conn-1"

    assert state.resolve_pending_command_future(
        command_id,
        {"request_id": command_id, "payload": {"status": "success"}},
    ) is True

    result = await task
    assert result["request_id"] == command_id
    assert state.pending == {}
