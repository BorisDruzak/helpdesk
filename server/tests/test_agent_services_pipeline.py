from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from websocket.agent_services import CommandResultService, OutboxIngestService
from websocket.command_result_components import (
    CommandResultEventPublisher,
    CommandResultLifecycleOutcome,
    CommandResultNormalizer,
)
from websocket.contexts import AgentConnectionContext
from websocket.outbox_ingest_components import (
    EnvelopeValidationResult,
    OutboxAckDecisionService,
    OutboxPersistenceService,
    OutboxPersistenceOutcome,
)
from websocket.validator import EventValidator


class _BatchAckManagerStub:
    def __init__(self):
        self.acks = []
        self.nacks = []
        self.flushed = 0

    def add_ack(self, device_id, outbox_id, trace_id):
        self.acks.append((device_id, outbox_id, trace_id))

    def add_nack(self, device_id, outbox_id, trace_id, nack_info):
        self.nacks.append((device_id, outbox_id, trace_id, nack_info.error_code))

    def has_pending(self, _device_id):
        return bool(self.acks or self.nacks)

    async def flush(self, _ws, _device_id):
        self.flushed += 1


@pytest.mark.asyncio
async def test_command_result_service_resolves_pending_future():
    service = CommandResultService(legacy_handler=None)
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
async def test_outbox_ingest_duplicate_is_acked_without_persistence_repeat():
    batch = _BatchAckManagerStub()
    service = OutboxIngestService(
        legacy_handler=None,
        batch_ack_manager=batch,
        event_validator=SimpleNamespace(),
    )
    state = SimpleNamespace()
    ctx = AgentConnectionContext(ws=SimpleNamespace(), request=SimpleNamespace(), state=state, agent_id="dev-1")
    msg = {
        "type": "outbox_item",
        "trace_id": "tr-1",
        "payload": {"outbox_id": "ob-1", "item_type": "job_event", "event": {}},
        "meta": {"actor_role": "agent"},
    }

    # First call (non-duplicate) will hit persistence path and emit final ACK/NACK.
    assert await service.handle(msg, ctx) is True
    # Second call is duplicate in runtime cache and should ACK directly.
    assert await service.handle(msg, ctx) is True

    assert ("dev-1", "ob-1", "tr-1") in batch.acks


@pytest.mark.asyncio
async def test_outbox_ack_decision_validation_nack():
    ack = OutboxAckDecisionService()
    batch = _BatchAckManagerStub()
    ctx = AgentConnectionContext(ws=SimpleNamespace(), request=SimpleNamespace(), state=SimpleNamespace(), agent_id="dev-1")
    check = EnvelopeValidationResult(ok=False, outbox_id="ob-2", trace_id="tr-2", error_message="bad payload")

    result = await ack.reject_invalid_envelope(batch_ack_manager=batch, ctx=ctx, envelope_check=check)

    assert result is True
    assert batch.nacks
    assert batch.nacks[0][3] == "VALIDATION_ERROR"
    assert batch.flushed == 1


@pytest.mark.asyncio
async def test_outbox_ack_decision_final_ack_and_nack():
    ack = OutboxAckDecisionService()
    batch = _BatchAckManagerStub()
    ctx = AgentConnectionContext(ws=SimpleNamespace(), request=SimpleNamespace(), state=SimpleNamespace(), agent_id="dev-1")

    await ack.apply_final_decision(
        batch_ack_manager=batch,
        ctx=ctx,
        outcome=OutboxPersistenceOutcome(
            should_continue=True,
            decision="ack",
            outbox_id="ob-ack",
            trace_id="tr-ack",
            persisted=True,
        ),
    )
    await ack.apply_final_decision(
        batch_ack_manager=batch,
        ctx=ctx,
        outcome=OutboxPersistenceOutcome(
            should_continue=True,
            decision="nack",
            outbox_id="ob-nack",
            trace_id="tr-nack",
            retryable=False,
            error_code="VALIDATION_ERROR",
            error_message="invalid",
        ),
    )

    assert ("dev-1", "ob-ack", "tr-ack") in batch.acks
    assert any(item[1] == "ob-nack" and item[3] == "VALIDATION_ERROR" for item in batch.nacks)


@pytest.mark.asyncio
async def test_command_result_event_publisher_updates_runtime_cache():
    normalizer = CommandResultNormalizer()
    publisher = CommandResultEventPublisher()
    message = {"request_id": "req-cache", "payload": {"status": "running", "data": {}, "error": {}, "meta": {}}}
    normalized = normalizer.normalize(message)
    state = SimpleNamespace()
    ctx = AgentConnectionContext(ws=SimpleNamespace(), request=SimpleNamespace(), state=state, agent_id="dev-1")
    outcome = CommandResultLifecycleOutcome(processed=True, command_id="req-cache", status="running")

    await publisher.publish_after_lifecycle(normalized, ctx, outcome)

    assert getattr(state, "_recent_operation_updates")["req-cache"]["status"] == "running"


@pytest.mark.asyncio
async def test_outbox_persistence_rejects_device_event_without_device_seq():
    service = OutboxPersistenceService()
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="dev-1",
    )
    message = {
        "type": "outbox_item",
        "trace_id": "tr-no-seq",
        "payload": {
            "outbox_id": "ob-no-seq",
            "item_type": "job_event",
            "event": {"event": "tools_changed"},
        },
    }
    envelope = EnvelopeValidationResult(ok=True, outbox_id="ob-no-seq", trace_id="tr-no-seq")
    outcome = await service.persist(
        message=message,
        ctx=ctx,
        event_validator=EventValidator(),
        envelope=envelope,
    )

    assert outcome.decision == "nack"
    assert outcome.error_code == "VALIDATION_ERROR"
    assert "device_seq" in (outcome.error_message or "")
