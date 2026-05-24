from types import SimpleNamespace
import uuid

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import config
from auth.context import AuthContext, AuthType
from auth.middleware import auth_middleware
import auth.middleware as auth_middleware_module
import auth.handlers as auth_handlers
import app.db as app_db_module
import app.repos.auth_tokens_repo as auth_tokens_repo_module
from auth.password_service import PasswordPolicyError, hash_password, parse_encoded, validate_password_policy, verify_password
from auth.rate_limit import client_ip
from routes import setup_routes
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX


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


@pytest.mark.no_db
def test_rate_limit_client_ip_ignores_x_forwarded_for_by_default(monkeypatch):
    monkeypatch.setattr(config, "TRUST_X_FORWARDED_FOR", False)
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", "")
    request = SimpleNamespace(headers={"X-Forwarded-For": "203.0.113.10"}, remote="198.51.100.5")

    assert client_ip(request) == "198.51.100.5"


@pytest.mark.no_db
def test_rate_limit_client_ip_uses_x_forwarded_for_only_for_trusted_proxy(monkeypatch):
    monkeypatch.setattr(config, "TRUST_X_FORWARDED_FOR", True)
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", "198.51.100.0/24")
    trusted_request = SimpleNamespace(headers={"X-Forwarded-For": "203.0.113.10"}, remote="198.51.100.5")
    untrusted_request = SimpleNamespace(headers={"X-Forwarded-For": "203.0.113.10"}, remote="192.0.2.5")

    assert client_ip(trusted_request) == "203.0.113.10"
    assert client_ip(untrusted_request) == "192.0.2.5"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_legacy_device_token_list_requires_admin_role(monkeypatch):
    device_id = str(uuid.uuid4())

    async def fake_extract_auth_context(request):
        token = request.headers.get("Authorization", "").replace("Bearer ", "", 1)
        if token == TEST_UI_ADMIN_TOKEN:
            return AuthContext(actor_id="admin", actor_role="admin", auth_type=AuthType.UI_TOKEN, token=token)
        if token == TEST_UI_SUPPORT_TOKEN:
            return AuthContext(actor_id="support", actor_role="support", auth_type=AuthType.UI_TOKEN, token=token)
        if token.startswith(TEST_UI_USER_PREFIX):
            return AuthContext(actor_id="operator", actor_role="user", auth_type=AuthType.UI_TOKEN, token=token)
        if token.startswith(TEST_AGENT_PREFIX):
            return AuthContext(actor_id=device_id, actor_role="agent", auth_type=AuthType.AGENT_TOKEN, token=token)
        return None

    async def fake_get_agent_tokens_by_device(self, requested_device_id):
        assert requested_device_id == device_id
        return []

    monkeypatch.setattr(auth_middleware_module, "extract_auth_context", fake_extract_auth_context)
    monkeypatch.setattr(app_db_module, "get_session", lambda: _FakeSessionContext())
    monkeypatch.setattr(
        auth_tokens_repo_module.AuthTokensRepo,
        "get_agent_tokens_by_device",
        fake_get_agent_tokens_by_device,
    )

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    for token in (
        TEST_AGENT_PREFIX + device_id,
        TEST_UI_SUPPORT_TOKEN,
        TEST_UI_USER_PREFIX + "operator",
    ):
        async with TestClient(TestServer(app)) as client:
            response = await client.get(f"/api/devices/{device_id}/tokens", headers=_bearer(token))
            assert response.status == 403

    async with TestClient(TestServer(app)) as client:
        admin_response = await client.get(f"/api/devices/{device_id}/tokens", headers=_bearer(TEST_UI_ADMIN_TOKEN))
        payload = await admin_response.json()

    assert admin_response.status == 200
    assert payload["status"] == "success"
    assert payload["device_id"] == device_id


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_legacy_device_token_revoke_requires_admin_and_scopes_device(monkeypatch):
    device_id = str(uuid.uuid4())
    token_hash = "own-token-hash"
    other_token_hash = "other-token-hash"
    revoke_calls: list[tuple[str, str]] = []

    async def fake_extract_auth_context(request):
        token = request.headers.get("Authorization", "").replace("Bearer ", "", 1)
        if token == TEST_UI_ADMIN_TOKEN:
            return AuthContext(actor_id="admin", actor_role="admin", auth_type=AuthType.UI_TOKEN, token=token)
        if token.startswith(TEST_AGENT_PREFIX):
            return AuthContext(actor_id=device_id, actor_role="agent", auth_type=AuthType.AGENT_TOKEN, token=token)
        return None

    async def fake_revoke_agent_token_by_hash(self, requested_hash, *, device_id):
        revoke_calls.append((requested_hash, device_id))
        return requested_hash == token_hash

    async def fake_audit(**_kwargs):
        return None

    monkeypatch.setattr(auth_middleware_module, "extract_auth_context", fake_extract_auth_context)
    monkeypatch.setattr(app_db_module, "get_session", lambda: _FakeSessionContext())
    monkeypatch.setattr(
        auth_tokens_repo_module.AuthTokensRepo,
        "revoke_agent_token_by_hash",
        fake_revoke_agent_token_by_hash,
    )
    monkeypatch.setattr(auth_handlers, "write_agent_runtime_audit", fake_audit)

    app = web.Application(middlewares=[auth_middleware])
    app["state"] = SimpleNamespace(users={})
    setup_routes(app)

    async with TestClient(TestServer(app)) as client:
        forbidden = await client.post(
            f"/api/devices/{device_id}/tokens/revoke",
            headers=_bearer(TEST_AGENT_PREFIX + device_id),
            json={"token_hash": token_hash},
        )
        assert forbidden.status == 403

    assert revoke_calls == []

    async with TestClient(TestServer(app)) as client:
        wrong_device = await client.post(
            f"/api/devices/{device_id}/tokens/revoke",
            headers=_bearer(TEST_UI_ADMIN_TOKEN),
            json={"token_hash": other_token_hash},
        )
        assert wrong_device.status == 404

        own_revoke = await client.post(
            f"/api/devices/{device_id}/tokens/revoke",
            headers=_bearer(TEST_UI_ADMIN_TOKEN),
            json={"token_hash": token_hash},
        )
        assert own_revoke.status == 200

    assert revoke_calls == [(other_token_hash, device_id), (token_hash, device_id)]
