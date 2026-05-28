from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeItem, Problem, ProblemKnownErrorLink
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


@pytest.mark.asyncio
async def test_problem_known_error_draft_handles_reused_problem_key_slug_collision(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        first = await ProblemService(session).create_problem({"title": "Old VPN problem", "description": "Historical problem"}, actor_id="support-1")
        old_link = await ProblemKnownErrorService(session).create_known_error_draft(first["problem_id"], actor_id="support-1")
        old_item = await session.get(KnowledgeItem, old_link["knowledge_item_id"])
        assert old_item is not None

        old_problem_row = await session.get(Problem, first["problem_id"])
        assert old_problem_row is not None
        await session.delete(old_problem_row)
        await session.flush()

        second = await ProblemService(session).create_problem({"title": "New VPN problem", "description": "Current problem"}, actor_id="support-1")
        assert second["problem_key"] == first["problem_key"]

        service = ProblemKnownErrorService(session)
        new_link = await service.create_known_error_draft(second["problem_id"], actor_id="support-1")
        repeated = await service.create_known_error_draft(second["problem_id"], actor_id="support-1")
        await session.commit()

        items = (await session.execute(select(KnowledgeItem).where(KnowledgeItem.source_ref == second["problem_id"]))).scalars().all()
        links = (await session.execute(select(ProblemKnownErrorLink).where(ProblemKnownErrorLink.problem_id == second["problem_id"]))).scalars().all()

    assert new_link["knowledge_item_id"] == repeated["knowledge_item_id"]
    assert len(items) == 1
    assert len(links) == 1
    assert items[0].slug != old_item.slug
    assert items[0].slug.startswith(f"known_error-{second['problem_key'].lower()}-")
