from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from problem.problem_service import ProblemService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_problem_service_lists_created_problem(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        created = await ProblemService(session).create_problem({"title": "VPN", "description": "VPN repeats"}, actor_id="support-1")
        listed = await ProblemService(session).list_problems()

    assert listed[0]["problem_id"] == created["problem_id"]
