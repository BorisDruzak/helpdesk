from __future__ import annotations

from pathlib import Path

import pytest

from pc_agent.core.action_trace import configure_action_trace, get_action_trace_recorder
from pc_agent.ws_agent import WSAgent


class _FakeWs:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ws_agent_uploads_observer_events_and_advances_cursor_after_ack(tmp_path: Path) -> None:
    recorder = configure_action_trace(tmp_path)
    recorder.record(
        recorder.context(source="ws_agent", action="connect", category="runtime"),
        stage="handshake",
        status="ok",
    )
    recorder.record(
        recorder.context(source="launcher", action="apply_update", category="update"),
        stage="apply",
        status="error",
        details={"reason": "download failed"},
    )

    agent = WSAgent(data_root=tmp_path)
    agent.device_id = "00000000-0000-0000-0000-00000000ad01"
    ws = _FakeWs()

    sent = await agent._upload_agent_observer_events_once(ws)

    assert sent == 2
    assert ws.sent[-1]["type"] == "agent_observer_batch"
    assert len(ws.sent[-1]["payload"]["events"]) == 2
    assert agent._pending_agent_observer_upload["max_seq"] == 2
    assert agent._load_agent_observer_upload_cursor() == 0

    await agent._handle_agent_observer_batch_ack({"status": "ok", "accepted_count": 2})

    assert agent._load_agent_observer_upload_cursor() == 2
    assert await agent._upload_agent_observer_events_once(ws) == 0


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_ws_agent_keeps_observer_cursor_when_upload_fails(tmp_path: Path) -> None:
    recorder = configure_action_trace(tmp_path)
    recorder.record(
        recorder.context(source="ws_agent", action="connect", category="runtime"),
        stage="startup",
        status="ok",
    )

    agent = WSAgent(data_root=tmp_path)
    agent.device_id = "00000000-0000-0000-0000-00000000ad11"
    ws = _FakeWs()

    assert await agent._upload_agent_observer_events_once(ws) == 1
    await agent._handle_agent_observer_batch_ack({"status": "error", "accepted_count": 0})

    assert agent._load_agent_observer_upload_cursor() == 0
    assert await agent._upload_agent_observer_events_once(ws) == 1
