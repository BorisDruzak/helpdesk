import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from aiohttp import web, WSMsgType
from aiohttp.test_utils import TestClient, TestServer
import pytest

import app.repos as repos_module
from auth.service import AuthService
from state_manager import StateManager
import websocket.ui_handler as ui_handler


pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


@pytest.fixture
def websocket_auth(monkeypatch):
    auth = SimpleNamespace(role="admin", active=True, queue_allowed=True, assignee_id=None, unavailable=False, reads=0)

    async def verify_token(self, token):
        auth.reads += 1
        if auth.unavailable:
            raise RuntimeError("authentication database unavailable")
        if not auth.active:
            return None
        return {"user_login": "operator", "actor_role": auth.role}

    @asynccontextmanager
    async def session():
        yield SimpleNamespace()

    class TicketRepo:
        def __init__(self, session):
            pass

        async def get_ticket(self, ticket_id):
            return SimpleNamespace(ticket_id=ticket_id, queue_id="queue-1", assignee_id=auth.assignee_id)

        async def is_actor_in_queue(self, queue_id, actor_id):
            return auth.queue_allowed

    monkeypatch.setattr(AuthService, "verify_ui_token", verify_token)
    monkeypatch.setattr(ui_handler, "get_session", session)
    monkeypatch.setattr(ui_handler, "TicketEventsRepo", TicketRepo)
    monkeypatch.setattr(ui_handler, "DB_AVAILABLE", True)
    return auth


@asynccontextmanager
async def connected_ui():
    state = StateManager()
    app = web.Application()
    app["state"] = state
    app.router.add_get("/ws_ui", ui_handler.websocket_ui_handler)
    async with TestClient(TestServer(app)) as client:
        async with client.ws_connect("/ws_ui") as ws:
            await ws.send_json({"type": "ui_hello", "token": "session-token"})
            assert (await ws.receive_json(timeout=2))["type"] == "ui_hello_ack"
            yield ws, state


async def subscribe_ticket(ws):
    await ws.send_json({"type": "subscribe_ticket", "ticket_id": "ticket-1", "skip_catchup": True})
    assert (await ws.receive_json(timeout=2))["type"] == "catchup_done"
    assert (await ws.receive_json(timeout=2))["type"] == "subscribe_ack"


@pytest.mark.parametrize("role", ["user", "auditor"])
async def test_internal_ticket_subscription_rejects_non_operator_roles(websocket_auth, role):
    websocket_auth.role = role
    async with connected_ui() as (ws, state):
        await ws.send_json({"type": "subscribe_ticket", "ticket_id": "ticket-1", "skip_catchup": True})
        response = await ws.receive_json(timeout=2)
        assert response["type"] == "error"
        assert "ticket-1" not in state.subscription_registry.ticket_subscribers


async def test_ticket_subscription_enforces_support_queue_scope(websocket_auth):
    websocket_auth.role = "support"
    websocket_auth.queue_allowed = False
    async with connected_ui() as (ws, state):
        await ws.send_json({"type": "subscribe_ticket", "ticket_id": "ticket-1", "skip_catchup": True})
        assert (await ws.receive_json(timeout=2))["type"] == "error"
        assert "ticket-1" not in state.subscription_registry.ticket_subscribers


@pytest.mark.parametrize("change", ["role", "inactive", "database"])
async def test_existing_ticket_room_stops_delivery_when_session_changes(websocket_auth, change):
    async with connected_ui() as (ws, state):
        await subscribe_ticket(ws)
        if change == "role":
            websocket_auth.role = "support"
        elif change == "inactive":
            websocket_auth.active = False
        else:
            websocket_auth.unavailable = True
        delivery = asyncio.create_task(state.subscription_registry.broadcast_to_ticket(
            "ticket-1", {"type": "ticket_event_committed", "ticket_id": "ticket-1", "payload": {"secret": "internal"}}
        ))
        try:
            message = await ws.receive(timeout=2)
            assert message.type == WSMsgType.CLOSE
            assert message.data == 4003
        finally:
            await delivery
        assert not state.subscription_registry.ticket_subscribers


async def test_existing_ticket_room_rechecks_queue_membership_before_push(websocket_auth):
    websocket_auth.role = "support"
    async with connected_ui() as (ws, state):
        await subscribe_ticket(ws)
        websocket_auth.queue_allowed = False
        delivery = asyncio.create_task(state.subscription_registry.broadcast_to_ticket(
            "ticket-1", {"type": "ticket_event_committed", "ticket_id": "ticket-1", "payload": {"secret": "internal"}}
        ))
        try:
            assert (await ws.receive(timeout=2)).type == WSMsgType.CLOSE
        finally:
            await delivery
        assert not state.subscription_registry.ticket_subscribers


async def test_new_subscription_revalidates_role_of_open_connection(websocket_auth):
    async with connected_ui() as (ws, state):
        websocket_auth.role = "user"
        await ws.send_json({"type": "subscribe_ticket", "ticket_id": "ticket-1", "skip_catchup": True})
        assert (await ws.receive(timeout=2)).type == WSMsgType.CLOSE
        assert not state.subscription_registry.ticket_subscribers


async def test_authorized_room_receives_event_and_ping_does_not_read_auth_db(websocket_auth):
    async with connected_ui() as (ws, state):
        await subscribe_ticket(ws)
        reads_before_ping = websocket_auth.reads
        await ws.send_json({"type": "ping"})
        assert (await ws.receive_json(timeout=2))["type"] == "pong"
        assert websocket_auth.reads == reads_before_ping
        event = {"type": "ticket_event_committed", "ticket_id": "ticket-1", "payload": {"message": "visible"}}
        await state.subscription_registry.broadcast_to_ticket("ticket-1", event)
        assert await ws.receive_json(timeout=2) == event


async def test_assigned_support_can_read_ticket_outside_queue(websocket_auth):
    websocket_auth.role = "support"
    websocket_auth.queue_allowed = False
    websocket_auth.assignee_id = "operator"
    async with connected_ui() as (ws, state):
        await subscribe_ticket(ws)
        event = {"type": "ticket_event_committed", "ticket_id": "ticket-1", "payload": {"message": "assigned"}}
        await state.subscription_registry.broadcast_to_ticket("ticket-1", event)
        assert await ws.receive_json(timeout=2) == event


@pytest.mark.parametrize("scope,identifier", [("device", "device_id"), ("chat", "job_id")])
async def test_non_operator_cannot_subscribe_to_internal_device_or_chat(websocket_auth, scope, identifier):
    websocket_auth.role = "user"
    async with connected_ui() as (ws, state):
        await ws.send_json({"type": f"subscribe_{scope}", identifier: "resource-1", "skip_catchup": True})
        assert (await ws.receive_json(timeout=2))["type"] == "error"


@pytest.mark.parametrize("scope,identifier", [("device", "device_id"), ("chat", "job_id")])
async def test_all_room_types_revalidate_push_and_cleanup_on_session_revocation(websocket_auth, scope, identifier):
    async with connected_ui() as (ws, state):
        await subscribe_ticket(ws)
        await ws.send_json({"type": f"subscribe_{scope}", identifier: "resource-1", "skip_catchup": True})
        assert (await ws.receive_json(timeout=2))["type"] == "catchup_done"
        assert (await ws.receive_json(timeout=2))["type"] == "subscribe_ack"
        websocket_auth.active = False
        broadcaster = getattr(state.subscription_registry, f"broadcast_to_{scope}")
        delivery = asyncio.create_task(broadcaster("resource-1", {"type": f"{scope}_event_committed"}))
        try:
            assert (await ws.receive(timeout=2)).type == WSMsgType.CLOSE
        finally:
            await delivery
        assert not state.subscription_registry.ticket_subscribers
        assert not state.subscription_registry.device_subscribers
        assert not state.subscription_registry.chat_subscribers


async def test_second_ui_hello_cannot_reuse_existing_rooms_as_another_role(websocket_auth):
    async with connected_ui() as (ws, state):
        await subscribe_ticket(ws)
        websocket_auth.role = "user"
        await ws.send_json({"type": "ui_hello", "token": "second-session"})
        assert (await ws.receive(timeout=2)).type == WSMsgType.CLOSE
        assert not state.subscription_registry.ticket_subscribers


@pytest.mark.parametrize("scope,identifier,change", [
    ("ticket", "ticket_id", "inactive"),
    ("ticket", "ticket_id", "role"),
    ("ticket", "ticket_id", "queue"),
    ("device", "device_id", "inactive"),
    ("device", "device_id", "role"),
    ("chat", "job_id", "inactive"),
    ("chat", "job_id", "role"),
])
async def test_catchup_stops_before_next_event_when_access_is_revoked(
    monkeypatch, websocket_auth, scope, identifier, change
):
    websocket_auth.role = "support"

    class ReplayEvents(list):
        def __iter__(self):
            yield self[0]
            if change == "inactive":
                websocket_auth.active = False
            elif change == "role":
                websocket_auth.role = "user"
            else:
                websocket_auth.queue_allowed = False
            yield self[1]

    events = ReplayEvents([
        SimpleNamespace(
            id=event_id, event_type="internal_update", operation_id=None,
            agent_seq=None, device_seq=None, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ts=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"secret": f"event-{event_id}"},
        )
        for event_id in (1, 2)
    ])

    async def get_events_since_id(self, **kwargs):
        return events

    monkeypatch.setattr(ui_handler.TicketEventsRepo, "get_events_since_id", get_events_since_id, raising=False)

    class ReplayRepo:
        def __init__(self, session):
            pass

        async def get_events_since_id(self, **kwargs):
            return events

    monkeypatch.setattr(repos_module, "DeviceEventsRepo", ReplayRepo, raising=False)
    monkeypatch.setattr(repos_module, "JobEventsRepo", ReplayRepo)
    async with connected_ui() as (ws, state):
        await ws.send_json({"type": f"subscribe_{scope}", identifier: "resource-1"})
        first = await ws.receive_json(timeout=2)
        assert first["type"] == f"{scope}_event_committed"
        assert first.get("payload", first.get("event")) == {"secret": "event-1"}
        revoked = await ws.receive(timeout=2)
        assert revoked.type == WSMsgType.CLOSE
        assert revoked.data == 4003
        assert not state.subscription_registry.ticket_subscribers
        assert not state.subscription_registry.device_subscribers
        assert not state.subscription_registry.chat_subscribers


async def test_ticketless_catchup_completion_keeps_original_ticket_acl(monkeypatch, websocket_auth):
    websocket_auth.role = "support"

    class CompletionRevocationEvents(list):
        def __getitem__(self, key):
            item = super().__getitem__(key)
            if key == -1:
                websocket_auth.queue_allowed = False
            return item

    events = CompletionRevocationEvents([SimpleNamespace(
        id=1, event_type="internal_update", operation_id=None, agent_seq=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"message": "initial"},
    )])

    async def get_events_since_id(self, **kwargs):
        return events

    monkeypatch.setattr(ui_handler.TicketEventsRepo, "get_events_since_id", get_events_since_id, raising=False)
    async with connected_ui() as (ws, state):
        await ws.send_json({"type": "subscribe_ticket", "ticket_id": "resource-1"})
        assert (await ws.receive_json(timeout=2))["type"] == "ticket_event_committed"
        assert (await ws.receive(timeout=2)).type == WSMsgType.CLOSE
        assert not state.subscription_registry.ticket_subscribers
