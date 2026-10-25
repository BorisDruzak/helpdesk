from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import auth.service as auth_service_module
import config as config_module
from auth.service import AuthService


@pytest.fixture(autouse=True)
def isolate_auth_fallback_state(monkeypatch):
    monkeypatch.setattr(AuthService, "_UI_DB_COOLDOWN_UNTIL", 0.0)
    monkeypatch.setattr(AuthService, "_LEGACY_TOKEN_STORE", {})


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("config_fallback,insecure_dev", [(False, False), (True, False), (False, True)])
async def test_authenticate_cooldown_cannot_enable_disabled_config_fallback(
    monkeypatch, config_fallback, insecure_dev
):
    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(auth_service_module, "get_session", failing_session)
    monkeypatch.setattr(config_module, "AUTH_UI_DB_USERS_ENABLED", True)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", config_fallback)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", insecure_dev)
    auth_service = AuthService(SimpleNamespace(users={"admin": "admin123"}))

    with pytest.raises(RuntimeError, match="db unavailable"):
        await auth_service.authenticate("admin", "admin123")
    with pytest.raises(RuntimeError):
        await auth_service.authenticate("admin", "admin123")


@pytest.fixture
def persisted_ui_session(monkeypatch):
    user = SimpleNamespace(user_login="operator", actor_role="support", is_active=True)
    token_record = SimpleNamespace(
        user_login="operator", actor_role="admin", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    state = SimpleNamespace(user=user, token=token_record, revoked=False)

    @asynccontextmanager
    async def session():
        yield SimpleNamespace()

    class TokenRepo:
        def __init__(self, session):
            pass

        async def verify_ui_token(self, token):
            return None if state.revoked else state.token

        async def revoke_active_ui_tokens_for_user(self, login):
            state.revoked = True

    class UserRepo:
        def __init__(self, session):
            pass

        async def get_by_login(self, login):
            return state.user

    monkeypatch.setattr(auth_service_module, "get_session", session)
    monkeypatch.setattr(auth_service_module, "AuthTokensRepo", TokenRepo)
    monkeypatch.setattr(auth_service_module, "UiUsersRepo", UserRepo)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", False)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", False)
    return state


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ui_token_uses_current_user_role_after_demotion(persisted_ui_session):
    auth_service = AuthService(SimpleNamespace(users={}))

    token_info = await auth_service.verify_ui_token("issued-before-demotion")

    assert token_info == {
        "user_login": "operator",
        "actor_role": "support",
        "created_at": "2026-01-01T00:00:00+00:00",
        "type": "ui",
    }


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("current_role", ["", "unknown", None])
async def test_ui_token_rejects_invalid_current_user_role(persisted_ui_session, current_role):
    persisted_ui_session.user.actor_role = current_role
    auth_service = AuthService(SimpleNamespace(users={}))

    assert await auth_service.verify_ui_token("issued-to-valid-admin") is None


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("user_exists", [False, True])
async def test_ui_token_rejects_missing_or_inactive_user(persisted_ui_session, user_exists):
    if user_exists:
        persisted_ui_session.user.is_active = False
    else:
        persisted_ui_session.user = None
    auth_service = AuthService(SimpleNamespace(users={}))

    assert await auth_service.verify_ui_token("issued-to-active-admin") is None


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ui_token_checks_registry_status_after_demotion_to_user(monkeypatch, persisted_ui_session):
    persisted_ui_session.user.actor_role = "user"

    async def registry_block(session, login):
        return {"person_id": "inactive-person", "status": "inactive"}

    async def disable_user(session, user, token_repo, **kwargs):
        user.is_active = False
        await token_repo.revoke_active_ui_tokens_for_user(user.user_login)

    auth_service = AuthService(SimpleNamespace(users={}))
    monkeypatch.setattr(auth_service, "_registry_person_block_for_ui_user", registry_block)
    monkeypatch.setattr(auth_service, "_disable_ui_user_for_registry_block", disable_user)

    assert await auth_service.verify_ui_token("issued-before-demotion") is None


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("config_fallback,insecure_dev", [(False, False), (True, False), (False, True)])
async def test_ui_token_rejects_legacy_store_when_fallback_is_disabled(
    monkeypatch, persisted_ui_session, config_fallback, insecure_dev
):
    persisted_ui_session.token = None
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", config_fallback)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", insecure_dev)
    AuthService._store_legacy_ui_token(
        "legacy-token", user_login="operator", actor_role="admin", expires_at=None
    )

    assert await AuthService(SimpleNamespace(users={})).verify_ui_token("legacy-token") is None


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ui_token_failure_and_revocation_logs_do_not_expose_token_prefix(monkeypatch):
    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(auth_service_module, "get_session", failing_session)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", True)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", True)
    messages = []
    monkeypatch.setattr(auth_service_module.logger, "warning", messages.append)
    monkeypatch.setattr(auth_service_module.logger, "info", messages.append)
    auth_service = AuthService(SimpleNamespace(users={}))
    token = "PRIVATE-session-token-value"

    assert await auth_service.verify_ui_token(token) is None
    AuthService._clear_ui_db_cooldown()
    assert await auth_service.revoke_ui_token(token) is False
    AuthService._store_legacy_ui_token(token, user_login="operator", actor_role="user", expires_at=None)
    auth_service.revoke_token(token)

    assert messages
    assert token[:8] not in "\n".join(messages)


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
    assert await auth_service.authenticate("admin", "admin123") == (True, "admin")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_authenticate_config_only_mode_remains_available_during_db_cooldown(monkeypatch):
    monkeypatch.setattr(config_module, "AUTH_UI_DB_USERS_ENABLED", False)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", False)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", False)
    monkeypatch.setattr(config_module, "UI_USER_ROLES", {"operator": "support"})
    AuthService._mark_ui_db_unavailable()

    assert await AuthService(SimpleNamespace(users={"operator": "configured-password"})).authenticate(
        "operator", "configured-password"
    ) == (True, "support")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ui_token_accepts_explicit_legacy_fallback_when_db_recovers(monkeypatch, persisted_ui_session):
    persisted_ui_session.token = None
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", True)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", True)
    AuthService._store_legacy_ui_token(
        "legacy-token", user_login="operator", actor_role="support", expires_at=None
    )

    token_info = await AuthService(SimpleNamespace(users={})).verify_ui_token("legacy-token")

    assert token_info is not None
    assert token_info["user_login"] == "operator"
    assert token_info["actor_role"] == "support"


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
