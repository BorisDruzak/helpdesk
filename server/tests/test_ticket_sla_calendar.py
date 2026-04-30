from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketBusinessCalendar, TicketSlaPolicy, TicketSlaTarget
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.calendar_engine import add_business_minutes
from tickets.sla_service import TicketSlaService
import tickets.sla_service as sla_service_module


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        fixed = datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
        return fixed if tz is None else fixed.astimezone(tz)


@pytest.mark.asyncio
async def test_start_sla_uses_business_calendar_for_due_dates(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_service_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        calendar = TicketBusinessCalendar(
            code=f"weekday_{uuid.uuid4().hex[:8]}",
            name="Weekday SLA",
            timezone="UTC",
            weekly_hours_json=[
                {"day": 0, "start": "09:00", "end": "17:00"},
                {"day": 1, "start": "09:00", "end": "17:00"},
                {"day": 2, "start": "09:00", "end": "17:00"},
                {"day": 3, "start": "09:00", "end": "17:00"},
                {"day": 4, "start": "09:00", "end": "17:00"},
            ],
            holidays_json=[],
            is_active=True,
        )
        session.add(calendar)
        await session.flush()
        policy = TicketSlaPolicy(
            name=f"Calendar SLA {uuid.uuid4().hex[:8]}",
            timezone="UTC",
            calendar_id=calendar.id,
            is_default=True,
            is_active=True,
        )
        session.add(policy)
        await session.flush()
        session.add(
            TicketSlaTarget(
                policy_id=policy.id,
                priority="P3",
                first_response_min=30,
                resolution_min=120,
            )
        )
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Calendar SLA",
            description="SLA must use business hours.",
            status="new",
            requester_id="requester-sla",
            ticket_type="incident",
            priority="P4",
        )
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        ticket = await repo.get_ticket(ticket_id)
        service = TicketSlaService(session, repo)
        assert await service.start_sla(ticket) is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)

    assert ticket is not None
    assert ticket.first_response_due_at == datetime(2026, 5, 4, 17, 0, tzinfo=timezone.utc)
    assert ticket.resolution_due_at == datetime(2026, 5, 5, 10, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_start_sla_uses_standalone_registry_policy_targets(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_service_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Standalone SLA",
            description="SLA must use versioned registry JSON targets.",
            status="new",
            requester_id="requester-standalone-sla",
            ticket_type="incident",
            priority="P3",
            custom_fields={
                "priority_class": "P2",
                "request_template": {
                    "sla_policy": {
                        "targets": {
                            "first_response": {"P2": "45m"},
                            "resolution": {"P2": "2h"},
                        }
                    }
                },
            },
        )
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        ticket = await repo.get_ticket(ticket_id)
        service = TicketSlaService(session, repo)
        assert await service.start_sla(ticket) is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)

    assert ticket is not None
    assert ticket.sla_policy_id is None
    assert ticket.first_response_due_at == datetime(2026, 5, 4, 17, 15, tzinfo=timezone.utc)
    assert ticket.resolution_due_at == datetime(2026, 5, 4, 18, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_start_sla_uses_standalone_registry_policy_calendar(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_service_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Standalone SLA calendar",
            description="Registry SLA should use embedded business calendar.",
            status="new",
            requester_id="requester-standalone-sla-calendar",
            ticket_type="incident",
            priority="P3",
            custom_fields={
                "priority_class": "P2",
                "request_template": {
                    "sla_policy": {
                        "calendar": {
                            "timezone": "UTC",
                            "weekly_hours_json": [
                                {"day": 0, "start": "09:00", "end": "17:00"},
                                {"day": 1, "start": "09:00", "end": "17:00"},
                            ],
                            "holidays_json": [],
                        },
                        "targets": {
                            "first_response": {"P2": "45m"},
                            "resolution": {"P2": "2h"},
                        },
                    }
                },
            },
        )
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        ticket = await repo.get_ticket(ticket_id)
        service = TicketSlaService(session, repo)
        assert await service.start_sla(ticket) is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)

    assert ticket is not None
    assert ticket.first_response_due_at == datetime(2026, 5, 5, 9, 15, tzinfo=timezone.utc)
    assert ticket.resolution_due_at == datetime(2026, 5, 5, 10, 30, tzinfo=timezone.utc)


def test_add_business_minutes_handles_seconds_before_interval_end() -> None:
    calendar = {
        "timezone": "UTC",
        "weekly_hours_json": [
            {"day": 0, "start": "09:00", "end": "17:00"},
            {"day": 1, "start": "09:00", "end": "17:00"},
        ],
        "holidays_json": [],
    }

    due_at = add_business_minutes(
        datetime(2026, 5, 4, 16, 59, 30, tzinfo=timezone.utc),
        2,
        calendar,
    )

    assert due_at == datetime(2026, 5, 5, 9, 1, 30, tzinfo=timezone.utc)
