from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from web_api import push_handlers as module

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_push_routes_require_authentication():
    from auth.middleware import auth_middleware
    from routes import setup_routes
    app = web.Application(middlewares=[auth_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        for method, path in [("GET", "/api/web/notifications/push/config"), ("POST", "/api/web/notifications/push/messages"), ("POST", "/api/web/notifications/push/subscribe")]:
            response = await client.request(method, path, json={"endpoint": "https://fcm.googleapis.com/fcm/send/synthetic"})
            assert response.status == 401


@pytest.fixture
async def push_client(monkeypatch):
    @web.middleware
    async def auth(request, handler):
        request["auth_context"] = AuthContext(actor_id="verified-user", actor_role="user", auth_type=AuthType.SESSION)
        return await handler(request)
    @asynccontextmanager
    async def session():
        yield SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(module, "get_session", session)
    repo = SimpleNamespace(subscribe=AsyncMock(), unsubscribe=AsyncMock(), get=AsyncMock(return_value=None), pending=AsyncMock(return_value=[]), acknowledge=AsyncMock())
    monkeypatch.setattr(module, "WebPushRepo", lambda _: repo)
    monkeypatch.setattr(module, "load_push_config", lambda: SimpleNamespace(public_key="synthetic-public-key"))
    app = web.Application(middlewares=[auth])
    for action, handler in [("subscribe", module.handle_push_subscribe), ("unsubscribe", module.handle_push_unsubscribe), ("status", module.handle_push_status), ("messages", module.handle_push_messages), ("acknowledge", module.handle_push_acknowledge)]:
        app.router.add_post(f"/{action}", handler)
    app.router.add_get("/config", module.handle_push_config)
    async with TestClient(TestServer(app)) as client:
        yield client, repo


@pytest.mark.asyncio
async def test_subscription_uses_verified_actor_and_never_returns_endpoint(push_client):
    client, repo = push_client
    endpoint = "https://fcm.googleapis.com/fcm/send/synthetic"
    response = await client.post("/subscribe", json={"endpoint": endpoint, "actor_id": "attacker-choice"})
    assert response.status == 200
    assert endpoint not in await response.text()
    repo.subscribe.assert_awaited_once_with(endpoint, "verified-user", "synthetic-public-key")
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, [], {"endpoint": "https://127.0.0.1/internal"}, {"endpoint": "https://evil.test/path"}])
async def test_invalid_subscription_cannot_reach_database(push_client, body):
    client, repo = push_client
    response = await client.post("/subscribe", json=body)
    assert response.status == 400
    repo.subscribe.assert_not_awaited()


@pytest.mark.asyncio
async def test_unconfigured_server_is_explicitly_disabled(push_client, monkeypatch):
    client, repo = push_client
    monkeypatch.setattr(module, "load_push_config", lambda: None)
    response = await client.get("/config")
    assert await response.json() == {"status": "ok", "enabled": False, "public_key": None}
    response = await client.post("/subscribe", json={"endpoint": "https://fcm.googleapis.com/fcm/send/synthetic"})
    assert response.status == 503
    repo.subscribe.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("ids", [[], [True], [-1], ["1"], list(range(1, 52))])
async def test_acknowledgement_is_bounded_and_strictly_typed(push_client, ids):
    client, repo = push_client
    response = await client.post("/acknowledge", json={"endpoint": "https://fcm.googleapis.com/fcm/send/synthetic", "notification_ids": ids})
    assert response.status == 400
    repo.acknowledge.assert_not_awaited()
