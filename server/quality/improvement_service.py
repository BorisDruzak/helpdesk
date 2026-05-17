from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import ContinuousImprovementAction
from quality.contracts import ACTION_PRIORITIES, ACTION_STATUSES, IMPROVEMENT_ACTION_TYPES
from quality.serializers import action_to_dict


class ContinuousImprovementService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_action(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        action_type = str(payload.get("action_type") or "").strip()
        if action_type not in IMPROVEMENT_ACTION_TYPES:
            raise ValueError("action_type is invalid")
        priority = str(payload.get("priority") or "medium").strip() or "medium"
        if priority not in ACTION_PRIORITIES:
            raise ValueError("priority is invalid")
        title = str(payload.get("title") or "").strip()
        if not title:
            raise ValueError("title is required")
        now = datetime.now(timezone.utc)
        row = ContinuousImprovementAction(
            action_id=str(uuid.uuid4()),
            source_kind=str(payload.get("source_kind") or "manual").strip() or "manual",
            source_ref=str(payload.get("source_ref") or "").strip() or None,
            ticket_id=str(payload.get("ticket_id") or "").strip() or None,
            review_id=str(payload.get("review_id") or "").strip() or None,
            feedback_id=str(payload.get("feedback_id") or "").strip() or None,
            service_code=str(payload.get("service_code") or "").strip() or None,
            offering_code=str(payload.get("offering_code") or "").strip() or None,
            action_type=action_type,
            title=title,
            description=str(payload.get("description") or "").strip() or None,
            status=str(payload.get("status") or "open").strip() or "open",
            priority=priority,
            owner_actor_id=str(payload.get("owner_actor_id") or "").strip() or None,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self._validate_status(row.status, row.owner_actor_id, row.outcome_notes)
        self.session.add(row)
        await self.session.flush()
        return action_to_dict(row)

    async def update_action(self, action_id: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(action_id)
        if "owner_actor_id" in payload:
            row.owner_actor_id = str(payload.get("owner_actor_id") or "").strip() or None
        if "status" in payload:
            row.status = str(payload.get("status") or "").strip()
        if "priority" in payload:
            row.priority = str(payload.get("priority") or "").strip()
        if row.status not in ACTION_STATUSES:
            raise ValueError("status is invalid")
        if row.priority not in ACTION_PRIORITIES:
            raise ValueError("priority is invalid")
        self._validate_status(row.status, row.owner_actor_id, row.outcome_notes)
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return action_to_dict(row)

    async def close_action(self, action_id: str, *, outcome_notes: str, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(action_id)
        notes = str(outcome_notes or "").strip()
        if not notes:
            raise ValueError("outcome is required")
        row.status = "done"
        row.outcome_notes = notes
        row.closed_at = datetime.now(timezone.utc)
        row.updated_at = row.closed_at
        await self.session.flush()
        return action_to_dict(row)

    async def list_actions(self, *, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(ContinuousImprovementAction).order_by(ContinuousImprovementAction.created_at.desc())
        if status:
            stmt = stmt.where(ContinuousImprovementAction.status == status)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [action_to_dict(row) for row in rows]

    def _validate_status(self, status: str, owner_actor_id: str | None, outcome_notes: str | None) -> None:
        if status in {"assigned", "in_progress"} and not owner_actor_id:
            raise ValueError("owner is required before assigned or in_progress")
        if status == "done" and not str(outcome_notes or "").strip():
            raise ValueError("outcome is required before done")

    async def _get(self, action_id: str) -> ContinuousImprovementAction:
        row = await self.session.get(ContinuousImprovementAction, action_id)
        if row is None:
            raise ValueError("action not found")
        return row

