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

    async def _fake_run_tool(self, **_kwargs):
        return {
            "status": "accepted",
            "device_id": "device-async-1",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
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
