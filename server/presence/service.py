from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DevicePresenceDailySummary, DevicePresenceSnapshot


PRESENCE_TOOL_ID = "presence.collect"


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def extract_presence_result_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if isinstance(result, dict) and isinstance(result.get("output"), dict):
        return dict(result["output"])
    if isinstance(result, dict):
        return dict(result)
    output = payload.get("output")
    if isinstance(output, dict):
        return dict(output)
    return None


class DevicePresenceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def persist_snapshot(self, *, device_id: str, snapshot: dict[str, Any]) -> DevicePresenceSnapshot:
        collected_at = _parse_datetime(snapshot.get("collected_at")) or datetime.now(timezone.utc)
        session = snapshot.get("session") if isinstance(snapshot.get("session"), dict) else {}
        row = DevicePresenceSnapshot(
            id=str(uuid.uuid4()),
            device_id=str(device_id),
            snapshot=dict(snapshot),
            collected_at=collected_at,
            received_at=datetime.now(timezone.utc),
            session_state=str(session.get("session_state") or "unknown"),
            current_user=str(session.get("current_user") or "") or None,
            idle_seconds=int(session.get("idle_seconds")) if isinstance(session.get("idle_seconds"), int) else None,
            locked=bool(session.get("locked")) if session.get("locked") is not None else None,
        )
        self.session.add(row)
        await self._upsert_daily_summary(device_id=str(device_id), snapshot=snapshot, collected_at=collected_at)
        await self.session.flush()
        return row

    async def _upsert_daily_summary(
        self,
        *,
        device_id: str,
        snapshot: dict[str, Any],
        collected_at: datetime,
    ) -> DevicePresenceDailySummary:
        today = snapshot.get("today") if isinstance(snapshot.get("today"), dict) else {}
        summary_date = str(today.get("date") or collected_at.date().isoformat())
        result = await self.session.execute(
            select(DevicePresenceDailySummary)
            .where(
                DevicePresenceDailySummary.device_id == str(device_id),
                DevicePresenceDailySummary.summary_date == summary_date,
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = DevicePresenceDailySummary(
                id=str(uuid.uuid4()),
                device_id=str(device_id),
                summary_date=summary_date,
            )
            self.session.add(row)
        for field in ("active_seconds", "idle_seconds", "locked_seconds", "offline_seconds", "unknown_seconds"):
            value = today.get(field)
            if isinstance(value, (int, float)):
                setattr(row, field, max(0, int(value)))
        row.updated_at = datetime.now(timezone.utc)
        return row

    async def get_latest(self, device_id: str) -> DevicePresenceSnapshot | None:
        result = await self.session.execute(
            select(DevicePresenceSnapshot)
            .where(DevicePresenceSnapshot.device_id == str(device_id))
            .order_by(desc(DevicePresenceSnapshot.collected_at), desc(DevicePresenceSnapshot.received_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_history(self, device_id: str, *, limit: int = 20) -> list[DevicePresenceSnapshot]:
        result = await self.session.execute(
            select(DevicePresenceSnapshot)
            .where(DevicePresenceSnapshot.device_id == str(device_id))
            .order_by(desc(DevicePresenceSnapshot.collected_at), desc(DevicePresenceSnapshot.received_at))
            .limit(max(1, min(int(limit or 20), 100)))
        )
        return list(result.scalars().all())

    async def get_today_summary(self, device_id: str, *, date: str | None = None) -> DevicePresenceDailySummary | None:
        summary_date = date or datetime.now(timezone.utc).date().isoformat()
        result = await self.session.execute(
            select(DevicePresenceDailySummary)
            .where(
                DevicePresenceDailySummary.device_id == str(device_id),
                DevicePresenceDailySummary.summary_date == summary_date,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def build_device_payload(self, device_id: str) -> dict[str, Any]:
        latest = await self.get_latest(device_id)
        today = await self.get_today_summary(device_id)
        history = await self.list_history(device_id, limit=20)
        return {
            "device_id": str(device_id),
            "latest": self.snapshot_to_dict(latest) if latest else None,
            "today": self.summary_to_dict(today) if today else None,
            "history": [self.snapshot_history_item(row) for row in history],
        }

    @staticmethod
    def snapshot_to_dict(row: DevicePresenceSnapshot) -> dict[str, Any]:
        return {
            "id": row.id,
            "collected_at": row.collected_at.isoformat(),
            "received_at": row.received_at.isoformat(),
            "session_state": row.session_state,
            "current_user": row.current_user,
            "idle_seconds": row.idle_seconds,
            "locked": row.locked,
            "result": dict(row.snapshot or {}),
        }

    @staticmethod
    def snapshot_history_item(row: DevicePresenceSnapshot) -> dict[str, Any]:
        return {
            "id": row.id,
            "collected_at": row.collected_at.isoformat(),
            "session_state": row.session_state,
            "current_user": row.current_user,
            "idle_seconds": row.idle_seconds,
            "locked": row.locked,
        }

    @staticmethod
    def summary_to_dict(row: DevicePresenceDailySummary) -> dict[str, Any]:
        return {
            "date": row.summary_date,
            "active_seconds": row.active_seconds,
            "idle_seconds": row.idle_seconds,
            "locked_seconds": row.locked_seconds,
            "offline_seconds": row.offline_seconds,
            "unknown_seconds": row.unknown_seconds,
            "updated_at": row.updated_at.isoformat(),
        }
