from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from routes import setup_routes
import web_api.requester_handlers as handlers

pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


@pytest.mark.parametrize("profile_complete", [False, True])
async def test_device_link_profile_and_safe_validation_before_endpoint(monkeypatch, profile_complete):
    endpoint = SimpleNamespace(redeem_device_binding=AsyncMock())
    monkeypatch.setattr(handlers.DomainPortContainer, "from_config", lambda **kw: SimpleNamespace(endpoint=endpoint))
    resolver = SimpleNamespace(resolve_person_for_web_user=AsyncMock(return_value=None),
        build_profile_completion=lambda *args, **kw: {"complete": profile_complete})
    monkeypatch.setattr(handlers, "RequesterIdentityResolver", lambda *args, **kw: resolver)
    monkeypatch.setattr(handlers.RequesterProfileSchemaService, "get_schema", AsyncMock(return_value={}))
    @asynccontextmanager
    async def session():
        yield SimpleNamespace()
    monkeypatch.setattr(handlers, "get_session", session)
    @web.middleware
    async def auth(request, handler):
        request["auth_context"] = AuthContext(actor_id="requester", actor_role="user", auth_type=AuthType.UI_TOKEN, token="test-only")
        return await handler(request)
    app = web.Application(middlewares=[auth])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        invalid = await client.post("/api/web/requester/devices/link", json={"code": "private-code", "device_id": "forged"})
        assert invalid.status == 400
        assert "private-code" not in await invalid.text()
        response = await client.post("/api/web/requester/devices/link", json={"code": "123-456"})
        assert response.status == 403
        assert (await response.json())["error_code"] == "REQUESTER_PROFILE_INCOMPLETE"
        endpoint.redeem_device_binding.assert_not_awaited()
