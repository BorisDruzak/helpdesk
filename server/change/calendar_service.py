from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select

from app.db.models import Change, ChangeWindow
from change.contracts import clean_text
from change.serializers import change_to_dict, window_to_dict


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").replace("Z", "+00:00")
    result = datetime.fromisoformat(raw)
    return result if result.tzinfo else result.replace(tzinfo=timezone.utc)


class ChangeCalendarService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_window(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        title = clean_text(payload.get("title"))
        if not title:
            raise ValueError("title is required")
        row = ChangeWindow(
            window_id=str(uuid.uuid4()),
            title=title,
            window_type=clean_text(payload.get("window_type")) or "maintenance",
            service_code=clean_text(payload.get("service_code")),
            offering_code=clean_text(payload.get("offering_code")),
            object_type=clean_text(payload.get("object_type")),
            object_ref=clean_text(payload.get("object_ref")),
            starts_at=_parse_dt(payload.get("starts_at")),
            ends_at=_parse_dt(payload.get("ends_at")),
            timezone_name=clean_text(payload.get("timezone")),
            recurrence_rule=clean_text(payload.get("recurrence_rule")),
            created_by=actor_id,
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.session.add(row)
        await self.session.flush()
        return window_to_dict(row)

    async def schedule_change(
        self,
        change_id: str,
        *,
        planned_start_at: Any,
        planned_end_at: Any,
        actor_id: str | None,
        blackout_override: bool = False,
        override_justification: str | None = None,
    ) -> dict[str, Any]:
        change = await self.session.get(Change, change_id)
        if change is None:
            raise ValueError("change not found")
        start = _parse_dt(planned_start_at)
        end = _parse_dt(planned_end_at)
        blackout = await self._blackout_conflict(change, start, end)
        if blackout and not blackout_override:
            raise ValueError("blackout window blocks scheduling")
        if blackout_override and not clean_text(override_justification):
            raise ValueError("blackout override justification is required")
        change.planned_start_at = start
        change.planned_end_at = end
        change.blackout_override = bool(blackout_override)
        if blackout_override:
            change.emergency_justification = clean_text(override_justification)
        change.status = "scheduled"
        change.scheduled_at = datetime.now(timezone.utc)
        await self.session.flush()
        return change_to_dict(change)

    async def list_windows(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(ChangeWindow).order_by(ChangeWindow.starts_at.desc()).limit(100))).scalars().all()
        return [window_to_dict(row) for row in rows]

    async def _blackout_conflict(self, change: Change, start: datetime, end: datetime) -> bool:
        stmt = select(ChangeWindow).where(
            ChangeWindow.window_type == "blackout",
            ChangeWindow.starts_at < end,
            ChangeWindow.ends_at > start,
            or_(ChangeWindow.service_code.is_(None), ChangeWindow.service_code == change.service_code),
            or_(ChangeWindow.offering_code.is_(None), ChangeWindow.offering_code == change.offering_code),
        )
        return (await self.session.execute(stmt)).first() is not None

