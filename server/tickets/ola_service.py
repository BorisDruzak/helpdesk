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
    targets = await get_ola_targets_for_queue(
        session,
        ticket.queue_id,
        extract_priority_class(ticket) or "P3",
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
