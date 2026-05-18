from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.db.models import Change, ChangeTask
from change.contracts import clean_text
from change.serializers import task_to_dict


class ChangeTaskService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_task(self, change_id: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        if await self.session.get(Change, change_id) is None:
            raise ValueError("change not found")
        title = clean_text(payload.get("title"))
        if not title:
            raise ValueError("title is required")
        order = (await self.session.execute(select(func.count(ChangeTask.task_id)).where(ChangeTask.change_id == change_id))).scalar_one()
        row = ChangeTask(
            task_id=str(uuid.uuid4()),
            change_id=change_id,
            title=title,
            description=clean_text(payload.get("description")),
            task_type=clean_text(payload.get("task_type")) or "implementation",
            owner_actor_id=clean_text(payload.get("owner_actor_id")),
            order_index=int(order),
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.session.add(row)
        await self.session.flush()
        return task_to_dict(row)

    async def update_task(self, change_id: str, task_id: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(change_id, task_id)
        if "status" in payload:
            row.status = clean_text(payload.get("status")) or row.status
        if "owner_actor_id" in payload:
            row.owner_actor_id = clean_text(payload.get("owner_actor_id"))
        if "result_notes" in payload:
            row.result_notes = clean_text(payload.get("result_notes"))
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return task_to_dict(row)

    async def complete_task(self, change_id: str, task_id: str, *, actor_id: str | None, result_notes: str | None = None) -> dict[str, Any]:
        row = await self._get(change_id, task_id)
        row.status = "done"
        row.completed_at = datetime.now(timezone.utc)
        row.result_notes = clean_text(result_notes)
        await self.session.flush()
        return task_to_dict(row)

    async def list_tasks(self, change_id: str) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(ChangeTask).where(ChangeTask.change_id == change_id).order_by(ChangeTask.order_index))).scalars().all()
        return [task_to_dict(row) for row in rows]

    async def _get(self, change_id: str, task_id: str) -> ChangeTask:
        row = (await self.session.execute(select(ChangeTask).where(ChangeTask.change_id == change_id, ChangeTask.task_id == task_id))).scalar_one_or_none()
        if row is None:
            raise ValueError("change task not found")
        return row

