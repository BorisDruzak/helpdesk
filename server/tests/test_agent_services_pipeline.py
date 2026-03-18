from types import SimpleNamespace
import asyncio

import pytest

from websocket.agent_services import CommandResultService, OutboxIngestService
from websocket.contexts import AgentConnectionContext


class _BatchAckManagerStub:
    def __init__(self):
        self.acks = []
        self.nacks = []
        self.flushed = 0

    def add_ack(self, device_id, outbox_id, trace_id):
        self.acks.append((device_id, outbox_id, trace_id))

    def add_nack(self, device_id, outbox_id, trace_id, nack_info):
        self.nacks.append((device_id, outbox_id, trace_id, nack_info))

    def has_pending(self, _device_id):
        return bool(self.acks or self.nacks)

    async def flush(self, _ws, _device_id):
        self.flushed += 1


@pytest.mark.asyncio
async def test_command_result_service_resolves_pending_future():
    async def legacy_handler(**_kwargs):
        return None

    service = CommandResultService(legacy_handler=legacy_handler)
    fut = asyncio.get_event_loop().create_future()
    agent_info = {"metadata": {"pending_command_futures": {"req-1": fut}}}
    state = SimpleNamespace(get_agent=lambda _agent_id: agent_info)
    ctx = AgentConnectionContext(ws=SimpleNamespace(), request=SimpleNamespace(), state=state, agent_id="dev-1")

    await service.handle(
        {
            "type": "command_result",
            "request_id": "req-1",
            "payload": {"status": "success", "data": {}, "error": {}, "meta": {}},
        },
        ctx,
    )

    assert fut.done()
    assert fut.result()["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_outbox_ingest_duplicate_is_acked_without_legacy_rewrite():
    calls = {"legacy": 0}

    async def legacy_handler(**_kwargs):
        calls["legacy"] += 1
        return True

    batch = _BatchAckManagerStub()
    service = OutboxIngestService(
        legacy_handler=legacy_handler,
        batch_ack_manager=batch,
        event_validator=SimpleNamespace(),
    )
    state = SimpleNamespace()
    ctx = AgentConnectionContext(ws=SimpleNamespace(), request=SimpleNamespace(), state=state, agent_id="dev-1")
    msg = {
        "type": "outbox_item",
        "trace_id": "tr-1",
        "payload": {"outbox_id": "ob-1", "item_type": "job_event"},
        "meta": {"actor_role": "agent"},
    }

    # First ingest goes through persistence path.
    assert await service.handle(msg, ctx) is True
    # Duplicate ingest should be ACKed and must not call legacy handler again.
    assert await service.handle(msg, ctx) is True

    assert calls["legacy"] == 1
    assert ("dev-1", "ob-1", "tr-1") in batch.acks
