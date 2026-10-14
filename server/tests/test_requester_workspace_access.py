"""The admin requester workspace uses the authenticated owner's boundaries."""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from auth.context import AuthContext, AuthType
from app.repos.request_scenario_session_repo import RequestScenarioSessionRepo, SessionAccessError
import web_api.requester_handlers as handlers

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [("user", 200), ("admin", 200), ("support", 403), ("auditor", 403)])
async def test_bootstrap_keeps_owner_identity_and_rejects_other_roles(monkeypatch, role, expected):
    @asynccontextmanager
    async def session():
        yield object()

    resolver = MagicMock()
    resolver.build_bootstrap = AsyncMock(return_value={"devices": [], "profile": None})
    monkeypatch.setattr(handlers, "get_session", session)
    monkeypatch.setattr(handlers, "RequesterIdentityResolver", MagicMock(return_value=resolver))
    monkeypatch.setattr("auth.middleware._write_web_auth_audit", AsyncMock())

    @web.middleware
    async def auth(request, handler):
        request["auth_context"] = AuthContext("own-login", role, AuthType.SESSION)
        return await handler(request)

    app = web.Application(middlewares=[auth])
    app.router.add_get("/api/web/requester/bootstrap", handlers.handle_web_requester_bootstrap)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/web/requester/bootstrap?actor_id=other-login")
        assert response.status == expected
    if expected == 200:
        resolver.build_bootstrap.assert_awaited_once_with(actor_id="own-login", state=None)
    else:
        resolver.build_bootstrap.assert_not_awaited()


@pytest.mark.parametrize("role", ["user", "admin"])
def test_scenario_repository_accepts_workspace_roles_without_changing_owner(role):
    repo = RequestScenarioSessionRepo(None, AuthContext("own-login", role, AuthType.SESSION))
    assert repo.owner == "own-login"


@pytest.mark.asyncio
async def test_admin_scenario_audit_preserves_authenticated_role(monkeypatch):
    from types import SimpleNamespace
    audit = AsyncMock()
    monkeypatch.setattr("app.repos.request_scenario_session_repo.ServiceCatalogRepo",
                        MagicMock(return_value=SimpleNamespace(append_audit=audit)))
    repo = RequestScenarioSessionRepo(None, AuthContext("own-login", "admin", AuthType.SESSION))
    row = SimpleNamespace(id="own-session", version_id="v1", current_block_id="q", revision=1, state="active")
    await repo._audit(row, "start")
    assert audit.await_args.kwargs["actor_role"] == "admin"
    assert audit.await_args.kwargs["actor_id"] == "own-login"


@pytest.mark.parametrize("role", ["support", "auditor", "agent", "system"])
def test_scenario_repository_still_rejects_non_requester_roles(role):
    with pytest.raises(SessionAccessError):
        RequestScenarioSessionRepo(None, AuthContext("own-login", role, AuthType.SESSION))
