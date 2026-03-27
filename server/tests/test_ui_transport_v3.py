"""
Integration tests for UI Transport V3.
"""
import pytest
import json
import asyncio
from aiohttp.test_utils import TestClient
from app.db.engine import async_sessionmaker
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.operations_repo import OperationsRepo
from tests.test_helpers import create_test_ticket

TEST_UI_SUPPORT_TOKEN = "test-ui-support-token"
TEST_UI_USER_PREFIX = "test-ui-user:"


async def ws_ui_hello(ws, token: str = TEST_UI_SUPPORT_TOKEN):
    await ws.send_json({"type": "ui_hello", "token": token})
    hello_ack = await ws.receive_json()
    assert hello_ack["type"] == "ui_hello_ack"
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
async def test_subscribe_ticket_with_catchup(test_client: TestClient, test_agent, test_engine):
    """Test subscribe_ticket with catch-up events."""
    # 1. Create ticket and add some events
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # Add some events to the ticket
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        await events_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="test_event",
            payload={"message": "test1"}
        )
        await events_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="test_event",
            payload={"message": "test2"}
        )
        await session.commit()
    
    # 2. Connect WebSocket and subscribe
    ws = await test_client.ws_connect("/ws_ui")
    await ws_ui_hello(ws)
    
    # Subscribe with since_event_id=0 (full history)
    await ws.send_json({
        "type": "subscribe_ticket",
        "ticket_id": ticket_id,
        "since_event_id": 0
    })
    
    # Receive catch-up events
    messages = await collect_subscription_messages(ws)
    
    # Verify catch-up events
    event_messages = [
        m for m in messages
        if m.get("type") == "ticket_event_committed" and m.get("event_type") == "test_event"
    ]
    assert len(event_messages) == 2
    
    # Verify subscribe_ack
    subscribe_ack = [m for m in messages if m.get("type") == "subscribe_ack"]
    assert len(subscribe_ack) == 1
    assert subscribe_ack[0]["ticket_id"] == ticket_id
    
    # Verify catchup_done
    catchup_done = [m for m in messages if m.get("type") == "catchup_done"]
    assert len(catchup_done) == 1
    assert catchup_done[0]["scope"] == "ticket"
    assert catchup_done[0]["id"] == ticket_id
    
    await ws.close()


@pytest.mark.asyncio
async def test_push_ticket_event_committed(test_client: TestClient, test_agent, test_engine):
    """Test that ticket events are pushed to subscribers after commit."""
    # 1. Create ticket
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # 2. Connect WebSocket and subscribe
    ws = await test_client.ws_connect("/ws_ui")
    await ws_ui_hello(ws)
    
    # Subscribe
    await ws.send_json({
        "type": "subscribe_ticket",
        "ticket_id": ticket_id,
        "since_event_id": 0
    })
    
    # Consume catch-up messages
    await collect_subscription_messages(ws)
    
    # 3. Add new event (should trigger push)
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        result = await events_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="test_event",
            payload={"message": "new_event"}
        )
        await session.commit()
        
        if result:
            # Push event (simulate what happens after commit)
            from state_manager import StateManager
            from websocket.ui_handler import push_ticket_event_committed
            state = test_client.app['state']
            inserted_id, created_at = result
            await push_ticket_event_committed(
                state,
                ticket_id=ticket_id,
                event_id=inserted_id,
                event_type="test_event",
                operation_id=None,
                agent_seq=None,
                created_at=created_at,
                payload={"message": "new_event"}
            )
    
    # 4. Receive pushed event
    msg = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
    assert msg["type"] == "ticket_event_committed"
    assert msg["ticket_id"] == ticket_id
    assert msg["event_type"] == "test_event"
    assert msg["payload"]["message"] == "new_event"
    
    await ws.close()


@pytest.mark.asyncio
async def test_push_operation_updated(test_client: TestClient, test_agent, test_engine):
    """Test that operation updates are pushed to subscribers."""
    # 1. Create ticket
    device_id = test_agent.device_id
    ticket_id, _ = await create_test_ticket(test_client, device_id=device_id)
    
    # 2. Create operation
    import uuid
    operation_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        operation = await op_repo.create_operation(
            operation_id=operation_id,
            device_id=device_id,
            kind="tool_call",
            actor_role="support",
            trace_id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            tool_name="test_tool"
        )
        await op_repo.update_status(
            operation_id=operation_id,
            new_status="running",
            expected_statuses=["queued"],
            timestamp_field="started_at",
        )
        await session.commit()
    
    # 3. Connect WebSocket and subscribe
    ws = await test_client.ws_connect("/ws_ui")
    await ws_ui_hello(ws)
    
    # Subscribe
    await ws.send_json({
        "type": "subscribe_ticket",
        "ticket_id": ticket_id,
        "since_event_id": 0
    })
    
    # Consume catch-up messages
    await collect_subscription_messages(ws)
    
    # 4. Update operation status (should trigger push)
    from app.services.operation_service import OperationService
    from websocket.ui_publisher import UiPublisherImpl
    state = test_client.app['state']
    ui_publisher = UiPublisherImpl(state)
    
    async with session_maker() as session:
        op_service = OperationService(session, publisher=ui_publisher)
        await op_service.mark_succeeded(operation_id)
        await session.commit()
    
    # 5. Receive pushed update
    msg = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
    assert msg["type"] == "operation_updated"
    assert msg["operation_id"] == operation_id
    assert msg["status"] == "succeeded"
    
    await ws.close()


@pytest.mark.asyncio
async def test_reconnect_catchup(test_client: TestClient, test_agent, test_engine):
    """Test reconnect with catch-up using since_event_id."""
    # 1. Create ticket and add events
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
            payload={"message": "event1"}
        )
        await events_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="test_event",
            payload={"message": "event2"}
        )
        await session.commit()
    
    # 2. First connection - get all events
    ws1 = await test_client.ws_connect("/ws_ui")
    await ws_ui_hello(ws1)
    
    await ws1.send_json({
        "type": "subscribe_ticket",
        "ticket_id": ticket_id,
        "since_event_id": 0
    })
    
    # Get last_event_id from catchup_done
    last_event_id = 0
    messages = await collect_subscription_messages(ws1)
    catchup_done = next(m for m in messages if m.get("type") == "catchup_done")
    last_event_id = catchup_done.get("last_event_id", 0)
    
    await ws1.close()
    
    # 3. Add more events
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        await events_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="test_event",
            payload={"message": "event3"}
        )
        await session.commit()
    
    # 4. Reconnect with since_event_id
    ws2 = await test_client.ws_connect("/ws_ui")
    await ws_ui_hello(ws2)
    
    await ws2.send_json({
        "type": "subscribe_ticket",
        "ticket_id": ticket_id,
        "since_event_id": last_event_id
    })
    
    # Should only receive new events
    messages = await collect_subscription_messages(ws2)
    
    # Verify only new event received
    event_messages = [
        m for m in messages
        if m.get("type") == "ticket_event_committed" and m.get("event_type") == "test_event"
    ]
    assert len(event_messages) == 1
    assert event_messages[0]["payload"]["message"] == "event3"
    
    await ws2.close()


@pytest.mark.asyncio
async def test_ping_pong(test_client: TestClient):
    """Test ping/pong keepalive."""
    ws = await test_client.ws_connect("/ws_ui")
    await ws_ui_hello(ws)

    # Send ping
    await ws.send_json({"type": "ping"})
    
    # Receive pong
    msg = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
    assert msg["type"] == "pong"
    assert "ts" in msg
    
    await ws.close()


@pytest.mark.asyncio
async def test_subscribe_device_with_catchup(test_client: TestClient, test_agent, test_engine):
    """Test subscribe_device with catch-up events."""
    device_id = test_agent.device_id
    
    # Add some device events
    from app.repos.device_events_repo import DeviceEventsRepo
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = DeviceEventsRepo(session)
        await events_repo.add_event(
            device_id=device_id,
            device_seq=1,
            event_type="test_device_event",
            payload={"message": "device_event1"}
        )
        await events_repo.add_event(
            device_id=device_id,
            device_seq=2,
            event_type="test_device_event",
            payload={"message": "device_event2"}
        )
        await session.commit()
    
    # Connect WebSocket and subscribe
    ws = await test_client.ws_connect("/ws_ui")
    await ws_ui_hello(ws)
    
    # Subscribe with since_event_id=0 (full history)
    await ws.send_json({
        "type": "subscribe_device",
        "device_id": device_id,
        "since_event_id": 0
    })
    
    # Receive catch-up events
    messages = await collect_subscription_messages(ws)
    
    # Verify catch-up events
    event_messages = [m for m in messages if m.get("type") == "device_event_committed"]
    assert len(event_messages) >= 2  # At least 2 events
    
    # Verify subscribe_ack
    subscribe_ack = [m for m in messages if m.get("type") == "subscribe_ack"]
    assert len(subscribe_ack) == 1
    assert subscribe_ack[0]["device_id"] == device_id
    
    # Verify catchup_done
    catchup_done = [m for m in messages if m.get("type") == "catchup_done"]
    assert len(catchup_done) == 1
    assert catchup_done[0]["scope"] == "device"
    assert catchup_done[0]["id"] == device_id
    
    await ws.close()


@pytest.mark.asyncio
async def test_message_read_creates_idempotent_event(test_client: TestClient, test_engine):
    """message_read создаётся один раз и не дублируется при повторном запросе."""
    device_id = "device-read-1"
    user_token = f"{TEST_UI_USER_PREFIX}{device_id}"

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        ticket_id = "ticket-read-1"
        await events_repo.create_ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Read test",
            description="Initial message",
            status="new",
            requester_id=device_id,
        )
        result = await events_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={
                "message_id": "support-msg-1",
                "from": "support",
                "text": "Ответ поддержки",
                "visibility": "public",
            },
        )
        assert result is not None
        support_event_id, _ = result
        await session.commit()

    read_resp = await test_client.post(
        f"/api/tickets/{ticket_id}/read",
        json={"last_read_event_id": support_event_id},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert read_resp.status == 200, await read_resp.text()
    read_data = await read_resp.json()
    assert read_data["status"] == "ok"
    assert read_data["no_op"] is False
    assert read_data["last_read_event_id"] == support_event_id
    assert read_data["messages_read_count"] == 1

    read_again_resp = await test_client.post(
        f"/api/tickets/{ticket_id}/read",
        json={"last_read_event_id": support_event_id},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert read_again_resp.status == 200, await read_again_resp.text()
    read_again_data = await read_again_resp.json()
    assert read_again_data["status"] == "ok"
    assert read_again_data["no_op"] is True

    async with session_maker() as session:
        events_repo = TicketEventsRepo(session)
        events = await events_repo.get_events(ticket_id, event_types=["message_read"])
        assert len(events) == 1
        payload = events[0].payload or {}
        assert payload["actor_id"] == device_id
        assert payload["actor_role"] == "user"
        assert payload["last_read_event_id"] == support_event_id
        assert payload["last_read_message_id"] == "support-msg-1"
        assert payload["messages_read_count"] == 1

