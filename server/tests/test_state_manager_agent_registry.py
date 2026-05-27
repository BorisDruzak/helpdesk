import asyncio

import pytest

from state_manager import StateManager


pytestmark = pytest.mark.no_db


class _WsStub:
    def __init__(self, *, closed: bool = False) -> None:
        self.closed = closed


def test_register_agent_replaces_connection_but_preserves_current_runtime_entry():
    state = StateManager()
    first_ws = _WsStub()
    second_ws = _WsStub()

    first_metadata = {"status": "online", "connected_at": 1.0, "connection_id": "conn-1"}
    second_metadata = {"status": "online", "connected_at": 2.0, "connection_id": "conn-2"}

    previous = state.register_agent("device-1", first_ws, first_metadata)
    assert previous is None

    previous = state.register_agent("device-1", second_ws, second_metadata)

    assert previous is not None
    assert previous["ws"] is first_ws
    assert state.get_agent("device-1")["ws"] is second_ws
    assert state.get_agent("device-1")["metadata"]["connection_id"] == "conn-2"
    assert state.unregister_agent("device-1", expected_connection_id="conn-1") is False
    assert state.get_agent("device-1")["ws"] is second_ws
    assert state.unregister_agent("device-1", expected_connection_id="conn-2") is True
    assert state.get_agent("device-1") is None


def test_diagnostic_probe_does_not_replace_runtime_agent_or_look_online():
    state = StateManager()
    runtime_ws = _WsStub()
    probe_ws = _WsStub()

    state.register_agent(
        "device-1",
        runtime_ws,
        {
            "status": "online",
            "connected_at": 1.0,
            "connection_id": "runtime-1",
            "client_kind": "agent_runtime",
        },
    )

    previous = state.register_agent(
        "device-1",
        probe_ws,
        {
            "status": "online",
            "connected_at": 2.0,
            "connection_id": "probe-1",
            "client_kind": "diagnostic_probe",
        },
    )

    assert previous is None
    assert state.get_agent("device-1")["ws"] is runtime_ws
    assert state.get_agent("device-1")["metadata"]["connection_id"] == "runtime-1"
    assert state.is_current_agent_connection("device-1", expected_connection_id="probe-1") is False
    assert state.is_agent_online("device-1") is True


@pytest.mark.asyncio
async def test_pending_command_future_survives_runtime_reconnect():
    state = StateManager()
    first_ws = _WsStub()
    second_ws = _WsStub()
    future = asyncio.get_event_loop().create_future()

    state.register_agent("device-1", first_ws, {"status": "online", "connected_at": 1.0, "connection_id": "conn-1"})
    state.register_pending_command_future(
        "op-1",
        future,
        device_id="device-1",
        connection_id="conn-1",
    )

    state.register_agent("device-1", second_ws, {"status": "online", "connected_at": 2.0, "connection_id": "conn-2"})

    assert state.resolve_pending_command_future("op-1", {"request_id": "op-1", "payload": {"status": "success"}}) is True
    assert future.done()
    assert future.result()["request_id"] == "op-1"
