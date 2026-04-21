from types import SimpleNamespace

import pytest

from websocket.agent_handler import _handle_agent_disconnect


class _FakeState:
    def __init__(self):
        self.current_ws = object()
        self.connected = {
            "device-1": {
                "ws": self.current_ws,
                "metadata": {"status": "online", "connection_id": "conn-1"},
            }
        }
        self.unregistered = []

    def get_agent(self, device_id):
        return self.connected.get(device_id)

    def is_current_agent_connection(self, device_id, *, expected_ws=None, expected_connection_id=None):
        current = self.connected.get(device_id)
        if current is None:
            return False
        if expected_ws is not None and current.get("ws") is not expected_ws:
            return False
        metadata = current.get("metadata", {})
        if expected_connection_id is not None and metadata.get("connection_id") != expected_connection_id:
            return False
        return True

    def set_agent_status(self, device_id, status, *, expected_ws=None, expected_connection_id=None):
        if not self.is_current_agent_connection(
            device_id,
            expected_ws=expected_ws,
            expected_connection_id=expected_connection_id,
        ):
            return False
        self.connected[device_id]["metadata"]["status"] = status
        return True

    def unregister_agent(self, device_id, *, expected_ws=None, expected_connection_id=None):
        self.unregistered.append((device_id, expected_ws, expected_connection_id))
        current = self.connected.get(device_id)
        if current is None:
            return False
        if expected_ws is not None and current.get("ws") is not expected_ws:
            return False
        metadata = current.get("metadata", {})
        if expected_connection_id is not None and metadata.get("connection_id") != expected_connection_id:
            return False
        self.connected.pop(device_id, None)
        return True


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_handle_agent_disconnect_writes_runtime_audit(monkeypatch):
    captured = {}

    async def _fake_write_agent_runtime_audit(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "websocket.agent_handler.write_agent_runtime_audit",
        _fake_write_agent_runtime_audit,
    )

    state = _FakeState()
    connection_ctx = SimpleNamespace(
        agent_id="device-1",
        ws=state.current_ws,
        connection_id="conn-1",
    )

    await _handle_agent_disconnect(state, connection_ctx)

    assert state.unregistered == [("device-1", state.current_ws, "conn-1")]
    assert captured["device_id"] == "device-1"
    assert captured["event_type"] == "agent_offline"
    assert captured["details_json"]["reason"] == "connection_closed"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_handle_agent_disconnect_ignores_superseded_connection(monkeypatch):
    captured = {}

    async def _fake_write_agent_runtime_audit(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "websocket.agent_handler.write_agent_runtime_audit",
        _fake_write_agent_runtime_audit,
    )

    state = _FakeState()
    stale_ws = object()
    connection_ctx = SimpleNamespace(
        agent_id="device-1",
        ws=stale_ws,
        connection_id="conn-stale",
    )

    await _handle_agent_disconnect(state, connection_ctx)

    assert state.connected["device-1"]["metadata"]["status"] == "online"
    assert state.unregistered == []
    assert captured == {}
