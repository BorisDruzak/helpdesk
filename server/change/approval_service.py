from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Change, ChangeApproval
from change.policy_service import ChangePolicyService
from change.serializers import approval_to_dict


class ChangeApprovalService:
    def __init__(self, session) -> None:
        self.session = session

    async def request_approvals(self, change_id: str, *, actor_id: str | None) -> dict:
        change = await self.session.get(Change, change_id)
        if change is None:
            raise ValueError("change not found")
        existing = (await self.session.execute(select(ChangeApproval).where(ChangeApproval.change_id == change_id))).scalars().all()
        if existing:
            return {"approvals": [approval_to_dict(row) for row in existing]}
        policy = await ChangePolicyService(self.session).effective_policy(
            {"change_type": change.change_type, "risk_level": change.risk_level, "service_code": change.service_code, "offering_code": change.offering_code}
        )
        mode = policy.get("approval_mode", "single")
        if mode == "none":
            row = ChangeApproval(change_id=change_id, approval_id=str(uuid.uuid4()), approval_stage="cab", status="skipped", required=False)
            self.session.add(row)
            await self.session.flush()
            return {"approvals": [approval_to_dict(row)]}
        actor_ids = list(policy.get("approver_actor_ids") or []) or ["change-manager"]
        rows = []
        for actor in actor_ids:
            row = ChangeApproval(
                approval_id=str(uuid.uuid4()),
                change_id=change_id,
                approval_stage="cab" if mode == "cab" else "technical_review",
                approver_actor_id=actor,
                approver_role=(policy.get("approver_roles") or [None])[0],
                required=True,
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        return {"approvals": [approval_to_dict(row) for row in rows]}

    async def decide_approval(self, change_id: str, approval_id: str, *, decision: str, actor_id: str | None, actor_role: str | None, comment: str | None = None) -> dict:
        row = (
            await self.session.execute(select(ChangeApproval).where(ChangeApproval.change_id == change_id, ChangeApproval.approval_id == approval_id))
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("approval not found")
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision is invalid")
        if row.approver_actor_id and actor_id != row.approver_actor_id and actor_role != "admin":
            raise ValueError("current actor is not an approver")
        row.status = decision
        row.decision_comment = comment
        row.decided_by_actor_id = actor_id
        row.decided_at = datetime.now(timezone.utc)
        await self.session.flush()
        return approval_to_dict(row)

    async def approval_status(self, change_id: str) -> dict:
        rows = (await self.session.execute(select(ChangeApproval).where(ChangeApproval.change_id == change_id))).scalars().all()
        required = [row for row in rows if row.required]
        if not rows:
            return {"satisfied": False, "rejected": False, "pending": True}
        if not required:
            return {
                "satisfied": all(row.status in {"approved", "skipped"} for row in rows),
                "rejected": any(row.status == "rejected" for row in rows),
                "pending": any(row.status == "pending" for row in rows),
            }
        return {
            "satisfied": bool(required) and all(row.status == "approved" for row in required),
            "rejected": any(row.status == "rejected" for row in rows),
            "pending": any(row.status == "pending" for row in rows),
        }

