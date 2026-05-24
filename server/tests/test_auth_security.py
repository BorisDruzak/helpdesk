from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import config
from auth.context import AuthContext, AuthType
from auth.middleware import auth_middleware
import auth.middleware as auth_middleware_module
import auth.handlers as auth_handlers
from auth.password_service import PasswordPolicyError, hash_password, parse_encoded, validate_password_policy, verify_password
from routes import setup_routes


@pytest.fixture(autouse=True)
def no_web_auth_audit(monkeypatch):
    async def noop_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(auth_middleware_module, "_write_web_auth_audit", noop_audit)


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_api_login_requires_auth(monkeypatch):
    async def no_auth(_request):
        return None

    monkeypatch.setattr(auth_middleware_module, "extract_auth_context", no_auth)
    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/login", json={"uuid": "00000000-0000-0000-0000-000000000001"})

    assert response.status == 401


@pytest.mark.asyncio
@pytest.mark.no_db
@pytest.mark.parametrize("role", ["support", "user", "agent"])
async def test_api_login_rejects_non_admin(monkeypatch, role):
    async def role_auth(_request):
        return AuthContext(actor_id="actor", actor_role=role, auth_type=AuthType.UI_TOKEN, token="test")

    monkeypatch.setattr(auth_middleware_module, "extract_auth_context", role_auth)
    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/login", json={"uuid": "00000000-0000-0000-0000-000000000001"})

    assert response.status == 403


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_api_login_admin_issues_minimal_response(monkeypatch):
    async def admin_auth(_request):
        return AuthContext(actor_id="admin-test", actor_role="admin", auth_type=AuthType.UI_TOKEN, token="test")

    async def fake_generate_agent_token(self, *, device_id, expires_hours, replace_existing=False, **_kwargs):
        assert device_id == "00000000-0000-0000-0000-000000000001"
        assert expires_hours == 4320
        assert replace_existing is False
        return "agent-token"

    async def fake_clear(self, *, device_id):
        assert device_id == "00000000-0000-0000-0000-000000000001"

    async def fake_audit(**_kwargs):
        return None

    monkeypatch.setattr(auth_middleware_module, "extract_auth_context", admin_auth)
    monkeypatch.setattr(auth_handlers.AuthService, "generate_agent_token", fake_generate_agent_token)
    monkeypatch.setattr(auth_handlers.ConnectionRequestService, "clear_pending_after_manual_token_issue", fake_clear)
    monkeypatch.setattr(auth_handlers, "write_agent_runtime_audit", fake_audit)

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/login", json={"uuid": "00000000-0000-0000-0000-000000000001"})
        payload = await response.json()

    assert response.status == 200
    assert payload == {
        "status": "success",
        "token": "agent-token",
        "device_id": "00000000-0000-0000-0000-000000000001",
    }


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_legacy_ui_login_disabled_by_default():
    app = web.Application()
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/ui_login", json={"login": "admin", "password": "admin123"})
        payload = await response.json()

    assert response.status == 410
    assert payload["error_code"] == "LEGACY_AUTH_DISABLED"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_query_token_rejected_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "AUTH_ALLOW_QUERY_TOKEN", False)

    async def protected(_request):
        return web.json_response({"status": "ok"})

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    app.router.add_get("/api/protected", protected)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/protected?token=raw-token")

    assert response.status == 401


@pytest.mark.no_db
def test_security_config_rejects_pilot_defaults(monkeypatch):
    monkeypatch.setattr(config, "PILOT_STAND_MODE", True)
    monkeypatch.setattr(config, "ALLOW_INSECURE_DEV_DEFAULTS", False)
    monkeypatch.setattr(config, "REQUIRE_HTTPS", False)
    monkeypatch.setattr(config, "REQUIRE_WSS", False)
    monkeypatch.setattr(config, "WEB_SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr(config, "AUTH_UI_CONFIG_FALLBACK_ENABLED", True)
    monkeypatch.setattr(config, "USERS", {"admin": "admin123", "user": "12345"})

    with pytest.raises(RuntimeError):
        config.validate_security_config()


@pytest.mark.no_db
def test_password_policy_and_hash_are_hardened():
    with pytest.raises(PasswordPolicyError):
        validate_password_policy("admin123", login="admin")
    with pytest.raises(PasswordPolicyError):
        validate_password_policy("short", login="operator")

    encoded = hash_password("LongEnoughPassword1")
    _iterations, salt, _digest = parse_encoded(encoded)
    assert len(salt) >= 32
    assert verify_password("LongEnoughPassword1", encoded)
    assert not verify_password("wrong", encoded)
