from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.policy_service import ChangePolicyService
from change.approval_service import ChangeApprovalService
from change.change_service import ChangeService


pytestmark = pytest.mark.db_cleanup("policies_config")

@pytest.mark.asyncio
async def test_change_policy_effective_preview_prefers_risk_over_global(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = ChangePolicyService(session)
        await service.save_policy(
            {
                "code": "global-default",
                "title": "Global",
                "scope_type": "global",
                "approval_mode": "single",
                "require_pir": True,
            },
            actor_id="admin-1",
        )
        await service.save_policy(
            {
                "code": "critical-cab",
                "title": "Critical CAB",
                "scope_type": "risk_level",
                "risk_level": "critical",
                "approval_mode": "cab",
                "approver_roles": ["change_manager"],
            },
            actor_id="admin-1",
        )
        preview = await service.effective_policy({"risk_level": "critical", "change_type": "normal"})
        await session.commit()

    assert preview["approval_mode"] == "cab"
    assert preview["approver_roles"] == ["change_manager"]


@pytest.mark.asyncio
async def test_standard_preapproved_policy_skips_approval_and_preserves_catalog(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        policy_service = ChangePolicyService(session)
        await policy_service.save_policy(
            {
                "code": "standard-laptop-agent-update",
                "title": "Preapproved laptop agent update",
                "scope_type": "change_type",
                "change_type": "standard",
                "standard_preapproved": True,
                "approval_mode": "single",
                "require_risk_assessment": False,
                "require_plan": False,
                "require_rollback_plan": False,
                "require_pir": False,
                "metadata": {
                    "standard_catalog": [
                        {
                            "code": "std-agent-update",
                            "title": "Agent minor update",
                            "allowed_window": "weekly maintenance",
                            "rollback": "launcher rollback",
                        }
                    ]
                },
            },
            actor_id="admin-1",
        )
        change = await ChangeService(session).create_change(
            {
                "title": "Agent minor update",
                "description": "Preapproved catalog entry",
                "change_type": "standard",
                "metadata": {"standard_change_code": "std-agent-update"},
            },
            actor_id="support-1",
        )
        approvals = await ChangeApprovalService(session).request_approvals(change["change_id"], actor_id="support-1")
        await ChangeService(session).transition_change(change["change_id"], "submitted", {}, actor_id="support-1")
        await ChangeService(session).transition_change(change["change_id"], "assessing", {}, actor_id="support-1")
        await ChangeService(session).transition_change(change["change_id"], "awaiting_approval", {}, actor_id="support-1")
        approved = await ChangeService(session).transition_change(change["change_id"], "approved", {}, actor_id="support-1")
        preview = await policy_service.effective_policy({"change_type": "standard"})
        await session.commit()

    assert approvals["approvals"][0]["status"] == "skipped"
    assert approved["status"] == "approved"
    assert preview["approval_mode"] == "none"
    assert preview["metadata"]["standard_catalog"][0]["code"] == "std-agent-update"

