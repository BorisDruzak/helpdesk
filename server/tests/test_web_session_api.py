from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from auth.middleware import AUTH_WHITELIST, WEB_SESSION_COOKIE_NAME, auth_middleware
from auth.rate_limit import reset_rate_limits
from access_control.catalog import CATALOG_VERSION
from routes import setup_routes
import auth.middleware as auth_middleware_module
import web_api.access_handlers as access_handlers_module
import web_api.registry_handlers as registry_handlers_module
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


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.no_db
def test_web_session_register_is_auth_whitelisted():
    assert "/api/web/session/register" in AUTH_WHITELIST


@pytest.mark.no_db
def test_web_session_password_reset_request_is_auth_whitelisted():
    assert "/api/web/session/password-reset-requests" in AUTH_WHITELIST


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_register_is_feature_flagged(monkeypatch):
    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", False, raising=False)

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/register",
            json={
                "login": "new.requester",
                "password": "VeryStrong123!",
                "password_repeat": "VeryStrong123!",
            },
        )
        payload = await response.json()

    assert response.status == 403
    assert payload["error_code"] == "SELF_REGISTRATION_DISABLED"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_register_validates_password_repeat(monkeypatch):
    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", True, raising=False)

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/register",
            json={
                "login": "new.requester",
                "password": "VeryStrong123!",
                "password_repeat": "DifferentStrong123!",
            },
        )
        payload = await response.json()

    assert response.status == 400
    assert payload["error_code"] == "PASSWORD_REPEAT_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_password_reset_request_accepts_login_without_revealing_user(monkeypatch):
    monkeypatch.setattr(session_handlers_module, "get_session", lambda: _FakeSessionContext())
    created: list[dict[str, str | None]] = []

    class FakePasswordResetRequestService:
        def __init__(self, session):
            self.session = session

        async def create_request(self, *, login: str, client_ip: str | None = None, user_agent: str | None = None):
            created.append({"login": login, "client_ip": client_ip, "user_agent": user_agent})
            return {"request_id": "reset-1", "status": "pending"}

    monkeypatch.setattr(session_handlers_module, "PasswordResetRequestService", FakePasswordResetRequestService, raising=False)

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/password-reset-requests",
            json={"login": " reset.user@example.test "},
            headers={"User-Agent": "reset-test"},
        )
        payload = await response.json()

    assert response.status == 200
    assert payload == {"status": "success", "data": {"accepted": True}}
    assert created == [
        {"login": "reset.user@example.test", "client_ip": "127.0.0.1", "user_agent": "reset-test"}
    ]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_register_creates_requester_user_without_cookie_or_role_escalation(monkeypatch):
    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", True, raising=False)
    monkeypatch.setattr(session_handlers_module, "get_session", lambda: _FakeSessionContext())
    created: dict[str, str] = {}

    class FakeUiUsersRepo:
        def __init__(self, session):
            self.session = session

        async def create_user(self, user_login, password_hash, actor_role="user", actor_id=None):
            created.update(
                {
                    "user_login": user_login,
                    "password_hash": password_hash,
                    "actor_role": actor_role,
                    "actor_id": actor_id,
                }
            )
            return SimpleNamespace(user_login=user_login, actor_role=actor_role, is_active=True)

    monkeypatch.setattr(session_handlers_module, "UiUsersRepo", FakeUiUsersRepo)

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/register",
            json={
                "login": "new.requester",
                "password": "VeryStrong123!",
                "password_repeat": "VeryStrong123!",
            },
        )
        payload = await response.json()

    assert response.status == 201
    assert payload["status"] == "success"
    assert payload["data"]["user_login"] == "new.requester"
    assert payload["data"]["actor_role"] == "user"
    assert payload["data"]["next_path"] == "/app/login?registered=1"
    assert "Set-Cookie" not in response.headers
    assert created["actor_role"] == "user"
    assert created["password_hash"] != "VeryStrong123!"
    assert "full_name" not in payload["data"]
    assert "department" not in payload["data"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_registry_password_reset_requests_can_be_listed_and_completed(monkeypatch):
    listed: list[dict[str, object]] = []
    completed: list[dict[str, str]] = []

    class FakePasswordResetRequestService:
        def __init__(self, session):
            self.session = session

        async def list_requests(self, *, status: str | None = None, limit: int = 100):
            listed.append({"status": status, "limit": limit})
            return [
                {
                    "request_id": "reset-1",
                    "login": "reset.user@example.test",
                    "status": "pending",
                    "requested_at": "2026-06-19T10:00:00+05:00",
                    "completed_at": None,
                    "completed_by": None,
                    "resolution_note": None,
                }
            ]

        async def complete_request(self, *, request_id: str, password: str, actor_id: str, reason: str | None = None):
            completed.append({"request_id": request_id, "password": password, "actor_id": actor_id, "reason": reason or ""})
            return {
                "request_id": request_id,
                "login": "reset.user@example.test",
                "status": "completed",
                "requested_at": "2026-06-19T10:00:00+05:00",
                "completed_at": "2026-06-19T10:05:00+05:00",
                "completed_by": actor_id,
                "resolution_note": reason,
            }

    @web.middleware
    async def admin_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="admin",
            actor_role="admin",
            auth_type=AuthType.UI_TOKEN,
            token="admin-token",
        )
        return await handler(request)

    monkeypatch.setattr(registry_handlers_module, "get_session", lambda: _FakeSessionContext())
    monkeypatch.setattr(registry_handlers_module, "PasswordResetRequestService", FakePasswordResetRequestService, raising=False)

    app = web.Application(middlewares=[admin_context_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        list_response = await client.get("/api/web/admin/registry/password-reset-requests?status=pending")
        list_payload = await list_response.json()
        complete_response = await client.post(
            "/api/web/admin/registry/password-reset-requests/reset-1/complete",
            json={"password": "StrongReset123!", "reason": "Проверено администратором"},
        )
        complete_payload = await complete_response.json()

    assert list_response.status == 200
    assert list_payload["data"]["items"][0]["login"] == "reset.user@example.test"
    assert listed == [{"status": "pending", "limit": 100}]
    assert complete_response.status == 200
    assert complete_payload["data"]["status"] == "completed"
    assert completed == [
        {
            "request_id": "reset-1",
            "password": "StrongReset123!",
            "actor_id": "admin",
            "reason": "Проверено администратором",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_register_rate_limit_blocks_repeated_attempts_before_create_user(monkeypatch):
    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", True, raising=False)
    monkeypatch.setattr(session_handlers_module, "get_session", lambda: _FakeSessionContext())
    created_logins: list[str] = []

    class FakeUiUsersRepo:
        def __init__(self, session):
            self.session = session

        async def create_user(self, user_login, password_hash, actor_role="user", actor_id=None):
            created_logins.append(user_login)
            return SimpleNamespace(user_login=user_login, actor_role=actor_role, is_active=True)

    monkeypatch.setattr(session_handlers_module, "UiUsersRepo", FakeUiUsersRepo)
    reset_rate_limits()

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    try:
        async with TestClient(TestServer(app)) as client:
            responses = []
            for _ in range(6):
                response = await client.post(
                    "/api/web/session/register",
                    json={
                        "login": "rate.limit.user",
                        "password": "VeryStrong123!",
                        "password_repeat": "VeryStrong123!",
                    },
                )
                responses.append((response.status, await response.json()))
    finally:
        reset_rate_limits()

    assert [status for status, _payload in responses] == [201, 201, 201, 201, 201, 429]
    assert responses[-1][1]["error_code"] == "RATE_LIMITED"
    assert created_logins == ["rate.limit.user"] * 5


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_register_rejects_actor_role_escalation_payload(monkeypatch):
    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", True, raising=False)

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/register",
            json={
                "login": "new.requester",
                "password": "VeryStrong123!",
                "password_repeat": "VeryStrong123!",
                "actor_role": "admin",
            },
        )
        payload = await response.json()

    assert response.status == 400
    assert payload["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_register_returns_duplicate_login_conflict(monkeypatch):
    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", True, raising=False)
    monkeypatch.setattr(session_handlers_module, "get_session", lambda: _FakeSessionContext())

    class FakeUiUsersRepo:
        def __init__(self, session):
            self.session = session

        async def create_user(self, *args, **kwargs):
            raise ValueError("User already exists")

    monkeypatch.setattr(session_handlers_module, "UiUsersRepo", FakeUiUsersRepo)

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/register",
            json={
                "login": "new.requester",
                "password": "VeryStrong123!",
                "password_repeat": "VeryStrong123!",
            },
        )
        payload = await response.json()

    assert response.status == 409
    assert payload["error_code"] == "LOGIN_ALREADY_EXISTS"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_register_rejects_login_longer_than_db_limit(monkeypatch):
    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", True, raising=False)
    monkeypatch.setattr(session_handlers_module, "get_session", lambda: _FakeSessionContext())
    created = False

    class FakeUiUsersRepo:
        def __init__(self, session):
            self.session = session

        async def create_user(self, *args, **kwargs):
            nonlocal created
            created = True
            raise AssertionError("registration must reject long login before DB write")

    monkeypatch.setattr(session_handlers_module, "UiUsersRepo", FakeUiUsersRepo)

    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/register",
            json={
                "login": "a" * 101,
                "password": "VeryStrong123!",
                "password_repeat": "VeryStrong123!",
            },
        )
        payload = await response.json()

    assert response.status == 400
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert created is False


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_register_rejects_retired_device_link_code(monkeypatch):
    monkeypatch.setattr(session_handlers_module.config_module, "WEB_SELF_REGISTRATION_ENABLED", True, raising=False)
    monkeypatch.setattr(session_handlers_module, "get_session", lambda: _FakeSessionContext())
    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/session/register",
            json={
                "login": "new.requester",
                "password": "VeryStrong123!",
                "password_repeat": "VeryStrong123!",
                "device_link_code": "retired",
            },
        )
        payload = await response.json()

    assert response.status == 400
    assert payload["error_code"] == "VALIDATION_ERROR"


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
        "/api/registry/options",
        "/api/notifications/preferences",
        "/api/notifications",
        "/api/admin/tickets/queues",
        "/api/admin/users",
        "/api/tickets",
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
        headers = {"Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token"}
        if method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            headers["Origin"] = str(client.make_url("/")).rstrip("/")
        response = await client.request(
            method,
            request_path,
            headers=headers,
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
async def test_web_session_cookie_auth_unsafe_requests_require_same_origin(monkeypatch):
    async def fake_verify_ui_token(_self, token: str):
        if token != "cookie-token":
            return None
        return {
            "user_login": "requester-cookie",
            "actor_role": "user",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "ui",
        }

    monkeypatch.setattr(auth_middleware_module.AuthService, "verify_ui_token", fake_verify_ui_token)

    async def protected_handler(request: web.Request):
        return web.json_response({"status": "ok", "actor_id": request["auth_context"].actor_id})

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    app.router.add_post("/api/admin/users", protected_handler)

    async with TestClient(TestServer(app)) as client:
        missing_origin = await client.post(
            "/api/admin/users",
            headers={"Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token"},
            json={"title": "csrf check"},
        )
        missing_payload = await missing_origin.json()
        wrong_origin = await client.post(
            "/api/admin/users",
            headers={
                "Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token",
                "Origin": "https://evil.example.test",
            },
            json={"title": "csrf check"},
        )
        wrong_payload = await wrong_origin.json()
        same_origin = await client.post(
            "/api/admin/users",
            headers={
                "Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token",
                "Origin": str(client.make_url("/")).rstrip("/"),
            },
            json={"title": "csrf check"},
        )
        same_payload = await same_origin.json()

    assert missing_origin.status == 403
    assert missing_payload["error_code"] == "CSRF_ORIGIN_REQUIRED"
    assert wrong_origin.status == 403
    assert wrong_payload["error_code"] == "CSRF_ORIGIN_MISMATCH"
    assert same_origin.status == 200
    assert same_payload == {"status": "ok", "actor_id": "requester-cookie"}


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_cookie_auth_bridges_access_password_alias_with_same_origin(monkeypatch):
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
    app.router.add_post("/api/web/admin/access/users/support1/password", protected_handler)

    async with TestClient(TestServer(app)) as client:
        missing_origin = await client.post(
            "/api/web/admin/access/users/support1/password",
            headers={"Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token"},
            json={"password": "StrongReset123!"},
        )
        missing_payload = await missing_origin.json()
        same_origin = await client.post(
            "/api/web/admin/access/users/support1/password",
            headers={
                "Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token",
                "Origin": str(client.make_url("/")).rstrip("/"),
            },
            json={"password": "StrongReset123!"},
        )
        same_payload = await same_origin.json()

    assert missing_origin.status == 403
    assert missing_payload["error_code"] == "CSRF_ORIGIN_REQUIRED"
    assert same_origin.status == 200
    assert same_payload == {
        "status": "ok",
        "actor_id": "admin-cookie",
        "actor_role": "admin",
        "path": "/api/web/admin/access/users/support1/password",
    }


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_access_password_alias_updates_only_new_password(monkeypatch):
    calls: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeUiUsersRepo:
        def __init__(self, _session):
            pass

        async def set_password(self, user_login, password_hash, *, actor_id=None):
            calls["user_login"] = user_login
            calls["password_hash"] = password_hash
            calls["actor_id"] = actor_id
            return True

    monkeypatch.setattr(access_handlers_module, "get_session", lambda: FakeSession())
    monkeypatch.setattr(access_handlers_module, "UiUsersRepo", FakeUiUsersRepo)

    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="admin-cookie",
            actor_role="admin",
            auth_type=AuthType.UI_TOKEN,
            token="cookie-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/admin/access/users/support1/password",
            json={"password": "StrongReset123!"},
        )
        payload = await response.json()

    assert response.status == 200
    assert payload == {"status": "success", "data": {"updated": True}}
    assert calls["user_login"] == "support1"
    assert calls["actor_id"] == "admin-cookie"
    assert "StrongReset123!" not in str(calls["password_hash"])


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_session_cookie_auth_accepts_forwarded_public_origin(monkeypatch):
    async def fake_verify_ui_token(_self, token: str):
        if token != "cookie-token":
            return None
        return {
            "user_login": "requester-cookie",
            "actor_role": "user",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "ui",
        }

    monkeypatch.setattr(auth_middleware_module.AuthService, "verify_ui_token", fake_verify_ui_token)

    async def protected_handler(request: web.Request):
        return web.json_response({"status": "ok", "actor_id": request["auth_context"].actor_id})

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    app.router.add_post("/api/web/requester/consents/consent-1/approve", protected_handler)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/requester/consents/consent-1/approve",
            headers={
                "Cookie": f"{WEB_SESSION_COOKIE_NAME}=cookie-token",
                "Origin": "https://example.test:9443",
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "example.test:9443",
            },
            json={"reason": "approve"},
        )
        payload = await response.json()

    assert response.status == 200
    assert payload == {"status": "ok", "actor_id": "requester-cookie"}


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_bearer_ui_token_unsafe_request_is_not_origin_gated(monkeypatch):
    async def fake_verify_ui_token(_self, token: str):
        if token != "bearer-token":
            return None
        return {
            "user_login": "requester-bearer",
            "actor_role": "user",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "ui",
        }

    monkeypatch.setattr(auth_middleware_module.AuthService, "verify_ui_token", fake_verify_ui_token)

    async def protected_handler(request: web.Request):
        return web.json_response({"status": "ok", "actor_id": request["auth_context"].actor_id})

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    app.router.add_post("/api/web/requester/tickets", protected_handler)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/web/requester/tickets",
            headers={"Authorization": "Bearer bearer-token"},
            json={"title": "bearer check"},
        )
        payload = await response.json()

    assert response.status == 200
    assert payload == {"status": "ok", "actor_id": "requester-bearer"}


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_public_ticket_token_auth_bridges_artifact_download(monkeypatch):
    async def fake_verify_ui_token(_self, token: str):
        return None

    async def fake_verify_ticket_public_session_token(_self, token: str):
        if token != "public-ticket-token":
            return None
        return {
            "actor_id": "public:ticket-1",
            "ticket_id": "ticket-1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "public_ticket",
        }

    monkeypatch.setattr(auth_middleware_module.AuthService, "verify_ui_token", fake_verify_ui_token)
    monkeypatch.setattr(
        auth_middleware_module.AuthService,
        "verify_ticket_public_session_token",
        fake_verify_ticket_public_session_token,
    )

    async def protected_handler(request: web.Request):
        auth_context = request["auth_context"]
        return web.json_response(
            {
                "status": "ok",
                "actor_id": auth_context.actor_id,
                "auth_type": auth_context.auth_type.value,
                "ticket_scope": auth_context.ticket_scope,
                "path": request.path,
            }
        )

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    route_path = "/api/artifacts/artifact-1/download"
    app.router.add_get(route_path, protected_handler)

    async with TestClient(TestServer(app)) as client:
        response = await client.get(
            f"{route_path}?ticket_id=ticket-1",
            headers={"Authorization": "Bearer public-ticket-token"},
        )
        payload = await response.json()

    assert response.status == 200
    assert payload == {
        "status": "ok",
        "actor_id": "public:ticket-1",
        "auth_type": "public_ticket_token",
        "ticket_scope": "ticket-1",
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
    assert data["available_workspaces"] == ["admin", "support", "requester"]
    assert data["permissions_version"] == CATALOG_VERSION
    assert "admin.access.view" in data["permissions"]
    assert "workspace.admin.view" in data["permissions"]
