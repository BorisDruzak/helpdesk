"""OBS1 operation/outbox lifecycle integrity checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceOutbox, Operation, TicketEvent
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput


SOURCE = "observer.operation_lifecycle"
TERMINAL_OPERATION_STATUSES = {"succeeded", "success", "failed", "denied", "timed_out", "canceled", "cancelled"}
ACTIVE_OPERATION_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
ACTIVE_OUTBOX_STATUSES = {"pending", "sent", "accepted", "running", "cancel_requested"}
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
) -> list[ObserverIntegrityEventInput]:
    now = _now()
    events: list[ObserverIntegrityEventInput] = []
    events.extend(await _terminal_operation_with_active_outbox(session, now=now, stale_after=stale_after, run_id=run_id))
    events.extend(await _active_operation_stuck(session, now=now, active_after=active_after, run_id=run_id))
    events.extend(await _terminal_tool_operation_missing_result_event(session, run_id=run_id))
    return events


async def _terminal_operation_with_active_outbox(
    session: AsyncSession,
    *,
    now: datetime,
    stale_after: timedelta,
    run_id: str | None,
) -> list[ObserverIntegrityEventInput]:
    cutoff = now - stale_after
    result = await session.execute(
        select(Operation, DeviceOutbox)
        .join(DeviceOutbox, DeviceOutbox.operation_id == Operation.operation_id)
        .where(
            Operation.status.in_(TERMINAL_OPERATION_STATUSES),
            DeviceOutbox.status.in_(ACTIVE_OUTBOX_STATUSES),
            DeviceOutbox.created_at <= cutoff,
        )
        .order_by(DeviceOutbox.created_at.asc())
        .limit(200)
    )
    events: list[ObserverIntegrityEventInput] = []
    for operation, outbox in result.all():
        operation_status = str(operation.status or "").lower()
        severity = "critical" if operation_status in {"succeeded", "success", "canceled", "cancelled"} else "error"
        age = _age_seconds(now, outbox.created_at)
        events.append(
            ObserverIntegrityEventInput(
                event_type="operation_outbox_mismatch",
                severity=severity,
                source=SOURCE,
                dedupe_key=f"operation_outbox_mismatch:{operation.operation_id}:{outbox.id}",
                device_id=operation.device_id,
                ticket_id=operation.ticket_id,
                operation_id=operation.operation_id,
                command_id=outbox.command_id,
                device_outbox_id=int(outbox.id),
                trace_id=operation.trace_id or outbox.trace_id,
                actor_role=operation.actor_role or outbox.actor_role,
                expected="Terminal operation must not have a related active device_outbox command beyond grace period.",
                actual=f"operation.status={operation.status}; device_outbox.status={outbox.status}; age_seconds={age}",
                evidence={
                    "operation_status": operation.status,
                    "outbox_status": outbox.status,
                    "outbox_command": outbox.command,
                    "operation_kind": operation.kind,
                    "tool_name": operation.tool_name,
                    "outbox_created_at": outbox.created_at.isoformat() if outbox.created_at else None,
                    "outbox_sent_at": outbox.sent_at.isoformat() if outbox.sent_at else None,
                    "operation_finished_at": (
                        operation.finished_at.isoformat()
                        if operation.finished_at
                        else (operation.canceled_at.isoformat() if operation.canceled_at else None)
                    ),
                    "age_seconds": age,
                },
                runbook="docs/runbooks/observer_operation_lifecycle.md",
                run_id=run_id,
            )
        )
    return events


async def _active_operation_stuck(
    session: AsyncSession,
    *,
    now: datetime,
    active_after: timedelta,
    run_id: str | None,
) -> list[ObserverIntegrityEventInput]:
    cutoff = now - active_after
    result = await session.execute(
        select(Operation)
        .where(Operation.status.in_(ACTIVE_OPERATION_STATUSES), Operation.queued_at <= cutoff)
        .order_by(Operation.queued_at.asc())
        .limit(200)
    )
    events: list[ObserverIntegrityEventInput] = []
    for operation in result.scalars().all():
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
    return events


async def _terminal_tool_operation_missing_result_event(
    session: AsyncSession,
    *,
    run_id: str | None,
) -> list[ObserverIntegrityEventInput]:
    result = await session.execute(
        select(Operation)
        .where(
            Operation.kind == "tool_call",
            Operation.status.in_(TERMINAL_OPERATION_STATUSES),
            Operation.ticket_id.is_not(None),
        )
        .order_by(Operation.finished_at.desc().nullslast(), Operation.queued_at.desc())
        .limit(200)
    )
    events: list[ObserverIntegrityEventInput] = []
    for operation in result.scalars().all():
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
    return events
