from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeItem, ProblemKnownErrorLink
from app.repos.knowledge_repo import serialize_item
from knowledge.contracts import actor_visible_visibilities
from problem.known_error_service import ProblemKnownErrorService
from problem.problem_service import ProblemService


@pytest.mark.asyncio
async def test_problem_creates_internal_known_error_and_workaround_drafts(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        problem = await ProblemService(session).create_problem(
            {
                "title": "Repeated VPN disconnects",
                "description": "Root cause known.",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
            },
            actor_id="support-1",
        )
        service = ProblemKnownErrorService(session)
        known_error = await service.create_known_error_draft(problem["problem_id"], actor_id="support-1")
        workaround = await service.create_workaround_draft(problem["problem_id"], actor_id="support-1")
        await session.commit()

        ke_item = await session.get(KnowledgeItem, known_error["knowledge_item_id"])
        workaround_item = await session.get(KnowledgeItem, workaround["knowledge_item_id"])
        links = (await session.execute(ProblemKnownErrorLink.__table__.select())).all()

    assert ke_item.item_type == "known_error"
    assert ke_item.visibility == "support_internal"
    assert workaround_item.item_type == "workaround"
    assert workaround_item.visibility == "support_internal"
    assert len(links) == 2
    assert "support_internal" not in actor_visible_visibilities("requester")
    assert serialize_item(ke_item)["visibility"] == "support_internal"
