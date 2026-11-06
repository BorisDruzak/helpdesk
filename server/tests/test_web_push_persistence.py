"""Real PostgreSQL: rollback, retry deduplication and per-browser ownership."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketNotification
from app.db.web_push_models import WebPushDelivery, WebPushSubscription
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.web_push_repo import WebPushRepo

pytestmark = pytest.mark.db_cleanup("full")
ENDPOINT = "https://fcm.googleapis.com/fcm/send/synthetic-browser"


async def seed(maker):
    ticket_id = str(uuid.uuid4())
    async with maker() as session:
        session.add(Ticket(ticket_id=ticket_id, title="Synthetic push test", description="Fixture only", status="queued", requester_id="push-requester", assignee_id="push-support"))
        await WebPushRepo(session).subscribe(ENDPOINT, "push-requester", "test-public-key")
        await session.commit()
    return ticket_id


@pytest.mark.asyncio
async def test_read_viewed_ticket_preserves_other_tickets_actors_and_revoked_scope(test_engine):
    from app.repos.notification_repo import NotificationRepo
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket = await seed(maker)
    other = str(uuid.uuid4())
    async with maker() as session:
        session.add(Ticket(ticket_id=other, title="Other ticket", description="Fixture", status="queued", requester_id="elsewhere"))
        await session.flush()
        for actor, target in [("push-requester", ticket), ("push-requester", other), ("other-actor", ticket)]:
            await NotificationRepo(session).create(actor, target, "chat_message", {"visibility": "public"})
        await session.commit()
        auth = SimpleNamespace(actor_id="push-requester", actor_role="user", ticket_scope=None)
        repo = NotificationRepo(session)
        assert await repo.mark_ticket_read("push-requester", ticket, auth_context=auth) == 1
        assert await repo.mark_ticket_read("push-requester", ticket, auth_context=auth) == 0
        assert await repo.mark_ticket_read("push-requester", other, auth_context=auth) == 0
        rows = (await session.scalars(select(TicketNotification))).all()
        assert [(row.actor_id, row.ticket_id) for row in rows if row.is_read] == [("push-requester", ticket)]
        assert await WebPushRepo(session).pending(ENDPOINT, "push-requester", auth_context=auth) == []


@pytest.mark.asyncio
async def test_event_and_browser_delivery_commit_or_rollback_together(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket = await seed(maker)
    values = dict(ticket_id=ticket, device_id=None, agent_seq=None, event_type="chat_message", event_id=str(uuid.uuid4()), payload={"sender_actor_id": "push-support", "sender_role": "support", "visibility": "public", "text": "Synthetic reply"})
    async with maker() as session:
        assert await TicketEventsRepo(session).add_event(**values)
        assert await session.scalar(select(func.count()).select_from(WebPushDelivery)) == 1
        await session.rollback()
    async with maker() as session:
        assert await session.scalar(select(func.count()).select_from(TicketNotification)) == 0
        assert await session.scalar(select(func.count()).select_from(WebPushDelivery)) == 0
        assert await TicketEventsRepo(session).add_event(**values)
        await session.commit()
    async with maker() as session:
        assert await TicketEventsRepo(session).add_event(**values) is None
        assert await session.scalar(select(func.count()).select_from(TicketNotification)) == 1
        assert await session.scalar(select(func.count()).select_from(WebPushDelivery)) == 1
        row = await session.scalar(select(TicketNotification))
        assert row.actor_id == "push-requester"
        assert await WebPushRepo(session).pending(ENDPOINT, "another-user") == []
        await WebPushRepo(session).acknowledge(ENDPOINT, "another-user", [row.id])
        assert len(await WebPushRepo(session).pending(ENDPOINT, "push-requester")) == 1
        await WebPushRepo(session).acknowledge(ENDPOINT, "push-requester", [row.id])
        assert await WebPushRepo(session).pending(ENDPOINT, "push-requester") == []


@pytest.mark.asyncio
async def test_internal_chat_excludes_requester_and_status_includes_requester(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket = await seed(maker)
    async with maker() as session:
        repo = TicketEventsRepo(session)
        await repo.add_event(ticket, None, None, "chat_message", {"sender_actor_id": "push-support", "sender_role": "support", "visibility": "internal"}, event_id=str(uuid.uuid4()))
        assert await session.scalar(select(func.count()).select_from(TicketNotification)) == 0
        await repo.add_event(ticket, None, None, "status_changed", {"actor_id": "push-support", "to_status": "in_progress"}, event_id=str(uuid.uuid4()))
        assert await session.scalar(select(func.count()).select_from(WebPushDelivery)) == 1
        await session.commit()


@pytest.mark.asyncio
async def test_rebinding_browser_removes_old_account_deliveries(test_engine):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket = await seed(maker)
    async with maker() as session:
        await TicketEventsRepo(session).add_event(ticket, None, None, "status_changed", {"actor_id": "push-support", "to_status": "resolved"}, event_id=str(uuid.uuid4()))
        await session.commit()
        await WebPushRepo(session).subscribe(ENDPOINT, "next-user", "test-public-key")
        await session.commit()
        assert await WebPushRepo(session).pending(ENDPOINT, "next-user") == []
        assert await WebPushRepo(session).get(ENDPOINT, "push-requester") is None
        assert await session.scalar(select(func.count()).select_from(WebPushDelivery)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [201, 410, 503])
async def test_dispatcher_committed_delivery_success_expiry_and_retry(test_engine, monkeypatch, status):
    from app.services import web_push_dispatcher as module
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket = await seed(maker)
    async with maker() as session:
        await TicketEventsRepo(session).add_event(ticket, None, None, "status_changed", {"actor_id": "push-support", "to_status": "resolved"}, event_id=str(uuid.uuid4()))
        await session.commit()
    send = AsyncMock(return_value=status)
    monkeypatch.setattr(module, "send_wakeup", send)
    worker = module.WebPushDispatcher(SimpleNamespace(public_key="test-public-key"), session_factory=maker)
    assert await worker.dispatch_one(object()) is True
    assert await worker.dispatch_one(object()) is False
    send.assert_awaited_once()
    async with maker() as session:
        subscription = await session.scalar(select(WebPushSubscription))
        delivery = await session.scalar(select(WebPushDelivery))
        if status == 410:
            assert subscription is None and delivery is None
        elif status == 201:
            assert delivery.sent_at is not None and subscription.failures == 0
        else:
            assert delivery.sent_at is None and subscription.failures == 1
            assert subscription.next_attempt_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_fresh_event_after_success_does_not_wait_for_retry_cooldown(test_engine, monkeypatch):
    from app.services import web_push_dispatcher as module
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket = await seed(maker)
    async def event():
        async with maker() as session:
            await TicketEventsRepo(session).add_event(ticket, None, None, "status_changed", {"actor_id": "push-support", "to_status": "resolved"}, event_id=str(uuid.uuid4()))
            await session.commit()
    send = AsyncMock(return_value=201)
    monkeypatch.setattr(module, "send_wakeup", send)
    worker = module.WebPushDispatcher(SimpleNamespace(public_key="test-public-key"), session_factory=maker)
    await event()
    assert await worker.dispatch_one(object())
    await event()
    assert await worker.dispatch_one(object())
    assert send.await_count == 2
