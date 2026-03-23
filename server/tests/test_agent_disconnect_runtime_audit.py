from types import SimpleNamespace

import pytest

from websocket.agent_handler import _handle_agent_disconnect


class _FakeState:
    def __init__(self):
        self.connected = {
            "device-1": {
                "metadata": {"status": "online"},
            }
        }
        self.unregistered = []

    def get_agent(self, device_id):
        return self.connected.get(device_id)

    def unregister_agent(self, device_id):
        self.unregistered.append(device_id)
        self.connected.pop(device_id, None)


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
    connection_ctx = SimpleNamespace(agent_id="device-1")

    await _handle_agent_disconnect(state, connection_ctx)

    assert state.unregistered == ["device-1"]
    assert captured["device_id"] == "device-1"
    assert captured["event_type"] == "agent_offline"
    assert captured["details_json"]["reason"] == "connection_closed"

