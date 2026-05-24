from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import auth.service as auth_service_module
import config as config_module
from auth.service import AuthService


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_authenticate_fails_closed_when_db_is_unavailable_by_default(monkeypatch):
    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(auth_service_module, "get_session", failing_session)
    monkeypatch.setattr(config_module, "AUTH_UI_DB_USERS_ENABLED", True)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", True)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", False)
    monkeypatch.setattr(config_module, "UI_USER_ROLES", {"admin": "admin"})

    auth_service = AuthService(SimpleNamespace(users={"admin": "admin123"}))

    with pytest.raises(RuntimeError, match="db unavailable"):
        await auth_service.authenticate("admin", "admin123")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_authenticate_config_fallback_requires_explicit_insecure_dev(monkeypatch):
    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(auth_service_module, "get_session", failing_session)
    monkeypatch.setattr(config_module, "AUTH_UI_DB_USERS_ENABLED", True)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", True)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", True)
    monkeypatch.setattr(config_module, "UI_USER_ROLES", {"admin": "admin"})

    auth_service = AuthService(SimpleNamespace(users={"admin": "admin123"}))

    ok, actor_role = await auth_service.authenticate("admin", "admin123")
    assert ok is True
    assert actor_role == "admin"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ui_token_lifecycle_falls_back_to_in_memory_store_when_db_is_unavailable(monkeypatch):
    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(auth_service_module, "get_session", failing_session)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", True)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", True)
    AuthService._LEGACY_TOKEN_STORE.clear()

    auth_service = AuthService(SimpleNamespace(users={"admin": "admin123"}))

    token = await auth_service.generate_ui_token("admin", "admin", expires_hours=24)
    token_info = await auth_service.verify_ui_token(token)
    revoked = await auth_service.revoke_ui_token(token)
    token_info_after_revoke = await auth_service.verify_ui_token(token)

    assert token_info is not None
    assert token_info["user_login"] == "admin"
    assert token_info["actor_role"] == "admin"
    assert token_info["type"] == "ui"
    assert revoked is True
    assert token_info_after_revoke is None


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ui_token_lifecycle_skips_repeated_db_probe_during_cooldown(monkeypatch):
    attempts = 0

    @asynccontextmanager
    async def failing_session():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(auth_service_module, "get_session", failing_session)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", True)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", True)
    AuthService._LEGACY_TOKEN_STORE.clear()
    monkeypatch.setattr(AuthService, "_UI_DB_FAILURE_COOLDOWN_SECONDS", 60.0, raising=False)
    monkeypatch.setattr(AuthService, "_UI_DB_COOLDOWN_UNTIL", 0.0, raising=False)

    auth_service = AuthService(SimpleNamespace(users={"admin": "admin123"}))

    token = await auth_service.generate_ui_token("admin", "admin", expires_hours=24)
    token_info = await auth_service.verify_ui_token(token)
    revoked = await auth_service.revoke_ui_token(token)

    assert attempts == 1
    assert token_info is not None
    assert token_info["user_login"] == "admin"
    assert revoked is True
