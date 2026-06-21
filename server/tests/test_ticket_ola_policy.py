from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent, TicketNotification, TicketQueue, TicketQueueMember
from tickets.policy_action_dispatcher import dispatch_policy_actions
from tickets import ola_service


pytestmark = pytest.mark.db_cleanup("tickets")

class FakeChannelProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, *, channel: str, actor_id: str, ticket_id: str, event_type: str, payload: dict):
        self.calls.append(
            {
                "channel": channel,
                "actor_id": actor_id,
                "ticket_id": ticket_id,
                "event_type": event_type,
                "payload": payload,
            }
        )
        return {"delivery_status": "sent", "provider_message_id": f"{channel}-{actor_id}"}


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


async def _queue_member(session, queue_id: int, actor_id: str, role: str | None = None) -> TicketQueueMember:
    member = TicketQueueMember(queue_id=queue_id, actor_id=actor_id, role_in_queue=role)
    session.add(member)
    await session.flush()
    return member


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
async def test_ola_processing_stop_accepts_legacy_alias_list_conditions(test_engine, monkeypatch) -> None:
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
            ola_policy=_policy(stop_conditions=["ticket_resolved", "ticket_closed"]),
        )
        ticket.ola_queue_id = queue.id
        ticket.ola_started_at = datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc)
        ticket.ola_processing_due_at = datetime(2026, 5, 4, 18, 0, tzinfo=timezone.utc)
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        assert await ola_service.close_ola_processing(session, ticket_id, status="waiting_on_user") is False
        assert await ola_service.close_ola_processing(session, ticket_id, status="resolved") is True
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        event_type = await session.scalar(
            select(TicketEvent.event_type)
            .where(TicketEvent.ticket_id == ticket_id)
            .where(TicketEvent.event_type == "ola_processing_stopped")
        )

    assert ticket.ola_processing_at == datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc)
    assert event_type == "ola_processing_stopped"


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


@pytest.mark.asyncio
async def test_ola_breach_actions_dispatch_to_queue_lead(test_engine, monkeypatch) -> None:
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    monkeypatch.setattr(ola_service, "datetime", FrozenDateTime)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        queue = await _queue(session)
        await _queue_member(session, queue.id, "queue-lead-ola", "lead")
        await _queue_member(session, queue.id, "queue-member-ola", "member")
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
        notifications = (
            await session.execute(
                select(TicketNotification)
                .where(TicketNotification.ticket_id == ticket_id)
                .order_by(TicketNotification.id)
            )
        ).scalars().all()
        audit_events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "policy_action_dispatched")
                .order_by(TicketEvent.id)
            )
        ).scalars().all()

    assert [item.actor_id for item in notifications] == ["queue-lead-ola"]
    assert notifications[0].event_type == "ola_breached"
    assert notifications[0].payload["source_event_type"] == "ola_breached"
    assert notifications[0].payload["policy_action_key"] == "notify_queue_lead"
    assert notifications[0].payload["breach_actions"]["notify_queue_lead"] is True
    assert len(audit_events) == 1
    assert audit_events[0].payload["actor_id"] == "queue-lead-ola"
    assert audit_events[0].payload["action_key"] == "notify_queue_lead"


@pytest.mark.asyncio
async def test_policy_action_dispatcher_is_idempotent_per_source_event_and_recipient(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        queue = await _queue(session)
        await _queue_member(session, queue.id, "queue-lead-idempotent", "lead")
        ticket = _ticket(ticket_id, queue.id, status="in_progress")
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        first = await dispatch_policy_actions(
            session,
            ticket=ticket,
            source_event_type="ola_breached",
            source_event_id="ola-breach-source-1",
            actions={"notify_queue_lead": True, "create_internal_event": True},
            payload={"ticket_id": ticket_id},
        )
        second = await dispatch_policy_actions(
            session,
            ticket=ticket,
            source_event_type="ola_breached",
            source_event_id="ola-breach-source-1",
            actions={"notify_queue_lead": True, "create_internal_event": True},
            payload={"ticket_id": ticket_id},
        )
        await session.commit()

    async with session_maker() as session:
        notifications = (
            await session.execute(
                select(TicketNotification)
                .where(TicketNotification.ticket_id == ticket_id)
                .order_by(TicketNotification.id)
            )
        ).scalars().all()
        audit_events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "policy_action_dispatched")
                .order_by(TicketEvent.id)
            )
        ).scalars().all()

    assert first["created_notifications"] == 1
    assert first["created_audit_events"] == 1
    assert second["created_notifications"] == 0
    assert second["created_audit_events"] == 0
    assert [item.actor_id for item in notifications] == ["queue-lead-idempotent"]
    assert len(audit_events) == 1


@pytest.mark.asyncio
async def test_policy_action_dispatcher_sends_external_channels_with_audit(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    provider = FakeChannelProvider()

    async with session_maker() as session:
        queue = await _queue(session)
        await _queue_member(session, queue.id, "queue-lead-external", "lead")
        ticket = _ticket(ticket_id, queue.id, status="in_progress")
        session.add(ticket)
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        result = await dispatch_policy_actions(
            session,
            ticket=ticket,
            source_event_type="ola_breached",
            source_event_id="ola-breach-source-external",
            actions={
                "notify_queue_lead": True,
                "create_internal_event": True,
                "channels": {"web": True, "email": True},
            },
            payload={"ticket_id": ticket_id},
            channel_provider=provider,
        )
        await session.commit()

    async with session_maker() as session:
        external_events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "external_notification_delivery")
                .order_by(TicketEvent.id)
            )
        ).scalars().all()

    assert result["external_deliveries"] == 1
    assert [item["channel"] for item in provider.calls] == ["email"]
    assert provider.calls[0]["payload"]["policy_action_key"] == "notify_queue_lead"
    assert len(external_events) == 1
    assert external_events[0].payload["channel"] == "email"
    assert external_events[0].payload["delivery_status"] == "sent"
    assert external_events[0].payload["provider_message_id"] == "email-queue-lead-external"
