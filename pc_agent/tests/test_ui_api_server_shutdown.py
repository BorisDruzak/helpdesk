import asyncio
import json
import sys
from pathlib import Path

import aiohttp
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pc_agent.ui_bridge.api_server import UiApiServer
from pc_agent.ui_bridge.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_replays_latest_connection_state_for_late_subscriber():
    bus = EventBus()

    await bus.publish(
        {
            "event_type": "connection_state",
            "data": {"state": "connected", "detail": "WS подключён"},
            "timestamp": "2026-04-13T10:43:31Z",
        }
    )

    replay = bus.get_replay_events()
    assert len(replay) == 1
    assert replay[0]["event_type"] == "connection_state"
    assert replay[0]["data"]["state"] == "connected"


@pytest.mark.asyncio
async def test_ui_api_server_stop_does_not_hang_with_active_sse_client():
    server = UiApiServer(EventBus(), host="127.0.0.1", port=0)
    await server.start()

    sockets = getattr(getattr(server.site, "_server", None), "sockets", None)
    assert sockets
    port = sockets[0].getsockname()[1]

    session = aiohttp.ClientSession()
    response = await session.get(
        f"http://127.0.0.1:{port}/ui/events",
        headers={"Accept": "text/event-stream"},
    )

    try:
        assert response.status == 200
        await asyncio.wait_for(response.content.readline(), timeout=1.0)
        await asyncio.wait_for(server.stop(), timeout=1.5)
        assert server.runner is None
        assert server.site is None
    finally:
        response.close()
        await session.close()


@pytest.mark.asyncio
async def test_ui_api_server_replays_connection_state_to_new_sse_client():
    bus = EventBus()
    await bus.publish(
        {
            "event_type": "connection_state",
            "data": {"state": "connected", "detail": "WS подключён"},
            "timestamp": "2026-04-13T10:43:31Z",
        }
    )

    server = UiApiServer(bus, host="127.0.0.1", port=0)
    await server.start()

    sockets = getattr(getattr(server.site, "_server", None), "sockets", None)
    assert sockets
    port = sockets[0].getsockname()[1]

    session = aiohttp.ClientSession()
    response = await session.get(
        f"http://127.0.0.1:{port}/ui/events",
        headers={"Accept": "text/event-stream"},
    )

    try:
        assert response.status == 200
        first_line = await asyncio.wait_for(response.content.readline(), timeout=1.0)
        assert first_line == b": connected\n"

        blank_line = await asyncio.wait_for(response.content.readline(), timeout=1.0)
        assert blank_line == b"\n"

        data_line = await asyncio.wait_for(response.content.readline(), timeout=1.0)
        assert data_line.startswith(b"data: ")
        payload = json.loads(data_line[len(b"data: ") :].decode("utf-8"))
        assert payload["event_type"] == "connection_state"
        assert payload["data"]["state"] == "connected"
        assert payload["data"]["detail"] == "WS подключён"
    finally:
        response.close()
        await session.close()
        await server.stop()


@pytest.mark.asyncio
async def test_ui_api_server_runtime_status_and_logs_endpoints():
    server = UiApiServer(
        EventBus(),
        host="127.0.0.1",
        port=0,
        on_get_runtime_status=lambda: {
            "device_id": "device-1",
            "connection_state": "connected",
            "log_runtime": {"level": "INFO", "file": "logs/agent.log"},
        },
        on_get_runtime_logs=lambda payload: {
            "source": payload.get("source"),
            "text": "line-1\nline-2",
            "lines": ["line-1", "line-2"],
        },
    )
    await server.start()

    sockets = getattr(getattr(server.site, "_server", None), "sockets", None)
    assert sockets
    port = sockets[0].getsockname()[1]

    session = aiohttp.ClientSession()
    try:
        async with session.get(f"http://127.0.0.1:{port}/ui/agent/status") as response:
            assert response.status == 200
            payload = await response.json()
            assert payload["status"] == "ok"
            assert payload["device_id"] == "device-1"
            assert payload["connection_state"] == "connected"

        async with session.get(f"http://127.0.0.1:{port}/ui/agent/logs?source=agent&lines=25") as response:
            assert response.status == 200
            payload = await response.json()
            assert payload["status"] == "ok"
            assert payload["source"] == "agent"
            assert payload["text"] == "line-1\nline-2"
            assert payload["lines"] == ["line-1", "line-2"]
    finally:
        await session.close()
        await server.stop()


@pytest.mark.asyncio
async def test_ui_api_server_update_endpoint():
    server = UiApiServer(
        EventBus(),
        host="127.0.0.1",
        port=0,
        on_trigger_update=lambda payload: {
            "status": "accepted",
            "message": "Update request sent",
            "recommendation": {
                "recommended_version": "3.1.3",
                "recommended_channel": "stable",
            },
            "payload_echo": payload,
        },
    )
    await server.start()

    sockets = getattr(getattr(server.site, "_server", None), "sockets", None)
    assert sockets
    port = sockets[0].getsockname()[1]

    session = aiohttp.ClientSession()
    try:
        async with session.post(f"http://127.0.0.1:{port}/ui/agent/update", json={"reason": "manual"}) as response:
            assert response.status == 200
            payload = await response.json()
            assert payload["status"] == "accepted"
            assert payload["recommendation"]["recommended_version"] == "3.1.3"
            assert payload["payload_echo"]["reason"] == "manual"
    finally:
        await session.close()
        await server.stop()


@pytest.mark.asyncio
async def test_ui_api_server_automation_endpoints():
    server = UiApiServer(
        EventBus(),
        host="127.0.0.1",
        port=0,
        on_get_automation_status=lambda: {
            "window_visible": True,
            "active_ticket_id": "ticket-1",
        },
        on_run_automation=lambda payload: {
            "status": "ok",
            "action": payload.get("action"),
            "echo": payload,
        },
    )
    await server.start()

    sockets = getattr(getattr(server.site, "_server", None), "sockets", None)
    assert sockets
    port = sockets[0].getsockname()[1]

    session = aiohttp.ClientSession()
    try:
        async with session.get(f"http://127.0.0.1:{port}/ui/automation/status") as response:
            assert response.status == 200
            payload = await response.json()
            assert payload["status"] == "ok"
            assert payload["window_visible"] is True
            assert payload["active_ticket_id"] == "ticket-1"

        async with session.post(
            f"http://127.0.0.1:{port}/ui/automation/run",
            json={"action": "window.show", "force": True},
        ) as response:
            assert response.status == 200
            payload = await response.json()
            assert payload["status"] == "ok"
            assert payload["action"] == "window.show"
            assert payload["echo"]["force"] is True
    finally:
        await session.close()
        await server.stop()
