from types import SimpleNamespace
import time
from collections import deque

import pytest

from config import OUTBOX_INGEST_RATE_LIMIT_PER_SEC
from websocket.agent_services import OutboxIngestService
from websocket.contexts import AgentConnectionContext


pytestmark = pytest.mark.db_cleanup("agent_runtime")

class _BatchAckRecorder:
    def __init__(self) -> None:
        self.nacks: list[dict] = []
        self.flush_calls: list[str] = []

    def add_nack(self, *, device_id, outbox_id, trace_id, nack_info):
        self.nacks.append(
            {
                "device_id": device_id,
                "outbox_id": outbox_id,
                "trace_id": trace_id,
                "error_code": nack_info.error_code,
                "retryable": nack_info.retryable,
            }
        )

    async def flush(self, _ws, device_id):
        self.flush_calls.append(device_id)


def _valid_device_outbox_payload(outbox_id: str, device_seq: int) -> dict:
    return {
        "outbox_id": outbox_id,
        "item_type": "job_event",
        "device_seq": device_seq,
        "event": {"event": "tools_changed"},
    }


@pytest.mark.asyncio
async def test_outbox_ingest_guard_returns_unauthorized_nack():
    called = {"legacy": 0}

    async def _legacy_handler(**_kwargs):
        called["legacy"] += 1
        return False

    batch = _BatchAckRecorder()
    service = OutboxIngestService(_legacy_handler, batch_ack_manager=batch, event_validator=SimpleNamespace())
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="device-1",
    )

    handled = await service.handle(
        {
            "type": "outbox_item",
            "trace_id": "trace-1",
            "meta": {"actor_role": "user"},
            "payload": _valid_device_outbox_payload("10", 1),
        },
        ctx,
    )

    assert handled is True
    assert called["legacy"] == 0
    assert len(batch.nacks) == 1
    assert batch.nacks[0]["error_code"] == "UNAUTHORIZED"
    assert batch.flush_calls == ["device-1"]


@pytest.mark.asyncio
async def test_outbox_ingest_guard_returns_rate_limited_nack():
    called = {"legacy": 0}

    async def _legacy_handler(**_kwargs):
        called["legacy"] += 1
        return False

    batch = _BatchAckRecorder()
    state = SimpleNamespace(_outbox_ingest_rate_state={"device-1": deque()})
    window = state._outbox_ingest_rate_state["device-1"]
    # Prefill sliding window to saturation threshold.
    now = time.monotonic()
    for _ in range(OUTBOX_INGEST_RATE_LIMIT_PER_SEC):
        window.append(now)

    service = OutboxIngestService(_legacy_handler, batch_ack_manager=batch, event_validator=SimpleNamespace())
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=state,
        agent_id="device-1",
    )

    handled = await service.handle(
        {
            "type": "outbox_item",
            "trace_id": "trace-2",
            "meta": {"actor_role": "agent"},
            "payload": _valid_device_outbox_payload("11", 2),
        },
        ctx,
    )

    assert handled is True
    assert called["legacy"] == 0
    assert len(batch.nacks) == 1
    assert batch.nacks[0]["error_code"] == "RATE_LIMITED"
    assert batch.nacks[0]["retryable"] is True
    assert batch.flush_calls == ["device-1"]
