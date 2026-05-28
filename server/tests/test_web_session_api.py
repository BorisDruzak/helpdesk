from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from auth.middleware import WEB_SESSION_COOKIE_NAME, auth_middleware
from access_control.catalog import CATALOG_VERSION
from routes import setup_routes
import auth.middleware as auth_middleware_module
import web_api.session_handlers as session_handlers_module


@pytest.fixture
async def web_api_client():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="support1",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_me_returns_typed_actor_payload(web_api_client):
    response = await web_api_client.get("/api/web/session/me")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    data = payload["data"]
    assert data["user_login"] == "support1"
    assert data["actor_role"] == "support"
    assert data["auth_type"] == "ui_token"
    assert data["default_workspace"] == "support"
    assert data["available_workspaces"] == ["support"]
    assert data["permissions_version"] == CATALOG_VERSION
    assert "workspace.support.view" in data["permissions"]
    assert "workspace.admin.view" not in data["permissions"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_me_returns_anonymous_bootstrap_without_cookie():
    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/web/session/me")
        payload = await response.json()

    assert response.status == 200
    assert payload == {
        "status": "success",
        "data": None,
    }


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_login_sets_http_only_cookie(monkeypatch):
    async def fake_authenticate(_self, login: str, password: str):
        assert login == "support"
        assert password == "secret"
        return True, "support"

    async def fake_generate_ui_token(_self, user_login: str, actor_role: str, expires_hours: int = 24):
        assert user_login == "support"
        assert actor_role == "support"
        assert expires_hours == 24
        return "issued-ui-token"

    monkeypatch.setattr(session_handlers_module.AuthService, "authenticate", fake_authenticate)
    monkeypatch.setattr(session_handlers_module.AuthService, "generate_ui_token", fake_generate_ui_token)

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/login",
            json={"login": "support", "password": "secret"},
        )
        payload = await response.json()
        set_cookie = response.headers["Set-Cookie"]

    assert response.status == 200

    assert payload["status"] == "success"
    data = payload["data"]
    assert data["user_login"] == "support"
    assert data["actor_role"] == "support"
    assert data["auth_type"] == "ui_token"
    assert data["default_workspace"] == "support"
    assert data["available_workspaces"] == ["support"]
    assert data["permissions_version"] == CATALOG_VERSION
    assert "ticket.queue.view" in data["permissions"]
    assert response.cookies[WEB_SESSION_COOKIE_NAME].value == "issued-ui-token"
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_logout_revokes_token_and_clears_cookie(monkeypatch):
    revoked_tokens: list[str] = []

    async def fake_revoke_ui_token(_self, token: str):
        revoked_tokens.append(token)
        return True

    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="support1",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="issued-ui-token",
        )
        return await handler(request)

    monkeypatch.setattr(session_handlers_module.AuthService, "revoke_ui_token", fake_revoke_ui_token)

    app = web.Application(middlewares=[auth_context_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/logout",
            headers={"Cookie": f"{WEB_SESSION_COOKIE_NAME}=issued-ui-token"},
        )
        payload = await response.json()
        set_cookie = response.headers["Set-Cookie"]

    assert response.status == 200
    assert payload == {"status": "success", "data": {"cleared": True}}
    assert revoked_tokens == ["issued-ui-token"]
    assert f"{WEB_SESSION_COOKIE_NAME}=" in set_cookie
    assert "Max-Age=0" in set_cookie


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_me_accepts_web_cookie_auth(monkeypatch):
    async def fake_verify_ui_token(_self, token: str):
        if token != "cookie-token":
            return None
        return {
            "user_login": "support-cookie",
            "actor_role": "support",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "ui",
        }

    monkeypatch.setattr(auth_middleware_module.AuthService, "verify_ui_token", fake_verify_ui_token)

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.get(
            "/api/web/session/me",
            headers={"Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token"},
        )
        payload = await response.json()

    assert response.status == 200
    assert payload["status"] == "success"
    data = payload["data"]
    assert data["user_login"] == "support-cookie"
    assert data["actor_role"] == "support"
    assert data["auth_type"] == "ui_token"
    assert data["default_workspace"] == "support"
    assert data["available_workspaces"] == ["support"]
    assert data["permissions_version"] == CATALOG_VERSION
    assert "ticket.detail.view" in data["permissions"]


@pytest.mark.asyncio
@pytest.mark.no_db
@pytest.mark.parametrize(
    "path",
    [
        "/api/modules/workbench",
        "/api/admin/tech/traces/runtime",
        "/api/admin/settings/observer",
        "/api/ticket_forms/packs",
        "/api/notifications/preferences",
        "/api/notifications",
    ],
)
async def test_web_session_cookie_auth_bridges_react_workbench_paths(monkeypatch, path: str):
    async def fake_verify_ui_token(_self, token: str):
        if token != "cookie-token":
            return None
        return {
            "user_login": "admin-cookie",
            "actor_role": "admin",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "ui",
        }

    monkeypatch.setattr(auth_middleware_module.AuthService, "verify_ui_token", fake_verify_ui_token)

    async def protected_handler(request: web.Request):
        auth_context = request["auth_context"]
        return web.json_response(
            {
                "status": "ok",
                "actor_id": auth_context.actor_id,
                "actor_role": auth_context.actor_role,
                "path": request.path,
            }
        )

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    app.router.add_get(path, protected_handler)
    if path == "/api/admin/settings/observer":
        app.router.add_patch(path, protected_handler)

    async with TestClient(TestServer(app)) as client:
        response = await client.get(
            path,
            headers={"Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token"},
        )
        payload = await response.json()

    assert response.status == 200
    assert payload == {
        "status": "ok",
        "actor_id": "admin-cookie",
        "actor_role": "admin",
        "path": path,
    }


@pytest.mark.asyncio
@pytest.mark.no_db
@pytest.mark.parametrize(
    ("method", "route_path", "request_path"),
    [
        ("POST", "/api/upload", "/api/upload"),
        ("GET", "/api/artifacts/artifact-1/download", "/api/artifacts/artifact-1/download"),
        ("GET", "/api/artifacts/artifact-1/download", "/api/artifacts/artifact-1/download?ticket_id=ticket-1"),
    ],
)
async def test_web_session_cookie_auth_bridges_legacy_attachment_paths(
    monkeypatch,
    method: str,
    route_path: str,
    request_path: str,
):
    async def fake_verify_ui_token(_self, token: str):
        if token != "cookie-token":
            return None
        return {
            "user_login": "support-cookie",
            "actor_role": "support",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "ui",
        }

    monkeypatch.setattr(auth_middleware_module.AuthService, "verify_ui_token", fake_verify_ui_token)

    async def protected_handler(request: web.Request):
        auth_context = request["auth_context"]
        return web.json_response(
            {
                "status": "ok",
                "actor_id": auth_context.actor_id,
                "actor_role": auth_context.actor_role,
                "auth_type": auth_context.auth_type.value,
                "path": request.path,
            }
        )

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    app.router.add_route(method, route_path, protected_handler)

    async with TestClient(TestServer(app)) as client:
        response = await client.request(
            method,
            request_path,
            headers={"Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token"},
        )
        payload = await response.json()

    assert response.status == 200
    assert payload == {
        "status": "ok",
        "actor_id": "support-cookie",
        "actor_role": "support",
        "auth_type": "ui_token",
        "path": route_path,
    }


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_me_exposes_admin_default_workspace():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="admin1",
            actor_role="admin",
            auth_type=AuthType.UI_TOKEN,
            token="admin-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/web/session/me")
        payload = await response.json()

    assert response.status == 200
    assert payload["status"] == "success"
    data = payload["data"]
    assert data["user_login"] == "admin1"
    assert data["actor_role"] == "admin"
    assert data["auth_type"] == "ui_token"
    assert data["default_workspace"] == "admin"
    assert data["available_workspaces"] == ["admin", "support"]
    assert data["permissions_version"] == CATALOG_VERSION
    assert "admin.access.view" in data["permissions"]
    assert "workspace.admin.view" in data["permissions"]
