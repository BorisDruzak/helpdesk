"""
WebSocket обработчик для UI клиентов.

Протокол:
- ui_hello: аутентификация UI клиента
- subscribe_ticket: подписка на события тикета с catch-up
- unsubscribe_ticket: отписка от тикета
- subscribe_device: подписка на события устройства (опционально)
- unsubscribe_device: отписка от устройства
- ping: keepalive
"""

import uuid
import json
import time
from datetime import datetime, timezone
from typing import Optional
from aiohttp import web, WSMsgType
from loguru import logger
from state_manager import StateManager
from auth.middleware import WEB_SESSION_COOKIE_NAME
from auth.service import AuthService
from auth.context import AuthContext, AuthType

# Import database components (lazy import to handle missing dependencies)
try:
    from app.db import get_session
    from app.repos import TicketEventsRepo, JobEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


def _is_closing_transport_error(error: Exception) -> bool:
    message = str(error or "").lower()
    return (
        "cannot write to closing transport" in message
        or "connection reset by peer" in message
        or "websocket connection is closing" in message
    )


def _extract_session_cookie_token(request: web.Request) -> Optional[str]:
    token = request.cookies.get(WEB_SESSION_COOKIE_NAME)
    if not token:
        return None
    return token.strip() or None


async def send_ticket_catchup(
    ws: web.WebSocketResponse,
    ticket_id: str,
    since_event_id: int,
    limit: int = 500
):
    """
    Send catch-up events for ticket subscription.
    
    Fetches events from DB with id > since_event_id and sends as ticket_event_committed.
    """
    if not DB_AVAILABLE:
        logger.warning(f"[send_ticket_catchup] DB unavailable, skipping catch-up for ticket_id={ticket_id}")
        await ws.send_json({
            "type": "catchup_done",
            "scope": "ticket",
            "id": ticket_id,
            "last_event_id": since_event_id,
            "truncated": False
        })
        return
    
    try:
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            
            # Fetch events with id > since_event_id
            events = await repo.get_events_since_id(
                ticket_id=ticket_id,
                since_event_id=since_event_id,
                limit=limit
            )
            
            truncated = len(events) >= limit
            
            # Send events
            for event in events:
                await ws.send_json({
                    "type": "ticket_event_committed",
                    "ticket_id": ticket_id,
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "operation_id": event.operation_id,
                    "agent_seq": event.agent_seq,
                    "ts": event.created_at.isoformat() if event.created_at else None,
                    "payload": event.payload
                })
            
            # Send catchup_done
            last_event_id = events[-1].id if events else since_event_id
            await ws.send_json({
                "type": "catchup_done",
                "scope": "ticket",
                "id": ticket_id,
                "last_event_id": last_event_id,
                "truncated": truncated
            })
            
            logger.debug(
                f"[send_ticket_catchup] Sent {len(events)} catch-up events "
                f"for ticket_id={ticket_id} since_event_id={since_event_id}"
            )
    except Exception as e:
        logger.error(f"[send_ticket_catchup] Error: {e}", exc_info=True)
        await ws.send_json({
            "type": "error",
            "error": f"Catch-up failed: {str(e)}"
        })


async def send_chat_catchup(
    ws: web.WebSocketResponse,
    job_id: str,
    since_event_id: int,
    limit: int = 500
):
    """
    Send catch-up events for chat subscription.
    
    Fetches job events from DB with id > since_event_id and sends as chat_event_committed.
    """
    if not DB_AVAILABLE:
        logger.warning(f"[send_chat_catchup] DB unavailable, skipping catch-up for job_id={job_id}")
        await ws.send_json({
            "type": "catchup_done",
            "scope": "chat",
            "id": job_id,
            "last_event_id": since_event_id,
            "truncated": False
        })
        return
    
    try:
        async with get_session() as session:
            from app.repos import JobEventsRepo
            repo = JobEventsRepo(session)
            
            # Fetch events with id > since_event_id
            events = await repo.get_events_since_id(
                job_id=job_id,
                since_event_id=since_event_id,
                limit=limit
            )
            
            truncated = len(events) >= limit
            
            # Send events
            for event in events:
                await ws.send_json({
                    "type": "chat_event_committed",
                    "job_id": job_id,
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "ts": event.ts.isoformat() if event.ts else None,
                    "event": event.payload  # Full event payload
                })
            
            # Send catchup_done
            last_event_id = events[-1].id if events else since_event_id
            await ws.send_json({
                "type": "catchup_done",
                "scope": "chat",
                "id": job_id,
                "last_event_id": last_event_id,
                "truncated": truncated
            })
            
            logger.debug(
                f"[send_chat_catchup] Sent {len(events)} catch-up events "
                f"for job_id={job_id} since_event_id={since_event_id}"
            )
    except Exception as e:
        logger.error(f"[send_chat_catchup] Error: {e}", exc_info=True)
        await ws.send_json({
            "type": "error",
            "error": f"Chat catch-up failed: {str(e)}"
        })


async def send_device_catchup(
    ws: web.WebSocketResponse,
    device_id: str,
    since_event_id: int,
    limit: int = 500
):
    """
    Send catch-up events for device subscription.
    
    Fetches device events from DB with id > since_event_id and sends as device_event_committed.
    """
    if not DB_AVAILABLE:
        logger.warning(f"[send_device_catchup] DB unavailable, skipping catch-up for device_id={device_id}")
        await ws.send_json({
            "type": "catchup_done",
            "scope": "device",
            "id": device_id,
            "last_event_id": since_event_id,
            "truncated": False
        })
        return
    
    try:
        async with get_session() as session:
            from app.repos import DeviceEventsRepo
            repo = DeviceEventsRepo(session)
            
            # Fetch events with id > since_event_id
            events = await repo.get_events_since_id(
                device_id=device_id,
                since_event_id=since_event_id,
                limit=limit
            )
            
            truncated = len(events) >= limit
            
            # Send events
            for event in events:
                await ws.send_json({
                    "type": "device_event_committed",
                    "device_id": device_id,
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "device_seq": event.device_seq,
                    "ts": event.created_at.isoformat() if event.created_at else None,
                    "payload": event.payload
                })
            
            # Send catchup_done
            last_event_id = events[-1].id if events else since_event_id
            await ws.send_json({
                "type": "catchup_done",
                "scope": "device",
                "id": device_id,
                "last_event_id": last_event_id,
                "truncated": truncated
            })
            
            logger.debug(
                f"[send_device_catchup] Sent {len(events)} catch-up events "
                f"for device_id={device_id} since_event_id={since_event_id}"
            )
    except Exception as e:
        logger.error(f"[send_device_catchup] Error: {e}", exc_info=True)
        await ws.send_json({
            "type": "error",
            "error": f"Device catch-up failed: {str(e)}"
        })


async def push_ticket_event_committed(
    state: StateManager,
    ticket_id: str,
    event_id: int,
    event_type: str,
    operation_id: Optional[str],
    agent_seq: Optional[int],
    created_at: datetime,
    payload: dict
):
    """
    Push ticket_event_committed to all ticket subscribers.
    
    КРИТИЧНО: Must be called AFTER commit in DB.
    КРИТИЧНО: Не делаем повторный SELECT - используем данные из INSERT RETURNING.
    """
    if not state.subscription_registry:
        return
    
    message = {
        "type": "ticket_event_committed",
        "ticket_id": ticket_id,
        "event_id": event_id,
        "event_type": event_type,
        "operation_id": operation_id,
        "agent_seq": agent_seq,
        "ts": created_at.isoformat() if created_at else None,
        "payload": payload
    }
    
    await state.subscription_registry.broadcast_to_ticket(
        ticket_id,
        message
    )


async def push_operation_updated(
    state: StateManager,
    operation
):
    """
    Push operation_updated to subscribers.
    
    If ticket_id exists → broadcast to ticket subscribers
    Else → broadcast to device subscribers (device-only operations)
    """
    if not state.subscription_registry:
        return
    
    # КРИТИЧНО: Operation не имеет поля updated_at, используем finished_at или queued_at как fallback
    # Определяем актуальный timestamp в зависимости от статуса
    timestamp = None
    if operation.finished_at:
        timestamp = operation.finished_at
    elif operation.started_at:
        timestamp = operation.started_at
    elif operation.accepted_at:
        timestamp = operation.accepted_at
    elif operation.sent_at:
        timestamp = operation.sent_at
    else:
        timestamp = operation.queued_at
    
    message = {
        "type": "operation_updated",
        "operation_id": operation.operation_id,
        "ticket_id": operation.ticket_id,
        "device_id": operation.device_id,
        "status": operation.status,
        "updated_at": timestamp.isoformat() if timestamp else None,
        "error": {
            "code": operation.error_code,
            "message": operation.error_message
        } if operation.error_code else None
    }
    
    if operation.ticket_id:
        await state.subscription_registry.broadcast_to_ticket(
            operation.ticket_id,
            message
        )
    else:
        await state.subscription_registry.broadcast_to_device(
            operation.device_id,
            message
        )


async def websocket_ui_handler(request):
    """
    WebSocket обработчик для веб-UI.
    
    Протокол:
    - ui_hello: аутентификация UI клиента
    - subscribe_ticket: подписка на события тикета с catch-up
    - unsubscribe_ticket: отписка от тикета
    - subscribe_device: подписка на события устройства (опционально)
    - unsubscribe_device: отписка от устройства
    - ping: keepalive
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    state = request.app['state']
    
    connection_id = str(uuid.uuid4())
    auth_context: Optional[AuthContext] = None  # Phase 3: AuthContext после ui_hello
    user_role = None  # Извлекается из токена
    
    # Регистрируем UI connection
    connection_data = {
        "ws": ws,
        "connection_id": connection_id,
        "role": user_role,
        "auth_context": None,  # Phase 3: будет установлен после ui_hello
        "connected_at": time.time(),
        "ticket_subscriptions": set(),
        "presence_key": f"ws:{connection_id}",
    }
    state.register_ui_connection(connection_id, connection_data)
    
    logger.info(f"🟢 Новое UI WebSocket соединение: connection_id={connection_id}")
    
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # a) type == "ui_hello"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    if msg_type == "ui_hello":
                        # Phase 3: Проверяем токен для аутентификации через БД
                        token = data.get("token") or _extract_session_cookie_token(request)
                        
                        if not token:
                            logger.warning(f"🔴 UI попытка подключения без токена: connection_id={connection_id}")
                            await ws.send_json({
                                "type": "error",
                                "error": "Token or session cookie required"
                            })
                            await ws.close(code=4003, message=b"Token or session cookie required")
                            return ws
                        
                        # Проверяем токен через AuthService (БД)
                        auth_service = AuthService(state)
                        token_info = await auth_service.verify_ui_token(token)
                        
                        if not token_info:
                            logger.warning(f"🔴 Невалидный токен UI: {token[:8]}... connection_id={connection_id}")
                            await ws.send_json({
                                "type": "error",
                                "error": "Invalid token"
                            })
                            await ws.close(code=4003, message=b"Invalid token")
                            return ws
                        
                        # КРИТИЧНО: actor_role берется из токена, не из payload
                        user_role = token_info["actor_role"]
                        user_login = token_info["user_login"]
                        
                        # Создаем AuthContext для этого соединения
                        auth_context = AuthContext(
                            actor_id=user_login,
                            actor_role=user_role,
                            auth_type=AuthType.UI_TOKEN,
                            token=token
                        )
                        
                        # Обновляем connection_data
                        connection_data["role"] = user_role
                        connection_data["auth_context"] = auth_context
                        
                        # Игнорируем role из payload с warning (если указан и отличается)
                        payload_role = data.get("role")
                        if payload_role and payload_role != user_role:
                            logger.warning(
                                f"⚠️ Role mismatch in ui_hello: token={user_role}, payload={payload_role}. "
                                f"Using role from token. connection_id={connection_id}"
                            )
                        
                        logger.success(
                            f"✅ UI аутентифицирован: connection_id={connection_id} "
                            f"user_login={user_login} role={user_role}"
                        )
                        
                        await ws.send_json({
                            "type": "ui_hello_ack",
                            "connection_id": connection_id,
                            "role": user_role  # Отправляем роль из токена
                        })
                        continue
                    
                    # Проверяем, что ui_hello был выполнен (auth_context установлен)
                    if msg_type != "ui_hello" and not auth_context:
                        logger.warning(
                            f"🔴 Попытка использовать WebSocket без аутентификации: "
                            f"msg_type={msg_type} connection_id={connection_id}"
                        )
                        await ws.send_json({
                            "type": "error",
                            "error": "Authentication required. Send ui_hello first."
                        })
                        continue
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # b) type == "subscribe_ticket"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "subscribe_ticket":
                        ticket_id = data.get("ticket_id")
                        since_event_id = data.get("since_event_id", 0)  # Default to 0 for full history
                        skip_catchup = bool(data.get("skip_catchup", False))
                        
                        if not ticket_id:
                            await ws.send_json({
                                "type": "error",
                                "error": "Missing ticket_id"
                            })
                            continue
                        
                        # КРИТИЧНО: Access check before subscription
                        # Validate ticket exists and user has access
                        if DB_AVAILABLE:
                            try:
                                async with get_session() as session:
                                    ticket_repo = TicketEventsRepo(session)
                                    ticket = await ticket_repo.get_ticket(ticket_id)
                                    
                                    if not ticket:
                                        await ws.send_json({
                                            "type": "error",
                                            "error": "Ticket not found"
                                        })
                                        continue
                                    
                                    # Authorization check (role-based)
                                    # admin/support can subscribe to any ticket
                                    # user can only subscribe to tickets bound to their device
                                    # Phase 3: Используем auth_context вместо user_role из payload
                                    if auth_context and not auth_context.has_role("admin", "support"):
                                        # user_id check when user_id is implemented (docs/archive/BOTTLENECKS_AND_RISKS.md Phase 3)
                                        pass
                            except Exception as e:
                                logger.error(f"[subscribe_ticket] Error checking access: {e}")
                                await ws.send_json({
                                    "type": "error",
                                    "error": f"Access check failed: {str(e)}"
                                })
                                continue
                        
                        # КРИТИЧНО: Порядок важен - catch-up ДО регистрации подписки
                        # 1. Send catch-up (replay) from DB FIRST
                        if skip_catchup:
                            await ws.send_json({
                                "type": "catchup_done",
                                "scope": "ticket",
                                "id": ticket_id,
                                "last_event_id": since_event_id,
                                "truncated": False
                            })
                        else:
                            await send_ticket_catchup(ws, ticket_id, since_event_id)
                        
                        # 2. THEN register subscription (after catch-up complete)
                        if state.subscription_registry:
                            await state.subscription_registry.add_ticket_subscriber(ticket_id, ws)
                        connection_data.setdefault("ticket_subscriptions", set()).add(ticket_id)
                        if auth_context and auth_context.has_role("admin", "support"):
                            state.touch_ticket_presence(
                                ticket_id,
                                auth_context.actor_id,
                                auth_context.actor_role,
                                presence_key=connection_data.get("presence_key"),
                            )
                        
                        # 3. Send ack
                        await ws.send_json({
                            "type": "subscribe_ack",
                            "ticket_id": ticket_id,
                            "since_event_id": since_event_id
                        })
                        
                        logger.info(
                            f"📋 UI подписан на тикет: connection_id={connection_id} "
                            f"ticket_id={ticket_id} since_event_id={since_event_id}"
                        )
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # c) type == "unsubscribe_ticket"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "unsubscribe_ticket":
                        ticket_id = data.get("ticket_id")
                        if ticket_id and state.subscription_registry:
                            await state.subscription_registry.remove_ticket_subscriber(ticket_id, ws)
                            connection_data.setdefault("ticket_subscriptions", set()).discard(ticket_id)
                            state.remove_ticket_presence(ticket_id, connection_data.get("presence_key"))
                            await ws.send_json({
                                "type": "unsubscribe_ack",
                                "ticket_id": ticket_id
                            })
                            logger.info(
                                f"📋 UI отписан от тикета: connection_id={connection_id} ticket_id={ticket_id}"
                            )
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # d) type == "subscribe_device"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "subscribe_device":
                        device_id = data.get("device_id")
                        since_event_id = data.get("since_event_id", 0)
                        skip_catchup = bool(data.get("skip_catchup", False))
                        skip_catchup = bool(data.get("skip_catchup", False))
                        
                        if not device_id:
                            await ws.send_json({
                                "type": "error",
                                "error": "Missing device_id"
                            })
                            continue
                        
                        # КРИТИЧНО: Access check
                        # Phase 3: Используем auth_context вместо user_role из connection_data
                        if auth_context and not auth_context.has_role("admin", "support"):
                            # For now, allow all (can be enhanced with user_id later)
                            pass
                        
                        # КРИТИЧНО: Порядок важен - catch-up ДО регистрации подписки
                        # 1. Send catch-up FIRST
                        if skip_catchup:
                            await ws.send_json({
                                "type": "catchup_done",
                                "scope": "device",
                                "id": device_id,
                                "last_event_id": since_event_id,
                                "truncated": False
                            })
                        else:
                            await send_device_catchup(ws, device_id, since_event_id)
                        
                        # 2. THEN register subscription
                        if state.subscription_registry:
                            await state.subscription_registry.add_device_subscriber(device_id, ws)
                        
                        # 3. Send ack
                        await ws.send_json({
                            "type": "subscribe_ack",
                            "device_id": device_id,
                            "since_event_id": since_event_id
                        })
                        
                        logger.info(
                            f"📋 UI подписан на устройство: connection_id={connection_id} "
                            f"device_id={device_id} since_event_id={since_event_id}"
                        )
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # e) type == "subscribe_chat"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "subscribe_chat":
                        job_id = data.get("job_id")
                        since_event_id = data.get("since_event_id", 0)
                        
                        if not job_id:
                            await ws.send_json({
                                "type": "error",
                                "error": "Missing job_id"
                            })
                            continue
                        
                        # КРИТИЧНО: Access check
                        # Phase 3: Используем auth_context вместо user_role из connection_data
                        if auth_context and not auth_context.has_role("admin", "support"):
                            # For now, allow all (can be enhanced with user_id later)
                            pass
                        
                        # КРИТИЧНО: Порядок важен - catch-up ДО регистрации подписки
                        # 1. Send catch-up FIRST
                        if skip_catchup:
                            await ws.send_json({
                                "type": "catchup_done",
                                "scope": "chat",
                                "id": job_id,
                                "last_event_id": since_event_id,
                                "truncated": False
                            })
                        else:
                            await send_chat_catchup(ws, job_id, since_event_id)
                        
                        # 2. THEN register subscription
                        if state.subscription_registry:
                            await state.subscription_registry.add_chat_subscriber(job_id, ws)
                        
                        # 3. Send ack
                        await ws.send_json({
                            "type": "subscribe_ack",
                            "job_id": job_id,
                            "since_event_id": since_event_id
                        })
                        
                        logger.info(
                            f"📋 UI подписан на чат: connection_id={connection_id} "
                            f"job_id={job_id} since_event_id={since_event_id}"
                        )
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # e) type == "unsubscribe_chat"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "unsubscribe_chat":
                        job_id = data.get("job_id")
                        if job_id and state.subscription_registry:
                            await state.subscription_registry.remove_chat_subscriber(job_id, ws)
                            await ws.send_json({
                                "type": "unsubscribe_ack",
                                "job_id": job_id
                            })
                            logger.info(
                                f"📋 UI отписан от чата: connection_id={connection_id} job_id={job_id}"
                            )
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # f) type == "unsubscribe_device"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "unsubscribe_device":
                        device_id = data.get("device_id")
                        if device_id and state.subscription_registry:
                            await state.subscription_registry.remove_device_subscriber(device_id, ws)
                            await ws.send_json({
                                "type": "unsubscribe_ack",
                                "device_id": device_id
                            })
                            logger.info(
                                f"📋 UI отписан от устройства: connection_id={connection_id} device_id={device_id}"
                            )
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # f) type == "ping"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "ping":
                        if auth_context and auth_context.has_role("admin", "support"):
                            for subscribed_ticket_id in list(connection_data.get("ticket_subscriptions") or []):
                                state.touch_ticket_presence(
                                    subscribed_ticket_id,
                                    auth_context.actor_id,
                                    auth_context.actor_role,
                                    presence_key=connection_data.get("presence_key"),
                                )
                        await ws.send_json({
                            "type": "pong",
                            "ts": datetime.now(timezone.utc).isoformat()
                        })
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # g) Неизвестный тип
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    else:
                        logger.warning(f"⚠️  Неизвестный тип сообщения от UI: {msg_type}")
                        await ws.send_json({
                            "type": "error",
                            "error": f"Unknown message type: {msg_type}"
                        })
                
                except json.JSONDecodeError:
                    logger.warning(f"⚠️  Получено не-JSON сообщение от UI")
                except Exception as e:
                    if _is_closing_transport_error(e):
                        logger.debug("UI websocket closed while sending a response; suppressing transport noise")
                        break
                    logger.error(f"❌ Ошибка обработки сообщения UI: {e}", exc_info=True)
            
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"❌ Ошибка WebSocket UI: {ws.exception()}")
                break
    
    finally:
        # КРИТИЧНО: Cleanup subscriptions on disconnect
        if state.subscription_registry:
            await state.subscription_registry.cleanup_ws(ws)
        state.clear_ticket_presence_key(connection_data.get("presence_key"))
        
        # Очистка при отключении
        conn_data = state.get_ui_connection(connection_id)
        if conn_data:
            state.unregister_ui_connection(connection_id)
        
        logger.warning(f"🔴 UI WebSocket отключен: connection_id={connection_id}")
    
    return ws
