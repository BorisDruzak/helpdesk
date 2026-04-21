from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from websocket.agent_services import (
    AgentCommandService,
    OutboxBatchIngestService,
    CommandResultService,
    OutboxAckDecisionService,
    OutboxIngestService,
)
from websocket.command_result_components import (
    CommandResultEventPublisher,
    CommandResultLifecycleOutcome,
    CommandResultNormalizer,
)
from websocket.contexts import AgentConnectionContext
from websocket.outbox_ingest_components import EnvelopeValidationResult, OutboxPersistenceService, OutboxPersistenceOutcome
from websocket.validator import EventValidator


pytestmark = pytest.mark.no_db


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
async def test_command_result_service_resolves_state_level_pending_future_without_runtime_agent():
    service = CommandResultService(legacy_handler=None)
    fut = asyncio.get_event_loop().create_future()

    class _StateStub:
        def __init__(self):
            self.pending = {"req-2": fut}

        def resolve_pending_command_future(self, command_id, result_data):
            future = self.pending.pop(command_id, None)
            if future is None or future.done():
                return False
            future.set_result(result_data)
            return True

        def get_agent(self, _agent_id):
            return None

    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=_StateStub(),
        agent_id="dev-1",
    )

    await service.handle(
        {
            "type": "command_result",
            "request_id": "req-2",
            "payload": {"status": "success", "data": {}, "error": {}, "meta": {}},
        },
        ctx,
    )

    assert fut.done()
    assert fut.result()["request_id"] == "req-2"


@pytest.mark.asyncio
async def test_outbox_ingest_duplicate_is_acked_without_persistence_repeat():
    batch = _BatchAckManagerStub()
    service = OutboxIngestService(
        legacy_handler=None,
        batch_ack_manager=batch,
        event_validator=EventValidator(),
    )
    state = SimpleNamespace()
    ctx = AgentConnectionContext(ws=SimpleNamespace(), request=SimpleNamespace(), state=state, agent_id="dev-1")
    msg = {
        "type": "outbox_item",
        "trace_id": "tr-1",
        "payload": {
            "outbox_id": "ob-1",
            "item_type": "job_event",
            "device_seq": 101,
            "event": {"event": "tools_changed"},
        },
        "meta": {"actor_role": "agent"},
    }

    # First call (non-duplicate) will hit persistence path and emit final ACK/NACK.
    assert await service.handle(msg, ctx) is True
    # Second call is duplicate in runtime cache and should ACK directly.
    assert await service.handle(msg, ctx) is True

    assert ("dev-1", "ob-1", "tr-1") in batch.acks


@pytest.mark.asyncio
async def test_outbox_batch_ingest_processes_items_and_flushes_once():
    batch = _BatchAckManagerStub()

    class _ItemServiceStub:
        async def handle(self, message, ctx, *, flush_immediately=True):
            batch.add_ack(
                device_id=ctx.agent_id,
                outbox_id=message["payload"]["outbox_id"],
                trace_id=message["trace_id"],
            )
            if flush_immediately:
                await batch.flush(ctx.ws, ctx.agent_id)
            return True

    batch_service = OutboxBatchIngestService(_ItemServiceStub(), batch)
    state = SimpleNamespace()
    ctx = AgentConnectionContext(ws=SimpleNamespace(), request=SimpleNamespace(), state=state, agent_id="dev-1")
    msg = {
        "type": "outbox_items_batch",
        "payload": {
            "items": [
                {
                    "type": "outbox_item",
                    "trace_id": "tr-batch-1",
                    "payload": {
                        "outbox_id": "ob-batch-1",
                        "item_type": "job_event",
                        "device_seq": 201,
                        "event": {"event": "tools_changed"},
                    },
                    "meta": {"actor_role": "agent"},
                },
                {
                    "type": "outbox_item",
                    "trace_id": "tr-batch-2",
                    "payload": {
                        "outbox_id": "ob-batch-2",
                        "item_type": "job_event",
                        "device_seq": 202,
                        "event": {"event": "tools_changed"},
                    },
                    "meta": {"actor_role": "agent"},
                },
            ]
        },
    }

    assert await batch_service.handle(msg, ctx) is True

    assert ("dev-1", "ob-batch-1", "tr-batch-1") in batch.acks
    assert ("dev-1", "ob-batch-2", "tr-batch-2") in batch.acks
    assert batch.flushed == 1


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


@pytest.mark.asyncio
async def test_agent_chat_raise_returns_canonical_ticket_id(monkeypatch):
    sent_messages = []
    queued_commands = []

    class _WsStub:
        async def send_json(self, payload):
            sent_messages.append(payload)

    class _StateStub(SimpleNamespace):
        def __init__(self):
            super().__init__()
            self.sessions = {}
            self.ui_connections = {}
            self.subscription_registry = None
            self.chat_sessions = self.sessions

        def get_agent(self, _agent_id):
            return {"metadata": {"user": "user-1"}}

        def create_chat_session(self, job_id, data):
            self.sessions[job_id] = data

    async def _fake_create_ticket(*args, **kwargs):
        return {"ticket_id": "ticket-canonical-1"}

    async def _fake_send_ws_command(**kwargs):
        queued_commands.append(kwargs)
        return {"status": "queued"}

    @asynccontextmanager
    async def _fake_get_session():
        yield object()

    monkeypatch.setattr("websocket.agent_services.create_ticket_with_side_effects", _fake_create_ticket)
    monkeypatch.setattr("websocket.agent_services.send_ws_command", _fake_send_ws_command)
    monkeypatch.setattr("websocket.agent_services.get_session", _fake_get_session)

    service = AgentCommandService()
    state = _StateStub()
    ctx = AgentConnectionContext(
        ws=_WsStub(),
        request=SimpleNamespace(),
        state=state,
        agent_id="dev-1",
    )

    await service.handle(
        {
            "type": "command",
            "request_id": "req-raise-1",
            "payload": {
                "command": "chat_raise",
                "params": {
                    "title": "Need support",
                    "reason": "agent_initiated",
                    "severity": "warning",
                    "context": {"screen": "main"},
                },
            },
        },
        ctx,
    )
    await asyncio.sleep(0)

    assert sent_messages
    observations = sent_messages[0]["payload"]["data"]["observations"]
    assert observations["job_id"]
    assert observations["ticket_id"] == "ticket-canonical-1"
    assert state.sessions[observations["job_id"]]["ticket_id"] == "ticket-canonical-1"
    assert queued_commands
    assert queued_commands[0]["params"]["params"]["ticket_id"] == "ticket-canonical-1"
