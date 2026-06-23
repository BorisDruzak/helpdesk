from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.change_service import ChangeService
from change.risk_service import RiskAssessmentService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_risk_assessment_scores_and_requires_override_reason(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        change = await ChangeService(session).create_change(
            {"title": "Database patch", "description": "Patch DB cluster", "change_type": "normal"},
            actor_id="support-1",
        )
        with pytest.raises(ValueError, match="override"):
            await RiskAssessmentService(session).create_assessment(
                change["change_id"],
                {
                    "risk_level": "low",
                    "risk_factors": {"service_criticality": "critical", "data_impact": "critical"},
                },
                actor_id="support-1",
            )
        assessment = await RiskAssessmentService(session).create_assessment(
            change["change_id"],
            {
                "risk_level": "critical",
                "risk_factors": {"service_criticality": "critical", "data_impact": "critical"},
            },
            actor_id="support-1",
        )
        await session.commit()

    assert assessment["suggested_risk_level"] == "critical"
    assert assessment["risk_level"] == "critical"

