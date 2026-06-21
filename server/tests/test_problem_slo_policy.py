from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ProblemSLOPolicy
from problem.problem_service import ProblemService
from problem.slo_service import ProblemSLOService


pytestmark = pytest.mark.db_cleanup("policies_config")

@pytest.mark.asyncio
async def test_problem_create_computes_slo_due_milestones_from_effective_policy(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            ProblemSLOPolicy(
                policy_id="severity-critical",
                scope_type="severity",
                severity="critical",
                enabled=True,
                investigation_due_hours=1,
                known_error_due_hours=4,
                workaround_due_hours=8,
                rca_due_hours=24,
                resolution_due_hours=72,
                closure_due_hours=96,
            )
        )
        await session.commit()

        problem = await ProblemService(session).create_problem(
            {"title": "Critical outage", "description": "Repeated outage", "severity": "critical"},
            actor_id="admin-1",
        )
        await session.commit()

    opened = datetime.fromisoformat(problem["opened_at"])
    assert datetime.fromisoformat(problem["investigation_due_at"]) == opened + timedelta(hours=1)
    assert datetime.fromisoformat(problem["known_error_due_at"]) == opened + timedelta(hours=4)
    assert datetime.fromisoformat(problem["workaround_due_at"]) == opened + timedelta(hours=8)
    assert datetime.fromisoformat(problem["rca_due_at"]) == opened + timedelta(hours=24)
    assert datetime.fromisoformat(problem["resolution_due_at"]) == opened + timedelta(hours=72)
    assert datetime.fromisoformat(problem["closure_due_at"]) == opened + timedelta(hours=96)


@pytest.mark.asyncio
async def test_problem_slo_service_marks_overdue_milestones(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        problem = await ProblemService(session).create_problem(
            {"title": "Aging problem", "description": "No RCA yet", "severity": "high"},
            actor_id="admin-1",
        )
        row = await ProblemSLOService(session).get_problem_row(problem["problem_id"])
        row.investigation_due_at = datetime.now(timezone.utc) - timedelta(hours=1)
        row.rca_due_at = datetime.now(timezone.utc) - timedelta(hours=1)
        breached = ProblemSLOService(session).refresh_breached_milestones(row, now=datetime.now(timezone.utc))

    assert "investigation" in breached
    assert "rca" in breached
