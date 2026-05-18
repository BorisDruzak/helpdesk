from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.db.models import Change, ChangePlan
from change.serializers import plan_to_dict


class ChangePlanService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_plan(self, change_id: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        if await self.session.get(Change, change_id) is None:
            raise ValueError("change not found")
        implementation = payload.get("implementation_steps") if isinstance(payload.get("implementation_steps"), list) else []
        rollback = payload.get("rollback_steps") if isinstance(payload.get("rollback_steps"), list) else []
        validation = payload.get("validation_steps") if isinstance(payload.get("validation_steps"), list) else []
        if not implementation:
            raise ValueError("implementation steps are required")
        version = (
            await self.session.execute(select(func.coalesce(func.max(ChangePlan.version_number), 0)).where(ChangePlan.change_id == change_id))
        ).scalar_one() + 1
        row = ChangePlan(
            plan_id=str(uuid.uuid4()),
            change_id=change_id,
            version_number=version,
            implementation_steps_json=implementation,
            rollback_steps_json=rollback,
            validation_steps_json=validation,
            communication_steps_json=payload.get("communication_steps") if isinstance(payload.get("communication_steps"), list) else [],
            pre_checks_json=payload.get("pre_checks") if isinstance(payload.get("pre_checks"), list) else [],
            post_checks_json=payload.get("post_checks") if isinstance(payload.get("post_checks"), list) else [],
            downtime_expected=bool(payload.get("downtime_expected", False)),
            downtime_minutes=payload.get("downtime_minutes"),
            created_by=actor_id,
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.session.add(row)
        await self.session.flush()
        return plan_to_dict(row)

    async def approve_plan(self, change_id: str, plan_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(change_id, plan_id)
        row.status = "approved"
        row.approved_by = actor_id
        row.approved_at = datetime.now(timezone.utc)
        await self.session.flush()
        return plan_to_dict(row)

    async def _get(self, change_id: str, plan_id: str) -> ChangePlan:
        row = (await self.session.execute(select(ChangePlan).where(ChangePlan.change_id == change_id, ChangePlan.plan_id == plan_id))).scalar_one_or_none()
        if row is None:
            raise ValueError("change plan not found")
        return row

