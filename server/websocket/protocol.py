"""
Протокол обмена сообщениями через WebSocket.
"""

import asyncio
import uuid
import json
import time
from typing import Dict, Optional, List
from datetime import datetime, timezone
from aiohttp import web
from loguru import logger
from config import (
    WS_COMMAND_TIMEOUT,
    WS_COMMAND_MAX_INFLIGHT_GLOBAL,
    WS_COMMAND_MAX_INFLIGHT_PER_DEVICE,
    WS_COMMAND_MAX_INFLIGHT_PER_DEVICE_RUN_TOOL,
)


class WsCommandQueueFullError(Exception):
    """Очередь WS-команд переполнена (лимит семафоров). Возвращать HTTP 429."""
    error_code = "WS_COMMAND_QUEUE_FULL"


async def send_ws_rpc_request(
    state,
    device_id: str,
    method: str,
    params: dict,
    *,
    actor_role: str = "admin",
    timeout: float = 30.0,
    trace_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    ticket_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> dict:
    """Send a Protocol V3 rpc_request to an online agent and wait for rpc_response."""
    agent_info = state.get_agent(device_id)
    if not agent_info:
        connected_ids = list(state.connected_agents.keys()) if hasattr(state, "connected_agents") else []
        logger.warning(
            f"[send_ws_rpc_request] Agent {device_id} not in connected_agents; "
            f"current connected_agents ({len(connected_ids)}): {connected_ids}"
        )
        raise ValueError(f"Agent {device_id} not connected")

    ws = agent_info.get("ws")
    if ws is None or getattr(ws, "closed", False):
        raise ValueError(f"Agent {device_id} websocket is not available")

    if not getattr(state, "_ws_command_global_semaphore", None):
        state._ws_command_global_semaphore = asyncio.Semaphore(WS_COMMAND_MAX_INFLIGHT_GLOBAL)
        state._ws_command_per_device_semaphores = {}
        state._ws_command_per_device_run_tool_semaphores = {}
        state._ws_command_semaphore_lock = asyncio.Lock()
    async with state._ws_command_semaphore_lock:
        if device_id not in state._ws_command_per_device_semaphores:
            state._ws_command_per_device_semaphores[device_id] = asyncio.Semaphore(WS_COMMAND_MAX_INFLIGHT_PER_DEVICE)
    device_sem = state._ws_command_per_device_semaphores[device_id]
    global_sem = state._ws_command_global_semaphore

    acquired_global = acquired_device = False
    try:
        await asyncio.wait_for(global_sem.acquire(), timeout=2.0)
        acquired_global = True
        await asyncio.wait_for(device_sem.acquire(), timeout=2.0)
        acquired_device = True
    except asyncio.TimeoutError:
        if acquired_device:
            device_sem.release()
        if acquired_global:
            global_sem.release()
        logger.warning(
            f"[send_ws_rpc_request] Queue full: device_id={device_id} method={method}"
        )
        raise WsCommandQueueFullError("WS RPC queue full")

    request_id = str(uuid.uuid4())
    trace_value = trace_id or str(uuid.uuid4())
    future = asyncio.get_event_loop().create_future()
    metadata = agent_info.setdefault("metadata", {})
    pending_map = metadata.setdefault("pending_rpc_futures", {})
    pending_map[request_id] = future

    envelope = {
        "type": "rpc_request",
        "request_id": request_id,
        "device_id": device_id,
        "protocol_version": "ws_ticket_v3",
        "trace_id": trace_value,
        "payload": {
            "method": method,
            "params": params if isinstance(params, dict) else {},
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_role": actor_role or "admin",
        },
    }
    if idempotency_key:
        envelope["idempotency_key"] = idempotency_key
    if ticket_id:
        envelope["ticket_id"] = ticket_id
    if job_id:
        envelope["job_id"] = job_id

    logger.info(
        f"[send_ws_rpc_request] TX rpc_request: device_id={device_id} "
        f"method={method} request_id={request_id}"
    )
    try:
        await ws.send_json(envelope)
        response = await asyncio.wait_for(future, timeout=timeout)
        logger.info(
            f"[send_ws_rpc_request] RX rpc_response: device_id={device_id} "
            f"method={method} request_id={request_id}"
        )
        return response
    except asyncio.TimeoutError:
        logger.error(
            f"[send_ws_rpc_request] Timeout waiting for rpc_response: "
            f"device_id={device_id} method={method} request_id={request_id}"
        )
        pending_map.pop(request_id, None)
        raise
    except Exception:
        pending_map.pop(request_id, None)
        raise
    finally:
        if acquired_global:
            global_sem.release()
        if acquired_device:
            device_sem.release()


async def send_outbox_ack(
    ws: web.WebSocketResponse,
    outbox_ids: List[str],
    agent_device_id: str,
    trace_id: str
) -> None:
    """
    Отправляет Protocol V3 outbox_ack.
    
    КРИТИЧНО: trace_id ДОЛЖЕН быть из входящего envelope (корреляция).
    Не генерируем новый trace_id для ACK - это нарушает трассировку.
    
    Args:
        ws: WebSocket connection
        outbox_ids: List of outbox IDs to acknowledge
        agent_device_id: Device ID of the agent
        trace_id: Trace ID from the incoming envelope
    """
    if not trace_id:
        logger.error("send_outbox_ack called without trace_id - this is a bug!")
        trace_id = str(uuid.uuid4())  # Fallback, но это ошибка
    
    ack_envelope = {
        "type": "outbox_ack",  # НЕ "ack"!
        "request_id": str(uuid.uuid4()),
        "device_id": agent_device_id,
        "protocol_version": "ws_ticket_v3",
        "trace_id": trace_id,  # Из входящего envelope!
        "payload": {
            "outbox_ids": outbox_ids
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_role": "server"
        }
    }
    
    try:
        await ws.send_json(ack_envelope)
        logger.info(f"[V3] TX outbox_ack: {len(outbox_ids)} items, trace_id={trace_id}")
    except Exception as e:
        logger.error(f"[V3] Failed to send outbox_ack: {e}")


async def send_outbox_nack(
    ws: web.WebSocketResponse,
    outbox_ids: List[str],
    agent_device_id: str,
    retryable: bool,
    error_code: str,
    error_message: str,
    trace_id: str,
    retry_after_sec: Optional[int] = None
) -> None:
    """
    Отправляет Protocol V3 outbox_nack.
    
    КРИТИЧНО: trace_id ДОЛЖЕН быть из входящего envelope (корреляция).
    
    Args:
        ws: WebSocket connection
        outbox_ids: List of outbox IDs to negative acknowledge
        agent_device_id: Device ID of the agent
        retryable: Whether the error is retryable
        error_code: Error code (e.g. UNKNOWN_TICKET, DEVICE_MISMATCH)
        error_message: Human-readable error message
        trace_id: Trace ID from the incoming envelope
        retry_after_sec: Optional seconds to wait before retry
    """
    if not trace_id:
        logger.error("send_outbox_nack called without trace_id - this is a bug!")
        trace_id = str(uuid.uuid4())  # Fallback
    
    nack_envelope = {
        "type": "outbox_nack",
        "request_id": str(uuid.uuid4()),
        "device_id": agent_device_id,
        "protocol_version": "ws_ticket_v3",
        "trace_id": trace_id,  # Из входящего envelope!
        "payload": {
            "outbox_ids": outbox_ids,
            "retryable": retryable,
            "retry_after_sec": retry_after_sec,
            "error": {
                "code": error_code,
                "message": error_message
            }
        },
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_role": "server"
        }
    }
    
    try:
        await ws.send_json(nack_envelope)
        logger.warning(
            f"[V3] TX outbox_nack: {len(outbox_ids)} items, "
            f"code={error_code}, retryable={retryable}, trace_id={trace_id}"
        )
    except Exception as e:
        logger.error(f"[V3] Failed to send outbox_nack: {e}")


async def push_chat_event_to_ui(state, job_id: str, event: dict):
    """
    Отправляет событие чата всем подписанным UI WebSocket'ам.
    
    Использует единый SubscriptionRegistry для подписок.
    Для событий chat_invite также отправляет всем admin/support подключениям.
    
    Args:
        state: StateManager instance
        job_id: ID чата
        event: Событие (ChatEvent)
    """
    # Формируем сообщение для UI
    message = {
        "type": "chat_event_committed",
        "job_id": job_id,
        "event": event,
        "ts": time.time()
    }
    
    # Для chat_invite отправляем всем admin/support подключениям (legacy broadcast)
    if event.get("event") == "chat_invite":
        logger.info(f"[push_chat_event_to_ui] Broadcasting chat_invite job_id={job_id} to all admin/support connections")
        
        dead_connections = []
        for conn_id, conn_data in state.ui_connections.items():
            ws = conn_data.get("ws")
            role = conn_data.get("role")
            
            # Отправляем только admin и support
            if role in ["admin", "support"]:
                try:
                    await ws.send_json(message)
                    logger.debug(f"[push_chat_event_to_ui] Sent chat_invite to {role} connection {conn_id}")
                except Exception as e:
                    logger.error(f"[push_chat_event_to_ui] Failed to send chat_invite to {conn_id}: {e}")
                    dead_connections.append(conn_id)
        
        # Удаляем мертвые подключения
        for conn_id in dead_connections:
            state.ui_connections.pop(conn_id, None)
            logger.debug(f"[push_chat_event_to_ui] Removed dead connection {conn_id}")
    
    # Для всех событий (включая chat_invite) отправляем подписчикам через SubscriptionRegistry
    if state.subscription_registry:
        await state.subscription_registry.broadcast_to_chat(job_id, message)
    else:
        # Fallback: используем старый механизм через chat_sessions
        if job_id in state.chat_sessions:
            session = state.chat_sessions[job_id]
            subscribers = session.get("subscribers", set())
            
            dead_sockets = set()
            for ws in subscribers:
                try:
                    await ws.send_json(message)
                    logger.debug(f"[push_chat_event_to_ui] TX to subscriber job_id={job_id} event={event.get('event')}")
                except Exception as e:
                    logger.error(f"[push_chat_event_to_ui] failed to send to subscriber: {e}")
                    dead_sockets.add(ws)
            
            # Удаляем мертвые соединения
            if dead_sockets:
                subscribers -= dead_sockets
                logger.debug(f"[push_chat_event_to_ui] removed {len(dead_sockets)} dead subscribers")


async def send_ws_command(
    state,
    device_id: str,
    command: str,
    params: dict,
    actor_role: Optional[str] = None,
    auth_context: Optional[object] = None,  # AuthContext type hint
    timeout: float = None,
    trace_id: Optional[str] = None,
    wait_for_result: bool = True,
) -> dict:
    """
    Универсальная функция для отправки команд агенту через WebSocket.
    
    Phase C: Commands are enqueued in device_outbox for reliable delivery.
    DeviceOutboxSender will handle actual sending and retry logic.
    
    This function still provides synchronous-like API with Future,
    but persistence ensures commands survive server restarts.
    
    КРИТИЧНО: actor_role берется из auth_context, не из параметра.
    Параметр actor_role сохраняется только для совместимости; новый код должен передавать auth_context.
    
    Args:
        state: StateManager instance
        device_id: ID устройства агента
        command: Имя команды
        params: Параметры команды
        actor_role: Роль актора (compatibility only; use auth_context in new code)
        auth_context: AuthContext с actor_role (приоритет над actor_role параметром)
        timeout: Таймаут ожидания ответа в секундах
        trace_id: Optional trace ID for correlation
        wait_for_result: If False, return immediately after enqueue
    
    Returns:
        dict: Ответ от агента (command_result)
    
    Raises:
        ValueError: Если агент не подключен или DB unavailable
        asyncio.TimeoutError: Если агент не ответил в течение timeout
    """
    # КРИТИЧНО: Используем actor_role из auth_context, не из параметра
    params = dict(params or {})
    if auth_context:
        from auth.context import AuthContext
        if isinstance(auth_context, AuthContext):
            actor_role = auth_context.actor_role
        else:
            logger.warning(
                f"[send_ws_command] Invalid auth_context type: {type(auth_context)}"
            )
    
    # Fallback на параметр actor_role (для обратной совместимости)
    if not actor_role:
        actor_role = "user"  # Минимальная роль по умолчанию
        logger.warning(
            f"[send_ws_command] actor_role not provided, using default 'user'. "
            f"Pass auth_context for proper authentication."
        )
    if timeout is None:
        timeout = WS_COMMAND_TIMEOUT
    
    agent_info = state.get_agent(device_id)
    if not agent_info:
        connected_ids = list(state.connected_agents.keys()) if hasattr(state, "connected_agents") else []
        logger.warning(
            f"[send_ws_command] Agent {device_id} not in connected_agents; "
            f"current connected_agents ({len(connected_ids)}): {connected_ids}"
        )
        raise ValueError(f"Agent {device_id} not connected")
    
    # Лимиты конкурентности: глобальный и per-device семафоры
    if not getattr(state, "_ws_command_global_semaphore", None):
        state._ws_command_global_semaphore = asyncio.Semaphore(WS_COMMAND_MAX_INFLIGHT_GLOBAL)
        state._ws_command_per_device_semaphores = {}
        state._ws_command_per_device_run_tool_semaphores = {}
        state._ws_command_semaphore_lock = asyncio.Lock()
    async with state._ws_command_semaphore_lock:
        if device_id not in state._ws_command_per_device_semaphores:
            state._ws_command_per_device_semaphores[device_id] = asyncio.Semaphore(WS_COMMAND_MAX_INFLIGHT_PER_DEVICE)
        if device_id not in state._ws_command_per_device_run_tool_semaphores:
            state._ws_command_per_device_run_tool_semaphores[device_id] = asyncio.Semaphore(
                WS_COMMAND_MAX_INFLIGHT_PER_DEVICE_RUN_TOOL
            )
    device_sem = state._ws_command_per_device_semaphores[device_id]
    run_tool_sem = state._ws_command_per_device_run_tool_semaphores[device_id]
    global_sem = state._ws_command_global_semaphore
    acquired_global = acquired_device = acquired_run_tool = False
    try:
        await asyncio.wait_for(global_sem.acquire(), timeout=2.0)
        acquired_global = True
        await asyncio.wait_for(device_sem.acquire(), timeout=2.0)
        acquired_device = True
        if command == "run_tool":
            await asyncio.wait_for(run_tool_sem.acquire(), timeout=2.0)
            acquired_run_tool = True
    except asyncio.TimeoutError:
        if acquired_run_tool:
            run_tool_sem.release()
        if acquired_device:
            device_sem.release()
        if acquired_global:
            global_sem.release()
        logger.warning(
            f"[send_ws_command] Queue full: device_id={device_id} command={command}"
        )
        raise WsCommandQueueFullError("WS command queue full")
    
    metadata = agent_info.setdefault("metadata", {})
    agent_device_id = metadata.get("device_id", device_id)
    
    # Generate IDs
    # КРИТИЧНО: command_id == request_id (единый UUID)
    # Если operation_id передан в params (через _operation_id), используем его
    # Иначе генерируем новый
    pre_created_operation_id = params.pop("_operation_id", None)  # Извлекаем и удаляем из params
    if pre_created_operation_id:
        command_id = pre_created_operation_id
        logger.debug(f"[send_ws_command] Using pre-created operation_id: {command_id}")
    else:
        command_id = str(uuid.uuid4())
    request_id = command_id  # Используем тот же UUID

    future = None
    waiter_registered = False
    if wait_for_result:
        future = asyncio.get_event_loop().create_future()
        if hasattr(state, "register_pending_command_future"):
            state.register_pending_command_future(
                command_id,
                future,
                device_id=device_id,
                connection_id=metadata.get("connection_id"),
            )
        else:
            metadata.setdefault("pending_command_futures", {})[command_id] = future
        waiter_registered = True

    # Phase C: Enqueue command in device_outbox AND create operation
    # КРИТИЧНО: operation_id = command_id = request_id (единый UUID)
    try:
        # Import here to avoid circular dependency
        from app.db import get_session
        from app.repos import DeviceOutboxRepo
        from app.repos.ticket_events_repo import TicketEventsRepo
        from app.services import OperationService
        
        # Extract ticket_id and job_id from params (if present)
        ticket_id = params.get("ticket_id") or params.get("chat_job_id")  # Support both formats
        job_id = params.get("job_id") or params.get("chat_job_id")
        
        # Determine operation kind from command
        if command == "run_tool":
            kind = "tool_call"
            tool_name = (
                params.get("tool_name") or params.get("tool") or
                (params.get("params") or {}).get("tool_name") or (params.get("params") or {}).get("tool")
            )
        else:
            kind = "command"
            tool_name = None
        
        # Политика/consent для run_tool проверяются на более высоком уровне (facade/HTTP handlers).
        # send_ws_command остается transport-слоем: enqueue + wait.
        
        async with get_session() as session:
            if not trace_id and ticket_id:
                ticket_trace_repo = TicketEventsRepo(session)
                try:
                    trace_id = await ticket_trace_repo.ensure_ticket_observer_root_trace_id(ticket_id)
                except Exception as exc:
                    logger.debug(f"[send_ws_command] ticket root trace fallback skipped: ticket_id={ticket_id} error={exc}")
            if not trace_id:
                trace_id = str(uuid.uuid4())
            # Атомарно в одной транзакции:
            # 1. Enqueue command в device_outbox
            repo = DeviceOutboxRepo(session)
            outbox_id = await repo.enqueue_command(
                device_id=device_id,
                command_id=command_id,
                command=command,
                params=params,
                request_id=request_id,
                trace_id=trace_id,
                actor_role=actor_role,
                operation_id=command_id  # operation_id = command_id
            )
            
            # 2. Create or get operation (materialized state)
            # КРИТИЧНО: Если операция уже создана (pre_created_operation_id), не создаем заново
            # Просто проверяем что она существует и обновляем job_id/ticket_id если нужно
            # КРИТИЧНО: Используем UiPublisher из state для push обновлений
            ui_publisher = state.ui_publisher if hasattr(state, 'ui_publisher') else None
            op_service = OperationService(session, publisher=ui_publisher)
            from app.repos import OperationsRepo
            op_repo = OperationsRepo(session)
            existing_op = await op_repo.get_by_operation_id(command_id)
            
            if existing_op:
                # Операция уже существует - используем её
                operation = existing_op
                # Обновляем job_id и ticket_id если они изменились
                if job_id and operation.job_id != job_id:
                    operation.job_id = job_id
                if ticket_id and operation.ticket_id != ticket_id:
                    operation.ticket_id = ticket_id
                logger.debug(
                    f"[send_ws_command] Using existing operation: "
                    f"operation_id={command_id}"
                )
            else:
                # Операция не существует - создаем новую
                operation = await op_service.enqueue_operation(
                    operation_id=command_id,  # operation_id = command_id
                    device_id=device_id,
                    kind=kind,
                    tool_name=tool_name,
                    command_name=command if kind == "command" else None,
                    ticket_id=ticket_id,
                    job_id=job_id,
                    actor_role=actor_role,
                    trace_id=trace_id
                )
            
            # КРИТИЧНО: tool_call_started теперь создаётся на сервере в ToolService.run_tool
            # ПЕРЕД отправкой команды, с operation_id сразу. Не нужно обновлять по call_id.
            # Legacy код удалён: больше не делаем UPDATE tool_call_started по call_id.
            # Корреляция теперь по operation_id, call_id - legacy поле (optional).
            
            await session.commit()
            
            logger.info(
                f"[send_ws_command] Enqueued: device_id={device_id} "
                f"command={command} command_id={command_id} outbox_id={outbox_id} "
                f"operation_id={operation.operation_id}"
            )
            dispatch = getattr(state, "device_dispatch_service", None)
            if dispatch is not None:
                try:
                    await dispatch.enqueue_device(device_id)
                except Exception as dispatch_exc:
                    logger.debug(f"[send_ws_command] dispatch enqueue skipped: {dispatch_exc}")
    except Exception as e:
        logger.error(f"[send_ws_command] Failed to enqueue command: {e}")
        if waiter_registered:
            if hasattr(state, "discard_pending_command_future"):
                state.discard_pending_command_future(command_id)
            else:
                metadata.get("pending_command_futures", {}).pop(command_id, None)
            waiter_registered = False
        if acquired_run_tool:
            run_tool_sem.release()
            acquired_run_tool = False
        if acquired_global:
            global_sem.release()
            acquired_global = False
        if acquired_device:
            device_sem.release()
            acquired_device = False
        raise ValueError(f"Failed to enqueue command: {e}")
    
    if not wait_for_result:
        logger.info(
            f"[send_ws_command] Enqueued without waiting: "
            f"command_id={command_id} device_id={device_id} command={command}"
        )
        if acquired_run_tool:
            run_tool_sem.release()
            acquired_run_tool = False
        if acquired_global:
            global_sem.release()
            acquired_global = False
        if acquired_device:
            device_sem.release()
            acquired_device = False
        return {
            "status": "accepted",
            "command_id": command_id,
            "request_id": request_id,
            "operation_id": command_id,
            "device_id": device_id,
            "trace_id": trace_id,
            "wait_for_result": False,
        }

    logger.info(
        f"[send_ws_command] Waiting for command_result: command_id={command_id} "
        f"timeout={timeout}s"
    )

    try:
        # Wait for agent's response
        response = await asyncio.wait_for(future, timeout=timeout)
        logger.info(
            f"[send_ws_command] RX command_result: command_id={command_id} "
            f"status={response.get('payload', {}).get('status', 'unknown')}"
        )
        return response
    except asyncio.TimeoutError:
        logger.error(
            f"[send_ws_command] Timeout waiting for command_result: "
            f"command_id={command_id} device_id={device_id} command={command}"
        )
        if hasattr(state, "discard_pending_command_future"):
            state.discard_pending_command_future(command_id)
        elif command_id in agent_info["metadata"].get("pending_command_futures", {}):
            del agent_info["metadata"]["pending_command_futures"][command_id]
        raise
    except Exception:
        if hasattr(state, "discard_pending_command_future"):
            state.discard_pending_command_future(command_id)
        elif command_id in agent_info["metadata"].get("pending_command_futures", {}):
            del agent_info["metadata"]["pending_command_futures"][command_id]
        raise
    finally:
        if acquired_run_tool:
            run_tool_sem.release()
        if acquired_global:
            global_sem.release()
        if acquired_device:
            device_sem.release()


async def enqueue_command_async(
    state,
    device_id: str,
    command: str,
    params: dict,
    actor_role: str = "user",
    trace_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    job_id: Optional[str] = None,
    operation_id: Optional[str] = None,
    require_online: bool = True,
) -> str:
    """
    Enqueue command without waiting for result (fire-and-forget).
    
    Args:
        state: StateManager instance
        device_id: ID устройства агента
        command: Имя команды
        params: Параметры команды
        actor_role: Роль актора (по умолчанию "user")
        trace_id: Optional trace ID for correlation
        ticket_id: Optional ticket ID
        job_id: Optional job ID
        operation_id: Optional pre-created operation_id
        require_online: Если True (по умолчанию), при отсутствии агента в connected_agents
            выбрасывается ValueError. Если False — команда всегда пишется в device_outbox
            (для Playbook Engine / deferred execution); доставка при появлении online.
    
    Returns:
        str: command_id (operation_id)
    
    Raises:
        ValueError: Если require_online=True и агент не подключен, или DB unavailable
    """
    if require_online:
        agent_info = state.get_agent(device_id)
        if not agent_info:
            connected_ids = list(state.connected_agents.keys()) if hasattr(state, "connected_agents") else []
            logger.warning(
                f"[enqueue_command_async] Agent {device_id} not in connected_agents; "
                f"current connected_agents ({len(connected_ids)}): {connected_ids}"
            )
            raise ValueError(f"Agent {device_id} not connected")
    
    # Generate IDs
    if operation_id:
        command_id = operation_id  # Используем переданный operation_id
    else:
        command_id = str(uuid.uuid4())
    request_id = command_id  # command_id == request_id
    if not trace_id:
        trace_id = str(uuid.uuid4())
    
    # Determine operation kind and command_name для kind=command (метрики, list_tools debounce)
    if command in ["run_tool", "execute_program", "screenshot", "collect"]:
        kind = "tool_call"
        tool_name = params.get("tool_name") or command
        command_name = None
    else:
        kind = "command"
        tool_name = None
        command_name = command
    
    try:
        from app.db import get_session
        from app.repos.device_outbox_repo import DeviceOutboxRepo
        from app.repos.operations_repo import OperationsRepo
        from app.services.operation_service import OperationService
        
        async with get_session() as session:
            # 1. Enqueue command в device_outbox
            repo = DeviceOutboxRepo(session)
            outbox_id = await repo.enqueue_command(
                device_id=device_id,
                command_id=command_id,
                command=command,
                params=params,
                request_id=request_id,
                trace_id=trace_id,
                actor_role=actor_role,
                operation_id=command_id  # operation_id = command_id
            )
            
            # 2. Create or reuse operation (materialized state)
            # Некоторые вызывающие коды передают pre-created operation_id, но reconcile/outbox
            # могут передавать только идентификатор без фактической записи в operations.
            # Поэтому здесь гарантируем наличие materialized operation для любого command_id.
            ui_publisher = state.ui_publisher if hasattr(state, 'ui_publisher') else None
            op_service = OperationService(session, publisher=ui_publisher)
            op_repo = OperationsRepo(session)
            existing_op = await op_repo.get_by_operation_id(command_id)

            if existing_op:
                if job_id and existing_op.job_id != job_id:
                    existing_op.job_id = job_id
                if ticket_id and existing_op.ticket_id != ticket_id:
                    existing_op.ticket_id = ticket_id
                logger.debug(
                    f"[enqueue_command_async] Using existing operation: operation_id={command_id}"
                )
            else:
                await op_service.enqueue_operation(
                    operation_id=command_id,
                    device_id=device_id,
                    kind=kind,
                    tool_name=tool_name,
                    command_name=command_name,
                    ticket_id=ticket_id,
                    job_id=job_id,
                    actor_role=actor_role,
                    trace_id=trace_id
                )
            
            await session.commit()
            
            logger.info(
                f"[enqueue_command_async] Enqueued: device_id={device_id} "
                f"command={command} command_id={command_id} outbox_id={outbox_id} "
                f"operation_id={command_id}"
            )
            dispatch = getattr(state, "device_dispatch_service", None)
            if dispatch is not None:
                try:
                    await dispatch.enqueue_device(device_id)
                except Exception as dispatch_exc:
                    logger.debug(f"[enqueue_command_async] dispatch enqueue skipped: {dispatch_exc}")
    except Exception as e:
        logger.error(f"[enqueue_command_async] Failed to enqueue command: {e}")
        raise ValueError(f"Failed to enqueue command: {e}")
    
    return command_id

