from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import config
from auth.middleware import WEB_SESSION_COOKIE_NAME, auth_middleware, extract_token_from_web_cookie
import auth.middleware as auth_middleware_module
from auth.password_service import PasswordPolicyError, hash_password, parse_encoded, validate_password_policy, verify_password
from auth.rate_limit import client_ip
from routes import setup_routes


@pytest.fixture(autouse=True)
def no_web_auth_audit(monkeypatch):
    async def noop_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(auth_middleware_module, "_write_web_auth_audit", noop_audit)


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
    monkeypatch.setattr(config, "APP_ENV", "dev", raising=False)
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
def test_security_config_rejects_app_env_pilot_defaults_without_legacy_flag(monkeypatch):
    monkeypatch.setattr(config, "APP_ENV", "pilot", raising=False)
    monkeypatch.setattr(config, "PILOT_STAND_MODE", False)
    monkeypatch.setattr(config, "ALLOW_INSECURE_DEV_DEFAULTS", False)
    monkeypatch.setattr(config, "REQUIRE_HTTPS", False)
    monkeypatch.setattr(config, "REQUIRE_WSS", False)
    monkeypatch.setattr(config, "WEB_SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr(config, "AUTH_UI_CONFIG_FALLBACK_ENABLED", True)
    monkeypatch.setattr(config, "USERS", {"admin": "admin123", "user": "12345"})

    with pytest.raises(RuntimeError) as exc_info:
        config.validate_security_config()

    message = str(exc_info.value)
    assert "REQUIRE_HTTPS" in message
    assert "default UI users/passwords" in message


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
