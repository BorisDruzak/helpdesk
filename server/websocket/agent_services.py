from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from app.db import get_session
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
    from app.repos import TicketEventsRepo

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
        if not agent_info:
            return

        agent_info["metadata"]["last_seen"] = time.time()
        payload = message.get("payload", {})
        operation_id = message.get("request_id")
        ack_status = payload.get("status")

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

                await session.commit()
        except Exception as exc:
            logger.error(f"[command_ack] Failed to update operation status: {exc}", exc_info=True)


class CommandResultService:
    """Normalizes and persists command_result lifecycle transitions."""

    def __init__(self, legacy_handler: Callable[..., Awaitable[None]]) -> None:
        self._legacy_handler = legacy_handler
        self._normalizer = CommandResultNormalizer()
        self._lifecycle = OperationLifecycleService()
        self._future_resolver = CommandResultFutureResolver()
        self._event_publisher = CommandResultEventPublisher()
        self._artifact_handler = CommandResultArtifactHandler()

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> None:
        # 1) normalize
        normalized = self._normalizer.normalize(message)
        # 2) lifecycle update
        lifecycle_outcome = await self._lifecycle.handle(self._legacy_handler, message, ctx, normalized)
        # 3) future resolve (sync wait path)
        self._future_resolver.resolve_from_context(normalized.command_id, message, ctx)
        # 4) artifact/result post-process
        await self._artifact_handler.post_process(normalized, ctx)
        # 5) publish side effects
        await self._event_publisher.publish_after_lifecycle(normalized, ctx, lifecycle_outcome)


class OperationLifecycleService:
    """Lifecycle orchestrator for command_result state transitions."""

    async def handle(
        self,
        legacy_handler: Callable[..., Awaitable[None]],
        message: dict[str, Any],
        ctx: AgentConnectionContext,
        normalized: Any,
    ) -> CommandResultLifecycleOutcome:
        await legacy_handler(
            ws=ctx.ws,
            data=message,
            state=ctx.state,
            agent_id=ctx.agent_id,
        )
        return CommandResultLifecycleOutcome(
            processed=True,
            command_id=normalized.command_id,
            status=normalized.status,
        )


class OutboxIngestService:
    """Validates and ingests outbox_item envelopes."""

    def __init__(
        self,
        legacy_handler: Callable[..., Awaitable[bool]],
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

    async def handle(self, message: dict[str, Any], ctx: AgentConnectionContext) -> bool:
        # 1) envelope validate
        envelope_check = self._validator.validate(message)
        if not envelope_check.ok:
            return await self._ack_decision.reject_invalid_envelope(
                batch_ack_manager=self._batch_ack_manager,
                ctx=ctx,
                envelope_check=envelope_check,
            )
        # 2) post-handshake guards
        if await self._apply_post_handshake_guards(message, ctx):
            return True
        # 3) dedupe check
        if self._dedupe.is_duplicate(ctx, envelope_check.outbox_id):
            self._ack_decision.ack_duplicate(
                batch_ack_manager=self._batch_ack_manager,
                ctx=ctx,
                envelope_check=envelope_check,
            )
            if ctx.agent_id and self._batch_ack_manager.has_pending(ctx.agent_id):
                await self._batch_ack_manager.flush(ctx.ws, ctx.agent_id)
            return True
        # 4) persistence
        persistence_outcome = await self._persistence.persist(
            legacy_handler=self._legacy_handler,
            message=message,
            ctx=ctx,
            batch_ack_manager=self._batch_ack_manager,
            event_validator=self._event_validator,
            envelope=envelope_check,
        )
        # 5) ack/nack decision lives in legacy persistence path for valid items.
        # 6) publish side effects
        await self._event_publish.publish_after_commit(ctx=ctx, outcome=persistence_outcome)
        return persistence_outcome.should_continue

    async def _apply_post_handshake_guards(
        self,
        message: dict[str, Any],
        ctx: AgentConnectionContext,
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
            )
            return True
        return False


class OutboxGuardService:
    def __init__(self, batch_ack_manager: Any) -> None:
        self._batch_ack_manager = batch_ack_manager

    async def reject_unauthorized(self, *, ctx: AgentConnectionContext, outbox_id: str, trace_id: str, actor_role: str) -> None:
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
        await self._batch_ack_manager.flush(ctx.ws, ctx.agent_id)

    async def reject_rate_limited(self, *, ctx: AgentConnectionContext, outbox_id: str, trace_id: str) -> None:
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
        if outbox_id in agent_seen:
            return True
        agent_seen.add(outbox_id)
        if len(agent_seen) > 10000:
            # bound runtime memory
            seen[ctx.agent_id] = set(list(agent_seen)[-5000:])
        return False


class OutboxPersistenceService(OutboxPersistenceComponent):
    """Adapter over persistence component."""


class OutboxAckDecisionService:
    def __init__(self) -> None:
        self._component = OutboxAckDecisionComponent()

    async def reject_invalid_envelope(self, *, batch_ack_manager: Any, ctx: AgentConnectionContext, envelope_check: Any) -> bool:
        if not ctx.agent_id or not envelope_check.trace_id:
            return True
        self._component.add_validation_nack(
            batch_ack_manager=batch_ack_manager,
            device_id=ctx.agent_id,
            outbox_id=envelope_check.outbox_id or "unknown",
            trace_id=envelope_check.trace_id,
            error=envelope_check.error_message or "Invalid outbox envelope",
        )
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


class OutboxEventPublishService(OutboxEventPublishComponent):
    """Adapter over post-commit side-effect publisher."""


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
                    ticket_repo = TicketEventsRepo(db_session)
                    created = await ticket_repo.create_ticket(
                        ticket_id=ticket_id,
                        device_id=ctx.agent_id,
                        title=title,
                        description=f"Agent-initiated: {reason} (severity: {severity})",
                        status="new",
                        requester_id=ctx.agent_id,
                    )
                    code = getattr(created, "ticket_code", None) or ""
                    if code:
                        snippet = (title or getattr(created, "description", "") or "")[:80].strip()
                        new_title = f"{code} {snippet}".strip() if snippet else code
                        if new_title:
                            await ticket_repo.update_ticket(ticket_id, title=new_title)
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


class AgentMessageRouter:
    """Routes incoming messages by envelope type to dedicated services."""

    def __init__(
        self,
        handshake_service: HandshakeService,
        command_ack_service: CommandAckService,
        command_result_service: CommandResultService,
        outbox_ingest_service: OutboxIngestService,
        agent_command_service: AgentCommandService,
    ) -> None:
        self._handshake_service = handshake_service
        self._command_ack_service = command_ack_service
        self._command_result_service = command_result_service
        self._outbox_ingest_service = outbox_ingest_service
        self._agent_command_service = agent_command_service

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
        if msg_type == "command":
            await self._agent_command_service.handle(message, ctx)
            return None
        if msg_type == "outbox_item":
            should_continue = await self._outbox_ingest_service.handle(message, ctx)
            return "__continue__" if should_continue else None
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
