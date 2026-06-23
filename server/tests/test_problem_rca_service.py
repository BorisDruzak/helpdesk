from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from problem.problem_service import ProblemService
from problem.rca_service import RCAService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_rca_records_are_versioned_and_require_human_approval(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        problem = await ProblemService(session).create_problem(
            {"title": "Repeated VPN outage", "description": "Pattern needs RCA."},
            actor_id="support-1",
        )
        service = RCAService(session)
        draft = await service.create_draft(
            problem["problem_id"],
            {
                "methodology": "five_whys",
                "problem_statement": "VPN users disconnect during auth.",
                "impact_summary": "Network offering reliability is degraded.",
                "root_cause": "Expired route on VPN gateway.",
                "root_cause_category": "configuration",
            },
            actor_id="support-1",
        )
        submitted = await service.submit_review(problem["problem_id"], draft["rca_id"], actor_id="support-1")
        approved = await service.approve(problem["problem_id"], draft["rca_id"], actor_id="qa-1")
        second = await service.create_draft(
            problem["problem_id"],
            {"methodology": "narrative", "problem_statement": "Updated RCA", "root_cause": "Config drift"},
            actor_id="support-1",
        )
        await session.commit()

    assert draft["version_number"] == 1
    assert submitted["status"] == "in_review"
    assert approved["status"] == "approved"
    assert approved["approved_by_actor_id"] == "qa-1"
    assert second["version_number"] == 2
