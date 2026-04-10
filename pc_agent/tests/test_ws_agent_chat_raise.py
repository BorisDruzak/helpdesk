import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.ws_agent import WSAgent


class _WsStub:
    def __init__(self):
        self.payloads = []

    async def send_json(self, payload):
        self.payloads.append(payload)


@pytest.mark.asyncio
async def test_chat_raise_returns_ticket_and_job_ids(tmp_path):
    agent = WSAgent(data_root=tmp_path, install_root=tmp_path / "install")
    agent.device_id = "device-test-1"
    agent._agent_ws = _WsStub()

    async def _complete_future():
        await asyncio.sleep(0)
        pending = next(iter(agent._pending_chat_raise.values()))
        pending.set_result(
            {
                "payload": {
                    "data": {
                        "observations": {
                            "job_id": "job-123",
                            "ticket_id": "ticket-456",
                        }
                    }
                }
            }
        )

    task = asyncio.create_task(_complete_future())
    try:
        result = await agent.chat_raise(title="Need support")
    finally:
        await task

    assert result == {"job_id": "job-123", "ticket_id": "ticket-456"}
    assert agent._agent_ws.payloads
    assert agent._agent_ws.payloads[0]["payload"]["command"] == "chat_raise"
