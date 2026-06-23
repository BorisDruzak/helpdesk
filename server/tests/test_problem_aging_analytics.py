from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Problem
from problem.analytics_service import ProblemAnalyticsService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_problem_analytics_reports_overdue_and_aging_metrics(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        session.add_all(
            [
                Problem(
                    problem_id="p-overdue",
                    problem_key="PRB-OVERDUE",
                    title="Overdue",
                    description="Overdue RCA",
                    status="investigating",
                    severity="high",
                    opened_at=now - timedelta(days=5),
                    rca_due_at=now - timedelta(days=1),
                    breached_milestones=["rca"],
                ),
                Problem(
                    problem_id="p-known-error",
                    problem_key="PRB-KNOWN",
                    title="Known",
                    description="Known error",
                    status="workaround_available",
                    severity="medium",
                    opened_at=now - timedelta(days=4),
                    known_error_at=now - timedelta(days=3),
                    workaround_available_at=now - timedelta(days=2),
                    root_cause_summary="Vendor defect",
                    workaround_summary="Restart the connector service.",
                ),
            ]
        )
        await session.commit()
        summary = await ProblemAnalyticsService(session).summary(now=now)

    assert summary["overdue_problem_count"] == 1
    assert summary["overdue_milestones"]["rca"] == 1
    assert summary["problems_without_workaround"] == 1
    assert summary["avg_time_to_known_error_hours"] == 24
    assert summary["avg_time_to_workaround_hours"] == 48
    assert "requester_id" not in repr(summary)
