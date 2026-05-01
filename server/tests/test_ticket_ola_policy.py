from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent, TicketQueue
from tickets import ola_service


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
        if tz is None:
            return value.replace(tzinfo=None)
        return value.astimezone(tz)


async def _queue(session, code: str = "networks") -> TicketQueue:
    queue = TicketQueue(code=code, name=code.title(), is_triage=False, auto_assign_enabled=False)
    session.add(queue)
    await session.flush()
    return queue


def _policy(**overrides):
    result = {
        "code": "default_queue_ola",
        "version": "1.2.0",
        "source": "request_template",
        "targets": {
            "ack": {"P1": "10m", "P3": "1h"},
            "processing": {"P1": "2h", "P3": "1d"},
        },
        "breach_actions": {
            "notify_queue_lead": True,
            "create_internal_event": True,
        },
    }
    result.update(overrides)
    return result


def _ticket(ticket_id: str, queue_id: int, *, status: str = "queued", ola_policy: dict | None = None) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        device_id=f"device-{ticket_id[:8]}",
        title="OLA policy",
        description="Policy-aware OLA behavior",
        status=status,
        requester_id="requester-ola",
        ticket_type="incident",
        priority="P3",
        queue_id=queue_id,
        custom_fields={
            "priority_class": "P1",
            "request_template": {
                "key": "website_unavailable",
                "policy_refs": {"ola": {"code": "__test_inline_ola_policy__"}},
                "ola_policy": ola_policy or _policy(),
            },
        },
    )


@pytest.mark.asyncio
async def test_start_ola_uses_policy_conditions_and_logs_source(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    monkeypatch.setattr(ola_service, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        queue = await _queue(session)
        ticket = _ticket(
            ticket_id,
            queue.id,
            ola_policy=_policy(start_conditions=["queue_changed"]),
        )
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert await ola_service.start_ola_for_ticket(session, ticket, trigger="ticket_created") is False
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.ola_started_at is None
        assert await ola_service.start_ola_for_ticket(session, ticket, trigger="queue_changed") is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "ola_started")
                .order_by(TicketEvent.id)
            )
        ).scalars().all()

    assert ticket.ola_started_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert ticket.ola_ack_due_at == datetime(2026, 5, 4, 16, 40, tzinfo=timezone.utc)
    assert ticket.ola_processing_due_at == datetime(2026, 5, 4, 18, 30, tzinfo=timezone.utc)
    assert ticket.custom_fields["ola_runtime"]["policy"] == {
        "code": "default_queue_ola",
        "version": "1.2.0",
        "source": "request_template",
    }
    assert ticket.custom_fields["ola_runtime"]["start_reason"] == "queue_changed"
    assert len(events) == 1
    assert events[0].payload["ola_policy"]["code"] == "default_queue_ola"
    assert events[0].payload["targets"] == {"ack_min": 10, "processing_min": 120}


@pytest.mark.asyncio
async def test_ola_stop_conditions_control_ack_and_processing_events(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    monkeypatch.setattr(ola_service, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        queue = await _queue(session)
        ticket = _ticket(
            ticket_id,
            queue.id,
            status="in_progress",
            ola_policy=_policy(
                stop_conditions={
                    "ack": ["assignee_set"],
                    "processing": [{"status_in": ["resolved", "closed"]}],
                }
            ),
        )
        ticket.ola_queue_id = queue.id
        ticket.ola_started_at = datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc)
        ticket.ola_ack_due_at = datetime(2026, 5, 4, 16, 10, tzinfo=timezone.utc)
        ticket.ola_processing_due_at = datetime(2026, 5, 4, 18, 0, tzinfo=timezone.utc)
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        assert await ola_service.close_ola_ack(session, ticket_id, trigger="status_changed") is False
        assert await ola_service.close_ola_ack(session, ticket_id, trigger="assignee_set") is True
        assert await ola_service.close_ola_processing(session, ticket_id, status="waiting_on_user") is False
        assert await ola_service.close_ola_processing(session, ticket_id, status="resolved") is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event_types = [
            row[0]
            for row in (
                await session.execute(
                    select(TicketEvent.event_type)
                    .where(TicketEvent.ticket_id == ticket_id)
                    .where(TicketEvent.event_type.in_(["ola_ack_stopped", "ola_processing_stopped"]))
                    .order_by(TicketEvent.id)
                )
            ).all()
        ]

    assert ticket.ola_ack_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert ticket.ola_processing_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert event_types == ["ola_ack_stopped", "ola_processing_stopped"]


@pytest.mark.asyncio
async def test_ola_pause_resume_uses_policy_conditions(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    monkeypatch.setattr(ola_service, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        queue = await _queue(session)
        ticket = _ticket(
            ticket_id,
            queue.id,
            status="waiting_on_user",
            ola_policy=_policy(
                pause_conditions=[{"status": "waiting_on_vendor"}],
                resume_conditions=["vendor_replied"],
            ),
        )
        ticket.ola_queue_id = queue.id
        ticket.ola_started_at = datetime(2026, 5, 4, 15, 0, tzinfo=timezone.utc)
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        assert await ola_service.pause_ola(session, ticket_id, trigger="status_changed") is False
        ticket = await session.get(Ticket, ticket_id)
        ticket.status = "waiting_on_vendor"
        await session.commit()

    async with session_maker() as session:
        assert await ola_service.pause_ola(session, ticket_id, trigger="status_changed") is True
        ticket = await session.get(Ticket, ticket_id)
        ticket.status = "in_progress"
        ticket.ola_paused_at = datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc)
        await session.commit()

    async with session_maker() as session:
        assert await ola_service.resume_ola(session, ticket_id, trigger="requester_replied") is False
        assert await ola_service.resume_ola(session, ticket_id, trigger="vendor_replied") is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event_types = [
            row[0]
            for row in (
                await session.execute(
                    select(TicketEvent.event_type)
                    .where(TicketEvent.ticket_id == ticket_id)
                    .where(TicketEvent.event_type.in_(["ola_paused", "ola_resumed"]))
                    .order_by(TicketEvent.id)
                )
            ).all()
        ]

    assert ticket.ola_paused_at is None
    assert ticket.ola_paused_seconds == 1800
    assert event_types == ["ola_paused", "ola_resumed"]


@pytest.mark.asyncio
async def test_ola_breach_check_emits_policy_aware_event(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    monkeypatch.setattr(ola_service, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        queue = await _queue(session)
        ticket = _ticket(ticket_id, queue.id, status="in_progress")
        ticket.ola_queue_id = queue.id
        ticket.ola_started_at = datetime(2026, 5, 4, 15, 0, tzinfo=timezone.utc)
        ticket.ola_ack_due_at = datetime(2026, 5, 4, 16, 10, tzinfo=timezone.utc)
        ticket.ola_processing_due_at = datetime(2026, 5, 4, 16, 20, tzinfo=timezone.utc)
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        assert await ola_service.check_ola_breaches(session) == 1
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "ola_breached")
                .order_by(TicketEvent.id)
            )
        ).scalars().all()

    assert ticket.ola_ack_breached_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert ticket.ola_processing_breached_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert len(events) == 1
    assert set(events[0].payload["breach_types"]) == {"ola_ack_breached_at", "ola_processing_breached_at"}
    assert events[0].payload["ola_policy"]["code"] == "default_queue_ola"
    assert events[0].payload["breach_actions"] == {
        "notify_queue_lead": True,
        "create_internal_event": True,
    }
