from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Ticket,
    TicketBusinessCalendar,
    TicketEvent,
    TicketNotification,
    TicketQueue,
    TicketQueueMember,
    TicketSlaPolicy,
    TicketSlaTarget,
)
from app.repos.ticket_events_repo import TicketEventsRepo
from app.services.ticket_sla_watchdog import TicketSlaWatchdog
import app.services.ticket_sla_watchdog as sla_watchdog_module
from tickets.calendar_engine import add_business_minutes
from tickets.sla_service import TicketSlaService
import tickets.sla_service as sla_service_module


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        fixed = datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
        return fixed if tz is None else fixed.astimezone(tz)


async def _queue(session, code: str = "sla-escalation") -> TicketQueue:
    queue = TicketQueue(code=f"{code}-{uuid.uuid4().hex[:8]}", name="SLA escalation", is_triage=False)
    session.add(queue)
    await session.flush()
    return queue


async def _queue_member(session, queue_id: int, actor_id: str, role: str | None = None) -> None:
    session.add(TicketQueueMember(queue_id=queue_id, actor_id=actor_id, role_in_queue=role))
    await session.flush()


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


@pytest.mark.asyncio
async def test_start_sla_respects_start_conditions_and_logs_policy_metadata(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_service_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Start conditions",
            description="SLA should start only on matching configured start conditions.",
            status="new",
            requester_id="requester-sla-start",
            ticket_type="incident",
            priority="P3",
            custom_fields={
                "priority_class": "P2",
                "request_template": {
                    "sla_policy": {
                        "code": "incident_sla_live",
                        "version": "1.2.3",
                        "source": "request_template",
                        "start_conditions": ["approval_received"],
                        "targets": {
                            "first_response": {"P2": "30m"},
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
        assert await service.start_sla(ticket, trigger="ticket_created") is False
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.first_response_due_at is None
        custom_fields = dict(ticket.custom_fields or {})
        request_template = dict(custom_fields.get("request_template") or {})
        sla_policy = dict(request_template.get("sla_policy") or {})
        sla_policy["start_conditions"] = ["ticket_created"]
        request_template["sla_policy"] = sla_policy
        custom_fields["request_template"] = request_template
        ticket.custom_fields = custom_fields
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        ticket = await repo.get_ticket(ticket_id)
        service = TicketSlaService(session, repo)
        assert await service.start_sla(ticket, trigger="ticket_created") is True
        await session.commit()

    async with session_maker() as session:
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "sla_started")
                .order_by(TicketEvent.id)
            )
        ).scalars().all()

    assert len(events) == 1
    assert events[0].payload["sla_policy"] == {
        "code": "incident_sla_live",
        "version": "1.2.3",
        "source": "request_template",
    }
    assert events[0].payload["targets"]["first_response_min"] == 30
    assert events[0].payload["targets"]["resolution_min"] == 120


@pytest.mark.asyncio
async def test_sla_pause_resume_uses_configured_conditions_and_logs_events(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_service_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Pause resume conditions",
            description="SLA pause and resume should follow policy conditions.",
            status="waiting_on_user",
            requester_id="requester-sla-pause",
            ticket_type="incident",
            priority="P3",
            custom_fields={
                "priority_class": "P2",
                "request_template": {
                    "sla_policy": {
                        "code": "conditional_sla",
                        "version": "2.0.0",
                        "pause_conditions": [{"status": "waiting_on_vendor", "pause_external_wait": True}],
                        "resume_conditions": ["vendor_replied"],
                        "targets": {
                            "first_response": {"P2": "30m"},
                            "resolution": {"P2": "2h"},
                        },
                    }
                },
                "pause_external_wait": True,
            },
        )
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketSlaService(session, repo)
        assert await service.pause_sla(ticket_id, trigger="status_changed") is False
        ticket = await repo.get_ticket(ticket_id)
        assert ticket.sla_paused_at is None
        ticket.status = "waiting_on_vendor"
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketSlaService(session, repo)
        assert await service.pause_sla(ticket_id, trigger="status_changed") is True
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        ticket = await repo.get_ticket(ticket_id)
        assert ticket.sla_paused_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
        ticket.status = "in_progress"
        ticket.sla_paused_at = datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc)
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketSlaService(session, repo)
        assert await service.resume_sla(ticket_id, trigger="requester_replied") is False
        assert await service.resume_sla(ticket_id, trigger="vendor_replied") is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        events = (
            await session.execute(
                select(TicketEvent.event_type, TicketEvent.payload)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type.in_(["sla_paused", "sla_resumed"]))
                .order_by(TicketEvent.id)
            )
        ).all()

    assert ticket.sla_paused_at is None
    assert ticket.sla_paused_seconds == 1800
    assert [row[0] for row in events] == ["sla_paused", "sla_resumed"]
    assert events[0][1]["sla_policy"]["code"] == "conditional_sla"
    assert events[1][1]["trigger"] == "vendor_replied"


@pytest.mark.asyncio
async def test_sla_stop_conditions_control_frt_and_resolution_stop(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_service_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Stop conditions",
            description="SLA stop conditions should be configurable.",
            status="in_progress",
            requester_id="requester-sla-stop",
            ticket_type="incident",
            priority="P3",
            custom_fields={
                "priority_class": "P2",
                "request_template": {
                    "sla_policy": {
                        "code": "stop_sla",
                        "version": "3.0.0",
                        "stop_conditions": {
                            "first_response": ["first_public_support_reply_sent"],
                            "resolution": [{"status_in": ["resolved", "closed"]}],
                        },
                        "targets": {
                            "first_response": {"P2": "30m"},
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
        service = TicketSlaService(session, repo)
        assert await service.close_frt(ticket_id, trigger="internal_note_added") is False
        assert await service.close_frt(ticket_id, trigger="first_public_support_reply_sent") is True
        assert await service.stop_resolution(ticket_id, status="waiting_on_user") is False
        assert await service.stop_resolution(ticket_id, status="resolved") is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event_types = [
            row[0]
            for row in (
                await session.execute(
                    select(TicketEvent.event_type)
                    .where(TicketEvent.ticket_id == ticket_id)
                    .where(TicketEvent.event_type.in_(["sla_first_response_stopped", "sla_resolution_stopped"]))
                    .order_by(TicketEvent.id)
                )
            ).all()
        ]

    assert ticket.first_response_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert ticket.resolution_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert event_types == ["sla_first_response_stopped", "sla_resolution_stopped"]


@pytest.mark.asyncio
async def test_sla_policy_accepts_live_status_and_resolution_aliases(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_service_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Live SLA aliases",
            description="Live policy aliases should drive SLA lifecycle.",
            status="waiting_on_user",
            requester_id="requester-sla-alias",
            ticket_type="incident",
            priority="P3",
            custom_fields={
                "priority_class": "P3",
                "request_template": {
                    "sla_policy": {
                        "code": "live_alias_sla",
                        "version": "1.0.0",
                        "pause_conditions": ["waiting_user", "waiting_approval"],
                        "resume_conditions": ["requester_replied", "approval_completed"],
                        "stop_conditions": {"resolution": ["ticket_resolved", "ticket_closed"]},
                        "targets": {
                            "first_response": {"P3": "30m"},
                            "resolution": {"P3": "2h"},
                        },
                    }
                },
            },
        )
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketSlaService(session, repo)
        assert await service.pause_sla(ticket_id, trigger="status_changed") is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.status = "in_progress"
        ticket.sla_paused_at = datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc)
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        service = TicketSlaService(session, repo)
        assert await service.resume_sla(ticket_id, trigger="requester_replied") is True
        assert await service.stop_resolution(ticket_id, status="resolved", trigger="status_changed") is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event_types = [
            row[0]
            for row in (
                await session.execute(
                    select(TicketEvent.event_type)
                    .where(TicketEvent.ticket_id == ticket_id)
                    .where(TicketEvent.event_type.in_(["sla_paused", "sla_resumed", "sla_resolution_stopped"]))
                    .order_by(TicketEvent.id)
                )
            ).all()
        ]

    assert ticket.sla_paused_at is None
    assert ticket.sla_paused_seconds == 1800
    assert ticket.resolution_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert event_types == ["sla_paused", "sla_resumed", "sla_resolution_stopped"]


@pytest.mark.asyncio
async def test_sla_watchdog_emits_configured_warning_before_breach(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_watchdog_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Warning before breach",
            description="SLA warning should use configured warning_before.",
            status="in_progress",
            requester_id="requester-sla-warning",
            ticket_type="incident",
            priority="P3",
            first_response_due_at=datetime(2026, 5, 4, 16, 50, tzinfo=timezone.utc),
            resolution_due_at=datetime(2026, 5, 4, 18, 30, tzinfo=timezone.utc),
            custom_fields={
                "priority_class": "P2",
                "request_template": {
                    "sla_policy": {
                        "code": "warning_sla",
                        "version": "4.0.0",
                        "warnings": {"warning_before": {"first_response": "30m", "resolution": "45m"}},
                        "breach_actions": {
                            "notify": ["assignee", "queue_lead"],
                            "escalate_to_queue_lead": True,
                        },
                    }
                },
            },
        )
        session.add(ticket)
        await session.commit()

    watchdog = TicketSlaWatchdog(interval=999)
    await watchdog._check_warnings()

    async with session_maker() as session:
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "sla_warning")
                .order_by(TicketEvent.id)
            )
        ).scalars().all()

    assert len(events) == 1
    assert events[0].payload["warning_type"] == "first_response"
    assert events[0].payload["sla_policy"]["code"] == "warning_sla"
    assert events[0].payload["breach_actions"] == {
        "notify": ["assignee", "queue_lead"],
        "escalate_to_queue_lead": True,
    }


@pytest.mark.asyncio
async def test_sla_warning_dispatches_policy_actions_to_assignee_and_queue_lead(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_watchdog_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        queue = await _queue(session)
        await _queue_member(session, queue.id, "sla-warning-lead", "lead")
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Warning policy action",
            description="SLA warning should dispatch configured recipients.",
            status="in_progress",
            requester_id="requester-sla-warning-dispatch",
            assignee_id="sla-warning-assignee",
            queue_id=queue.id,
            ticket_type="incident",
            priority="P3",
            first_response_due_at=datetime(2026, 5, 4, 16, 50, tzinfo=timezone.utc),
            resolution_due_at=datetime(2026, 5, 4, 18, 30, tzinfo=timezone.utc),
            custom_fields={
                "priority_class": "P2",
                "request_template": {
                    "sla_policy": {
                        "code": "warning_dispatch_sla",
                        "version": "4.1.0",
                        "warnings": {"warning_before": {"first_response": "30m"}},
                        "breach_actions": {
                            "notify": ["assignee"],
                            "escalate_to_queue_lead": True,
                            "create_internal_event": True,
                        },
                    }
                },
            },
        )
        session.add(ticket)
        await session.commit()

    watchdog = TicketSlaWatchdog(interval=999)
    await watchdog._check_warnings()

    async with session_maker() as session:
        notifications = (
            await session.execute(
                select(TicketNotification)
                .where(TicketNotification.ticket_id == ticket_id)
                .where(TicketNotification.event_type == "sla_warning")
                .order_by(TicketNotification.actor_id)
            )
        ).scalars().all()
        audit_events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "policy_action_dispatched")
                .order_by(TicketEvent.payload["actor_id"].astext)
            )
        ).scalars().all()

    assert [item.actor_id for item in notifications] == ["sla-warning-assignee", "sla-warning-lead"]
    assert {item.payload["policy_action_key"] for item in notifications} == {
        "notify:assignee",
        "escalate_to_queue_lead",
    }
    assert all(item.payload["source_event_type"] == "sla_warning" for item in notifications)
    assert len(audit_events) == 2
    assert {item.payload["actor_id"] for item in audit_events} == {"sla-warning-assignee", "sla-warning-lead"}


@pytest.mark.asyncio
async def test_sla_breach_dispatches_policy_actions_to_queue_lead(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(sla_watchdog_module, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        queue = await _queue(session)
        await _queue_member(session, queue.id, "sla-breach-lead", "queue_lead")
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=f"device-{ticket_id[:8]}",
            title="Breach policy action",
            description="SLA breach should dispatch configured recipients.",
            status="in_progress",
            requester_id="requester-sla-breach-dispatch",
            queue_id=queue.id,
            ticket_type="incident",
            priority="P3",
            first_response_due_at=datetime(2026, 5, 1, 16, 10, tzinfo=timezone.utc),
            resolution_due_at=datetime(2026, 5, 1, 16, 20, tzinfo=timezone.utc),
            custom_fields={
                "priority_class": "P2",
                "request_template": {
                    "sla_policy": {
                        "code": "breach_dispatch_sla",
                        "version": "4.2.0",
                        "breach_actions": {
                            "notify_queue_lead": True,
                            "create_internal_event": True,
                        },
                    }
                },
            },
        )
        session.add(ticket)
        await session.commit()

    watchdog = TicketSlaWatchdog(interval=999)
    await watchdog._check_breaches()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        notifications = (
            await session.execute(
                select(TicketNotification)
                .where(TicketNotification.ticket_id == ticket_id)
                .where(TicketNotification.event_type == "sla_breached")
                .where(TicketNotification.payload["policy_action_key"].astext == "notify_queue_lead")
            )
        ).scalars().all()
        audit_events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "policy_action_dispatched")
            )
        ).scalars().all()

    assert ticket.first_response_breached_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert ticket.resolution_breached_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert [item.actor_id for item in notifications] == ["sla-breach-lead"]
    assert notifications[0].payload["source_event_type"] == "sla_breached"
    assert len(audit_events) == 1
    assert audit_events[0].payload["actor_id"] == "sla-breach-lead"


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
