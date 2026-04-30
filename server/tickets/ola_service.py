"""
Stage 11: OLA (Operational Level Agreement) — queue-level ack/processing таймеры.

Старт OLA: при создании тикета и при смене очереди.
ack: закрывается при назначении assignee_id.
processing: закрывается при смене очереди (handoff) или при переходе в Resolved/Closed.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket, TicketQueueOlaTarget
from config import TICKET_OLA_ENABLED
from tickets.statuses import extract_priority_class


def _get_request_template(custom_fields: object) -> dict:
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    return request_template if isinstance(request_template, dict) else {}


def _duration_to_minutes(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw.isdigit():
            return int(raw)
        multiplier = 1
        if raw.endswith("m"):
            raw = raw[:-1]
        elif raw.endswith("h"):
            raw = raw[:-1]
            multiplier = 60
        elif raw.endswith("d"):
            raw = raw[:-1]
            multiplier = 60 * 24
        try:
            return int(float(raw) * multiplier)
        except ValueError:
            return None
    return None


def _target_from_policy_map(target_map: object, priority: str) -> int | None:
    if not isinstance(target_map, dict):
        return None
    candidates = [priority]
    if priority != "P3":
        candidates.append("P3")
    for key in candidates:
        value = target_map.get(key)
        minutes = _duration_to_minutes(value)
        if minutes is not None:
            return minutes
    return None


def _get_template_ola_targets(ticket: Ticket, priority: str) -> Optional[tuple[int, int]]:
    request_template = _get_request_template(getattr(ticket, "custom_fields", None))
    policy = request_template.get("ola_policy") or {}
    if not isinstance(policy, dict):
        return None
    targets = policy.get("targets") if isinstance(policy.get("targets"), dict) else policy
    if not isinstance(targets, dict):
        return None
    ack_min = _target_from_policy_map(targets.get("ack"), priority)
    processing_min = _target_from_policy_map(targets.get("processing"), priority)
    if ack_min is None or processing_min is None:
        return None
    return ack_min, processing_min


async def get_ola_targets_for_queue(
    session: AsyncSession,
    queue_id: int,
    priority: str,
) -> Optional[tuple[int, int]]:
    """(ack_min, processing_min) для очереди и приоритета или None."""
    if not TICKET_OLA_ENABLED:
        return None
    result = await session.execute(
        select(TicketQueueOlaTarget).where(
            TicketQueueOlaTarget.queue_id == queue_id,
            TicketQueueOlaTarget.priority == priority,
        )
    )
    row = result.scalar_one_or_none()
    if row is None and priority != "P3":
        fallback_result = await session.execute(
            select(TicketQueueOlaTarget).where(
                TicketQueueOlaTarget.queue_id == queue_id,
                TicketQueueOlaTarget.priority == "P3",
            )
        )
        row = fallback_result.scalar_one_or_none()
    if not row:
        return None
    return row.ack_min, row.processing_min


async def start_ola_for_ticket(
    session: AsyncSession,
    ticket: Ticket,
    started_at: Optional[datetime] = None,
) -> None:
    """
    Установить OLA для тикета: ola_queue_id, ola_started_at, ola_ack_due_at, ola_processing_due_at.
    Вызывать при создании тикета или смене очереди (если OLA включён).
    """
    if not TICKET_OLA_ENABLED or not ticket.queue_id:
        return
    now = started_at or datetime.now(timezone.utc)
    priority = extract_priority_class(ticket) or "P3"
    targets = _get_template_ola_targets(ticket, priority)
    if not targets:
        targets = await get_ola_targets_for_queue(
            session,
            ticket.queue_id,
            priority,
        )
    if not targets:
        return
    ack_min, processing_min = targets
    ack_due = now + timedelta(minutes=ack_min)
    processing_due = now + timedelta(minutes=processing_min)
    await session.execute(
        update(Ticket).where(Ticket.ticket_id == ticket.ticket_id).values(
            ola_queue_id=ticket.queue_id,
            ola_started_at=now,
            ola_ack_due_at=ack_due,
            ola_processing_due_at=processing_due,
            ola_ack_at=None,
            ola_ack_breached_at=None,
            ola_processing_at=None,
            ola_processing_breached_at=None,
            ola_paused_at=None,
            ola_paused_seconds=None,
        )
    )


async def close_ola_ack(session: AsyncSession, ticket_id: str, at: Optional[datetime] = None) -> None:
    """Закрыть ack (назначение assignee). Записывает ola_ack_at."""
    if not TICKET_OLA_ENABLED:
        return
    now = at or datetime.now(timezone.utc)
    await session.execute(
        update(Ticket).where(Ticket.ticket_id == ticket_id).values(ola_ack_at=now)
    )


async def close_ola_processing(
    session: AsyncSession,
    ticket_id: str,
    at: Optional[datetime] = None,
) -> None:
    """Закрыть processing (handoff или Resolved/Closed). Записывает ola_processing_at."""
    if not TICKET_OLA_ENABLED:
        return
    now = at or datetime.now(timezone.utc)
    await session.execute(
        update(Ticket).where(Ticket.ticket_id == ticket_id).values(ola_processing_at=now)
    )


def build_ola_block(ticket: Ticket) -> Optional[dict]:
    """Собрать OLA-блок для ответа GET /api/tickets/{id}/sla."""
    if not TICKET_OLA_ENABLED or ticket.ola_queue_id is None:
        return None
    return {
        "ola_queue_id": ticket.ola_queue_id,
        "ola_started_at": ticket.ola_started_at.isoformat() if ticket.ola_started_at else None,
        "ola_ack_due_at": ticket.ola_ack_due_at.isoformat() if ticket.ola_ack_due_at else None,
        "ola_ack_at": ticket.ola_ack_at.isoformat() if ticket.ola_ack_at else None,
        "ola_ack_breached_at": ticket.ola_ack_breached_at.isoformat() if ticket.ola_ack_breached_at else None,
        "ola_processing_due_at": ticket.ola_processing_due_at.isoformat() if ticket.ola_processing_due_at else None,
        "ola_processing_at": ticket.ola_processing_at.isoformat() if ticket.ola_processing_at else None,
        "ola_processing_breached_at": ticket.ola_processing_breached_at.isoformat() if ticket.ola_processing_breached_at else None,
        "ola_paused_at": ticket.ola_paused_at.isoformat() if ticket.ola_paused_at else None,
        "ola_paused_seconds": ticket.ola_paused_seconds,
    }
