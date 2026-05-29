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


ALLOWED_OUTBOX_ITEM_TYPES = {"job_event"}


def _clean_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _validate_outbox_contract(message: dict[str, Any]) -> Optional[str]:
    payload = message.get("payload")
    if not isinstance(payload, dict):
        return "Payload is not a dict"

    item_type = payload.get("item_type")
    if item_type not in ALLOWED_OUTBOX_ITEM_TYPES:
        return f"Unsupported item_type: {item_type!r}"

    event_raw = payload.get("event")
    if not isinstance(event_raw, dict):
        return "payload.event must be an object"

    agent_seq = payload.get("agent_seq")
    device_seq = payload.get("device_seq")
    has_agent_seq = agent_seq is not None
    has_device_seq = device_seq is not None
    if has_agent_seq == has_device_seq:
        return "Protocol V3 outbox item must set exactly one of agent_seq or device_seq"

    top_level_ticket_id = _clean_optional_str(message.get("ticket_id"))
    event_ticket_id = _clean_optional_str(event_raw.get("ticket_id"))

    if has_agent_seq:
        if not top_level_ticket_id:
            return "Ticket event requires top-level ticket_id"
        if event_ticket_id and event_ticket_id != top_level_ticket_id:
            return "event.ticket_id mismatch with top-level ticket_id"
        return None

    if top_level_ticket_id or event_ticket_id:
        return "Device event must not include ticket_id context"
    return None


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
        contract_error = _validate_outbox_contract(message)
        if contract_error:
            return EnvelopeValidationResult(
                ok=False,
                outbox_id=str(outbox_id),
                trace_id=trace_id,
                error_message=contract_error,
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
        contract_error = _validate_outbox_contract(message)
        if contract_error:
            return OutboxPersistenceOutcome(
                should_continue=True,
                decision="nack",
                outbox_id=envelope.outbox_id,
                trace_id=envelope.trace_id,
                retryable=False,
                error_code="VALIDATION_ERROR",
                error_message=contract_error,
                persisted=False,
            )
        event_raw = payload.get("event", {})
        event = dict(event_raw)
        event_type = event.get("event", "unknown")
        agent_seq = payload.get("agent_seq")
        device_seq = payload.get("device_seq")
        is_ticket_event = agent_seq is not None and device_seq is None
        ticket_id = _clean_optional_str(message.get("ticket_id")) if is_ticket_event else None
        event_id = payload.get("event_id")
        if not is_ticket_event:
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
                if not is_ticket_event:
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
                        created_event_id=inserted_id,
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
    async def _enqueue_toolset_refresh(
        self,
        *,
        ctx: Any,
        outcome: OutboxPersistenceOutcome,
        reason: str,
    ) -> None:
        device_id = getattr(ctx, "agent_id", None)
        if not device_id:
            return
        payload = outcome.payload_event if isinstance(outcome.payload_event, dict) else {}
        reported_hash_raw = payload.get("toolset_hash")
        reported_hash = str(reported_hash_raw).strip() if reported_hash_raw else None
        try:
            from app.db import get_session
            from app.repos import DevicesRepo, OperationsRepo

            async with get_session() as session:
                devices_repo = DevicesRepo(session)
                device = await devices_repo.get_by_device_id(device_id)
                if not device:
                    return
                if (
                    reported_hash
                    and device.current_toolset_hash == reported_hash
                    and device.current_toolset_snapshot_id
                ):
                    logger.debug(
                        "[outbox_pipeline] skip list_tools after toolset event: "
                        f"device_id={device_id} hash={reported_hash} already current"
                    )
                    return
                op_repo = OperationsRepo(session)
                if await op_repo.has_pending_list_tools(device_id):
                    logger.debug(
                        "[outbox_pipeline] skip list_tools after toolset event: "
                        f"device_id={device_id} already has pending list_tools"
                    )
                    return

            from websocket.protocol import enqueue_command_async

            command_id = await enqueue_command_async(
                state=ctx.state,
                device_id=device_id,
                command="list_tools",
                params={},
                actor_role="server",
                trace_id=outcome.trace_id,
                require_online=False,
            )
            async with get_session() as session:
                devices_repo = DevicesRepo(session)
                await devices_repo.update_toolset_refresh_time(device_id)
                await session.commit()
            logger.info(
                "[outbox_pipeline] enqueued list_tools after toolset event: "
                f"device_id={device_id} reason={reason} command_id={command_id} "
                f"reported_hash={reported_hash}"
            )
        except Exception as exc:
            logger.warning(
                "[outbox_pipeline] list_tools refresh after toolset event failed: "
                f"device_id={device_id} reason={reason} error={exc}"
            )

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
                try:
                    from app.db import get_session
                    from diagnostics.recipe_execution_service import RecipeExecutionService

                    async with get_session() as session:
                        await RecipeExecutionService(session, state=ctx.state).resume_waiting_dependencies_for_device(ctx.agent_id)
                        await session.commit()
                except Exception as resume_exc:
                    logger.warning(f"[outbox_pipeline] recipe dependency resume after module_state_changed failed: {resume_exc}")
            except Exception as exc:
                logger.warning(f"[outbox_pipeline] reconcile after module_state_changed failed: {exc}")
            await self._enqueue_toolset_refresh(
                ctx=ctx,
                outcome=outcome,
                reason="module_state_changed",
            )
        if outcome.event_type == "tools_changed" and getattr(ctx, "agent_id", None):
            try:
                from app.db import get_session
                from diagnostics.recipe_execution_service import RecipeExecutionService

                async with get_session() as session:
                    await RecipeExecutionService(session, state=ctx.state).resume_waiting_dependencies_for_device(ctx.agent_id)
                    await session.commit()
            except Exception as resume_exc:
                logger.warning(f"[outbox_pipeline] recipe dependency resume after tools_changed failed: {resume_exc}")
            await self._enqueue_toolset_refresh(
                ctx=ctx,
                outcome=outcome,
                reason="tools_changed",
            )
        logger.debug(
            f"[outbox_pipeline] processed outbox_id={outcome.outbox_id} trace_id={outcome.trace_id}"
        )
