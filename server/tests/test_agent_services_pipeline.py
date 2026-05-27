from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import websocket.agent_services as agent_services
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


def test_agent_services_keeps_command_lifecycle_db_available():
    assert agent_services.DB_AVAILABLE is True


class _BatchAckManagerStub:
    def __init__(self):
        self.acks = []
        self.nacks = []
        self.flushed = 0

    def add_ack(self, device_id, outbox_id, trace_id):
        self.acks.append((device_id, outbox_id, trace_id))

    def add_nack(self, device_id, outbox_id, trace_id, nack_info):
        self.nacks.append(
            (
                device_id,
                outbox_id,
                trace_id,
                nack_info.error_code,
                nack_info.error_message,
                nack_info.retryable,
            )
        )

    def has_pending(self, _device_id):
        return bool(self.acks or self.nacks)

    async def flush(self, _ws, _device_id):
        self.flushed += 1


def _outbox_message(
    *,
    outbox_id: str = "ob-contract",
    trace_id: str | None = "tr-contract",
    ticket_id: str | None = None,
    event_ticket_id: str | None = None,
    agent_seq: int | None = None,
    device_seq: int | None = None,
    item_type: str = "job_event",
    actor_role: str = "agent",
    event_name: str = "tools_changed",
):
    event = {"event": event_name}
    if event_ticket_id is not None:
        event["ticket_id"] = event_ticket_id
    message = {
        "type": "outbox_item",
        "payload": {
            "outbox_id": outbox_id,
            "item_type": item_type,
            "event": event,
        },
        "meta": {"actor_role": actor_role},
    }
    if trace_id is not None:
        message["trace_id"] = trace_id
    if ticket_id is not None:
        message["ticket_id"] = ticket_id
    if agent_seq is not None:
        message["payload"]["agent_seq"] = agent_seq
    if device_seq is not None:
        message["payload"]["device_seq"] = device_seq
    return message


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

    class _AckPersistence:
        async def persist(self, *, message, ctx, event_validator, envelope):
            return OutboxPersistenceOutcome(
                should_continue=True,
                decision="ack",
                outbox_id=envelope.outbox_id,
                trace_id=envelope.trace_id,
                persisted=True,
            )

    service._persistence = _AckPersistence()
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
async def test_outbox_ingest_retryable_nack_does_not_mark_duplicate():
    batch = _BatchAckManagerStub()
    service = OutboxIngestService(
        legacy_handler=None,
        batch_ack_manager=batch,
        event_validator=EventValidator(),
    )

    class _FlakyPersistence:
        def __init__(self):
            self.calls = 0

        async def persist(self, *, message, ctx, event_validator, envelope):
            self.calls += 1
            if self.calls == 1:
                return OutboxPersistenceOutcome(
                    should_continue=True,
                    decision="nack",
                    outbox_id=envelope.outbox_id,
                    trace_id=envelope.trace_id,
                    retryable=True,
                    error_code="SERVER_ERROR",
                    error_message="transient db error",
                )
            return OutboxPersistenceOutcome(
                should_continue=True,
                decision="ack",
                outbox_id=envelope.outbox_id,
                trace_id=envelope.trace_id,
                persisted=True,
            )

    persistence = _FlakyPersistence()
    service._persistence = persistence
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="dev-1",
    )
    msg = {
        "type": "outbox_item",
        "trace_id": "tr-retry-1",
        "payload": {
            "outbox_id": "ob-retry-1",
            "item_type": "job_event",
            "device_seq": 301,
            "event": {"event": "tools_changed"},
        },
        "meta": {"actor_role": "agent"},
    }

    assert await service.handle(msg, ctx) is True
    assert await service.handle(msg, ctx) is True

    assert persistence.calls == 2
    assert any(item[1] == "ob-retry-1" and item[3] == "SERVER_ERROR" for item in batch.nacks)
    assert ("dev-1", "ob-retry-1", "tr-retry-1") in batch.acks


@pytest.mark.asyncio
async def test_outbox_ingest_missing_trace_id_returns_validation_nack():
    batch = _BatchAckManagerStub()
    service = OutboxIngestService(
        legacy_handler=None,
        batch_ack_manager=batch,
        event_validator=EventValidator(),
    )
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="dev-1",
    )
    msg = {
        "type": "outbox_item",
        "payload": {
            "outbox_id": "ob-missing-trace",
            "item_type": "job_event",
            "device_seq": 302,
            "event": {"event": "tools_changed"},
        },
        "meta": {"actor_role": "agent"},
    }

    assert await service.handle(msg, ctx) is True

    assert batch.nacks
    device_id, outbox_id, trace_id, error_code = batch.nacks[0][:4]
    assert device_id == "dev-1"
    assert outbox_id == "ob-missing-trace"
    assert trace_id
    assert error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "message", "expected_text"),
    [
        (
            "both_seq",
            _outbox_message(
                outbox_id="ob-both-seq",
                ticket_id="ticket-1",
                event_ticket_id="ticket-1",
                agent_seq=1,
                device_seq=1,
            ),
            "exactly one",
        ),
        (
            "neither_seq",
            _outbox_message(outbox_id="ob-neither-seq"),
            "exactly one",
        ),
        (
            "top_ticket_only_device_seq",
            _outbox_message(
                outbox_id="ob-top-ticket-device",
                ticket_id="ticket-1",
                device_seq=2,
            ),
            "ticket_id",
        ),
        (
            "ticket_event_without_top_ticket_id",
            _outbox_message(
                outbox_id="ob-agent-no-ticket",
                event_ticket_id="ticket-1",
                agent_seq=3,
            ),
            "ticket_id",
        ),
        (
            "event_ticket_mismatch",
            _outbox_message(
                outbox_id="ob-ticket-mismatch",
                ticket_id="ticket-1",
                event_ticket_id="ticket-2",
                agent_seq=4,
            ),
            "mismatch",
        ),
        (
            "unknown_item_type",
            _outbox_message(
                outbox_id="ob-unknown-type",
                ticket_id="ticket-1",
                event_ticket_id="ticket-1",
                agent_seq=5,
                item_type="unknown_live_probe_type",
            ),
            "item_type",
        ),
        (
            "event_payload_not_object",
            {
                "type": "outbox_item",
                "trace_id": "tr-event-not-object",
                "ticket_id": "ticket-1",
                "payload": {
                    "outbox_id": "ob-event-not-object",
                    "item_type": "job_event",
                    "agent_seq": 6,
                    "event": "not-an-object",
                },
                "meta": {"actor_role": "agent"},
            },
            "event",
        ),
    ],
)
async def test_outbox_ingest_rejects_malformed_contract_before_persistence(case_name, message, expected_text):
    batch = _BatchAckManagerStub()
    service = OutboxIngestService(
        legacy_handler=None,
        batch_ack_manager=batch,
        event_validator=EventValidator(),
    )

    class _NoPersistence:
        async def persist(self, *, message, ctx, event_validator, envelope):
            raise AssertionError(f"{case_name} should be rejected before persistence")

    service._persistence = _NoPersistence()
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="dev-1",
    )

    assert await service.handle(message, ctx) is True

    assert not batch.acks
    assert batch.nacks
    assert batch.nacks[0][1] == message["payload"]["outbox_id"]
    assert batch.nacks[0][3] == "VALIDATION_ERROR"
    assert batch.nacks[0][5] is False
    assert expected_text in batch.nacks[0][4]


@pytest.mark.asyncio
async def test_outbox_ingest_wrong_actor_role_still_returns_unauthorized():
    batch = _BatchAckManagerStub()
    service = OutboxIngestService(
        legacy_handler=None,
        batch_ack_manager=batch,
        event_validator=EventValidator(),
    )

    class _NoPersistence:
        async def persist(self, *, message, ctx, event_validator, envelope):
            raise AssertionError("unauthorized actor should be rejected before persistence")

    service._persistence = _NoPersistence()
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="dev-1",
    )
    msg = _outbox_message(
        outbox_id="ob-wrong-actor",
        ticket_id="ticket-1",
        event_ticket_id="ticket-1",
        agent_seq=7,
        actor_role="user",
    )

    assert await service.handle(msg, ctx) is True

    assert not batch.acks
    assert batch.nacks
    assert batch.nacks[0][3] == "UNAUTHORIZED"


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
async def test_outbox_persistence_unknown_ticket_nacks_without_insert(monkeypatch):
    service = OutboxPersistenceService()
    inserted_ticket_events = []

    class _FakeSession:
        async def commit(self):
            raise AssertionError("unknown ticket must not commit")

        async def rollback(self):
            pass

    @asynccontextmanager
    async def _fake_get_session():
        yield _FakeSession()

    class _TicketEventsRepo:
        def __init__(self, session):
            self.session = session

        async def get_ticket(self, ticket_id):
            return None

        async def add_event(self, **kwargs):
            inserted_ticket_events.append(kwargs)
            raise AssertionError("unknown ticket must not insert")

    monkeypatch.setattr("app.db.get_session", _fake_get_session)
    monkeypatch.setattr("app.repos.TicketEventsRepo", _TicketEventsRepo)
    monkeypatch.setattr("websocket.validator.TicketEventsRepo", _TicketEventsRepo)
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="dev-1",
    )
    msg = _outbox_message(
        outbox_id="ob-unknown-ticket",
        trace_id="tr-unknown-ticket",
        ticket_id="ticket-missing",
        event_ticket_id="ticket-missing",
        agent_seq=8,
    )

    outcome = await service.persist(
        message=msg,
        ctx=ctx,
        event_validator=EventValidator(),
        envelope=EnvelopeValidationResult(ok=True, outbox_id="ob-unknown-ticket", trace_id="tr-unknown-ticket"),
    )

    assert outcome.decision == "nack"
    assert outcome.error_code == "UNKNOWN_TICKET"
    assert inserted_ticket_events == []


@pytest.mark.asyncio
async def test_outbox_persistence_valid_ticket_event_uses_top_level_ticket_id(monkeypatch):
    service = OutboxPersistenceService()
    inserted_ticket_events = []

    class _FakeSession:
        async def commit(self):
            pass

        async def rollback(self):
            pass

    @asynccontextmanager
    async def _fake_get_session():
        yield _FakeSession()

    class _TicketEventsRepo:
        def __init__(self, session):
            self.session = session

        async def get_ticket(self, ticket_id):
            return SimpleNamespace(ticket_id=ticket_id, device_id="dev-1")

        async def add_event(self, **kwargs):
            inserted_ticket_events.append(kwargs)
            return (321, "created-at")

    monkeypatch.setattr("app.db.get_session", _fake_get_session)
    monkeypatch.setattr("app.repos.TicketEventsRepo", _TicketEventsRepo)
    monkeypatch.setattr("websocket.validator.TicketEventsRepo", _TicketEventsRepo)
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="dev-1",
    )
    msg = _outbox_message(
        outbox_id="ob-valid-ticket",
        trace_id="tr-valid-ticket",
        ticket_id="ticket-valid",
        agent_seq=9,
        event_name="tool_call_result",
    )

    outcome = await service.persist(
        message=msg,
        ctx=ctx,
        event_validator=EventValidator(),
        envelope=EnvelopeValidationResult(ok=True, outbox_id="ob-valid-ticket", trace_id="tr-valid-ticket"),
    )

    assert outcome.decision == "ack"
    assert outcome.persisted is True
    assert outcome.ticket_id == "ticket-valid"
    assert inserted_ticket_events[0]["ticket_id"] == "ticket-valid"
    assert inserted_ticket_events[0]["agent_seq"] == 9


@pytest.mark.asyncio
async def test_outbox_persistence_valid_device_event_uses_device_seq(monkeypatch):
    service = OutboxPersistenceService()
    inserted_device_events = []

    class _FakeSession:
        async def commit(self):
            pass

        async def rollback(self):
            pass

    @asynccontextmanager
    async def _fake_get_session():
        yield _FakeSession()

    class _DeviceEventsRepo:
        def __init__(self, session):
            self.session = session

        async def add_event(self, **kwargs):
            inserted_device_events.append(kwargs)
            return 654

    monkeypatch.setattr("app.db.get_session", _fake_get_session)
    monkeypatch.setattr("app.repos.DeviceEventsRepo", _DeviceEventsRepo)
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=SimpleNamespace(),
        agent_id="dev-1",
    )
    msg = _outbox_message(
        outbox_id="ob-valid-device",
        trace_id="tr-valid-device",
        device_seq=10,
        event_name="tools_changed",
    )

    outcome = await service.persist(
        message=msg,
        ctx=ctx,
        event_validator=EventValidator(),
        envelope=EnvelopeValidationResult(ok=True, outbox_id="ob-valid-device", trace_id="tr-valid-device"),
    )

    assert outcome.decision == "ack"
    assert outcome.persisted is True
    assert outcome.event_type == "tools_changed"
    assert inserted_device_events[0]["device_id"] == "dev-1"
    assert inserted_device_events[0]["device_seq"] == 10


@pytest.mark.asyncio
async def test_agent_chat_raise_returns_canonical_ticket_id(monkeypatch):
    sent_messages = []
    queued_commands = []
    events = []

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
            events.append(("create_chat_session", data["ticket_id"]))
            self.sessions[job_id] = data

    async def _fake_create_ticket(*args, **kwargs):
        events.append(("create_ticket", kwargs.get("title")))
        return {"ticket_id": "ticket-canonical-1"}

    def _fake_description(**kwargs):
        return "fake description"

    async def _fake_send_ws_command(**kwargs):
        events.append(("send_ws_command", kwargs.get("command")))
        queued_commands.append(kwargs)
        return {"status": "queued"}

    class _FakeDbSession:
        async def commit(self):
            pass

    @asynccontextmanager
    async def _fake_get_session():
        yield _FakeDbSession()

    monkeypatch.setattr("websocket.agent_services.create_ticket_with_side_effects", _fake_create_ticket)
    monkeypatch.setattr("websocket.agent_services.build_agent_raise_description", _fake_description)
    monkeypatch.setattr("websocket.agent_services.TICKET_CREATE_AVAILABLE", True)
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
    assert events[0][0] == "create_ticket"
    assert ("create_chat_session", "ticket-canonical-1") in events


@pytest.mark.asyncio
async def test_agent_chat_raise_create_failure_returns_error_without_side_effects(monkeypatch):
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
        raise RuntimeError("db create failed")

    def _fake_description(**kwargs):
        return "fake description"

    async def _fake_send_ws_command(**kwargs):
        queued_commands.append(kwargs)
        return {"status": "queued"}

    class _FakeDbSession:
        async def commit(self):
            raise AssertionError("failed create must not commit")

    @asynccontextmanager
    async def _fake_get_session():
        yield _FakeDbSession()

    monkeypatch.setattr("websocket.agent_services.create_ticket_with_side_effects", _fake_create_ticket)
    monkeypatch.setattr("websocket.agent_services.build_agent_raise_description", _fake_description)
    monkeypatch.setattr("websocket.agent_services.TICKET_CREATE_AVAILABLE", True)
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
            "request_id": "req-raise-fail",
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
    payload = sent_messages[0]["payload"]
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "TICKET_CREATE_FAILED"
    assert "ticket_id" not in payload.get("data", {}).get("observations", {})
    assert state.sessions == {}
    assert queued_commands == []
