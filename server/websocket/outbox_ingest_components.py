"""
Focused components for outbox ingest pipeline decomposition.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from websocket.batch_ack_manager import NackInfo
from tickets.statuses import enrich_chat_payload_with_requester_name


@dataclass
class EnvelopeValidationResult:
    ok: bool
    outbox_id: Optional[str]
    trace_id: Optional[str]
    error_message: Optional[str] = None


class OutboxEnvelopeValidator:
    def validate(self, message: dict[str, Any]) -> EnvelopeValidationResult:
        trace_raw = message.get("trace_id")
        trace_id = str(trace_raw).strip() if trace_raw else None
        payload = message.get("payload", {})
        if not isinstance(payload, dict):
            return EnvelopeValidationResult(
                ok=False,
                outbox_id=None,
                trace_id=trace_id or str(uuid.uuid4()),
                error_message="Payload is not a dict",
            )
        outbox_id = payload.get("outbox_id")
        if not outbox_id:
            return EnvelopeValidationResult(
                ok=False,
                outbox_id=None,
                trace_id=trace_id or str(uuid.uuid4()),
                error_message="Missing outbox_id in payload",
            )
        if not trace_id:
            return EnvelopeValidationResult(
                ok=False,
                outbox_id=str(outbox_id),
                trace_id=str(uuid.uuid4()),
                error_message="Missing trace_id in envelope",
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
    decision: str
    outbox_id: Optional[str]
    trace_id: Optional[str]
    retryable: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    persisted: bool = False
    duplicate: bool = False
    event_type: Optional[str] = None
    ticket_id: Optional[str] = None
    operation_id: Optional[str] = None
    payload_event: Optional[dict[str, Any]] = None
    created_event_id: Optional[int] = None
    created_at: Optional[Any] = None


class OutboxPersistenceService:
    """
    Persistence step wrapper. The actual storage logic can live in injected handler
    while this service owns the persistence contract.
    """

    async def persist(
        self,
        *,
        message: dict[str, Any],
        ctx: Any,
        event_validator: Any,
        envelope: EnvelopeValidationResult,
    ) -> OutboxPersistenceOutcome:
        from app.db import get_session
        from app.repos import DeviceEventsRepo, TicketEventsRepo
        from config import ENABLE_DB_PERSISTENCE

        payload = message.get("payload", {})
        item_type = payload.get("item_type", "unknown")
        if item_type != "job_event":
            return OutboxPersistenceOutcome(
                should_continue=True,
                decision="ack",
                outbox_id=envelope.outbox_id,
                trace_id=envelope.trace_id,
                persisted=False,
            )
        event_raw = payload.get("event", {})
        if not isinstance(event_raw, dict):
            return OutboxPersistenceOutcome(
                should_continue=True,
                decision="nack",
                outbox_id=envelope.outbox_id,
                trace_id=envelope.trace_id,
                retryable=False,
                error_code="VALIDATION_ERROR",
                error_message="payload.event must be an object",
                persisted=False,
            )
        event = dict(event_raw)
        ticket_id = event.get("ticket_id")
        event_type = event.get("event", "unknown")
        agent_seq = payload.get("agent_seq")
        device_seq = payload.get("device_seq")
        event_id = payload.get("event_id")
        if not ticket_id:
            device_validation = await event_validator.validate_device_event(
                device_id=ctx.agent_id,
                device_seq=device_seq,
                event_type=event_type,
                payload=event,
            )
            if not device_validation.valid:
                return OutboxPersistenceOutcome(
                    should_continue=True,
                    decision="nack",
                    outbox_id=envelope.outbox_id,
                    trace_id=envelope.trace_id,
                    retryable=device_validation.retryable,
                    error_code=device_validation.error_code or "VALIDATION_ERROR",
                    error_message=device_validation.error_message or "Device event validation failed",
                )
        if not ENABLE_DB_PERSISTENCE:
            return OutboxPersistenceOutcome(
                should_continue=True,
                decision="ack",
                outbox_id=envelope.outbox_id,
                trace_id=envelope.trace_id,
                persisted=False,
                event_type=event_type,
                ticket_id=ticket_id,
                payload_event=event,
            )
        try:
            async with get_session() as session:
                if not ticket_id:
                    device_events = DeviceEventsRepo(session)
                    inserted_id = await device_events.add_event(
                        device_id=ctx.agent_id,
                        device_seq=device_seq,
                        event_type=event_type,
                        payload=event,
                        trace_id=envelope.trace_id,
                        event_id=event_id,
                    )
                    await session.commit()
                    return OutboxPersistenceOutcome(
                        should_continue=True,
                        decision="ack",
                        outbox_id=envelope.outbox_id,
                        trace_id=envelope.trace_id,
                        persisted=inserted_id is not None,
                        duplicate=inserted_id is None,
                        event_type=event_type,
                        payload_event=event,
                    )

                validation = await event_validator.validate_ticket_event(
                    session=session,
                    ticket_id=ticket_id,
                    device_id=ctx.agent_id,
                    agent_seq=agent_seq,
                    event_type=event_type,
                    payload=event,
                )
                if not validation.valid:
                    await session.rollback()
                    return OutboxPersistenceOutcome(
                        should_continue=True,
                        decision="nack",
                        outbox_id=envelope.outbox_id,
                        trace_id=envelope.trace_id,
                        retryable=validation.retryable,
                        error_code=validation.error_code or "VALIDATION_ERROR",
                        error_message=validation.error_message or "Ticket event validation failed",
                    )
                ticket_events = TicketEventsRepo(session)
                if event_type == "chat_message":
                    ticket = await ticket_events.get_ticket(ticket_id)
                    if ticket is not None:
                        event = enrich_chat_payload_with_requester_name(ticket, event)
                inserted = await ticket_events.add_event(
                    ticket_id=ticket_id,
                    device_id=ctx.agent_id,
                    agent_seq=agent_seq,
                    event_type=event_type,
                    payload=event,
                    trace_id=envelope.trace_id,
                    event_id=event_id,
                    operation_id=event.get("operation_id"),
                )
                await session.commit()
                if inserted is None:
                    return OutboxPersistenceOutcome(
                        should_continue=True,
                        decision="ack",
                        outbox_id=envelope.outbox_id,
                        trace_id=envelope.trace_id,
                        persisted=False,
                        duplicate=True,
                        event_type=event_type,
                        ticket_id=ticket_id,
                        payload_event=event,
                    )
                inserted_id, created_at = inserted
                return OutboxPersistenceOutcome(
                    should_continue=True,
                    decision="ack",
                    outbox_id=envelope.outbox_id,
                    trace_id=envelope.trace_id,
                    persisted=True,
                    duplicate=False,
                    event_type=event_type,
                    ticket_id=ticket_id,
                    operation_id=event.get("operation_id"),
                    payload_event=event,
                    created_event_id=inserted_id,
                    created_at=created_at,
                )
        except Exception as exc:
            logger.error(f"[outbox_pipeline] persistence failed: {exc}", exc_info=True)
            return OutboxPersistenceOutcome(
                should_continue=True,
                decision="nack",
                outbox_id=envelope.outbox_id,
                trace_id=envelope.trace_id,
                retryable=True,
                error_code="SERVER_ERROR",
                error_message=f"Internal server error: {exc}",
            )


class OutboxEventPublishService:
    async def publish_after_commit(self, *, ctx: Any, outcome: OutboxPersistenceOutcome) -> None:
        if not outcome.outbox_id:
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
        if outcome.ticket_id and outcome.created_event_id and outcome.payload_event:
            try:
                from websocket.ui_handler import push_ticket_event_committed

                await push_ticket_event_committed(
                    ctx.state,
                    ticket_id=outcome.ticket_id,
                    event_id=outcome.created_event_id,
                    event_type=outcome.event_type or "unknown",
                    operation_id=outcome.operation_id,
                    agent_seq=None,
                    created_at=outcome.created_at,
                    payload=outcome.payload_event,
                )
            except Exception as exc:
                logger.warning(f"[outbox_pipeline] push_ticket_event_committed failed: {exc}")
        if outcome.payload_event:
            job_id = outcome.payload_event.get("job_id")
            if job_id:
                try:
                    from websocket.job_event_persistence import persist_job_event
                    from websocket.protocol import push_chat_event_to_ui

                    ctx.state.append_job_event(job_id, outcome.payload_event)
                    await persist_job_event(job_id, outcome.payload_event)
                    await push_chat_event_to_ui(ctx.state, job_id, outcome.payload_event)
                except Exception as exc:
                    logger.warning(f"[outbox_pipeline] job side effects failed: {exc}")
        if outcome.event_type == "module_state_changed" and getattr(ctx, "agent_id", None):
            try:
                modules_snapshot = outcome.payload_event.get("modules_snapshot") if isinstance(outcome.payload_event, dict) else None
                if isinstance(modules_snapshot, list):
                    from app.db import get_session
                    from websocket.modules_sync import flatten_modules_list, sync_modules_inventory

                    async with get_session() as session:
                        await sync_modules_inventory(
                            session=session,
                            device_id=ctx.agent_id,
                            inventory=flatten_modules_list(modules_snapshot),
                            source="event",
                        )
                        await session.commit()
                    logger.info(
                        "[outbox_pipeline] synced device_modules from module_state_changed: "
                        f"device_id={ctx.agent_id} modules={len(modules_snapshot)}"
                    )

                from modules.reconcile import reconcile_device

                await reconcile_device(
                    device_id=ctx.agent_id,
                    state=ctx.state,
                    reason="event_module_state_changed",
                )
            except Exception as exc:
                logger.warning(f"[outbox_pipeline] reconcile after module_state_changed failed: {exc}")
        logger.debug(
            f"[outbox_pipeline] processed outbox_id={outcome.outbox_id} trace_id={outcome.trace_id}"
        )
