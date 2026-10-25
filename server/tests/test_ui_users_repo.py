from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import UiToken, UiUser
from app.repos.ui_users_repo import UiUsersRepo
import auth.admin_users_handlers as admin_users_handlers
import auth.middleware as auth_middleware_module
import auth.service as auth_service_module
import config as config_module
from auth.service import AuthService


pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
@pytest.mark.parametrize("current_role", ["support", "user"])
async def test_existing_ui_token_observes_role_update_and_deactivation(test_engine, monkeypatch, current_role):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    @asynccontextmanager
    async def isolated_session():
        async with session_maker() as session:
            yield session

    monkeypatch.setattr(auth_service_module, "get_session", isolated_session)
    monkeypatch.setattr(auth_middleware_module, "get_session", isolated_session)
    monkeypatch.setattr(admin_users_handlers, "get_session", isolated_session)
    monkeypatch.setattr(admin_users_handlers, "AUTH_UI_DB_USERS_ENABLED", True)
    monkeypatch.setattr(auth_middleware_module, "_WEB_AUTH_AUDIT_LAST_SEEN", {})
    monkeypatch.setattr(AuthService, "_UI_DB_COOLDOWN_UNTIL", 0.0)
    monkeypatch.setattr(config_module, "AUTH_UI_CONFIG_FALLBACK_ENABLED", False)
    monkeypatch.setattr(config_module, "ALLOW_INSECURE_DEV_DEFAULTS", False)
    login = "session-role-update@example.test"
    async with session_maker() as session:
        assert list((await session.execute(select(UiToken))).scalars()) == []
        await UiUsersRepo(session).create_user(login, "unused-password-hash", actor_role="admin")
    auth_service = AuthService(SimpleNamespace(users={}))
    token = await auth_service.generate_ui_token(login, "admin", expires_hours=24)
    await auth_service.generate_ui_token(login, "admin", expires_hours=24)
    assert (await auth_service.verify_ui_token(token))["actor_role"] == "admin"

    app = web.Application(middlewares=[auth_middleware_module.auth_middleware])
    app["state"] = SimpleNamespace(users={})
    app.router.add_get("/api/admin/users/{user_login}", admin_users_handlers.handle_admin_users_get)
    headers = {"Authorization": f"Bearer {token}"}
    async with TestClient(TestServer(app)) as client:
        allowed = await client.get(f"/api/admin/users/{login}", headers=headers)
        assert allowed.status == 200
        assert (await allowed.json())["actor_role"] == "admin"

        async with session_maker() as session:
            await UiUsersRepo(session).update_user(login, actor_role=current_role, actor_id="admin")

        assert (await auth_service.verify_ui_token(token))["actor_role"] == current_role
        forbidden = await client.get(f"/api/admin/users/{login}", headers=headers)
        assert forbidden.status == 403
        assert (await forbidden.json())["error_code"] == "FORBIDDEN"

        async with session_maker() as session:
            records = list((await session.execute(select(UiToken))).scalars())
            assert len(records) == 2
            assert all(record.actor_role == "admin" and record.revoked_at is None for record in records)
            await UiUsersRepo(session).update_user(login, is_active=False, actor_id="admin")

        unauthenticated = await client.get(f"/api/admin/users/{login}", headers=headers)
        assert unauthenticated.status == 401
        assert (await unauthenticated.json())["error_code"] == "AUTH_REQUIRED"

    async with session_maker() as session:
        records = list((await session.execute(select(UiToken))).scalars())
        assert len(records) == 2
        assert all(record.revoked_at is not None for record in records)
    assert await auth_service.verify_ui_token(token) is None


@pytest.mark.asyncio
async def test_ui_users_repo_rejects_case_variant_login(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = UiUsersRepo(session)
        first = await repo.create_user("Alice.Case@Test.Example", "hash-a", actor_role="user", actor_id="admin")

    async with session_maker() as session:
        repo = UiUsersRepo(session)
        lookup = await repo.get_by_login("alice.case@test.example")
        with pytest.raises(ValueError, match="User already exists"):
            await repo.create_user("alice.case@test.example", "hash-b", actor_role="user", actor_id="admin")

    assert first.user_login == "alice.case@test.example"
    assert lookup is not None
    assert lookup.user_login == "alice.case@test.example"


@pytest.mark.asyncio
async def test_ui_users_repo_failed_attempts_are_atomic_across_stale_sessions(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "lockout-race@example.test"

    async with session_maker() as session:
        repo = UiUsersRepo(session)
        await repo.create_user(login, "hash-a", actor_role="user", actor_id="admin")

    async with session_maker() as first_session, session_maker() as second_session:
        first_repo = UiUsersRepo(first_session)
        second_repo = UiUsersRepo(second_session)

        first_user = await first_repo.get_by_login(login)
        second_user = await second_repo.get_by_login(login)
        assert first_user is not None
        assert second_user is not None
        assert first_user.failed_attempts == 0
        assert second_user.failed_attempts == 0

        first_locked = await first_repo.increment_failed_attempts(login, max_attempts=2, lock_minutes=15)
        second_locked = await second_repo.increment_failed_attempts(login, max_attempts=2, lock_minutes=15)

    async with session_maker() as session:
        user = (
            await session.execute(
                select(UiUser).where(UiUser.user_login == login)
            )
        ).scalar_one()

    assert first_locked is False
    assert second_locked is True
    assert user.failed_attempts == 2
    assert user.locked_until is not None
