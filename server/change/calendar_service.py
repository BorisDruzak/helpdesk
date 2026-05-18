from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select

from app.db.models import Change, ChangeWindow
from change.contracts import clean_text
from change.serializers import change_to_dict, window_to_dict


ACTIVE_PLANNED_STATUSES = {"approved", "scheduled", "implementation_in_progress"}
WEEKDAY_CODES = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


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
        if end <= start:
            raise ValueError("planned_end_at must be after planned_start_at")
        blackout = await self._blackout_conflict(change, start, end)
        if blackout and not blackout_override:
            raise ValueError("blackout window blocks scheduling")
        if blackout_override and not clean_text(override_justification):
            raise ValueError("blackout override justification is required")
        overlap = await self._change_overlap(change, start, end)
        if overlap is not None:
            raise ValueError(f"overlap with scheduled change {overlap.change_key}")
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
            or_(ChangeWindow.service_code.is_(None), ChangeWindow.service_code == change.service_code),
            or_(ChangeWindow.offering_code.is_(None), ChangeWindow.offering_code == change.offering_code),
        ).limit(500)
        rows = (await self.session.execute(stmt)).scalars().all()
        return any(_window_overlaps(row, start, end) for row in rows)

    async def _change_overlap(self, change: Change, start: datetime, end: datetime) -> Change | None:
        stmt = select(Change).where(
            Change.change_id != change.change_id,
            Change.planned_start_at.is_not(None),
            Change.planned_end_at.is_not(None),
            Change.planned_start_at < end,
            Change.planned_end_at > start,
            Change.status.in_(ACTIVE_PLANNED_STATUSES),
            or_(Change.service_code == change.service_code, Change.offering_code == change.offering_code),
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        for row in rows:
            if _same_change_scope(change, row):
                return row
        return None


def _same_change_scope(left: Change, right: Change) -> bool:
    if left.offering_code and right.offering_code:
        return left.offering_code == right.offering_code
    if left.service_code and right.service_code:
        return left.service_code == right.service_code
    return not left.service_code and not right.service_code and not left.offering_code and not right.offering_code


def _window_overlaps(row: ChangeWindow, start: datetime, end: datetime) -> bool:
    recurrence = clean_text(row.recurrence_rule)
    if not recurrence:
        return row.starts_at < end and row.ends_at > start
    return any(_ranges_overlap(occurrence_start, occurrence_end, start, end) for occurrence_start, occurrence_end in _iter_occurrences(row, start, end))


def _ranges_overlap(left_start: datetime, left_end: datetime, right_start: datetime, right_end: datetime) -> bool:
    return left_start < right_end and left_end > right_start


def _iter_occurrences(row: ChangeWindow, start: datetime, end: datetime):
    rule = _parse_rrule(row.recurrence_rule)
    freq = rule.get("FREQ")
    if freq not in {"DAILY", "WEEKLY"}:
        if row.starts_at < end and row.ends_at > start:
            yield row.starts_at, row.ends_at
        return
    duration = row.ends_at - row.starts_at
    interval = max(1, int(rule.get("INTERVAL", "1")))
    count = int(rule["COUNT"]) if str(rule.get("COUNT") or "").isdigit() else None
    until = _parse_rrule_until(rule.get("UNTIL"))
    bydays = {WEEKDAY_CODES[item] for item in str(rule.get("BYDAY") or "").split(",") if item in WEEKDAY_CODES}
    base = row.starts_at
    cursor_date = base.date()
    stop = min(end + duration + timedelta(days=1), until + timedelta(days=1) if until else end + duration + timedelta(days=1))
    emitted = 0
    while cursor_date <= stop.date():
        candidate = datetime.combine(cursor_date, time(base.hour, base.minute, base.second, base.microsecond), tzinfo=base.tzinfo)
        if candidate >= base and _candidate_matches(candidate, base, freq, interval, bydays):
            emitted += 1
            if count is not None and emitted > count:
                break
            candidate_end = candidate + duration
            if candidate_end > start and candidate < end:
                yield candidate, candidate_end
        cursor_date += timedelta(days=1)


def _candidate_matches(candidate: datetime, base: datetime, freq: str, interval: int, bydays: set[int]) -> bool:
    days = (candidate.date() - base.date()).days
    if days < 0:
        return False
    if freq == "DAILY":
        return days % interval == 0
    weeks = days // 7
    expected_weekday = candidate.weekday() in bydays if bydays else candidate.weekday() == base.weekday()
    return expected_weekday and weeks % interval == 0


def _parse_rrule(value: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in str(value or "").split(";"):
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        result[key.strip().upper()] = raw.strip().upper()
    return result


def _parse_rrule_until(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.replace("Z", "+00:00")
    if len(raw) == 8 and raw.isdigit():
        return datetime.fromisoformat(f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}").replace(tzinfo=timezone.utc)
    return _parse_dt(raw)

