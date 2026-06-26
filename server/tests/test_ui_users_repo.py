from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import UiUser
from app.repos.ui_users_repo import UiUsersRepo


pytestmark = pytest.mark.db_cleanup("registry_access")


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
