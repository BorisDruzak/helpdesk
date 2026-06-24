"""
API обработчики для управления операциями.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from aiohttp import web
from loguru import logger

from access_control.service import can
from config import ALLOW_REMOTE_CODE
from app.db import get_session
from app.db.models import DeviceOutbox, Ticket
from app.repos.operations_repo import OperationsRepo
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.services.operation_service import OperationService
from auth.context import AuthContext
from auth.middleware import require_auth
from consent.operation_consent import create_operation_user_consent, redact_operation_event_params
from consent.service import ConsentAccessError
from core.policy_engine import PolicyEngine
from core.tool_metadata import ToolMetadata
from shared.tool_contracts import normalize_risk_level
from tools.service import ToolExecutionService
from websocket.device_outbox_sender import _send_single_command


_RETRYABLE_OPERATION_STATUSES = {"failed", "timed_out", "timeout"}
_HIGH_RISK_TOOL_LEVELS = {"high", "dangerous", "system_write", "code_exec"}


def _operation_payload(operation) -> dict[str, Any]:
    return {
        "operation_id": operation.operation_id,
        "device_id": operation.device_id,
        "ticket_id": operation.ticket_id,
        "job_id": operation.job_id,
        "kind": operation.kind,
        "tool_name": operation.tool_name,
        "actor_role": operation.actor_role,
        "trace_id": operation.trace_id,
        "status": operation.status,
        "deadline_at": operation.deadline_at.isoformat() if operation.deadline_at else None,
        "queued_at": operation.queued_at.isoformat() if operation.queued_at else None,
        "sent_at": operation.sent_at.isoformat() if operation.sent_at else None,
        "accepted_at": operation.accepted_at.isoformat() if operation.accepted_at else None,
        "started_at": operation.started_at.isoformat() if operation.started_at else None,
        "finished_at": operation.finished_at.isoformat() if operation.finished_at else None,
        "retry_count": operation.retry_count,
        "max_retries": operation.max_retries,
        "retry_of_operation_id": getattr(operation, "retry_of_operation_id", None),
        "error_code": operation.error_code,
        "error_message": operation.error_message,
        "result_summary": operation.result_summary,
        "result_event_id": operation.result_event_id,
    }


def _json_error(error: str, *, status: int, error_code: str, **payload: Any) -> web.Response:
    body = {"status": "error", "error": error, "error_code": error_code}
    body.update(payload)
    return web.json_response(body, status=status)


async def _require_permission(session, auth_context: AuthContext, permission_code: str) -> web.Response | None:
    if await can(session, auth_context, permission_code):
        return None
    return _json_error(
        f"Недостаточно прав: {permission_code}",
        status=403,
        error_code="FORBIDDEN",
        required_permission=permission_code,
    )


def _tool_risk_permission(risk_level: str | None) -> str:
    normalized = str(risk_level or "").strip().lower()
    if normalized in _HIGH_RISK_TOOL_LEVELS:
        return "module.tool.run.high_risk"
    return "module.tool.run.low_risk"


def _find_raw_tool_entry(raw_items: list[object], tool_name: str) -> dict | None:
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        current = str(raw_item.get("tool") or raw_item.get("name") or "").strip()
        aliases = raw_item.get("aliases") if isinstance(raw_item.get("aliases"), list) else []
        if current == tool_name or tool_name in aliases:
            return raw_item
    return None


def _tool_metadata_from_raw_tool(raw_tool: dict, tool_name: str) -> ToolMetadata:
    spec = raw_tool.get("spec") if isinstance(raw_tool.get("spec"), dict) else {}
    spec_metadata = spec.get("metadata") if isinstance(spec.get("metadata"), dict) else {}
    raw_metadata = raw_tool.get("metadata") if isinstance(raw_tool.get("metadata"), dict) else {}
    metadata = dict(spec_metadata)
    metadata.update(raw_metadata)

    allow_roles = metadata.get("allow_roles")
    if tool_name in ("screen.collect", "screen.record"):
        screen_roles = ["user", "agent", "llm", "support", "admin"]
        allow_roles = list(dict.fromkeys((allow_roles or []) + screen_roles))
        metadata["requires_consent"] = False

    return ToolMetadata(
        domain=str(metadata.get("domain") or "system"),
        platforms=metadata.get("platforms", ["any"]),
        risk_level=normalize_risk_level(spec.get("risk_level") or metadata.get("risk_level") or "safe_read"),
        scopes=metadata.get("scopes", []),
        requires_consent=bool(metadata.get("requires_consent")),
        allow_roles=allow_roles,
        timeout_sec=metadata.get("timeout_sec"),
        idempotent=bool(metadata.get("idempotent")),
        origin=str(metadata.get("origin") or "builtin"),
        side_effects=bool(metadata.get("side_effects")),
        tool_kind=metadata.get("tool_kind") or "diagnostic",
    )


async def _resolve_retry_tool_metadata(
    *,
    tool_service: ToolExecutionService,
    device_id: str,
    tool_name: str,
) -> ToolMetadata | None:
    for source, method_name in (("device", "get_tools_list"), ("server", "get_tools_from_server")):
        method = getattr(tool_service, method_name, None)
        if not callable(method):
            continue
        try:
            raw_items = await method(device_id) or []
        except Exception as exc:
            logger.debug(
                f"[operation_retry] tool metadata lookup skipped: "
                f"device_id={device_id} tool={tool_name} source={source} error={exc}"
            )
            raw_items = []
        raw_tool = _find_raw_tool_entry(raw_items, tool_name)
        if raw_tool is not None:
            return _tool_metadata_from_raw_tool(raw_tool, tool_name)
    return None


def _extract_replay_params(outbox_entry: DeviceOutbox, tool_name: str, ticket_id: str) -> dict[str, Any] | None:
    payload = outbox_entry.params if isinstance(outbox_entry.params, dict) else {}
    if str(payload.get("tool_name") or payload.get("tool") or "").strip() not in {"", tool_name}:
        return None
    if str(payload.get("ticket_id") or "").strip() not in {"", ticket_id}:
        return None
    raw_params = payload.get("params")
    if raw_params is None:
        raw_params = {}
    if not isinstance(raw_params, dict):
        return None
    return {
        str(key): value
        for key, value in raw_params.items()
        if isinstance(key, str) and not key.startswith("_") and key not in {"operation_id", "request_id", "call_id"}
    }


async def handle_get_operations(request: web.Request) -> web.Response:
    """
    GET /api/operations
    
    Получить список операций с фильтрацией.
    
    Query параметры:
        - device_id: Фильтр по device_id (optional)
        - ticket_id: Фильтр по ticket_id (optional)
        - status: Фильтр по статусу (optional, может быть несколько через запятую)
        - limit: Максимальное количество операций (default: 100)
        - active_only: Только активные операции (default: false)
    
    Returns:
        JSON array of operations
    """
    try:
        # Получить query параметры
        device_id = request.query.get("device_id")
        ticket_id = request.query.get("ticket_id")
        status_param = request.query.get("status")
        limit = int(request.query.get("limit", "100"))
        active_only = request.query.get("active_only", "false").lower() == "true"
        
        # Парсинг статусов
        statuses = None
        if status_param:
            statuses = [s.strip() for s in status_param.split(",")]
        
        async with get_session() as session:
            repo = OperationsRepo(session)
            
            if active_only:
                # Получить только активные операции
                operations = await repo.get_active_operations(
                    device_id=device_id,
                    ticket_id=ticket_id,
                    limit=limit
                )
            else:
                # Получить операции с фильтрацией
                operations = await repo.get_operations(
                    device_id=device_id,
                    ticket_id=ticket_id,
                    statuses=statuses,
                    limit=limit
                )
            
            # Сериализация операций
            result = []
            for op in operations:
                result.append({
                    "operation_id": op.operation_id,
                    "device_id": op.device_id,
                    "ticket_id": op.ticket_id,
                    "job_id": op.job_id,
                    "kind": op.kind,
                    "tool_name": op.tool_name,
                    "actor_role": op.actor_role,
                    "trace_id": op.trace_id,
                    "status": op.status,
                    "deadline_at": op.deadline_at.isoformat() if op.deadline_at else None,
                    "queued_at": op.queued_at.isoformat() if op.queued_at else None,
                    "sent_at": op.sent_at.isoformat() if op.sent_at else None,
                    "accepted_at": op.accepted_at.isoformat() if op.accepted_at else None,
                    "started_at": op.started_at.isoformat() if op.started_at else None,
                    "finished_at": op.finished_at.isoformat() if op.finished_at else None,
                    "retry_count": op.retry_count,
                    "max_retries": op.max_retries,
                    "retry_of_operation_id": getattr(op, "retry_of_operation_id", None),
                    "error_code": op.error_code,
                    "error_message": op.error_message,
                    "result_summary": op.result_summary,
                    "result_event_id": op.result_event_id,
                })
            
            return web.json_response({
                "status": "success",
                "operations": result,
                "count": len(result)
            })
    
    except Exception as e:
        logger.error(f"[handle_get_operations] Error: {e}", exc_info=True)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_get_operation(request: web.Request) -> web.Response:
    """
    GET /api/operations/{operation_id}
    
    Получить конкретную операцию по ID.
    
    Args:
        operation_id: Operation ID from URL
    
    Returns:
        JSON object with operation details
    """
    try:
        operation_id = request.match_info["operation_id"]
        
        async with get_session() as session:
            repo = OperationsRepo(session)
            operation = await repo.get_by_operation_id(operation_id)
            
            if not operation:
                return web.json_response({
                    "status": "error",
                    "error": "Operation not found"
                }, status=404)
            
            # Сериализация операции
            result = {
                "operation_id": operation.operation_id,
                "device_id": operation.device_id,
                "ticket_id": operation.ticket_id,
                "job_id": operation.job_id,
                "kind": operation.kind,
                "tool_name": operation.tool_name,
                "actor_role": operation.actor_role,
                "trace_id": operation.trace_id,
                "status": operation.status,
                "deadline_at": operation.deadline_at.isoformat() if operation.deadline_at else None,
                "queued_at": operation.queued_at.isoformat() if operation.queued_at else None,
                "sent_at": operation.sent_at.isoformat() if operation.sent_at else None,
                "accepted_at": operation.accepted_at.isoformat() if operation.accepted_at else None,
                "started_at": operation.started_at.isoformat() if operation.started_at else None,
                "finished_at": operation.finished_at.isoformat() if operation.finished_at else None,
                "retry_count": operation.retry_count,
                "max_retries": operation.max_retries,
                "retry_of_operation_id": getattr(operation, "retry_of_operation_id", None),
                "error_code": operation.error_code,
                "error_message": operation.error_message,
                "result_summary": operation.result_summary,
                "result_event_id": operation.result_event_id,
            }
            
            return web.json_response({
                "status": "success",
                "operation": result
            })
    
    except Exception as e:
        logger.error(f"[handle_get_operation] Error: {e}", exc_info=True)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


@require_auth("admin", "support", "auditor")
async def handle_web_admin_get_operation(request: web.Request) -> web.Response:
    """
    GET /api/web/admin/operations/{operation_id}

    Read-only web-session alias for the Tech Panel operation detail page.
    """
    try:
        operation_id = request.match_info["operation_id"]
        async with get_session() as session:
            repo = OperationsRepo(session)
            operation = await repo.get_by_operation_id(operation_id)
            if not operation:
                return web.json_response(
                    {"status": "error", "error": "Operation not found", "error_code": "NOT_FOUND"},
                    status=404,
                )
            return web.json_response({"status": "success", "operation": _operation_payload(operation)})
    except Exception as exc:
        logger.error(f"[handle_web_admin_get_operation] Error: {exc}", exc_info=True)
        return web.json_response({"status": "error", "error": "Operation lookup failed"}, status=500)


async def handle_retry_operation(request: web.Request) -> web.Response:
    """
    POST /api/operations/{operation_id}/retry
    POST /api/tickets/{ticket_id}/operations/{operation_id}/retry

    Re-run a failed/timed-out tool operation after revalidating ticket context,
    permissions, device online state, tool availability, risk policy, consent,
    and replayable params.
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return _json_error(
                "Authentication required",
                status=401,
                error_code="AUTH_REQUIRED",
            )

        operation_id = str(request.match_info["operation_id"]).strip()
        scoped_ticket_id = str(request.match_info.get("ticket_id") or "").strip() or None
        body = await request.json() if request.content_type == "application/json" else {}
        if not isinstance(body, dict):
            return _json_error("Request body must be an object", status=400, error_code="VALIDATION_ERROR")
        reason = str(body.get("reason") or "manual_retry").strip() or "manual_retry"

        if "actor_role" in body:
            logger.warning(
                "[handle_retry_operation] actor_role in JSON body ignored: "
                f"using actor_role={auth_context.actor_role} from AuthContext"
            )

        state = request.app.get("state")
        if state is None:
            return _json_error("Server state unavailable", status=503, error_code="SERVER_STATE_UNAVAILABLE")

        retry_operation_id = str(uuid.uuid4())
        retry_trace_id = str(uuid.uuid4())
        replay_params: dict[str, Any]
        target_ticket_id: str
        target_device_id: str
        tool_name: str
        original_job_id: str | None
        risk_level = "safe_read"

        async with get_session() as session:
            op_repo = OperationsRepo(session)
            outbox_repo = DeviceOutboxRepo(session)
            ticket_repo = TicketEventsRepo(session)

            target_op = await op_repo.get_by_operation_id(operation_id)
            if target_op is None:
                return _json_error("Operation not found", status=404, error_code="NOT_FOUND")

            if target_op.kind not in {"tool_call", "run_tool", "tool"} or not target_op.tool_name:
                return _json_error(
                    "Only tool operations can be retried",
                    status=409,
                    error_code="OPERATION_KIND_NOT_RETRYABLE",
                    operation_id=operation_id,
                )

            if target_op.status not in _RETRYABLE_OPERATION_STATUSES:
                return _json_error(
                    "Operation is not in a retryable terminal status",
                    status=409,
                    error_code="OPERATION_NOT_RETRYABLE",
                    operation_id=operation_id,
                    current_status=target_op.status,
                )

            max_retries = int(target_op.max_retries or 0)
            retry_count = int(target_op.retry_count or 0)
            if max_retries <= 0 or retry_count >= max_retries:
                return _json_error(
                    "Operation retry limit reached",
                    status=409,
                    error_code="RETRY_LIMIT_REACHED",
                    operation_id=operation_id,
                    retry_count=retry_count,
                    max_retries=max_retries,
                )

            target_ticket_id = str(target_op.ticket_id or "").strip()
            if not target_ticket_id:
                return _json_error(
                    "Operation has no ticket context",
                    status=400,
                    error_code="TICKET_CONTEXT_REQUIRED",
                    operation_id=operation_id,
                )
            if scoped_ticket_id and scoped_ticket_id != target_ticket_id:
                return _json_error(
                    "Operation belongs to a different ticket",
                    status=403,
                    error_code="TICKET_CONTEXT_MISMATCH",
                    operation_id=operation_id,
                    ticket_id=scoped_ticket_id,
                    operation_ticket_id=target_ticket_id,
                )

            ticket = await ticket_repo.get_ticket(target_ticket_id)
            if ticket is None:
                return _json_error("Ticket not found", status=404, error_code="TICKET_NOT_FOUND")

            target_device_id = str(target_op.device_id or "").strip()
            ticket_device_id = str(getattr(ticket, "device_id", "") or "").strip()
            if ticket_device_id and ticket_device_id != target_device_id:
                return _json_error(
                    "Operation device does not match ticket device",
                    status=403,
                    error_code="TICKET_DEVICE_MISMATCH",
                    operation_id=operation_id,
                    ticket_id=target_ticket_id,
                    device_id=target_device_id,
                    ticket_device_id=ticket_device_id,
                )

            if auth_context.actor_role == "agent" and target_device_id != auth_context.actor_id:
                return _json_error(
                    "Agent token is not allowed for this device context",
                    status=403,
                    error_code="DEVICE_CONTEXT_MISMATCH",
                    device_id=target_device_id,
                )

            denied = await _require_permission(session, auth_context, "ticket.tool.run")
            if denied:
                return denied

            agent_info = state.get_agent(target_device_id) if hasattr(state, "get_agent") else None
            if not agent_info:
                return _json_error(
                    "Device agent is offline",
                    status=503,
                    error_code="DEVICE_OFFLINE",
                    device_id=target_device_id,
                )

            source_outbox = await outbox_repo.get_latest_by_operation_id(operation_id)
            if source_outbox is None or source_outbox.command != "run_tool":
                return _json_error(
                    "Replay payload is not available for this operation",
                    status=409,
                    error_code="RETRY_PARAMS_UNAVAILABLE",
                    operation_id=operation_id,
                )

            tool_name = str(target_op.tool_name)
            if source_outbox.params is None or not isinstance(source_outbox.params, dict):
                return _json_error(
                    "Replay payload is not available for this operation",
                    status=409,
                    error_code="RETRY_PARAMS_UNAVAILABLE",
                    operation_id=operation_id,
                )
            extracted_params = _extract_replay_params(source_outbox, tool_name, target_ticket_id)
            if extracted_params is None:
                return _json_error(
                    "Replay payload is not available for this operation",
                    status=409,
                    error_code="RETRY_PARAMS_UNAVAILABLE",
                    operation_id=operation_id,
                )
            replay_params = extracted_params

            tool_service = ToolExecutionService(state)
            metadata = await _resolve_retry_tool_metadata(
                tool_service=tool_service,
                device_id=target_device_id,
                tool_name=tool_name,
            )
            if metadata is None:
                return _json_error(
                    "Tool is not currently available for this device",
                    status=409,
                    error_code="TOOL_UNAVAILABLE",
                    operation_id=operation_id,
                    tool_name=tool_name,
                    device_id=target_device_id,
                )

            risk_level = str(getattr(metadata, "risk_level", None) or "safe_read")
            denied = await _require_permission(session, auth_context, _tool_risk_permission(risk_level))
            if denied:
                return denied

            policy_decision = PolicyEngine(config={"allow_remote_code": ALLOW_REMOTE_CODE}).check_policy(
                actor_role=auth_context.actor_role,
                tool_name=tool_name,
                metadata=metadata,
                params=replay_params,
            )
            if not policy_decision.allow:
                return _json_error(
                    "Policy violation",
                    status=403,
                    error_code=policy_decision.reason or "POLICY_DENIED",
                    required_role=policy_decision.required_role,
                    actor_role=auth_context.actor_role,
                    tool_name=tool_name,
                )

            original_job_id = target_op.job_id
            if policy_decision.requires_consent:
                new_retry_count = await op_repo.increment_retry_count_if_available(operation_id)
                if new_retry_count is None:
                    return _json_error(
                        "Operation retry limit reached",
                        status=409,
                        error_code="RETRY_LIMIT_REACHED",
                        operation_id=operation_id,
                        retry_count=retry_count,
                        max_retries=max_retries,
                    )

                ui_publisher = state.ui_publisher if hasattr(state, "ui_publisher") else None
                op_service = OperationService(session, publisher=ui_publisher)
                retry_operation = await op_service.enqueue_operation(
                    operation_id=retry_operation_id,
                    device_id=target_device_id,
                    kind="tool_call",
                    actor_role=auth_context.actor_role,
                    trace_id=retry_trace_id,
                    ticket_id=target_ticket_id,
                    job_id=original_job_id,
                    tool_name=tool_name,
                    retry_of_operation_id=operation_id,
                    max_retries=max_retries,
                    initial_status="waiting_consent",
                )
                try:
                    await create_operation_user_consent(
                        session,
                        operation=retry_operation,
                        ticket=ticket,
                        requested_by_actor_id=auth_context.actor_id,
                        requested_by_role=auth_context.actor_role,
                        risk_level=risk_level,
                        tool_name=tool_name,
                        params=replay_params,
                        policy_decision=policy_decision,
                    )
                except ConsentAccessError as exc:
                    await session.rollback()
                    return _json_error(str(exc), status=exc.status, error_code=exc.error_code)
                event_trace_id = str(getattr(retry_operation, "trace_id", None) or retry_trace_id)
                event_params = redact_operation_event_params(replay_params)
                event_payload = {
                    "event": "operation_retry_consent_requested",
                    "operation_id": operation_id,
                    "retry_operation_id": retry_operation_id,
                    "retry_of_operation_id": operation_id,
                    "tool_name": tool_name,
                    "params": event_params,
                    "reason": reason,
                    "actor_id": auth_context.actor_id,
                    "actor_role": auth_context.actor_role,
                    "risk_level": risk_level,
                    "requires_consent": True,
                    "status": "waiting_consent",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                started_result = await ticket_repo.add_event(
                    ticket_id=target_ticket_id,
                    device_id=target_device_id,
                    agent_seq=None,
                    event_type="tool_call_started",
                    payload={
                        **event_payload,
                        "event": "tool_call_started",
                        "status": "waiting_consent",
                    },
                    trace_id=event_trace_id,
                    operation_id=retry_operation_id,
                )
                consent_result = await ticket_repo.add_event(
                    ticket_id=target_ticket_id,
                    device_id=target_device_id,
                    agent_seq=None,
                    event_type="operation_retry_consent_requested",
                    payload=event_payload,
                    trace_id=event_trace_id,
                    operation_id=retry_operation_id,
                )
                if started_result is not None or consent_result is not None:
                    await session.commit()
                else:
                    await session.rollback()

                return web.json_response(
                    {
                        "status": "waiting_consent",
                        "operation_id": retry_operation_id,
                        "retry_of_operation_id": operation_id,
                        "ticket_id": target_ticket_id,
                        "device_id": target_device_id,
                        "tool_name": tool_name,
                        "poll_url": f"/api/operations/{retry_operation_id}",
                        "trace_id": event_trace_id,
                        "retry_requires_consent": True,
                        "consent_state": "waiting_consent",
                        "consent_action_url": f"/api/operations/{retry_operation_id}/approve",
                    },
                    status=202,
                )

            new_retry_count = await op_repo.increment_retry_count_if_available(operation_id)
            if new_retry_count is None:
                return _json_error(
                    "Operation retry limit reached",
                    status=409,
                    error_code="RETRY_LIMIT_REACHED",
                    operation_id=operation_id,
                    retry_count=retry_count,
                    max_retries=max_retries,
                )

            ui_publisher = state.ui_publisher if hasattr(state, "ui_publisher") else None
            op_service = OperationService(session, publisher=ui_publisher)
            await op_service.enqueue_operation(
                operation_id=retry_operation_id,
                device_id=target_device_id,
                kind="tool_call",
                actor_role=auth_context.actor_role,
                trace_id=retry_trace_id,
                ticket_id=target_ticket_id,
                job_id=original_job_id,
                tool_name=tool_name,
                retry_of_operation_id=operation_id,
                max_retries=max_retries,
                initial_status="queued",
            )
            await session.commit()

        dispatch_params = dict(replay_params)
        dispatch_params["_operation_id"] = retry_operation_id
        result = await ToolExecutionService(state).run_tool(
            device_id=target_device_id,
            ticket_id=target_ticket_id,
            tool_name=tool_name,
            params=dispatch_params,
            call_id=str(uuid.uuid4()),
            auth_context=auth_context,
            wait_for_result=False,
        )

        dispatch_status = str(result.get("status") or "accepted")
        if dispatch_status != "accepted":
            return _json_error(
                str(result.get("error") or "Tool retry dispatch failed"),
                status=503,
                error_code=str(result.get("error_code") or "TOOL_RETRY_DISPATCH_FAILED"),
                operation_id=retry_operation_id,
                retry_of_operation_id=operation_id,
            )

        async with get_session() as event_session:
            event_repo = TicketEventsRepo(event_session)
            ev_result = await event_repo.add_event(
                ticket_id=target_ticket_id,
                device_id=target_device_id,
                agent_seq=None,
                event_type="operation_retried",
                payload={
                    "event": "operation_retried",
                    "operation_id": operation_id,
                    "retry_operation_id": retry_operation_id,
                    "retry_of_operation_id": operation_id,
                    "tool_name": tool_name,
                    "reason": reason,
                    "actor_id": auth_context.actor_id,
                    "actor_role": auth_context.actor_role,
                    "risk_level": risk_level,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
                trace_id=str(result.get("trace_id") or retry_trace_id),
                operation_id=retry_operation_id,
            )
            if ev_result is not None:
                await event_session.commit()
            else:
                await event_session.rollback()

        return web.json_response(
            {
                "status": "accepted",
                "operation_id": retry_operation_id,
                "retry_of_operation_id": operation_id,
                "ticket_id": target_ticket_id,
                "device_id": target_device_id,
                "tool_name": tool_name,
                "poll_url": f"/api/operations/{retry_operation_id}",
                "trace_id": str(result.get("trace_id") or retry_trace_id),
            },
            status=202,
        )

    except Exception as e:
        logger.error(f"[handle_retry_operation] Error: {e}", exc_info=True)
        return _json_error(str(e), status=500, error_code="OPERATION_RETRY_FAILED")


async def _ensure_web_support_can_cancel_operation(
    session,
    auth_context: AuthContext,
    target_op,
) -> web.Response | None:
    if auth_context.actor_role not in {"admin", "support"}:
        return _json_error(
            "Support/admin role required",
            status=403,
            error_code="FORBIDDEN",
            required_role="support",
        )

    denied = await _require_permission(session, auth_context, "ticket.tool.run")
    if denied:
        return denied

    ticket_id = str(getattr(target_op, "ticket_id", None) or "").strip()
    if not ticket_id:
        return _json_error(
            "Operation is not bound to a support ticket",
            status=404,
            error_code="OPERATION_TICKET_NOT_FOUND",
        )

    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        return _json_error(
            "Ticket not found for operation",
            status=404,
            error_code="TICKET_NOT_FOUND",
        )

    return None


async def _handle_cancel_operation(
    request: web.Request,
    *,
    web_support_boundary: bool = False,
) -> web.Response:
    """
    POST /api/operations/{operation_id}/cancel
    
    Отменить операцию.
    
    1. Проверяет идемпотентность (active_cancel_operation_id)
    2. Устанавливает статус cancel_requested в operations с status_before_cancel
    3. Создает cancel-op операцию (kind="cancel_operation")
    4. Устанавливает active_cancel_operation_id в target-op
    5. Отправляет команду cancel_operation через device_outbox
    6. Записывает op_cancel_requested event в ticket_events
    
    Args:
        operation_id: Operation ID from URL
    
    Returns:
        JSON with operation status
    """
    try:
        operation_id = request.match_info["operation_id"]
        
        # КРИТИЧНО: Получаем actor_role из AuthContext, не из JSON body
        auth_context: AuthContext = request.get('auth_context')
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED"
            }, status=401)
        
        # Получить body для reason
        body = await request.json() if request.content_type == "application/json" else {}
        cancel_reason = body.get("reason")
        
        # КРИТИЧНО: Игнорируем actor_role из JSON body с warning
        if "actor_role" in body:
            logger.warning(
                f"[handle_cancel_operation] actor_role in JSON body ignored: "
                f"using actor_role={auth_context.actor_role} from AuthContext"
            )
            body.pop("actor_role", None)
        
        # КРИТИЧНО: Используем actor_role из AuthContext
        actor_role = auth_context.actor_role
        
        async with get_session() as session:
            # Получить операцию
            repo = OperationsRepo(session)
            target_op = await repo.get_by_operation_id(operation_id)
            
            if not target_op:
                return web.json_response({
                    "status": "error",
                    "error": "Operation not found"
                }, status=404)

            if web_support_boundary:
                denied = await _ensure_web_support_can_cancel_operation(session, auth_context, target_op)
                if denied:
                    return denied
            
            # Проверить, что операцию можно отменить
            terminal_statuses = ["succeeded", "failed", "timed_out", "canceled"]
            if target_op.status in terminal_statuses:
                return web.json_response({
                    "status": "noop",
                    "reason": "already_terminal",
                    "target_operation_id": operation_id
                }, status=409)
            
            # Идемпотентность: если уже cancel_requested, вернуть существующий cancel_operation_id
            if target_op.status == "cancel_requested":
                if target_op.active_cancel_operation_id:
                    return web.json_response({
                        "status": "ok",
                        "message": "Cancel already requested",
                        "target_operation_id": operation_id,
                        "cancel_operation_id": target_op.active_cancel_operation_id
                    })
                else:
                    # Странная ситуация: cancel_requested но нет active_cancel_operation_id
                    logger.warning(
                        f"[handle_cancel_operation] Operation {operation_id} in cancel_requested "
                        f"but no active_cancel_operation_id"
                    )
            
            # Создать cancel-op операцию
            cancel_operation_id = str(uuid.uuid4())
            cancel_trace_id = str(getattr(target_op, "trace_id", None) or "").strip() or str(uuid.uuid4())
            
            # КРИТИЧНО: Используем UiPublisher из state для push обновлений
            state = request.app.get('state')
            ui_publisher = state.ui_publisher if state and hasattr(state, 'ui_publisher') else None
            op_service = OperationService(session, publisher=ui_publisher)
            
            success = await op_service.mark_cancel_requested(
                operation_id=operation_id,
                status_before_cancel=target_op.status,
                cancel_reason=cancel_reason,
                active_cancel_operation_id=cancel_operation_id,
                expected_statuses=[target_op.status]
            )
            
            if not success:
                await session.rollback()
                async with get_session() as check_session:
                    current_op = await OperationsRepo(check_session).get_by_operation_id(operation_id)
                
                if current_op and current_op.status == "cancel_requested" and current_op.active_cancel_operation_id:
                    return web.json_response({
                        "status": "ok",
                        "message": "Cancel already requested",
                        "target_operation_id": operation_id,
                        "cancel_operation_id": current_op.active_cancel_operation_id
                    })
                
                if current_op and current_op.status in terminal_statuses:
                    return web.json_response({
                        "status": "noop",
                        "reason": "already_terminal",
                        "target_operation_id": operation_id
                    }, status=409)
                
                return web.json_response({
                    "status": "error",
                    "error": "Failed to update operation status (concurrent modification?)"
                }, status=409)
            
            # Создать cancel-op операцию
            cancel_op = await op_service.enqueue_operation(
                operation_id=cancel_operation_id,
                device_id=target_op.device_id,
                kind="cancel_operation",
                actor_role=actor_role,
                trace_id=cancel_trace_id,
                ticket_id=target_op.ticket_id,
                job_id=target_op.job_id,
                tool_name=None
            )
            
            # Установить cancel_target_operation_id в cancel-op
            await repo.update_status(
                operation_id=cancel_operation_id,
                new_status="queued",
                cancel_target_operation_id=operation_id
            )
            
            # Установить статус cancel_requested в target-op с status_before_cancel
            # target-op already moved to cancel_requested above.
            
            # Записать op_cancel_requested event в ticket_events (если есть ticket_id)
            # Stage 7: отдельная сессия — при IntegrityError (дубликат) основной flow не ломается
            if target_op.ticket_id:
                async with get_session() as ev_session:
                    ev_repo = TicketEventsRepo(ev_session)
                    ev_result = await ev_repo.add_event(
                        ticket_id=target_op.ticket_id,
                        device_id=target_op.device_id,
                        agent_seq=None,  # Server-originated
                        event_type="op_cancel_requested",
                        payload={
                            "operation_id": operation_id,
                            "cancel_operation_id": cancel_operation_id,
                            "status_before_cancel": target_op.status,
                            "reason": cancel_reason
                        },
                        trace_id=cancel_trace_id,
                        operation_id=operation_id
                    )
                    if ev_result is not None:
                        await ev_session.commit()
                    else:
                        await ev_session.rollback()
            
            # Отправить команду cancel_operation через device_outbox
            outbox_repo = DeviceOutboxRepo(session)
            cancel_outbox_id = await outbox_repo.enqueue_command(
                device_id=target_op.device_id,
                command_id=cancel_operation_id,  # command_id == operation_id для cancel-op
                command="cancel_operation",
                params={
                    "target_operation_id": operation_id,
                    "operation_id": operation_id  # Для обратной совместимости
                },
                request_id=cancel_operation_id,
                trace_id=cancel_trace_id,
                actor_role=actor_role,
                operation_id=cancel_operation_id
            )
            
            await session.commit()

            # Best-effort fast path: if the agent is online, push cancel immediately
            # instead of waiting for the next dispatch cycle.
            state = request.app.get("state")
            agent_info = state.get_agent(target_op.device_id) if state else None
            if agent_info:
                try:
                    async with get_session() as send_session:
                        send_repo = DeviceOutboxRepo(send_session)
                        cancel_entry = await send_session.get(DeviceOutbox, cancel_outbox_id)
                        if cancel_entry is not None and cancel_entry.status == "pending":
                            metadata = agent_info.get("metadata", {}) or {}
                            agent_device_id = metadata.get("device_id", target_op.device_id)
                            await _send_single_command(
                                state_manager=state,
                                ws=agent_info["ws"],
                                agent_device_id=agent_device_id,
                                cmd=cancel_entry,
                                repo=send_repo,
                            )
                            await send_session.commit()
                            logger.info(
                                f"[handle_cancel_operation] Immediate dispatch sent for cancel_operation "
                                f"cancel_operation_id={cancel_operation_id}"
                            )
                except Exception as dispatch_exc:
                    logger.warning(
                        f"[handle_cancel_operation] Immediate dispatch skipped for "
                        f"cancel_operation_id={cancel_operation_id}: {dispatch_exc}"
                    )
             
            logger.info(
                f"[handle_cancel_operation] Cancel requested: "
                f"target_operation_id={operation_id} cancel_operation_id={cancel_operation_id}"
            )
            
            return web.json_response({
                "status": "ok",
                "target_operation_id": operation_id,
                "cancel_operation_id": cancel_operation_id
            })
    
    except Exception as e:
        logger.error(f"[handle_cancel_operation] Error: {e}", exc_info=True)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_cancel_operation(request: web.Request) -> web.Response:
    return await _handle_cancel_operation(request)


@require_auth("admin", "support")
async def handle_web_support_cancel_operation(request: web.Request) -> web.Response:
    return await _handle_cancel_operation(request, web_support_boundary=True)


async def handle_approve_consent(request: web.Request) -> web.Response:
    """
    POST /api/operations/{operation_id}/approve
    
    Approve consent for operation in waiting_consent status.
    
    Phase 5: Transitions operation from waiting_consent → queued and enqueues command.
    
    Request JSON (optional):
    {
        "reason": "string" (optional)
    }
    
    Returns:
        200 OK: {"status": "ok", "operation_id": "..."}
        400 Bad Request: Operation not in waiting_consent
        401 Unauthorized: Authentication required
        404 Not Found: Operation not found
    """
    try:
        # Phase 2: Получаем actor_role из AuthContext
        auth_context: AuthContext = request.get('auth_context')
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED"
            }, status=401)
        
        operation_id = request.match_info["operation_id"]
        
        # Получаем reason из body (опционально)
        data = await request.json() if request.content_length else {}
        reason = data.get("reason")
        
        # КРИТИЧНО: Используем actor_role из AuthContext
        actor_role = auth_context.actor_role
        decided_by = auth_context.actor_id  # user_login для UI, device_id для agent
        
        async with get_session() as session:
            # КРИТИЧНО: Используем UiPublisher из state для push обновлений
            state = request.app.get('state')
            ui_publisher = state.ui_publisher if state and hasattr(state, 'ui_publisher') else None
            op_service = OperationService(session, publisher=ui_publisher)
            
            success = await op_service.approve_consent(
                operation_id=operation_id,
                decided_by=decided_by,
                reason=reason
            )
            
            if not success:
                # Проверяем, существует ли операция
                repo = OperationsRepo(session)
                operation = await repo.get_by_operation_id(operation_id)
                
                if not operation:
                    return web.json_response({
                        "status": "error",
                        "error": "Operation not found",
                        "error_code": "NOT_FOUND"
                    }, status=404)
                
                if operation.status != "waiting_consent":
                    return web.json_response({
                        "status": "error",
                        "error": f"Operation not in waiting_consent status (current: {operation.status})",
                        "error_code": "INVALID_STATUS",
                        "current_status": operation.status
                    }, status=400)
                
                # Другая ошибка
                return web.json_response({
                    "status": "error",
                    "error": "Failed to approve consent"
                }, status=500)
            
            await session.commit()

            dispatch_result = await ToolExecutionService(state).resume_approved_operation(
                operation_id,
                auth_context=auth_context,
            )
            if dispatch_result.get("status") != "accepted":
                return web.json_response({
                    "status": "error",
                    "error": dispatch_result.get("error") or "approved operation dispatch failed",
                    "error_code": dispatch_result.get("error_code") or "APPROVED_OPERATION_DISPATCH_FAILED",
                    "operation_id": operation_id,
                }, status=500)
            
            logger.info(
                f"[handle_approve_consent] Consent approved: "
                f"operation_id={operation_id} decided_by={decided_by}"
            )
            
            return web.json_response({
                "status": "ok",
                "operation_id": operation_id,
                "message": "Consent approved, operation enqueued"
            })
    
    except Exception as e:
        logger.error(f"[handle_approve_consent] Error: {e}", exc_info=True)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_deny_consent(request: web.Request) -> web.Response:
    """
    POST /api/operations/{operation_id}/deny
    
    Deny consent for operation in waiting_consent status.
    
    Phase 5: Transitions operation from waiting_consent → denied (terminal status).
    
    Request JSON (optional):
    {
        "reason": "string" (optional)
    }
    
    Returns:
        200 OK: {"status": "ok", "operation_id": "..."}
        400 Bad Request: Operation not in waiting_consent
        401 Unauthorized: Authentication required
        404 Not Found: Operation not found
    """
    try:
        # Phase 2: Получаем actor_role из AuthContext
        auth_context: AuthContext = request.get('auth_context')
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED"
            }, status=401)
        
        operation_id = request.match_info["operation_id"]
        
        # Получаем reason из body (опционально)
        data = await request.json() if request.content_length else {}
        reason = data.get("reason")
        
        # КРИТИЧНО: Используем actor_role из AuthContext
        actor_role = auth_context.actor_role
        decided_by = auth_context.actor_id  # user_login для UI, device_id для agent
        
        async with get_session() as session:
            # КРИТИЧНО: Используем UiPublisher из state для push обновлений
            state = request.app.get('state')
            ui_publisher = state.ui_publisher if state and hasattr(state, 'ui_publisher') else None
            op_service = OperationService(session, publisher=ui_publisher)
            
            success = await op_service.deny_consent(
                operation_id=operation_id,
                decided_by=decided_by,
                reason=reason
            )
            
            if not success:
                # Проверяем, существует ли операция
                repo = OperationsRepo(session)
                operation = await repo.get_by_operation_id(operation_id)
                
                if not operation:
                    return web.json_response({
                        "status": "error",
                        "error": "Operation not found",
                        "error_code": "NOT_FOUND"
                    }, status=404)
                
                if operation.status != "waiting_consent":
                    return web.json_response({
                        "status": "error",
                        "error": f"Operation not in waiting_consent status (current: {operation.status})",
                        "error_code": "INVALID_STATUS",
                        "current_status": operation.status
                    }, status=400)
                
                # Другая ошибка
                return web.json_response({
                    "status": "error",
                    "error": "Failed to deny consent"
                }, status=500)
            
            await session.commit()
            
            logger.info(
                f"[handle_deny_consent] Consent denied: "
                f"operation_id={operation_id} decided_by={decided_by} reason={reason}"
            )
            
            return web.json_response({
                "status": "ok",
                "operation_id": operation_id,
                "message": "Consent denied, operation marked as denied"
            })
    
    except Exception as e:
        logger.error(f"[handle_deny_consent] Error: {e}", exc_info=True)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)
