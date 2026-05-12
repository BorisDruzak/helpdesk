from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from app.db import get_session
from app.repos.agent_observer_events_repo import AgentObserverEventsRepo
from app.repos.operations_repo import OperationsRepo
from config import ENABLE_DB_PERSISTENCE, OUTBOX_INGEST_RATE_LIMIT_PER_SEC
from websocket.protocol import push_chat_event_to_ui, send_ws_command
from websocket.batch_ack_manager import NackInfo
from websocket.command_result_components import (
    CommandResultNormalizer,
    CommandResultFutureResolver,
    CommandResultArtifactHandler,
    CommandResultEventPublisher,
    CommandResultLifecycleOutcome,
)
from websocket.outbox_ingest_components import (
    OutboxEnvelopeValidator as OutboxEnvelopeValidatorComponent,
    OutboxAckDecisionService as OutboxAckDecisionComponent,
    OutboxPersistenceService as OutboxPersistenceComponent,
    OutboxEventPublishService as OutboxEventPublishComponent,
)

from .contexts import AgentConnectionContext, EnvelopeContext

try:
    from tickets.create_flow import build_agent_raise_description, create_ticket_with_side_effects

    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class HandshakeService:
    """Validates handshake and registers agent session."""

    def __init__(
        self,
        legacy_handler: Callable[..., Awaitable[tuple[Any, Optional[str], Optional[str], bool]]],
        dispatch_service: Optional[Any] = None,
    ) -> None:
        self._legacy_handler = legacy_handler
        self._dispatch_service = dispatch_service

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> Optional[Any]:
        close_ws, agent_id, device_id, authenticated = await self._legacy_handler(
            ws=ctx.ws,
            data=message,
            request=ctx.request,
            state=ctx.state,
        )
        if close_ws is not None:
            return close_ws

        ctx.agent_id = agent_id or ctx.agent_id
        ctx.device_id = device_id or ctx.device_id
        ctx.authenticated = authenticated

        meta = message.get("meta", {})
        capabilities = meta.get("capabilities", [])
        if isinstance(capabilities, list):
            ctx.capabilities = capabilities
        if ctx.agent_id and hasattr(ctx.state, "get_agent"):
            agent_info = ctx.state.get_agent(ctx.agent_id)
            if agent_info:
                metadata = agent_info.get("metadata", {}) or {}
                ctx.connection_id = metadata.get("connection_id")
                ctx.session_metadata = metadata

        if ctx.device_id and self._dispatch_service is not None:
            try:
                await self._dispatch_service.on_agent_online(ctx.device_id)
            except Exception as exc:
                logger.debug(f"[HandshakeService] on_agent_online skipped: {exc}")

        return None


class CommandAckService:
    """Idempotent handling of command_ack to update operation states."""

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> None:
        if not ctx.agent_id:
            return
        agent_info = ctx.state.get_agent(ctx.agent_id)
        if agent_info:
            agent_info["metadata"]["last_seen"] = time.time()
        payload = message.get("payload", {})
        operation_id = message.get("request_id")
        ack_status = payload.get("status")
        logger.info(
            "[command_ack] received: "
            f"operation_id={operation_id} ack_status={ack_status} "
            f"agent_id={ctx.agent_id} connection_id={ctx.connection_id}"
        )

        if not operation_id:
            logger.warning(f"[command_ack] Missing operation_id (request_id) from agent {ctx.agent_id}")
            return

        if not (DB_AVAILABLE and ENABLE_DB_PERSISTENCE):
            return

        try:
            async with get_session() as session:
                from app.services.operation_service import OperationService

                ui_publisher = ctx.state.ui_publisher if hasattr(ctx.state, "ui_publisher") else None
                op_service = OperationService(session, publisher=ui_publisher)

                if ack_status == "accepted":
                    await op_service.mark_accepted(
                        operation_id=operation_id,
                        expected_statuses=["sent", "queued"],
                    )
                elif ack_status == "rejected":
                    await op_service.mark_failed(
                        operation_id=operation_id,
                        error_code=payload.get("error_code", "REJECTED"),
                        error_message=payload.get("error_message", "Command rejected by agent"),
                        expected_statuses=["sent", "queued"],
                    )
                else:
                    logger.warning(
                        f"[command_ack] Unknown ack_status={ack_status} operation_id={operation_id}"
                    )

                # Коммит выполняет get_session() при выходе; второй commit() не нужен.
        except Exception as exc:
            logger.error(f"[command_ack] Failed to update operation status: {exc}", exc_info=True)


class CommandResultService:
    """Normalizes and persists command_result lifecycle transitions."""

    def __init__(self, legacy_handler: Optional[Callable[..., Awaitable[None]]] = None) -> None:
        self._legacy_handler = legacy_handler
        self._normalizer = CommandResultNormalizer()
        self._lifecycle = OperationLifecycleService()
        self._future_resolver = CommandResultFutureResolver()
        self._event_publisher = CommandResultEventPublisher()
        self._artifact_handler = CommandResultArtifactHandler()

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> None:
        # 1) normalize
        normalized = self._normalizer.normalize(message)
        logger.info(
            "[command_result] received: "
            f"operation_id={normalized.command_id} status={normalized.lifecycle_status} "
            f"agent_id={ctx.agent_id} connection_id={ctx.connection_id}"
        )
        # 2) lifecycle update
        lifecycle_outcome = await self._lifecycle.handle(
            legacy_handler=self._legacy_handler,
            message=message,
            ctx=ctx,
            normalized=normalized,
        )
        # 3) future resolve (sync wait path)
        self._future_resolver.resolve_from_context(normalized.command_id, message, ctx)
        # 4) artifact/result post-process
        await self._artifact_handler.post_process(normalized, ctx, lifecycle_outcome)
        # 5) publish side effects
        await self._event_publisher.publish_after_lifecycle(normalized, ctx, lifecycle_outcome)


class OperationLifecycleService:
    """Lifecycle orchestrator for command_result state transitions."""

    async def handle(
        self,
        legacy_handler: Optional[Callable[..., Awaitable[None]]],
        message: dict[str, Any],
        ctx: AgentConnectionContext,
        normalized: Any,
    ) -> CommandResultLifecycleOutcome:
        if not ctx.agent_id:
            return CommandResultLifecycleOutcome(
                processed=False,
                command_id=normalized.command_id,
                status=normalized.lifecycle_status,
            )
        agent_info = ctx.state.get_agent(ctx.agent_id)
        if agent_info:
            agent_info["metadata"]["last_seen"] = time.time()
            agent_info["metadata"]["last_response"] = message
        if not normalized.command_id:
            return CommandResultLifecycleOutcome(
                processed=False,
                command_id=None,
                status=normalized.lifecycle_status,
            )
        if not (DB_AVAILABLE and ENABLE_DB_PERSISTENCE):
            if legacy_handler is not None:
                await legacy_handler(ws=ctx.ws, data=message, state=ctx.state, agent_id=ctx.agent_id)
                return CommandResultLifecycleOutcome(
                    processed=True,
                    command_id=normalized.command_id,
                    status=normalized.lifecycle_status,
                )
            return CommandResultLifecycleOutcome(
                processed=False,
                command_id=normalized.command_id,
                status=normalized.lifecycle_status,
            )
        try:
            async with get_session() as session:
                from app.repos import DeviceOutboxRepo
                from app.services.operation_service import OperationService

                outbox_repo = DeviceOutboxRepo(session)
                op_service = OperationService(session, publisher=None)
                op_repo = OperationsRepo(session)
                operation_id = normalized.command_id
                operation = await op_repo.get_by_operation_id(operation_id)
                lifecycle_status = normalized.lifecycle_status

                expected_statuses = ["queued", "sent", "accepted", "running", "waiting_consent"]
                processed = True

                if lifecycle_status == "queued":
                    await op_repo.update_status(operation_id, "queued", expected_statuses=["waiting_consent"])
                elif lifecycle_status == "sent":
                    await op_service.mark_sent(operation_id, expected_statuses=["queued", "waiting_consent"])
                elif lifecycle_status == "accepted":
                    await op_service.mark_accepted(operation_id, expected_statuses=["sent", "queued"])
                elif lifecycle_status == "running":
                    await op_service.mark_running(operation_id, expected_statuses=["accepted", "sent", "queued"])
                elif lifecycle_status == "waiting_consent":
                    await op_service.mark_waiting_consent(
                        operation_id,
                        expected_statuses=["accepted", "running", "sent", "queued"],
                    )
                    await outbox_repo.mark_as_delivered(operation_id)
                elif lifecycle_status == "succeeded":
                    result_summary = None
                    observations = normalized.data_payload.get("observations")
                    if isinstance(observations, dict):
                        result_summary = str(observations)[:500]
                    if operation and operation.kind == "agent_update":
                        # P0 contract: update operation becomes terminal only after
                        # reconnect-handshake confirmation of applied version.
                        await op_service.mark_running(
                            operation_id=operation_id,
                            expected_statuses=expected_statuses,
                        )
                        await op_repo.update_status(
                            operation_id=operation_id,
                            new_status="running",
                            expected_statuses=["running"],
                            result_summary=(result_summary or "scheduled")[:500],
                        )
                    elif operation and operation.kind == "cancel_operation":
                        cancel_status = (
                            normalized.data_payload.get("cancel_status")
                            or (observations or {}).get("cancel_status")
                        )
                        target_operation_id = (
                            operation.cancel_target_operation_id
                            or normalized.data_payload.get("target_operation_id")
                            or (observations or {}).get("target_operation_id")
                        )
                        await op_service.mark_succeeded(
                            operation_id=operation_id,
                            result_summary=(result_summary or str(cancel_status or "completed"))[:500],
                            expected_statuses=expected_statuses,
                        )
                        if target_operation_id and cancel_status in {"canceled", "already_finished"}:
                            await op_service.mark_canceled(
                                operation_id=target_operation_id,
                                expected_statuses=["cancel_requested", "running", "accepted", "waiting_consent"],
                            )
                            if operation.ticket_id:
                                from app.repos.ticket_events_repo import TicketEventsRepo

                                events_repo = TicketEventsRepo(session)
                                await events_repo.add_event(
                                    ticket_id=operation.ticket_id,
                                    device_id=operation.device_id,
                                    agent_seq=None,
                                    event_type="op_canceled",
                                    payload={
                                        "operation_id": target_operation_id,
                                        "cancel_operation_id": operation.operation_id,
                                        "cancel_status": cancel_status,
                                    },
                                    trace_id=operation.trace_id,
                                    operation_id=target_operation_id,
                                )
                    else:
                        await op_service.mark_succeeded(
                            operation_id=operation_id,
                            result_summary=result_summary,
                            expected_statuses=expected_statuses,
                        )
                    await outbox_repo.mark_as_delivered(operation_id)
                elif lifecycle_status == "failed":
                    error_code = normalized.error_info.get("code", "UNKNOWN_ERROR")
                    error_message = normalized.error_info.get("message", "Unknown error")
                    await op_service.mark_failed(
                        operation_id=operation_id,
                        error_code=error_code,
                        error_message=error_message,
                        expected_statuses=expected_statuses,
                    )
                    await outbox_repo.mark_as_delivered(operation_id)
                elif lifecycle_status in {"canceled", "cancel_requested"}:
                    if lifecycle_status == "cancel_requested":
                        await op_service.mark_cancel_requested(operation_id, expected_statuses=["queued", "sent", "accepted", "running", "waiting_consent"])
                    else:
                        await op_service.mark_canceled(operation_id, expected_statuses=["cancel_requested", "running", "accepted", "waiting_consent"])
                        await outbox_repo.mark_as_delivered(operation_id)
                else:
                    processed = False
                    logger.warning(
                        "[command_result] unsupported lifecycle status: "
                        f"operation_id={operation_id} status={lifecycle_status}"
                    )

                # Снимок скаляров до выхода из get_session(): после commit/expiry повторный доступ к ORM
                # может вызвать implicit lazy-load → greenlet_spawn / await_only (SQLAlchemy async).
                if (
                    processed
                    and operation is not None
                    and getattr(operation, "playbook_run_id", None)
                    and lifecycle_status in {"succeeded", "failed", "timed_out", "canceled"}
                ):
                    from app.services.playbook_engine import advance_after_terminal

                    terminal_status = "succeeded" if lifecycle_status == "succeeded" else "failed"
                    result_payload = (
                        {"data": normalized.data_payload}
                        if terminal_status == "succeeded"
                        else {"error": normalized.error_info}
                    )
                    await advance_after_terminal(
                        session,
                        ctx.state,
                        operation_id,
                        terminal_status,
                        result_payload,
                    )

                operation_kind_out = operation.kind if operation else None
                ticket_id_out = operation.ticket_id if operation else None
                trace_id_out = operation.trace_id if operation else None

                if not processed and legacy_handler is not None:
                    await legacy_handler(ws=ctx.ws, data=message, state=ctx.state, agent_id=ctx.agent_id)
                    processed = True
                logger.info(
                    "[command_result] lifecycle outcome: "
                    f"operation_id={operation_id} status={lifecycle_status} "
                    f"processed={processed} operation_kind={operation_kind_out} "
                    f"ticket_id={ticket_id_out}"
                )
                return CommandResultLifecycleOutcome(
                    processed=processed,
                    command_id=normalized.command_id,
                    status=lifecycle_status,
                    operation_id=operation_id,
                    operation_kind=operation_kind_out,
                    ticket_id=ticket_id_out,
                    trace_id=trace_id_out,
                    failure_code=normalized.error_info.get("code"),
                    failure_message=normalized.error_info.get("message"),
                )
        except Exception as exc:
            logger.error(f"[command_result] lifecycle pipeline failed: {exc}", exc_info=True)
            if legacy_handler is not None:
                await legacy_handler(ws=ctx.ws, data=message, state=ctx.state, agent_id=ctx.agent_id)
                return CommandResultLifecycleOutcome(
                    processed=True,
                    command_id=normalized.command_id,
                    status=normalized.lifecycle_status,
                )
            return CommandResultLifecycleOutcome(
                processed=False,
                command_id=normalized.command_id,
                status=normalized.lifecycle_status,
            )


class OutboxIngestService:
    """Validates and ingests outbox_item envelopes."""

    def __init__(
        self,
        legacy_handler: Optional[Callable[..., Awaitable[bool]]],
        batch_ack_manager: Any,
        event_validator: Any,
    ) -> None:
        self._legacy_handler = legacy_handler
        self._batch_ack_manager = batch_ack_manager
        self._event_validator = event_validator
        self._validator = OutboxEnvelopeValidatorComponent()
        self._guards = OutboxGuardService(batch_ack_manager)
        self._dedupe = OutboxDedupService()
        self._persistence = OutboxPersistenceService()
        self._ack_decision = OutboxAckDecisionService()
        self._event_publish = OutboxEventPublishService()

    async def handle(
        self,
        message: dict[str, Any],
        ctx: AgentConnectionContext,
        *,
        flush_immediately: bool = True,
    ) -> bool:
        # 1) envelope validate
        envelope_check = self._validator.validate(message)
        if not envelope_check.ok:
            return await self._ack_decision.reject_invalid_envelope(
                batch_ack_manager=self._batch_ack_manager,
                ctx=ctx,
                envelope_check=envelope_check,
                flush_immediately=flush_immediately,
            )
        # 2) post-handshake guards
        if await self._apply_post_handshake_guards(
            message,
            ctx,
            flush_immediately=flush_immediately,
        ):
            return True
        # 3) dedupe check
        if self._dedupe.is_duplicate(ctx, envelope_check.outbox_id):
            self._ack_decision.ack_duplicate(
                batch_ack_manager=self._batch_ack_manager,
                ctx=ctx,
                envelope_check=envelope_check,
            )
            if flush_immediately and ctx.agent_id and self._batch_ack_manager.has_pending(ctx.agent_id):
                await self._batch_ack_manager.flush(ctx.ws, ctx.agent_id)
            return True
        # 4) persistence
        persistence_outcome = await self._persistence.persist(
            message=message,
            ctx=ctx,
            event_validator=self._event_validator,
            envelope=envelope_check,
        )
        # 5) ack/nack decision
        await self._ack_decision.apply_final_decision(
            batch_ack_manager=self._batch_ack_manager,
            ctx=ctx,
            outcome=persistence_outcome,
            flush_immediately=flush_immediately,
        )
        if not (
            persistence_outcome.decision == "nack"
            and persistence_outcome.retryable
        ):
            self._dedupe.mark_processed(ctx, envelope_check.outbox_id)
        # 6) publish side effects
        await self._event_publish.publish_after_commit(ctx=ctx, outcome=persistence_outcome)
        return persistence_outcome.should_continue

    async def _apply_post_handshake_guards(
        self,
        message: dict[str, Any],
        ctx: AgentConnectionContext,
        *,
        flush_immediately: bool = True,
    ) -> bool:
        """
        Apply post-handshake message-level guards that return typed outbox_nack.
        """
        if not ctx.agent_id:
            return False
        payload = message.get("payload") if isinstance(message, dict) else None
        if not isinstance(payload, dict):
            return False
        outbox_id = payload.get("outbox_id")
        trace_id = message.get("trace_id")
        if not outbox_id or not trace_id:
            return False

        # 1) UNAUTHORIZED (message-level, post-handshake).
        actor_role = ((message.get("meta") or {}).get("actor_role") or "agent").lower()
        if actor_role not in {"agent", "system"}:
            await self._guards.reject_unauthorized(
                ctx=ctx,
                outbox_id=str(outbox_id),
                trace_id=trace_id,
                actor_role=actor_role,
                flush_immediately=flush_immediately,
            )
            return True

        # 2) RATE_LIMITED (message-level, post-handshake).
        # Sliding 1-second window per agent connection.
        rate_state = getattr(ctx.state, "_outbox_ingest_rate_state", None)
        if rate_state is None:
            rate_state = {}
            setattr(ctx.state, "_outbox_ingest_rate_state", rate_state)
        window = rate_state.setdefault(ctx.agent_id, deque())
        now = time.monotonic()
        while window and (now - window[0]) > 1.0:
            window.popleft()
        window.append(now)
        if len(window) > OUTBOX_INGEST_RATE_LIMIT_PER_SEC:
            await self._guards.reject_rate_limited(
                ctx=ctx,
                outbox_id=str(outbox_id),
                trace_id=trace_id,
                flush_immediately=flush_immediately,
            )
            return True
        return False


class OutboxGuardService:
    def __init__(self, batch_ack_manager: Any) -> None:
        self._batch_ack_manager = batch_ack_manager

    async def reject_unauthorized(
        self,
        *,
        ctx: AgentConnectionContext,
        outbox_id: str,
        trace_id: str,
        actor_role: str,
        flush_immediately: bool = True,
    ) -> None:
        self._batch_ack_manager.add_nack(
            device_id=ctx.agent_id,
            outbox_id=outbox_id,
            trace_id=trace_id,
            nack_info=NackInfo(
                retryable=False,
                error_code="UNAUTHORIZED",
                error_message=f"actor_role '{actor_role}' is not allowed for outbox_item",
                retry_after_sec=None,
            ),
        )
        if flush_immediately:
            await self._batch_ack_manager.flush(ctx.ws, ctx.agent_id)

    async def reject_rate_limited(
        self,
        *,
        ctx: AgentConnectionContext,
        outbox_id: str,
        trace_id: str,
        flush_immediately: bool = True,
    ) -> None:
        self._batch_ack_manager.add_nack(
            device_id=ctx.agent_id,
            outbox_id=outbox_id,
            trace_id=trace_id,
            nack_info=NackInfo(
                retryable=True,
                error_code="RATE_LIMITED",
                error_message="Outbox ingest rate limit exceeded",
                retry_after_sec=1,
            ),
        )
        if flush_immediately:
            await self._batch_ack_manager.flush(ctx.ws, ctx.agent_id)


class OutboxDedupService:
    def is_duplicate(self, ctx: AgentConnectionContext, outbox_id: Optional[str]) -> bool:
        if not ctx.agent_id or not outbox_id:
            return False
        key = "_outbox_seen_ids"
        seen = getattr(ctx.state, key, None)
        if seen is None:
            seen = {}
            setattr(ctx.state, key, seen)
        agent_seen = seen.setdefault(ctx.agent_id, set())
        return outbox_id in agent_seen

    def mark_processed(self, ctx: AgentConnectionContext, outbox_id: Optional[str]) -> None:
        if not ctx.agent_id or not outbox_id:
            return
        key = "_outbox_seen_ids"
        seen = getattr(ctx.state, key, None)
        if seen is None:
            seen = {}
            setattr(ctx.state, key, seen)
        agent_seen = seen.setdefault(ctx.agent_id, set())
        agent_seen.add(outbox_id)
        if len(agent_seen) > 10000:
            # bound runtime memory
            seen[ctx.agent_id] = set(list(agent_seen)[-5000:])


class OutboxPersistenceService(OutboxPersistenceComponent):
    """Adapter over persistence component."""


class OutboxAckDecisionService:
    def __init__(self) -> None:
        self._component = OutboxAckDecisionComponent()

    async def reject_invalid_envelope(
        self,
        *,
        batch_ack_manager: Any,
        ctx: AgentConnectionContext,
        envelope_check: Any,
        flush_immediately: bool = True,
    ) -> bool:
        if not ctx.agent_id or not envelope_check.trace_id:
            return True
        self._component.add_validation_nack(
            batch_ack_manager=batch_ack_manager,
            device_id=ctx.agent_id,
            outbox_id=envelope_check.outbox_id or "unknown",
            trace_id=envelope_check.trace_id,
            error=envelope_check.error_message or "Invalid outbox envelope",
        )
        if flush_immediately:
            await batch_ack_manager.flush(ctx.ws, ctx.agent_id)
        return True

    def ack_duplicate(self, *, batch_ack_manager: Any, ctx: AgentConnectionContext, envelope_check: Any) -> None:
        if not ctx.agent_id or not envelope_check.outbox_id or not envelope_check.trace_id:
            return
        self._component.add_duplicate_ack(
            batch_ack_manager=batch_ack_manager,
            device_id=ctx.agent_id,
            outbox_id=envelope_check.outbox_id,
            trace_id=envelope_check.trace_id,
        )

    async def apply_final_decision(
        self,
        *,
        batch_ack_manager: Any,
        ctx: AgentConnectionContext,
        outcome: Any,
        flush_immediately: bool = True,
    ) -> None:
        if not ctx.agent_id or not outcome.outbox_id or not outcome.trace_id:
            return
        if outcome.decision == "nack":
            batch_ack_manager.add_nack(
                device_id=ctx.agent_id,
                outbox_id=outcome.outbox_id,
                trace_id=outcome.trace_id,
                nack_info=NackInfo(
                    retryable=bool(outcome.retryable),
                    error_code=outcome.error_code or "SERVER_ERROR",
                    error_message=outcome.error_message or "Outbox processing failed",
                    retry_after_sec=30 if outcome.retryable else None,
                ),
            )
        else:
            batch_ack_manager.add_ack(
                device_id=ctx.agent_id,
                outbox_id=outcome.outbox_id,
                trace_id=outcome.trace_id,
            )
        if flush_immediately:
            await batch_ack_manager.flush(ctx.ws, ctx.agent_id)


class OutboxEventPublishService(OutboxEventPublishComponent):
    """Adapter over post-commit side-effect publisher."""


class OutboxBatchIngestService:
    """Processes batched outbox_item envelopes in one WS frame."""

    def __init__(self, item_service: OutboxIngestService, batch_ack_manager: Any) -> None:
        self._item_service = item_service
        self._batch_ack_manager = batch_ack_manager

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> bool:
        payload = message.get("payload") if isinstance(message, dict) else None
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items:
            invalid_trace_id = (message.get("trace_id") if isinstance(message, dict) else None) or str(uuid.uuid4())
            invalid_message = {
                "type": "outbox_item",
                "trace_id": invalid_trace_id,
                "payload": {"outbox_id": "batch-envelope"},
                "meta": {"actor_role": "agent"},
            }
            return await self._item_service.handle(invalid_message, ctx, flush_immediately=True)

        should_continue = True
        batch_trace_id = message.get("trace_id") if isinstance(message, dict) else None

        for index, raw_item in enumerate(items):
            if not isinstance(raw_item, dict):
                if ctx.agent_id:
                    self._batch_ack_manager.add_nack(
                        device_id=ctx.agent_id,
                        outbox_id=f"batch-item-{index}",
                        trace_id=batch_trace_id or str(uuid.uuid4()),
                        nack_info=NackInfo(
                            retryable=False,
                            error_code="VALIDATION_ERROR",
                            error_message="outbox_items_batch payload.items must contain objects",
                            retry_after_sec=None,
                        ),
                    )
                continue

            item_message = dict(raw_item)
            item_message["type"] = "outbox_item"
            if not item_message.get("trace_id") and batch_trace_id:
                item_message["trace_id"] = batch_trace_id

            item_result = await self._item_service.handle(
                item_message,
                ctx,
                flush_immediately=False,
            )
            should_continue = should_continue and item_result

        if ctx.agent_id and self._batch_ack_manager.has_pending(ctx.agent_id):
            await self._batch_ack_manager.flush(ctx.ws, ctx.agent_id)
        return should_continue


class AgentCommandService:
    """Handles commands initiated by agent -> server."""

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> None:
        if not ctx.agent_id:
            return
        agent_info = ctx.state.get_agent(ctx.agent_id)
        if not agent_info:
            return

        agent_info["metadata"]["last_seen"] = time.time()
        req_id = message.get("request_id")
        payload = message.get("payload", {})
        command = payload.get("command")
        params = payload.get("params", {})

        if command != "chat_raise":
            logger.warning(f"[SERVER] Unknown command from agent {ctx.agent_id}: {command}")
            await ctx.ws.send_json(
                {
                    "type": "command_result",
                    "request_id": req_id,
                    "device_id": ctx.agent_id,
                    "payload": {
                        "status": "error",
                        "error": {"code": "UNKNOWN_COMMAND", "message": f"Unknown command: {command}"},
                    },
                }
            )
            return

        title = params.get("title", "Agent Support Request")
        reason = params.get("reason", "agent_initiated")
        severity = params.get("severity", "warning")
        context_payload = params.get("context", {})
        chat_job_id = str(uuid.uuid4())
        ticket_id = str(uuid.uuid4())

        session_data = {
            "chat_job_id": chat_job_id,
            "ticket_id": ticket_id,
            "device_id": ctx.agent_id,
            "owner_uuid": agent_info["metadata"].get("user", "unknown"),
            "created_by": "agent",
            "status": "active",
            "created_at": time.time(),
            "subscribers": set(),
            "events": [],
        }
        ctx.state.create_chat_session(chat_job_id, session_data)

        if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
            try:
                async with get_session() as db_session:
                    created = await create_ticket_with_side_effects(
                        db_session,
                        device_id=ctx.agent_id,
                        requester_id=ctx.agent_id,
                        title=title,
                        description=build_agent_raise_description(
                            reason=str(reason or "agent_initiated"),
                            severity=str(severity or "warning"),
                            context=context_payload if isinstance(context_payload, dict) else {},
                        ),
                        user_display_name=ctx.agent_id,
                        initial_message_sender_role="agent",
                        initial_message_from="agent",
                        include_public_access=False,
                        state=ctx.state,
                    )
                    ticket_id = created["ticket_id"]
                    session_data["ticket_id"] = ticket_id
                    await db_session.commit()
            except Exception as exc:
                logger.opt(exception=True).error("❌ [V3] Failed to create ticket for chat_raise: {}", exc)

        await ctx.ws.send_json(
            {
                "type": "command_result",
                "request_id": req_id,
                "device_id": ctx.agent_id,
                "payload": {
                    "status": "success",
                    "data": {
                        "observations": {
                            "job_id": chat_job_id,
                            "ticket_id": ticket_id,
                            "message": "Chat session created",
                        }
                    },
                },
            }
        )

        invite_event = {
            "event": "chat_invite",
            "job_id": chat_job_id,
            "ticket_id": ticket_id,
            "device_id": ctx.agent_id,
            "from": "agent",
            "title": title,
            "reason": reason,
            "severity": severity,
            "context": context_payload,
            "ts": time.time(),
        }
        await push_chat_event_to_ui(ctx.state, chat_job_id, invite_event)

        async def _background_notify() -> None:
            try:
                await send_ws_command(
                    state=ctx.state,
                    device_id=ctx.agent_id,
                    command="start_job",
                    params={"job_type": "support_chat", "params": {"job_id": chat_job_id, "ticket_id": ticket_id}},
                    actor_role="agent",
                )
            except Exception as exc:
                logger.opt(exception=True).error("[chat_raise] Failed to send start_job to agent: {}", exc)

            try:
                await send_ws_command(
                    state=ctx.state,
                    device_id=ctx.agent_id,
                    command="ui_notify",
                    params={"event": invite_event},
                    actor_role="agent",
                )
            except Exception as exc:
                logger.opt(exception=True).error("[chat_raise] Failed to send ui_notify to agent: {}", exc)

        asyncio.create_task(_background_notify())


class RpcResponseService:
    """Resolves pending rpc_request futures when agent sends rpc_response."""

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> None:
        if not ctx.agent_id:
            return
        agent_info = ctx.state.get_agent(ctx.agent_id)
        if not agent_info:
            return

        agent_info["metadata"]["last_seen"] = time.time()
        agent_info["metadata"]["status"] = "online"
        request_id = message.get("request_id")
        if not request_id:
            logger.warning(f"[rpc_response] Missing request_id from agent {ctx.agent_id}")
            return

        pending = agent_info["metadata"].get("pending_rpc_futures", {})
        future = pending.pop(request_id, None)
        if future is None:
            logger.warning(
                f"[rpc_response] No pending future for request_id={request_id} "
                f"from agent {ctx.agent_id}"
            )
            return
        if not future.done():
            future.set_result(message)


class AgentObserverTelemetryService:
    """Persists authenticated agent observer telemetry batches."""

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> None:
        request_id = message.get("request_id")
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        event_container = payload if payload else message
        if not ctx.authenticated or not ctx.agent_id:
            await ctx.ws.send_json(
                {
                    "type": "agent_observer_batch_ack",
                    "request_id": request_id,
                    "status": "error",
                    "error_code": "UNAUTHENTICATED",
                    "accepted_count": 0,
                    "rejected_count": len(event_container.get("events") or []) if isinstance(event_container.get("events"), list) else 0,
                }
            )
            return

        events = event_container.get("events")
        if not isinstance(events, list):
            await ctx.ws.send_json(
                {
                    "type": "agent_observer_batch_ack",
                    "request_id": request_id,
                    "status": "error",
                    "error_code": "INVALID_SCHEMA",
                    "accepted_count": 0,
                    "rejected_count": 0,
                }
            )
            return

        async with get_session() as session:
            repo = AgentObserverEventsRepo(session)
            rows = await repo.ingest_batch(device_id=ctx.agent_id, events=events)
            await session.commit()

        runtime = getattr(ctx.state, "observer_refresh_runtime", None)
        for row in rows:
            if runtime is not None and getattr(row, "trace_id", None):
                try:
                    await runtime.enqueue_trace(row.trace_id)
                except Exception as exc:
                    logger.debug(f"[agent_observer_batch] enqueue skipped: {exc}")

        await ctx.ws.send_json(
            {
                "type": "agent_observer_batch_ack",
                "request_id": request_id,
                "status": "ok",
                "accepted_count": len(rows),
                "rejected_count": max(0, len(events) - len(rows)),
            }
        )


class AgentMessageRouter:
    """Routes incoming messages by envelope type to dedicated services."""

    def __init__(
        self,
        handshake_service: HandshakeService,
        command_ack_service: CommandAckService,
        command_result_service: CommandResultService,
        rpc_response_service: RpcResponseService,
        outbox_ingest_service: OutboxIngestService,
        agent_command_service: AgentCommandService,
        outbox_batch_ingest_service: Optional[OutboxBatchIngestService] = None,
        agent_observer_telemetry_service: Optional[AgentObserverTelemetryService] = None,
    ) -> None:
        self._handshake_service = handshake_service
        self._command_ack_service = command_ack_service
        self._command_result_service = command_result_service
        self._rpc_response_service = rpc_response_service
        self._outbox_ingest_service = outbox_ingest_service
        self._outbox_batch_ingest_service = outbox_batch_ingest_service
        self._agent_command_service = agent_command_service
        self._agent_observer_telemetry_service = agent_observer_telemetry_service or AgentObserverTelemetryService()

    async def route(
        self,
        message: dict[str, Any],
        ctx: AgentConnectionContext,
        envelope: EnvelopeContext,
    ) -> Optional[Any]:
        msg_type = envelope.message_type

        if msg_type == "handshake":
            return await self._handshake_service.handle(message, ctx)
        if msg_type == "pong":
            if ctx.agent_id:
                agent_info = ctx.state.get_agent(ctx.agent_id)
                if agent_info:
                    agent_info["metadata"]["last_seen"] = time.time()
                    agent_info["metadata"]["status"] = "online"
            return None
        if msg_type == "command_ack":
            await self._command_ack_service.handle(message, ctx)
            return None
        if msg_type == "command_result":
            await self._command_result_service.handle(message, ctx)
            return None
        if msg_type == "rpc_response":
            await self._rpc_response_service.handle(message, ctx)
            return None
        if msg_type == "command":
            await self._agent_command_service.handle(message, ctx)
            return None
        if msg_type == "outbox_item":
            should_continue = await self._outbox_ingest_service.handle(message, ctx)
            return "__continue__" if should_continue else None
        if msg_type == "outbox_items_batch" and self._outbox_batch_ingest_service is not None:
            should_continue = await self._outbox_batch_ingest_service.handle(message, ctx)
            return "__continue__" if should_continue else None
        if msg_type == "agent_observer_batch":
            await self._agent_observer_telemetry_service.handle(message, ctx)
            return None
        return None


class AgentLoopSafetyService:
    """Keeps websocket loop focused on transport concerns."""

    @staticmethod
    async def handle_unknown_message_type(msg_type: Optional[str], ctx: AgentConnectionContext) -> None:
        if msg_type is None:
            logger.warning(
                f"[SERVER] Received message without type from agent {ctx.agent_id}, ignoring"
            )
            return
        logger.warning(
            f"[SERVER] Unknown message type '{msg_type}' from agent {ctx.agent_id}, ignoring"
        )

    @staticmethod
    async def handle_outbox_processing_exception(
        *,
        batch_ack_manager: Any,
        data: dict[str, Any],
        agent_id: Optional[str],
        error: Exception,
        ws: Any,
    ) -> None:
        if not agent_id:
            return
        payload = data.get("payload", {}) if isinstance(data, dict) else {}
        outbox_id = payload.get("outbox_id") if isinstance(payload, dict) else None
        trace_id = data.get("trace_id") if isinstance(data, dict) else None
        if not outbox_id or not trace_id:
            return

        from websocket.batch_ack_manager import NackInfo

        batch_ack_manager.add_nack(
            device_id=agent_id,
            outbox_id=str(outbox_id),
            trace_id=trace_id,
            nack_info=NackInfo(
                retryable=True,
                error_code="SERVER_ERROR",
                error_message=f"Internal server error during processing: {str(error)}",
                retry_after_sec=30,
            ),
        )
        if batch_ack_manager.has_pending(agent_id):
            await batch_ack_manager.flush(ws, agent_id)
