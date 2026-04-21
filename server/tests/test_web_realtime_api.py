import asyncio

import pytest
from aiohttp.test_utils import TestClient
from app.db.engine import async_sessionmaker
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.middleware import WEB_SESSION_COOKIE_NAME
from tests.conftest import TEST_UI_SUPPORT_TOKEN
from tests.test_helpers import create_test_ticket


async def ws_ui_cookie_hello(ws, token: str = TEST_UI_SUPPORT_TOKEN):
    await ws.send_json({"type": "ui_hello"})
    hello_ack = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
    assert hello_ack["type"] == "ui_hello_ack"
    assert hello_ack["role"] == "support"
    return hello_ack


async def collect_subscription_messages(ws):
    messages = []
    saw_catchup_done = False
    saw_subscribe_ack = False

    while not (saw_catchup_done and saw_subscribe_ack):
        msg = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
        messages.append(msg)
        if msg.get("type") == "catchup_done":
            saw_catchup_done = True
        elif msg.get("type") == "subscribe_ack":
            saw_subscribe_ack = True

    return messages


@pytest.mark.asyncio
async def test_web_realtime_bootstrap_returns_ws_ui_bridge_contract(test_client: TestClient):
    response = await test_client.get(
        "/api/web/realtime/bootstrap",
        headers={"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"},
    )

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"] == {
        "transport": "ws_ui_bridge",
        "auth_mode": "session_cookie",
        "hello_message_type": "ui_hello",
        "socket_url": "/ws_ui",
        "ping_interval_ms": 20000,
        "channels": [
            {
                "channel": "support.queue",
                "scope": "ticket",
                "subscribe_message_type": "subscribe_ticket",
                "unsubscribe_message_type": "unsubscribe_ticket",
                "supports_catchup": True,
                "supports_live_only": True,
            },
            {
                "channel": "ticket.stream",
                "scope": "ticket",
                "subscribe_message_type": "subscribe_ticket",
                "unsubscribe_message_type": "unsubscribe_ticket",
                "supports_catchup": True,
                "supports_live_only": True,
            },
            {
                "channel": "admin.devices",
                "scope": "device",
                "subscribe_message_type": "subscribe_device",
                "unsubscribe_message_type": "unsubscribe_device",
                "supports_catchup": True,
                "supports_live_only": True,
            },
            {
                "channel": "tech.feed",
                "scope": "device",
                "subscribe_message_type": "subscribe_device",
                "unsubscribe_message_type": "unsubscribe_device",
                "supports_catchup": True,
                "supports_live_only": True,
            },
        ],
    }


@pytest.mark.asyncio
async def test_ws_ui_hello_accepts_http_only_web_session_cookie(test_client: TestClient):
    ws = await test_client.ws_connect(
        "/ws_ui",
        headers={"Cookie": f"{WEB_SESSION_COOKIE_NAME}={TEST_UI_SUPPORT_TOKEN}"},
    )

    await ws_ui_cookie_hello(ws)
    await ws.close()


@pytest.mark.asyncio
async def test_ws_ui_subscribe_ticket_skip_catchup_returns_live_only_ack(
    test_client: TestClient,
    test_agent,
    test_engine,
):
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        await events_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="test_event",
            payload={"message": "history-1"},
        )
        await events_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="test_event",
            payload={"message": "history-2"},
        )
        await session.commit()

    ws = await test_client.ws_connect(
        "/ws_ui",
        headers={"Cookie": f"{WEB_SESSION_COOKIE_NAME}={TEST_UI_SUPPORT_TOKEN}"},
    )
    await ws_ui_cookie_hello(ws)

    await ws.send_json(
        {
            "type": "subscribe_ticket",
            "ticket_id": ticket_id,
            "since_event_id": 0,
            "skip_catchup": True,
        }
    )

    messages = await collect_subscription_messages(ws)

    assert [msg for msg in messages if msg.get("type") == "ticket_event_committed"] == []
    catchup_done = next(msg for msg in messages if msg.get("type") == "catchup_done")
    assert catchup_done == {
        "type": "catchup_done",
        "scope": "ticket",
        "id": ticket_id,
        "last_event_id": 0,
        "truncated": False,
    }
    subscribe_ack = next(msg for msg in messages if msg.get("type") == "subscribe_ack")
    assert subscribe_ack["ticket_id"] == ticket_id
    assert subscribe_ack["since_event_id"] == 0

    await ws.close()
