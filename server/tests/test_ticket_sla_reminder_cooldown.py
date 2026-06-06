from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import and_, func, select

from app.db.engine import get_session
from app.db.models import Ticket, TicketEvent
from app.services.ticket_sla_watchdog import TicketSlaWatchdog


async def _seed_breached_ticket(*, ticket_id: str, device_id: str, now: datetime) -> None:
    async with get_session() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code=f"T-{ticket_id[-6:].upper()}",
                device_id=device_id,
                title="SLA reminder cooldown test",
                description="seeded by regression test",
                status="in_progress",
                priority="P3",
                requester_id="requester-sla-cooldown",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(hours=2),
                first_response_due_at=now - timedelta(days=1),
                resolution_due_at=now - timedelta(hours=2),
                resolution_breached_at=now - timedelta(hours=2),
            )
        )
        await session.commit()


async def _count_reminders(ticket_id: str) -> int:
    async with get_session() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(TicketEvent).where(
                    and_(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "sla_reminder_sent")
                )
            )
            or 0
        )


@pytest.mark.asyncio
async def test_sla_reminder_startup_grace_skips_first_cycle_for_overdue_ticket(test_engine) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ticket_id = str(uuid.uuid4())
    await _seed_breached_ticket(ticket_id=ticket_id, device_id=str(uuid.uuid4()), now=now)

    watchdog = TicketSlaWatchdog(interval=999, startup_grace_seconds=3600)
    await watchdog._check_reminders()

    assert await _count_reminders(ticket_id) == 0


@pytest.mark.asyncio
async def test_sla_reminder_uses_existing_event_as_cooldown_source_without_custom_field(test_engine) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    await _seed_breached_ticket(ticket_id=ticket_id, device_id=device_id, now=now)

    async with get_session() as session:
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="sla_reminder_sent",
                payload={"ticket_id": ticket_id, "ts": (now - timedelta(minutes=30)).isoformat()},
                trace_id=str(uuid.uuid4()),
                created_at=now - timedelta(minutes=30),
            )
        )
        await session.commit()

    watchdog = TicketSlaWatchdog(interval=999, startup_grace_seconds=0)
    await watchdog._check_reminders()

    assert await _count_reminders(ticket_id) == 1
