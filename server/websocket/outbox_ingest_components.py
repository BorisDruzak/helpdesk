"""
Focused components for outbox ingest pipeline decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from websocket.batch_ack_manager import NackInfo


@dataclass
class EnvelopeValidationResult:
    ok: bool
    outbox_id: Optional[str]
    trace_id: Optional[str]
    error_message: Optional[str] = None


class OutboxEnvelopeValidator:
    def validate(self, message: dict[str, Any]) -> EnvelopeValidationResult:
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            return EnvelopeValidationResult(
                ok=False,
                outbox_id=None,
                trace_id=message.get("trace_id"),
                error_message="Payload is not a dict",
            )
        outbox_id = payload.get("outbox_id")
        trace_id = message.get("trace_id")
        if not outbox_id:
            return EnvelopeValidationResult(
                ok=False,
                outbox_id=None,
                trace_id=trace_id,
                error_message="Missing outbox_id in payload",
            )
        return EnvelopeValidationResult(ok=True, outbox_id=str(outbox_id), trace_id=trace_id)


class OutboxAckDecisionService:
    def add_validation_nack(self, *, batch_ack_manager, device_id: str, outbox_id: str, trace_id: str, error: str) -> None:
        batch_ack_manager.add_nack(
            device_id=device_id,
            outbox_id=outbox_id,
            trace_id=trace_id,
            nack_info=NackInfo(
                retryable=False,
                error_code="VALIDATION_ERROR",
                error_message=error,
                retry_after_sec=None,
            ),
        )

    def add_duplicate_ack(self, *, batch_ack_manager, device_id: str, outbox_id: str, trace_id: str) -> None:
        batch_ack_manager.add_ack(device_id=device_id, outbox_id=outbox_id, trace_id=trace_id)


@dataclass
class OutboxPersistenceOutcome:
    should_continue: bool
    persisted: bool
    outbox_id: Optional[str]
    trace_id: Optional[str]


class OutboxPersistenceService:
    """
    Persistence step wrapper. The actual storage logic can live in injected handler
    while this service owns the persistence contract.
    """

    async def persist(
        self,
        *,
        legacy_handler,
        message: dict[str, Any],
        ctx: Any,
        batch_ack_manager: Any,
        event_validator: Any,
        envelope: EnvelopeValidationResult,
    ) -> OutboxPersistenceOutcome:
        should_continue = await legacy_handler(
            ws=ctx.ws,
            data=message,
            state=ctx.state,
            agent_id=ctx.agent_id,
            batch_ack_manager=batch_ack_manager,
            event_validator=event_validator,
        )
        return OutboxPersistenceOutcome(
            should_continue=should_continue,
            persisted=bool(should_continue),
            outbox_id=envelope.outbox_id,
            trace_id=envelope.trace_id,
        )


class OutboxEventPublishService:
    async def publish_after_commit(self, *, ctx: Any, outcome: OutboxPersistenceOutcome) -> None:
        if not outcome.persisted or not outcome.outbox_id:
            return
        cache_key = "_recent_outbox_processed"
        cache = getattr(ctx.state, cache_key, None)
        if cache is None:
            cache = {}
            setattr(ctx.state, cache_key, cache)
        cache[outcome.outbox_id] = {"trace_id": outcome.trace_id}
        if len(cache) > 2000:
            for key in list(cache.keys())[:800]:
                cache.pop(key, None)
        logger.debug(
            f"[outbox_pipeline] processed outbox_id={outcome.outbox_id} trace_id={outcome.trace_id}"
        )
