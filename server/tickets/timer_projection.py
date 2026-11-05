"""Shared read-only SLA/OLA timers; canonical pause, completion and breach rules."""
from datetime import datetime, timedelta, timezone

def _aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _ticket_timer_status(
    due_at: datetime | None,
    *,
    breached_at: datetime | None = None,
    paused_at: datetime | None = None,
    paused_seconds: int | None = None,
    now: datetime | None = None,
) -> str:
    due_at = _aware_datetime(due_at)
    breached_at = _aware_datetime(breached_at)
    paused_at = _aware_datetime(paused_at)
    now = _aware_datetime(now) or datetime.now(timezone.utc)
    if due_at is None:
        return "unknown"
    if breached_at is not None:
        return "breached"
    if paused_at is not None:
        return "paused"
    effective_due_at = due_at + timedelta(seconds=max(0, int(paused_seconds or 0)))
    remaining_seconds = int((effective_due_at - now).total_seconds())
    if remaining_seconds < 0:
        return "breached"
    if remaining_seconds <= 30 * 60:
        return "at_risk"
    return "ok"


def project_ticket_timer(
    ticket,
    *,
    due_attr: str,
    breached_attr: str | None = None,
    paused_attr: str | None = None,
    paused_seconds_attr: str | None = None,
    completed_attr: str | None = None,
    anchor_attr: str = "created_at",
    now: datetime | None = None,
) -> dict:
    due_at = _aware_datetime(getattr(ticket, due_attr, None))
    now = _aware_datetime(now) or datetime.now(timezone.utc)
    paused_seconds = int(getattr(ticket, paused_seconds_attr, None) or 0) if paused_seconds_attr else 0
    effective_due_at = due_at + timedelta(seconds=max(0, paused_seconds)) if due_at is not None else None
    anchor_at = _aware_datetime(getattr(ticket, anchor_attr, None) or getattr(ticket, "created_at", None))
    target_seconds = None
    if anchor_at is not None and due_at is not None:
        target_seconds = max(0, int((due_at - anchor_at).total_seconds()))
    completed_at = _aware_datetime(getattr(ticket, completed_attr, None)) if completed_attr else None
    if completed_at is not None:
        return dict(
            due_at=None,
            remaining_seconds=None,
            target_seconds=target_seconds,
            status="completed",
            completed_at=completed_at.isoformat(),
            completed_within_target=False if breached_attr and getattr(ticket, breached_attr, None) is not None
            else completed_at <= effective_due_at if effective_due_at else None,
        )
    paused_at = _aware_datetime(getattr(ticket, paused_attr, None)) if paused_attr else None
    countdown_at = paused_at or now
    return dict(
        due_at=due_at.isoformat() if due_at is not None else None,
        remaining_seconds=int((effective_due_at - countdown_at).total_seconds()) if effective_due_at is not None else None,
        target_seconds=target_seconds,
        status=_ticket_timer_status(
            due_at,
            breached_at=getattr(ticket, breached_attr, None) if breached_attr else None,
            paused_at=getattr(ticket, paused_attr, None) if paused_attr else None,
            paused_seconds=paused_seconds,
            now=now,
        ),
    )
