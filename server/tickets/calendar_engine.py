"""
Stage 11: Движок бизнес-календаря для SLA (рабочие часы, праздники).

Формат weekly_hours_json: список {"day": 0-6 (0=Пн, 6=Вс), "start": "HH:MM", "end": "HH:MM"} в timezone календаря.
Формат holidays_json: список дат "YYYY-MM-DD" (нерабочие дни).
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
import zoneinfo


def _parse_time(s: str) -> tuple[int, int]:
    """'HH:MM' -> (hours, minutes)."""
    parts = (s or "00:00").strip().split(":")
    h = int(parts[0]) if len(parts) > 0 else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    return h, m


def _get_calendar_tz(calendar: Optional[dict]) -> zoneinfo.ZoneInfo:
    tz_name = (calendar or {}).get("timezone") or "UTC"
    try:
        return zoneinfo.ZoneInfo(tz_name)
    except Exception:
        return timezone.utc


def _is_holiday(dt: datetime, calendar: Optional[dict]) -> bool:
    holidays = (calendar or {}).get("holidays_json") or []
    if not holidays:
        return False
    date_str = dt.strftime("%Y-%m-%d")
    return date_str in holidays


def _weekday_in_calendar(dt: datetime, calendar: Optional[dict]) -> int:
    """День недели в календаре: 0=Пн, 6=Вс (Python weekday: 0=Пн)."""
    return dt.weekday()


def _minutes_since_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def _is_inside_work_interval(dt: datetime, calendar: Optional[dict]) -> bool:
    if not calendar:
        return True
    weekly = (calendar.get("weekly_hours_json") or [])
    if not weekly:
        return False
    day = _weekday_in_calendar(dt, calendar)
    mins = _minutes_since_midnight(dt)
    for slot in weekly:
        if slot.get("day") != day:
            continue
        sh, sm = _parse_time(slot.get("start") or "00:00")
        eh, em = _parse_time(slot.get("end") or "23:59")
        start_m = sh * 60 + sm
        end_m = eh * 60 + em
        if start_m <= mins < end_m:
            return True
    return False


def _next_work_start_after(dt: datetime, calendar: Optional[dict], tz: zoneinfo.ZoneInfo) -> Optional[datetime]:
    """Следующий момент начала рабочего интервала после dt (в tz)."""
    weekly = (calendar or {}).get("weekly_hours_json") or []
    if not weekly:
        return None
    local = dt.astimezone(tz)
    day = local.weekday()
    mins = _minutes_since_midnight(local)
    same_day = [s for s in weekly if s.get("day") == day]
    for slot in same_day:
        sh, sm = _parse_time(slot.get("start") or "00:00")
        start_m = sh * 60 + sm
        if mins < start_m:
            return local.replace(hour=sh, minute=sm, second=0, microsecond=0)
    for ahead in range(1, 8):
        next_day = (day + ahead) % 7
        cand = local + timedelta(days=ahead)
        cand = cand.replace(hour=0, minute=0, second=0, microsecond=0)
        if _is_holiday(cand, calendar):
            continue
        for slot in weekly:
            if slot.get("day") != next_day:
                continue
            sh, sm = _parse_time(slot.get("start") or "00:00")
            return cand.replace(hour=sh, minute=sm, second=0, microsecond=0)
    return None


def _next_work_end_after(dt: datetime, calendar: Optional[dict], tz: zoneinfo.ZoneInfo) -> Optional[datetime]:
    """Следующий конец рабочего интервала после dt (в tz)."""
    weekly = (calendar or {}).get("weekly_hours_json") or []
    if not weekly:
        return None
    local = dt.astimezone(tz)
    day = local.weekday()
    mins = _minutes_since_midnight(local)
    for slot in weekly:
        if slot.get("day") != day:
            continue
        eh, em = _parse_time(slot.get("end") or "23:59")
        end_m = eh * 60 + em
        if mins < end_m:
            return local.replace(hour=eh, minute=em, second=0, microsecond=0)
    for ahead in range(1, 8):
        next_day = (day + ahead) % 7
        cand = local + timedelta(days=ahead)
        cand = cand.replace(hour=0, minute=0, second=0, microsecond=0)
        if _is_holiday(cand, calendar):
            continue
        for slot in weekly:
            if slot.get("day") != next_day:
                continue
            eh, em = _parse_time(slot.get("end") or "23:59")
            return cand.replace(hour=eh, minute=em, second=0, microsecond=0)
    return None


def add_business_minutes(
    start_utc: datetime,
    minutes: int,
    calendar: Optional[dict],
) -> datetime:
    """
    Добавить minutes рабочих минут к start_utc по календарю.
    Если calendar None или пустой — считаем 24x7 (просто start_utc + minutes).
    """
    if not calendar or not (calendar.get("weekly_hours_json")):
        return start_utc + timedelta(minutes=minutes)
    tz = _get_calendar_tz(calendar)
    local = start_utc.astimezone(tz)
    remaining_seconds = minutes * 60
    cur = local
    while remaining_seconds > 0:
        if _is_holiday(cur, calendar):
            nstart = _next_work_start_after(cur, calendar, tz)
            if nstart is None:
                break
            cur = nstart
            continue
        if not _is_inside_work_interval(cur, calendar):
            nstart = _next_work_start_after(cur, calendar, tz)
            if nstart is None:
                cur = cur + timedelta(seconds=remaining_seconds)
                break
            cur = nstart
            continue
        nend = _next_work_end_after(cur, calendar, tz)
        if nend is None:
            cur = cur + timedelta(seconds=remaining_seconds)
            break
        if cur >= nend:
            nstart = _next_work_start_after(cur, calendar, tz)
            if nstart is None:
                cur = cur + timedelta(seconds=remaining_seconds)
                break
            cur = nstart
            continue
        available_seconds = int((nend - cur).total_seconds())
        if available_seconds <= 0:
            cur = nend
            continue
        segment_seconds = min(remaining_seconds, available_seconds)
        cur = cur + timedelta(seconds=segment_seconds)
        remaining_seconds -= segment_seconds
    return cur.astimezone(timezone.utc)


def business_seconds_between(
    start_utc: datetime,
    end_utc: datetime,
    calendar: Optional[dict],
) -> int:
    """
    Количество рабочих секунд между start_utc и end_utc по календарю.
    Если calendar None или пустой — 24x7: (end - start).total_seconds().
    """
    if not calendar or not (calendar.get("weekly_hours_json")):
        delta = end_utc - start_utc
        return max(0, int(delta.total_seconds()))
    tz = _get_calendar_tz(calendar)
    total = 0
    cur = start_utc.astimezone(tz)
    end_local = end_utc.astimezone(tz)
    while cur < end_local:
        if _is_holiday(cur, calendar):
            nstart = _next_work_start_after(cur, calendar, tz)
            if nstart is None or nstart >= end_local:
                break
            cur = nstart
            continue
        nend = _next_work_end_after(cur, calendar, tz)
        if nend is None:
            total += int((end_local - cur).total_seconds())
            break
        if cur >= nend:
            nstart = _next_work_start_after(cur, calendar, tz)
            if nstart is None or nstart >= end_local:
                break
            cur = nstart
            continue
        segment_end = min(nend, end_local)
        if segment_end > cur:
            total += int((segment_end - cur).total_seconds())
        cur = segment_end
    return max(0, total)
