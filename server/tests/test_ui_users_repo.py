from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

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
