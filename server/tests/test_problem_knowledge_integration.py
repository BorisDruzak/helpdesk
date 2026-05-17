from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from problem.known_error_service import ProblemKnownErrorService
from problem.problem_service import ProblemService


@pytest.mark.asyncio
async def test_problem_known_error_uses_knowledge_platform_draft_visibility(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        problem = await ProblemService(session).create_problem({"title": "VPN known error", "description": "VPN pattern"}, actor_id="support-1")
        link = await ProblemKnownErrorService(session).create_known_error_draft(problem["problem_id"], actor_id="support-1")

    assert link["link_type"] == "known_error"
    assert link["knowledge_item_id"]
