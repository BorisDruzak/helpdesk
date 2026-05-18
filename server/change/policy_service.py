from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import ChangePolicy
from change.contracts import clean_text


DEFAULT_POLICY = {
    "require_risk_assessment": True,
    "require_plan": True,
    "require_rollback_plan": True,
    "require_pir": True,
    "standard_preapproved": False,
    "approval_mode": "single",
    "approver_roles": [],
    "approver_actor_ids": ["change-manager"],
    "blackout_enforced": True,
    "min_lead_time_hours": None,
    "max_emergency_retro_hours": 72,
    "metadata": {},
}


class ChangePolicyService:
    def __init__(self, session) -> None:
        self.session = session

    async def save_policy(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        code = clean_text(payload.get("code"))
        title = clean_text(payload.get("title"))
        if not code or not title:
            raise ValueError("code and title are required")
        existing = (await self.session.execute(select(ChangePolicy).where(ChangePolicy.code == code))).scalar_one_or_none()
        row = existing or ChangePolicy(policy_id=str(uuid.uuid4()), code=code, title=title)
        row.title = title
        row.enabled = bool(payload.get("enabled", True))
        row.scope_type = clean_text(payload.get("scope_type")) or "global"
        row.service_code = clean_text(payload.get("service_code"))
        row.offering_code = clean_text(payload.get("offering_code"))
        row.change_type = clean_text(payload.get("change_type"))
        row.risk_level = clean_text(payload.get("risk_level"))
        row.require_risk_assessment = bool(payload.get("require_risk_assessment", True))
        row.require_plan = bool(payload.get("require_plan", True))
        row.require_rollback_plan = bool(payload.get("require_rollback_plan", True))
        row.require_pir = bool(payload.get("require_pir", True))
        row.standard_preapproved = bool(payload.get("standard_preapproved", False))
        row.approval_mode = clean_text(payload.get("approval_mode")) or "single"
        row.approver_roles_json = payload.get("approver_roles") if isinstance(payload.get("approver_roles"), list) else []
        row.approver_actor_ids_json = payload.get("approver_actor_ids") if isinstance(payload.get("approver_actor_ids"), list) else []
        row.cab_group = clean_text(payload.get("cab_group"))
        row.min_lead_time_hours = _optional_int(payload.get("min_lead_time_hours"))
        row.max_emergency_retro_hours = _optional_int(payload.get("max_emergency_retro_hours"))
        row.blackout_enforced = bool(payload.get("blackout_enforced", True))
        row.metadata_json = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        row.updated_at = datetime.now(timezone.utc)
        if existing is None:
            self.session.add(row)
        await self.session.flush()
        return self._to_dict(row)

    async def list_policies(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(ChangePolicy).order_by(ChangePolicy.created_at.desc()))).scalars().all()
        return [self._to_dict(row) for row in rows]

    async def effective_policy(self, context: dict[str, Any]) -> dict[str, Any]:
        rows = (await self.session.execute(select(ChangePolicy).where(ChangePolicy.enabled.is_(True)))).scalars().all()
        selected = None
        selected_rank = -1
        for row in rows:
            rank = self._rank(row, context)
            if rank > selected_rank:
                selected = row
                selected_rank = rank
        result = dict(DEFAULT_POLICY)
        if selected is not None:
            result.update(self._to_dict(selected))
        if context.get("change_type") == "standard" and result.get("standard_preapproved"):
            result["approval_mode"] = "none"
        return result

    def _rank(self, row: ChangePolicy, context: dict[str, Any]) -> int:
        if row.scope_type == "offering" and row.offering_code and row.offering_code == context.get("offering_code"):
            return 50
        if row.scope_type == "service" and row.service_code and row.service_code == context.get("service_code"):
            return 40
        if row.scope_type == "risk_level" and row.risk_level and row.risk_level == context.get("risk_level"):
            return 30
        if row.scope_type == "change_type" and row.change_type and row.change_type == context.get("change_type"):
            return 20
        if row.scope_type == "global":
            return 10
        return -1

    def _to_dict(self, row: ChangePolicy) -> dict[str, Any]:
        return {
            "policy_id": row.policy_id,
            "code": row.code,
            "title": row.title,
            "enabled": row.enabled,
            "scope_type": row.scope_type,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "change_type": row.change_type,
            "risk_level": row.risk_level,
            "require_risk_assessment": row.require_risk_assessment,
            "require_plan": row.require_plan,
            "require_rollback_plan": row.require_rollback_plan,
            "require_pir": row.require_pir,
            "standard_preapproved": row.standard_preapproved,
            "approval_mode": row.approval_mode,
            "approver_roles": row.approver_roles_json or [],
            "approver_actor_ids": row.approver_actor_ids_json or [],
            "cab_group": row.cab_group,
            "min_lead_time_hours": row.min_lead_time_hours,
            "max_emergency_retro_hours": row.max_emergency_retro_hours,
            "blackout_enforced": row.blackout_enforced,
            "metadata": row.metadata_json or {},
        }


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)

