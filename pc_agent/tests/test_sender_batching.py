from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.sender import WSOutboxFlusher
from ws_agent import WSAgent


pytestmark = pytest.mark.no_db


def _make_outbox_item(*, outbox_id: int, device_seq: int) -> dict:
    return {
        "id": outbox_id,
        "payload": {"event": "tools_changed", "tool_count": outbox_id},
        "device_seq": device_seq,
        "agent_seq": None,
        "ticket_id": None,
        "job_id": None,
        "event_id": None,
        "attempts": 0,
    }


class _DbManagerStub:
    def __init__(self, batch: list[dict]) -> None:
        self.batch = batch
        self.failed: list[tuple[list[int], str]] = []
        self.leases: list[tuple[list[int], float]] = []

    async def claim_outbox_batch(self, *, limit: int, lease_sec: int) -> list[dict]:
        return self.batch[:limit]

    async def mark_outbox_failed(self, outbox_ids, reason: str) -> None:
        self.failed.append((list(outbox_ids), reason))

    async def update_outbox_lease(self, outbox_ids, lease_until: float) -> None:
        self.leases.append((list(outbox_ids), lease_until))


@pytest.mark.asyncio
async def test_sender_uses_batch_envelope_when_server_supports_it():
    db = _DbManagerStub(
        [
            _make_outbox_item(outbox_id=101, device_seq=1),
            _make_outbox_item(outbox_id=102, device_seq=2),
        ]
    )
    flusher = WSOutboxFlusher(db_manager=db, device_id="device-1")
    flusher.supports_outbox_batch = True
    sent: list[dict] = []

    async def _send(msg_type, request_id, payload, ticket_id=None, job_id=None, trace_id=None):
        sent.append(
            {
                "msg_type": msg_type,
                "request_id": request_id,
                "payload": payload,
                "ticket_id": ticket_id,
                "job_id": job_id,
                "trace_id": trace_id,
            }
        )

    result = await flusher._send_pending_batch(_send)

    assert result is True
    assert len(sent) == 1
    assert sent[0]["msg_type"] == "outbox_items_batch"
    assert len(sent[0]["payload"]["items"]) == 2
    assert all(item["type"] == "outbox_item" for item in sent[0]["payload"]["items"])
    assert set(flusher.inflight_deadlines) == {101, 102}


@pytest.mark.asyncio
async def test_sender_falls_back_to_single_outbox_items_without_batch_capability():
    db = _DbManagerStub(
        [
            _make_outbox_item(outbox_id=201, device_seq=11),
            _make_outbox_item(outbox_id=202, device_seq=12),
        ]
    )
    flusher = WSOutboxFlusher(db_manager=db, device_id="device-1")
    flusher.supports_outbox_batch = False
    sent: list[dict] = []

    async def _send(msg_type, request_id, payload, ticket_id=None, job_id=None, trace_id=None):
        sent.append(
            {
                "msg_type": msg_type,
                "request_id": request_id,
                "payload": payload,
                "ticket_id": ticket_id,
                "job_id": job_id,
                "trace_id": trace_id,
            }
        )

    result = await flusher._send_pending_batch(_send)

    assert result is True
    assert [item["msg_type"] for item in sent] == ["outbox_item", "outbox_item"]
    assert set(flusher.inflight_deadlines) == {201, 202}


@pytest.mark.asyncio
async def test_ws_agent_enables_batch_outbox_after_handshake_ack(tmp_path):
    agent = WSAgent(data_root=tmp_path, install_root=tmp_path / "install")
    agent.flusher = SimpleNamespace(supports_outbox_batch=False)

    async def _publish_connection_state(_state, _detail):
        return None

    agent._publish_connection_state = _publish_connection_state

    await agent.handle_message(
        SimpleNamespace(),
        json.dumps(
            {
                "type": "handshake_ack",
                "payload": {
                    "server_capabilities": ["protocol_v3", "outbox_batch_v1"],
                },
            }
        ),
    )

    assert "outbox_batch_v1" in agent.server_capabilities
    assert agent.flusher.supports_outbox_batch is True
