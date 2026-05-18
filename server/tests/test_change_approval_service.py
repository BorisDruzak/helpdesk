from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.approval_service import ChangeApprovalService
from change.change_service import ChangeService


@pytest.mark.asyncio
async def test_change_approval_enforces_approver_identity_and_rejection_blocks(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        change = await ChangeService(session).create_change(
            {"title": "Router update", "description": "Update route", "change_type": "normal"},
            actor_id="support-1",
        )
        requested = await ChangeApprovalService(session).request_approvals(change["change_id"], actor_id="support-1")
        approval_id = requested["approvals"][0]["approval_id"]
        with pytest.raises(ValueError, match="approver"):
            await ChangeApprovalService(session).decide_approval(
                change["change_id"],
                approval_id,
                decision="approved",
                actor_id="someone-else",
                actor_role="support",
            )
        rejected = await ChangeApprovalService(session).decide_approval(
            change["change_id"],
            approval_id,
            decision="rejected",
            actor_id=requested["approvals"][0]["approver_actor_id"],
            actor_role="support",
            comment="Not enough testing",
        )
        status = await ChangeApprovalService(session).approval_status(change["change_id"])
        await session.commit()

    assert rejected["status"] == "rejected"
    assert status["rejected"] is True
    assert status["satisfied"] is False

