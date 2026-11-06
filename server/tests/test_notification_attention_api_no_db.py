from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from auth.context import AuthContext, AuthType
from tickets import handlers as module

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_scoped_read_route_requires_authentication():
    from auth.middleware import auth_middleware
    from routes import setup_routes
    app = web.Application(middlewares=[auth_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        assert (await client.post('/api/web/notifications/read_ticket', json={'ticket_id': 't77'})).status == 401


@pytest.mark.asyncio
async def test_scoped_read_uses_authenticated_actor_validates_body_and_commits(monkeypatch):
    actor = AuthContext(actor_id='employee', actor_role='user', auth_type=AuthType.SESSION)
    @web.middleware
    async def auth(request, handler):
        request['auth_context'] = actor
        return await handler(request)
    session = SimpleNamespace(commit=AsyncMock())
    @asynccontextmanager
    async def database():
        yield session
    repo = SimpleNamespace(mark_ticket_read=AsyncMock(return_value=2))
    monkeypatch.setattr(module, 'get_session', database)
    monkeypatch.setattr(module, 'NotificationRepo', lambda _: repo)
    app = web.Application(middlewares=[auth])
    app.router.add_post('/read', module.handle_notifications_read_ticket)
    async with TestClient(TestServer(app)) as client:
        for body in [[], {'expected_actor_id': 'employee'}, {'ticket_id': '', 'expected_actor_id': 'employee'}, {'ticket_id': True, 'expected_actor_id': 'employee'}, {'ticket_id': 'x' * 129, 'expected_actor_id': 'employee'}]:
            assert (await client.post('/read', json=body)).status == 400
        for body in [{'ticket_id': 't77'}, {'ticket_id': 't77', 'expected_actor_id': 'old-tab-user'}]:
            assert (await client.post('/read', json=body)).status == 409
        repo.mark_ticket_read.assert_not_awaited()
        response = await client.post('/read', json={'ticket_id': 't77', 'expected_actor_id': 'employee', 'actor_id': 'other'})
        assert response.status == 200
        assert (await response.json())['updated'] == 2
        repo.mark_ticket_read.assert_awaited_once_with('employee', 't77', auth_context=actor)
        session.commit.assert_awaited_once()
