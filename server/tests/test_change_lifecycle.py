from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.approval_service import ChangeApprovalService
from change.change_service import ChangeService
from change.plan_service import ChangePlanService
from change.risk_service import RiskAssessmentService


@pytest.mark.asyncio
async def test_normal_change_requires_risk_plan_rollback_and_approval(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = ChangeService(session)
        change = await service.create_change(
            {"title": "VPN gateway update", "description": "Deploy permanent fix", "change_type": "normal"},
            actor_id="support-1",
        )
        await service.transition_change(change["change_id"], "submitted", {}, actor_id="support-1")
        await service.transition_change(change["change_id"], "assessing", {}, actor_id="support-1")
        with pytest.raises(ValueError, match="risk"):
            await service.transition_change(change["change_id"], "awaiting_approval", {}, actor_id="support-1")

        risk = await RiskAssessmentService(session).create_assessment(
            change["change_id"],
            {"risk_factors": {"service_criticality": "high", "rollback_complexity": "medium"}},
            actor_id="support-1",
        )
        await RiskAssessmentService(session).submit_assessment(change["change_id"], risk["assessment_id"], actor_id="support-1")
        await RiskAssessmentService(session).approve_assessment(change["change_id"], risk["assessment_id"], actor_id="manager-1")

        plan = await ChangePlanService(session).create_plan(
            change["change_id"],
            {
                "implementation_steps": [{"title": "Deploy config"}],
                "rollback_steps": [{"title": "Restore previous config"}],
                "validation_steps": [{"title": "Smoke VPN"}],
            },
            actor_id="support-1",
        )
        await ChangePlanService(session).approve_plan(change["change_id"], plan["plan_id"], actor_id="manager-1")
        await service.transition_change(change["change_id"], "awaiting_approval", {}, actor_id="support-1")
        approval = await ChangeApprovalService(session).request_approvals(change["change_id"], actor_id="support-1")
        with pytest.raises(ValueError, match="approvals"):
            await service.transition_change(change["change_id"], "approved", {}, actor_id="support-1")
        await ChangeApprovalService(session).decide_approval(
            change["change_id"],
            approval["approvals"][0]["approval_id"],
            decision="approved",
            actor_id=approval["approvals"][0]["approver_actor_id"],
            actor_role="support",
        )
        approved = await service.transition_change(change["change_id"], "approved", {}, actor_id="support-1")
        await session.commit()

    assert approved["status"] == "approved"

