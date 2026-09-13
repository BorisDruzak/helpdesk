"""OBS1 ticket-operation lifecycle integrity checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Operation, TicketEvent
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput
from observer.checks.types import ObserverIntegrityCheckResult, limit_plus_one_window


SOURCE = "observer.operation_lifecycle"
QUERY_LIMIT = 200
TERMINAL_OPERATION_STATUSES = {"succeeded", "success", "failed", "denied", "timed_out", "canceled", "cancelled"}
ACTIVE_OPERATION_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
RESULT_EVENT_TYPES = {"tool_call_result"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age_seconds(now: datetime, value: datetime | None) -> int | None:
    value = _as_utc(value)
    if value is None:
        return None
    return max(0, int((now - value).total_seconds()))


async def check_operation_lifecycle(
    session: AsyncSession,
    *,
    run_id: str | None = None,
    stale_after: timedelta = timedelta(minutes=10),
    active_after: timedelta = timedelta(minutes=30),
) -> ObserverIntegrityCheckResult:
    now = _now()
    events: list[ObserverIntegrityEventInput] = []
    stuck_active, stuck_active_complete, stuck_active_scanned = await _active_operation_stuck(
        session,
        now=now,
        active_after=active_after,
        run_id=run_id,
    )
    missing_result, missing_result_complete, missing_result_scanned = await _terminal_tool_operation_missing_result_event(
        session,
        run_id=run_id,
    )
    events.extend(stuck_active)
    events.extend(missing_result)
    return ObserverIntegrityCheckResult(
        source=SOURCE,
        events=events,
        complete=stuck_active_complete and missing_result_complete,
        scanned_count=stuck_active_scanned + missing_result_scanned,
        limit=QUERY_LIMIT,
    )


async def _active_operation_stuck(
    session: AsyncSession,
    *,
    now: datetime,
    active_after: timedelta,
    run_id: str | None,
) -> tuple[list[ObserverIntegrityEventInput], bool, int]:
    cutoff = now - active_after
    result = await session.execute(
        select(Operation)
        .where(Operation.status.in_(ACTIVE_OPERATION_STATUSES), Operation.queued_at <= cutoff)
        .order_by(Operation.queued_at.asc())
        .limit(QUERY_LIMIT + 1)
    )
    rows = result.scalars().all()
    window, complete = limit_plus_one_window(rows, limit=QUERY_LIMIT)
    events: list[ObserverIntegrityEventInput] = []
    for operation in window:
        age = _age_seconds(now, operation.queued_at)
        severity = "error" if age is not None and age > int(active_after.total_seconds() * 2) else "warning"
        events.append(
            ObserverIntegrityEventInput(
                event_type="operation_stuck_active",
                severity=severity,
                source=SOURCE,
                dedupe_key=f"operation_stuck_active:{operation.operation_id}",
                device_id=operation.device_id,
                ticket_id=operation.ticket_id,
                operation_id=operation.operation_id,
                trace_id=operation.trace_id,
                actor_role=operation.actor_role,
                expected="Active operations should progress or reach a terminal state within the configured threshold.",
                actual=f"operation.status={operation.status}; queued_age_seconds={age}",
                evidence={
                    "operation_status": operation.status,
                    "operation_kind": operation.kind,
                    "tool_name": operation.tool_name,
                    "queued_at": operation.queued_at.isoformat() if operation.queued_at else None,
                    "deadline_at": operation.deadline_at.isoformat() if operation.deadline_at else None,
                    "age_seconds": age,
                },
                runbook="docs/runbooks/observer_operation_lifecycle.md",
                run_id=run_id,
            )
        )
    return events, complete, len(rows)


async def _terminal_tool_operation_missing_result_event(
    session: AsyncSession,
    *,
    run_id: str | None,
) -> tuple[list[ObserverIntegrityEventInput], bool, int]:
    result = await session.execute(
        select(Operation)
        .where(
            Operation.kind == "tool_call",
            Operation.status.in_(TERMINAL_OPERATION_STATUSES),
            Operation.ticket_id.is_not(None),
        )
        .order_by(Operation.finished_at.desc().nullslast(), Operation.queued_at.desc())
        .limit(QUERY_LIMIT + 1)
    )
    rows = result.scalars().all()
    window, complete = limit_plus_one_window(rows, limit=QUERY_LIMIT)
    events: list[ObserverIntegrityEventInput] = []
    for operation in window:
        count = int(
            await session.scalar(
                select(func.count())
                .select_from(TicketEvent)
                .where(
                    TicketEvent.operation_id == operation.operation_id,
                    TicketEvent.event_type.in_(RESULT_EVENT_TYPES),
                )
            )
            or 0
        )
        if count > 0 or operation.result_event_id is not None:
            continue
        events.append(
            ObserverIntegrityEventInput(
                event_type="operation_missing_terminal_event",
                severity="error",
                source=SOURCE,
                dedupe_key=f"operation_missing_terminal_event:{operation.operation_id}",
                device_id=operation.device_id,
                ticket_id=operation.ticket_id,
                operation_id=operation.operation_id,
                trace_id=operation.trace_id,
                actor_role=operation.actor_role,
                expected="Terminal ticket-bound tool operations must have a terminal tool_call_result ticket event.",
                actual=f"operation.status={operation.status}; result_event_id is null; tool_call_result_count=0",
                evidence={
                    "operation_status": operation.status,
                    "operation_kind": operation.kind,
                    "tool_name": operation.tool_name,
                    "finished_at": operation.finished_at.isoformat() if operation.finished_at else None,
                },
                runbook="docs/runbooks/observer_operation_lifecycle.md",
                run_id=run_id,
            )
        )
    return events, complete, len(rows)
