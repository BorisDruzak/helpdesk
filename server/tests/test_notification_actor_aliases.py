"""UI notification identities match the bounded aliases used for queue access."""
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketNotification, TicketQueue, TicketQueueMember, UiUser
from app.db.web_push_models import WebPushDelivery, WebPushSubscription
from app.repos.notification_repo import NotificationRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.web_push_repo import WebPushRepo
from tickets.notification_service import notify_ticket_event

pytestmark = pytest.mark.db_cleanup("full")
STORED = "Existing.Mixed"
PASSWORD = "existing.mixed"
ENDPOINT = "https://fcm.googleapis.com/fcm/send/alias-fixture"


async def seed(session, *, queue=False):
    session.add(UiUser(user_login=STORED, password_hash="fixture", actor_role="support", is_active=True))
    ticket = Ticket(ticket_id=str(uuid.uuid4()), title="Alias fixture", description="Fixture",
                    status="queued", requester_id="other-requester")
    if queue:
        target = TicketQueue(code="alias-" + uuid.uuid4().hex, name="Alias queue")
        session.add(target)
        await session.flush()
        ticket.queue_id = target.id
        session.add(TicketQueueMember(queue_id=target.id, actor_id=STORED))
    session.add(ticket)
    await session.flush()
    return ticket


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["list", "get", "count", "mark", "mark_all", "mark_ticket"])
async def test_password_actor_can_read_and_acknowledge_stored_login_notifications(test_engine, operation):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        ticket = await seed(session)
        repo = NotificationRepo(session)
        row = await repo.create(STORED, ticket.ticket_id, "chat_message", {"visibility": "public"})
        other = await repo.create("unrelated", ticket.ticket_id, "chat_message", {})
        auth = SimpleNamespace(actor_id=PASSWORD, actor_role="support", ticket_scope=None)
        if operation == "list":
            assert [item.id for item in await repo.list_by_actor(PASSWORD, auth_context=auth)] == [row.id]
        elif operation == "get":
            assert await repo.get_by_id(row.id, PASSWORD) is row
            assert await repo.get_by_id(other.id, PASSWORD) is None
        elif operation == "count":
            assert await repo.unread_count(PASSWORD, auth_context=auth) == 1
        elif operation == "mark":
            assert await repo.mark_read(row.id, PASSWORD)
            assert not await repo.mark_read(other.id, PASSWORD)
        elif operation == "mark_all":
            assert await repo.mark_all_read(PASSWORD) == 1
        else:
            assert await repo.mark_ticket_read(PASSWORD, ticket.ticket_id, auth_context=auth) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("subscriber,recipient", [(PASSWORD, STORED), (STORED, PASSWORD)])
async def test_push_fanout_and_browser_acknowledgement_share_ui_aliases(test_engine, subscriber, recipient):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        ticket = await seed(session)
        push = WebPushRepo(session)
        await push.subscribe(ENDPOINT, subscriber, "fixture-public-key")
        row = await NotificationRepo(session).create(recipient, ticket.ticket_id, "chat_message", {"visibility": "public"})
        assert await session.scalar(select(func.count()).select_from(WebPushDelivery)) == 1
        auth = SimpleNamespace(actor_id=recipient, actor_role="support", ticket_scope=None)
        assert [item.id for item in await push.pending(ENDPOINT, recipient, auth_context=auth)] == [row.id]
        # Switching login method in the same browser must retain pending events.
        await push.subscribe(ENDPOINT, recipient, "fixture-public-key")
        assert [item.id for item in await push.pending(ENDPOINT, subscriber)] == [row.id]
        await push.acknowledge(ENDPOINT, recipient, [row.id])
        assert await push.pending(ENDPOINT, subscriber) == []
        await push.unsubscribe(ENDPOINT, subscriber)
        assert await session.scalar(select(func.count()).select_from(WebPushSubscription)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("initiator,expected", [("another-operator", 1), (PASSWORD, 0)])
async def test_mixed_queue_member_and_assignee_receive_once_and_suppress_own_event(test_engine, monkeypatch, initiator, expected):
    import app.repos.ticket_events_repo as ticket_repo_module
    monkeypatch.setattr(ticket_repo_module, "unified_queue_enabled", lambda: False)
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        ticket = await seed(session, queue=True)
        ticket.assignee_id = PASSWORD
        await session.flush()
        await WebPushRepo(session).subscribe(ENDPOINT, PASSWORD, "fixture-public-key")
        await notify_ticket_event(TicketEventsRepo(session), NotificationRepo(session), ticket.ticket_id,
                                 "chat_message", {"visibility": "internal"}, initiator_id=initiator,
                                 raise_on_error=True)
        rows = list((await session.scalars(select(TicketNotification))).all())
        assert len(rows) == expected
        if rows:
            assert rows[0].actor_id == STORED
        assert await session.scalar(select(func.count()).select_from(WebPushDelivery)) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("owner,reader,ambiguous", [
    (STORED, "EXISTING.MIXED", False),
    ("Unknown.Actor", "unknown.actor", False),
    (STORED, PASSWORD, True),
])
async def test_notification_aliases_do_not_grant_unknown_spellings_or_ambiguous_users(test_engine, owner, reader, ambiguous):
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        ticket = await seed(session)
        push = WebPushRepo(session)
        await push.subscribe(ENDPOINT, owner, "fixture-public-key")
        if ambiguous:
            # Simulate a pre-hardening database; transaction rollback restores
            # this index together with the fixture rows in the isolated DB.
            await session.execute(text("DROP INDEX uq_ui_users_user_login_normalized"))
            session.add(UiUser(user_login=PASSWORD, password_hash="fixture", actor_role="support", is_active=True))
            await session.flush()
        row = await NotificationRepo(session).create(owner, ticket.ticket_id, "chat_message", {})
        repo = NotificationRepo(session)
        assert await repo.list_by_actor(reader) == []
        assert await repo.unread_count(reader) == 0
        assert await repo.get_by_id(row.id, reader) is None
        assert not await repo.mark_read(row.id, reader)
        assert await repo.mark_all_read(reader) == 0
        assert await push.get(ENDPOINT, reader) is None
        assert await push.pending(ENDPOINT, reader) == []
        await push.unsubscribe(ENDPOINT, reader)
        assert await session.scalar(select(func.count()).select_from(WebPushSubscription)) == 1
        if not ambiguous:
            assert await repo.get_by_id(row.id, owner) is row
            assert await push.get(ENDPOINT, owner) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_row", [False, True])
async def test_password_notification_preferences_apply_to_stored_queue_recipient(test_engine, monkeypatch, legacy_row):
    from app.db.models import TicketNotificationPref
    from app.repos.notification_prefs_repo import NotificationPrefsRepo
    import app.repos.ticket_events_repo as ticket_repo_module
    monkeypatch.setattr(ticket_repo_module, "unified_queue_enabled", lambda: False)
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        ticket = await seed(session, queue=True)
        prefs = NotificationPrefsRepo(session)
        if legacy_row:
            session.add(TicketNotificationPref(actor_id=PASSWORD, mute_internal=True,
                                               muted_event_types=[], suppress_self=False))
            await session.flush()
        else:
            await prefs.upsert(PASSWORD, mute_internal=True, suppress_self=False)
        assert await prefs.get_or_default(STORED) == (True, [], False)
        await notify_ticket_event(TicketEventsRepo(session), NotificationRepo(session), ticket.ticket_id,
                                 "chat_message", {"visibility": "internal"}, prefs_repo=prefs,
                                 raise_on_error=True)
        assert await session.scalar(select(func.count()).select_from(TicketNotification)) == 0
        await prefs.upsert(STORED, mute_internal=False)
        assert await prefs.get_or_default(PASSWORD) == (False, [], False)
        await notify_ticket_event(TicketEventsRepo(session), NotificationRepo(session), ticket.ticket_id,
                                 "chat_message", {"visibility": "internal"}, initiator_id=PASSWORD,
                                 prefs_repo=prefs, raise_on_error=True)
        assert await session.scalar(select(func.count()).select_from(TicketNotification)) == 1
