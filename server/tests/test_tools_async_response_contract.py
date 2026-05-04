import uuid

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app_keys import STATE_APP_KEY, bind_app_value
from auth.context import AuthContext, AuthType
from tools.handlers import handle_tools_run
from tests.test_helpers import TEST_ECHO_TOOL


@pytest.fixture
async def test_client_no_db():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="support-test",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    bind_app_value(app, key=STATE_APP_KEY, legacy_name="state", value=object())
    app.router.add_post("/api/tools/run", handle_tools_run)
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_async_returns_poll_url(test_client_no_db, monkeypatch):
    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _fake_run_tool(self, **_kwargs):
        return {
            "status": "accepted",
            "device_id": "device-async-1",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    response = await test_client_no_db.post(
        "/api/tools/run",
        json={
            "device_id": "device-async-1",
            "ticket_id": "ticket-async-1",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "hello"},
        },
    )
    assert response.status == 202
    payload = await response.json()

    assert payload["status"] == "accepted"
    assert payload["operation_id"]
    assert payload["poll_url"] == f"/api/operations/{payload['operation_id']}"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_rejects_agent_token_for_different_device_context(monkeypatch):
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="device-owned",
            actor_role="agent",
            auth_type=AuthType.AGENT_TOKEN,
            token="agent-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    bind_app_value(app, key=STATE_APP_KEY, legacy_name="state", value=object())
    app.router.add_post("/api/tools/run", handle_tools_run)

    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _unexpected_run_tool(self, **_kwargs):
        pytest.fail("agent device context mismatch reached dispatch")

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _unexpected_run_tool)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/tools/run",
            json={
                "device_id": "device-other",
                "ticket_id": "ticket-other-device",
                "tool_name": "screen.collect",
                "params": {},
            },
        )
        payload = await response.json()

    assert response.status == 403
    assert payload["status"] == "error"
    assert payload["error_code"] == "DEVICE_CONTEXT_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_uses_server_registry_metadata_when_device_snapshot_is_stale(monkeypatch):
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="device-async-2",
            actor_role="agent",
            auth_type=AuthType.AGENT_TOKEN,
            token="agent-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    bind_app_value(app, key=STATE_APP_KEY, legacy_name="state", value=object())
    app.router.add_post("/api/tools/run", handle_tools_run)

    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return [
            {
                "tool": "network_ping.ping",
                "module": "network_ping",
                "aliases": ["ping"],
                "spec": {
                    "metadata": {
                        "risk_level": "safe_read",
                        "requires_consent": False,
                        "allow_roles": ["admin", "support", "agent", "llm"],
                    }
                },
            }
        ]

    async def _fake_run_tool(self, **_kwargs):
        return {
            "status": "accepted",
            "device_id": "device-async-2",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/tools/run",
            json={
                "device_id": "device-async-2",
                "ticket_id": "ticket-async-2",
                "tool_name": "network_ping.ping",
                "params": {"host": "127.0.0.1"},
            },
        )
        payload = await response.json()

    assert response.status == 202
    assert payload["status"] == "accepted"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_async_surfaces_dispatch_error(test_client_no_db, monkeypatch):
    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _fake_run_tool(self, **kwargs):
        operation_id = kwargs["params"]["_operation_id"]
        return {
            "status": "error",
            "error": "WS command queue full",
            "error_code": "WS_COMMAND_QUEUE_FULL",
            "operation_id": operation_id,
            "trace_id": "trace-async-failure",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    response = await test_client_no_db.post(
        "/api/tools/run",
        json={
            "device_id": "device-async-fail",
            "ticket_id": "ticket-async-fail",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "hello"},
        },
    )
    assert response.status == 429
    payload = await response.json()

    assert payload["status"] == "error"
    assert payload["error_code"] == "WS_COMMAND_QUEUE_FULL"
    assert payload["operation_id"]
    assert payload["poll_url"] == f"/api/operations/{payload['operation_id']}"
    assert payload["trace_id"] == "trace-async-failure"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_wait_mode_surfaces_dispatch_error(test_client_no_db, monkeypatch):
    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _fake_run_tool(self, **kwargs):
        operation_id = kwargs["params"]["_operation_id"]
        return {
            "status": "error",
            "error": "Agent not connected",
            "error_code": "AGENT_NOT_CONNECTED",
            "operation_id": operation_id,
            "trace_id": "trace-sync-failure",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    response = await test_client_no_db.post(
        "/api/tools/run?wait=1",
        json={
            "device_id": "device-sync-fail",
            "ticket_id": "ticket-sync-fail",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "hello"},
        },
    )
    assert response.status == 503
    payload = await response.json()

    assert payload["status"] == "error"
    assert payload["error_code"] == "AGENT_NOT_CONNECTED"
    assert payload["operation_id"]
    assert payload["poll_url"] == f"/api/operations/{payload['operation_id']}"
    assert payload["trace_id"] == "trace-sync-failure"
