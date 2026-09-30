from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from auth import rate_limit
from domain_ports.endpoint import EndpointBindingVerified, EndpointDeviceRef, EndpointNotFound
from routes import setup_routes
import web_api.requester_handlers as handlers

pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


@pytest.fixture
def binding_client(monkeypatch):
    """Keep auth/HTTP and the production limiter real; stub DB-owned ports."""
    rate_limit.reset_rate_limits()
    clock = [1000.0]
    monkeypatch.setattr(rate_limit, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(rate_limit.config, "TRUST_X_FORWARDED_FOR", True)
    monkeypatch.setattr(rate_limit.config, "TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    endpoint = SimpleNamespace(redeem_device_binding=AsyncMock(return_value=EndpointNotFound()))
    registry = SimpleNamespace(bind_endpoint_possession=AsyncMock(return_value=SimpleNamespace(status="active")))
    monkeypatch.setattr(handlers.DomainPortContainer, "from_config",
        lambda **kw: SimpleNamespace(endpoint=endpoint, registry=registry))
    resolver = SimpleNamespace(resolve_person_for_web_user=AsyncMock(return_value=SimpleNamespace(person_id="person")),
        build_profile_completion=lambda *args, **kw: {"complete": True},
        list_allowed_devices=AsyncMock(return_value=[]))
    monkeypatch.setattr(handlers, "RequesterIdentityResolver", lambda *args, **kw: resolver)
    monkeypatch.setattr(handlers.RequesterProfileSchemaService, "get_schema", AsyncMock(return_value={}))
    @asynccontextmanager
    async def session():
        yield SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(handlers, "get_session", session)
    @web.middleware
    async def auth(request, handler):
        request["auth_context"] = AuthContext(actor_id=request.headers.get("X-Test-Actor", "A"),
            actor_role="user", auth_type=AuthType.UI_TOKEN, token="test-only")
        return await handler(request)
    app = web.Application(middlewares=[auth])
    setup_routes(app)
    yield app, endpoint, registry, clock
    rate_limit.reset_rate_limits()


async def test_requester_failed_codes_throttle_actor_before_adapter_and_leave_other_actor_free(binding_client):
    app, endpoint, registry, clock = binding_client
    path = "/api/web/requester/devices/link"
    async with TestClient(TestServer(app)) as client:
        for _ in range(5):
            response = await client.post(path, json={"code": "123456"})
            assert response.status == 400
        assert endpoint.redeem_device_binding.await_count == 5
        verified = EndpointBindingVerified(device=EndpointDeviceRef(external_id=str(uuid4())), hostname="PC", platform="windows")
        endpoint.redeem_device_binding.return_value = verified
        response = await client.post(path, json={"code": "123456"})
        assert response.status == 429
        assert (await response.json())["error_code"] == "DEVICE_BINDING_THROTTLED"
        assert response.headers["Cache-Control"] == "no-store"
        assert "123456" not in await response.text()
        assert endpoint.redeem_device_binding.await_count == 5
        registry.bind_endpoint_possession.assert_not_awaited()
        response = await client.post(path, headers={"X-Test-Actor": "B"}, json={"code": "234567"})
        assert response.status == 200
        assert (await response.json())["data"]["binding_status"] == "active"
        assert endpoint.redeem_device_binding.await_count == 6
        endpoint.redeem_device_binding.assert_awaited_with("234567")
        clock[0] += 601
        response = await client.post(path, json={"code": "345678"})
        assert response.status == 200


async def test_requester_binding_ip_pair_and_untrusted_forwarding(binding_client, monkeypatch):
    app, endpoint, registry, clock = binding_client
    path = "/api/web/requester/devices/link"
    async with TestClient(TestServer(app)) as client:
        for _ in range(5):
            assert (await client.post(path, headers={"X-Forwarded-For": "192.0.2.1"},
                json={"code": "123456"})).status == 400
        assert (await client.post(path, headers={"X-Forwarded-For": "192.0.2.1"},
            json={"code": "123456"})).status == 429
        assert (await client.post(path, headers={"X-Forwarded-For": "192.0.2.2"},
            json={"code": "123456"})).status == 400
        monkeypatch.setattr(rate_limit.config, "TRUST_X_FORWARDED_FOR", False)
        for index in range(5):
            assert (await client.post(path, headers={"X-Forwarded-For": f"192.0.2.{index+3}"},
                json={"code": "123456"})).status == 400
        response = await client.post(path, headers={"X-Forwarded-For": "192.0.2.99"}, json={"code": "123456"})
        assert response.status == 429
        assert "192.0.2" not in await response.text()
        assert endpoint.redeem_device_binding.await_count == 11


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
