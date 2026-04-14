"""
API обработчики для управления операциями.
"""

import uuid
from datetime import datetime, timezone
from aiohttp import web
from loguru import logger

from app.db import get_session
from app.db.models import DeviceOutbox
from app.repos.operations_repo import OperationsRepo
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.services.operation_service import OperationService
from auth.context import AuthContext
from websocket.device_outbox_sender import _send_single_command


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


async def handle_cancel_operation(request: web.Request) -> web.Response:
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
            cancel_trace_id = str(uuid.uuid4())
            
            # КРИТИЧНО: Используем UiPublisher из state для push обновлений
            state = request.app.get('state')
            ui_publisher = state.ui_publisher if state and hasattr(state, 'ui_publisher') else None
            op_service = OperationService(session, publisher=ui_publisher)
            
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
            success = await op_service.mark_cancel_requested(
                operation_id=operation_id,
                status_before_cancel=target_op.status,
                cancel_reason=cancel_reason,
                active_cancel_operation_id=cancel_operation_id
            )
            
            if not success:
                # Rollback: удалить cancel-op если не удалось обновить target-op
                await session.rollback()
                return web.json_response({
                    "status": "error",
                    "error": "Failed to update operation status (concurrent modification?)"
                }, status=409)
            
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
