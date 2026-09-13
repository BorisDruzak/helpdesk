from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.ticket_events_repo import TicketEventsRepo
from state_manager import StateManager
from tickets.handlers import _ticket_presence_payload


pytestmark = pytest.mark.db_cleanup("tickets")

@pytest.mark.asyncio
async def test_requester_read_cursor_accepts_agent_message_read_events(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = "ticket-presence-1"
    device_id = "device-presence-1"

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        await repo.create_ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Unread counters",
            description="Check requester cursor",
            status="new",
            requester_id="requester-1",
        )
        support_event = await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={
                "message_id": "support-message-1",
                "sender_role": "support",
                "from": "support",
                "text": "Support reply",
                "visibility": "public",
            },
        )
        assert support_event is not None
        support_event_id, _ = support_event
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="message_read",
            payload={
                "actor_id": device_id,
                "actor_role": "agent",
                "read_scope": "requester",
                "last_read_event_id": support_event_id,
                "last_read_message_id": "support-message-1",
                "messages_read_count": 1,
                "tool_calls_read_count": 0,
            },
            event_id=f"message_read:requester:{support_event_id}",
        )
        await session.commit()

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        cursor = await repo.get_latest_message_read_cursor(ticket_id, "requester")
        counters = await repo.get_ticket_chat_counters_batch([ticket_id])

    assert cursor["last_read_event_id"] == support_event_id
    assert counters[ticket_id]["requester_last_read_event_id"] == support_event_id
    assert counters[ticket_id]["requester_unread_messages"] == 0


@pytest.mark.no_db
def test_state_manager_ticket_presence_expires_and_clears(monkeypatch):
    state = StateManager()

    monkeypatch.setattr("state_manager.time.time", lambda: 100.0)
    state.touch_ticket_presence("ticket-1", "device-1", "agent", presence_key="agent:device-1")
    state.touch_ticket_presence("ticket-1", "support-1", "support", presence_key="ws:1")

    online_presence = state.get_ticket_presence("ticket-1")
    assert online_presence["requester_online"] is True
    assert online_presence["support_online"] is True
    assert online_presence["requester_actor_ids"] == ["device-1"]
    assert online_presence["support_actor_ids"] == ["support-1"]

    state.clear_ticket_presence_key("ws:1")
    support_cleared_presence = state.get_ticket_presence("ticket-1")
    assert support_cleared_presence["requester_online"] is True
    assert support_cleared_presence["support_online"] is False

    monkeypatch.setattr("state_manager.time.time", lambda: 200.0)
    expired_presence = state.get_ticket_presence("ticket-1")
    assert expired_presence["requester_online"] is False
    assert expired_presence["support_online"] is False


@pytest.mark.no_db
def test_ticket_presence_hides_retired_agent_runtime_as_offline():
    state = SimpleNamespace(
        get_ticket_presence=lambda _ticket_id: {
            "requester_online": True,
            "requester_last_seen_at": None,
            "requester_actor_ids": ["requester-1"],
            "support_online": False,
            "support_last_seen_at": None,
            "support_actor_ids": [],
        }
    )

    payload = _ticket_presence_payload(
        SimpleNamespace(app={"state": state}),
        SimpleNamespace(ticket_id="ticket-1", device_id="device-1"),
    )

    assert payload["agent_online"] is False
