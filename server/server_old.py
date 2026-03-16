"""
ARCHIVED: не участвует в runtime. TODO в этом файле не входят в рабочий бэклог.
См. docs/BOTTLENECKS_AND_RISKS.md.

WebSocket сервер для управления удалёнными PC агентами (relay-архитектура).

Этот сервер выступает в роли ретранслятора команд между веб-интерфейсом
и удалёнными агентами. Сервер НЕ выполняет сбор данных - он только:
1. Аутентифицирует агентов
2. Регистрирует подключённые агенты
3. Пересылает команды от веб-интерфейса к агентам
4. Возвращает ответы от агентов обратно к веб-интерфейсу

Вся логика сбора данных (SystemCollector, ScreenCollector, etc.)
выполняется на стороне агента через ws_agent.py и AgentOrchestrator.
"""

import asyncio
import json
import time
import uuid
import sys
import os
import hashlib
import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path
from aiohttp import web, WSMsgType
from loguru import logger

# ============================================================================
# Модели данных
# ============================================================================

@dataclass
class Ticket:
    """Модель тикета поддержки."""
    ticket_id: str            # uuid
    title: str
    description: str
    user_display_name: str
    device_id: str
    created_at: str           # ISO timestamp
    updated_at: str           # ISO timestamp
    assigned_to: str | None   # "support" | "admin" | None
    tags: list[str]
    status: str               # "open" | "closed"
    
    def to_dict(self) -> dict:
        """Сериализует тикет в словарь для API ответов."""
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "description": self.description,
            "user_display_name": self.user_display_name,
            "device_id": self.device_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "assigned_to": self.assigned_to,
            "tags": self.tags,
            "status": self.status
        }


@dataclass
class Session:
    """Модель сессии поддержки."""
    session_id: str           # uuid
    ticket_id: str
    device_id: str
    job_id: str | None
    status: str               # "open" | "closed"
    created_at: str
    updated_at: str
    last_activity_at: str
    
    def to_dict(self) -> dict:
        """Сериализует сессию в словарь для API ответов."""
        return {
            "session_id": self.session_id,
            "ticket_id": self.ticket_id,
            "device_id": self.device_id,
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_activity_at": self.last_activity_at
        }

# ============================================================================
# Утилиты
# ============================================================================

def now_iso() -> str:
    """Возвращает текущее время в формате ISO timestamp."""
    return datetime.utcnow().isoformat() + 'Z'


def new_ticket_id() -> str:
    """Генерирует новый UUID для тикета."""
    return str(uuid.uuid4())


def new_session_id() -> str:
    """Генерирует новый UUID для сессии."""
    return str(uuid.uuid4())


def append_ticket_event(ticket_id: str, event: dict) -> None:
    """
    Добавляет событие в журнал тикета.
    Автоматически добавляет timestamp и device_id, если их нет.
    Ограничивает размер до 500 событий (хвост).
    """
    if ticket_id not in ticket_events:
        ticket_events[ticket_id] = []
    
    # Добавляем ts, если нет
    if 'ts' not in event:
        event['ts'] = now_iso()
    
    # Добавляем device_id, если нет (берем из тикета)
    if 'device_id' not in event and ticket_id in tickets:
        event['device_id'] = tickets[ticket_id].device_id
    
    ticket_events[ticket_id].append(event)
    
    # Ограничение размера: сохраняем только последние 500 событий
    MAX_EVENTS = 500
    if len(ticket_events[ticket_id]) > MAX_EVENTS:
        ticket_events[ticket_id] = ticket_events[ticket_id][-MAX_EVENTS:]


def is_duplicate_ticket_message(ticket_id: str, message_id: str) -> bool:
    """
    Проверяет, было ли сообщение с данным message_id уже обработано для данного тикета.
    
    Args:
        ticket_id: ID тикета
        message_id: ID сообщения
    
    Returns:
        True если сообщение уже было обработано (дубликат), False если это новое сообщение
    """
    if ticket_id not in ticket_seen_message_ids:
        ticket_seen_message_ids[ticket_id] = set()
    
    if message_id in ticket_seen_message_ids[ticket_id]:
        return True
    
    # Отмечаем сообщение как обработанное
    ticket_seen_message_ids[ticket_id].add(message_id)
    return False


def create_system_ticket_for_admin_action(device_id: str, tool_name: str, params: dict) -> tuple[str, str]:
    """
    Создаёт системный тикет для административных действий (например, запуск tool).
    
    Args:
        device_id: ID устройства
        tool_name: Имя вызываемого tool
        params: Параметры tool
    
    Returns:
        tuple[ticket_id, session_id]: ID созданного тикета и сессии
    """
    # Генерация идентификаторов
    ticket_id = new_ticket_id()
    session_id = new_session_id()
    timestamp = now_iso()
    
    # Формирование title и description
    title = f"Admin action: {tool_name}"
    params_str = json.dumps(params, ensure_ascii=False, indent=2)
    if len(params_str) > 500:
        params_str = params_str[:500] + "..."
    description = f"Run tool {tool_name} with params:\n{params_str}"
    
    # Создание тикета
    ticket = Ticket(
        ticket_id=ticket_id,
        title=title,
        description=description,
        user_display_name="admin",
        device_id=device_id,
        created_at=timestamp,
        updated_at=timestamp,
        assigned_to=None,
        tags=["admin", "tool"],
        status="open"
    )
    
    # Создание сессии
    session = Session(
        session_id=session_id,
        ticket_id=ticket_id,
        device_id=device_id,
        job_id=None,
        status="open",
        created_at=timestamp,
        updated_at=timestamp,
        last_activity_at=timestamp
    )
    
    # Сохранение в хранилища
    tickets[ticket_id] = ticket
    sessions_by_ticket[ticket_id] = session
    sessions_by_id[session_id] = session
    
    # Инициализация логов
    ticket_events[ticket_id] = []
    ticket_messages[ticket_id] = []
    
    # Запись событий в лог
    append_ticket_event(ticket_id, {
        "type": "ticket_created",
        "ticket_id": ticket_id,
        "session_id": session_id,
        "device_id": device_id,
        "ts": timestamp
    })
    
    append_ticket_event(ticket_id, {
        "type": "session_opened",
        "ticket_id": ticket_id,
        "session_id": session_id,
        "device_id": device_id,
        "ts": timestamp
    })
    
    # Создаём первичное сообщение
    initial_message_id = str(uuid.uuid4())
    initial_message_record = {
        "ticket_id": ticket_id,
        "message_id": initial_message_id,
        "from_role": "admin",
        "text": f"Run tool {tool_name}",
        "ts": timestamp,
        "direction": "to_agent",
        "is_initial": True
    }
    ticket_messages[ticket_id].append(initial_message_record)
    
    append_ticket_event(ticket_id, {
        "type": "initial_message_created",
        "ticket_id": ticket_id,
        "message_id": initial_message_id,
        "ts": timestamp
    })
    
    logger.info(f"✅ Создан системный тикет {ticket_id} для устройства {device_id}")
    logger.info(f"   Tool: {tool_name}")
    logger.info(f"   Сессия: {session_id}")
    
    return ticket_id, session_id

# ============================================================================
# Хранилище пользователей (логин: пароль)
# ============================================================================
USERS = {
    'admin': 'admin123',
    'user': '12345'
}

# Хранилище токенов (токен: информация_об_агенте)
TOKENS: Dict[str, dict] = {}

# Папка для загружаемых файлов (скриншоты, логи)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Хранилище job событий (для теста в памяти)
# Формат: job_events[job_id] = [event1, event2, ...]
job_events: Dict[str, list] = {}

# Хранилище UI WebSocket подключений (для веб-интерфейса поддержки)
# Формат: ui_connections[connection_id] = {ws, role, subscribed_chats, connected_at}
ui_connections: Dict[str, dict] = {}

# Хранилище chat сессий (ChatSession - единственный источник истины)
# Формат: chat_sessions[chat_job_id] = {chat_job_id, device_id, owner_uuid, created_by, status, created_at, subscribers, events}
chat_sessions: Dict[str, dict] = {}

# ============================================================================
# Хранилище Ticket и Session (in-memory)
# ============================================================================

# Хранилище тикетов (ticket_id -> Ticket)
tickets: dict[str, Ticket] = {}

# Хранилище сессий по тикету (ticket_id -> Session)
sessions_by_ticket: dict[str, Session] = {}

# Хранилище сессий по ID (session_id -> Session)
sessions_by_id: dict[str, Session] = {}

# Хранилище событий по тикету (ticket_id -> list[dict])
ticket_events: dict[str, list[dict]] = {}

# Хранилище сообщений по тикету (ticket_id -> list[dict])
ticket_messages: dict[str, list[dict]] = {}

# Хранилище для дедупликации сообщений по тикету (ticket_id -> set[message_id])
ticket_seen_message_ids: dict[str, set[str]] = {}

# ============================================================================
# Реестры подключений (заготовки)
# ============================================================================

# Реестр подключённых агентов (device_id -> ws)
connected_agents: dict[str, Any] = {}

# Реестр административных клиентов
admin_clients: set[Any] = set()

# ============================================================================
# Tools cache (in-memory)
# ============================================================================

tools_cache = {
    "ts": 0.0,
    "ttl_sec": 20.0,     # default 20 seconds
    "data": None
}

async def handle_login(request):
    """
    HTTP API для входа агента: POST /api/login
    
    Аутентифицирует пользователя по логину/паролю и выдаёт токен,
    который агент будет использовать для WebSocket подключения.
    """
    try:
        data = await request.json()
        uuid_str = data.get("uuid")
        login = data.get("login")
        password = data.get("password")
        
        if not uuid_str or not login or not password:
            return web.json_response({
                "status": "error",
                "error": "Missing uuid, login or password"
            }, status=400)
        
        # Проверяем логин/пароль
        if login in USERS and USERS[login] == password:
            # Генерируем токен
            token = f"token-{uuid_str}"
            
            # Сохраняем в TOKENS
            TOKENS[token] = {
                "uuid": uuid_str,
                "user": login,
                "created_at": time.time()
            }
            
            print(f"✅ Успешная аутентификация: {login} (UUID: {uuid_str})")
            
            return web.json_response({
                "status": "success",
                "token": token
            })
        else:
            print(f"⚠️  Неудачная попытка входа: {login}")
            return web.json_response({
                "status": "error",
                "error": "Invalid credentials"
            }, status=401)
    
    except Exception as e:
        print(f"❌ Ошибка при входе: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def push_chat_event_to_ui(job_id: str, event: dict):
    """
    Отправляет событие чата всем подписанным UI WebSocket'ам.
    
    Для событий chat_invite отправляет всем admin/support подключениям,
    независимо от подписки на конкретный чат.
    
    Args:
        job_id: ID чата
        event: Событие (ChatEvent)
    """
    # Формируем сообщение для UI
    message = {
        "type": "chat_event",
        "job_id": job_id,
        "event": event,
        "ts": time.time()
    }
    
    # Для chat_invite отправляем всем admin/support подключениям
    if event.get("event") == "chat_invite":
        logger.info(f"[push_chat_event_to_ui] Broadcasting chat_invite job_id={job_id} to all admin/support connections")
        
        dead_connections = []
        for conn_id, conn_data in ui_connections.items():
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
            ui_connections.pop(conn_id, None)
            logger.debug(f"[push_chat_event_to_ui] Removed dead connection {conn_id}")
        
        return
    
    # Для остальных событий отправляем только подписчикам
    if job_id not in chat_sessions:
        logger.warning(f"[push_chat_event_to_ui] chat_session {job_id} not found")
        return
    
    session = chat_sessions[job_id]
    subscribers = session.get("subscribers", set())
    
    if not subscribers:
        logger.debug(f"[push_chat_event_to_ui] no subscribers for job_id={job_id}")
        return
    
    # Отправляем всем подписчикам
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

async def websocket_handler(request):
    """
    WebSocket обработчик для relay-архитектуры сервер-агент.
    
    Сервер выступает в роли ретранслятора команд между веб-интерфейсом и агентами.
    Вся логика сбора данных выполняется на стороне агента (ws_agent.py).
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    agent_id = None
    device_id = None
    authenticated = False
    
    logger.info("🟢 Новое WebSocket соединение")
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # a) type == "handshake"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    if msg_type == "handshake":
                        # Проверяем токен для аутентификации
                        token = data.get("token")
                        
                        if not token or token not in TOKENS:
                            logger.warning("🔴 Попытка несанкционированного доступа")
                            await ws.close(code=4003, message=b"Unauthorized")
                            return ws
                        
                        # Токен валиден - разрешаем работу
                        authenticated = True
                        token_info = TOKENS[token]
                        
                        device_id = data.get("device_id", f"agent_{uuid.uuid4().hex[:8]}")
                        agent_id = device_id
                        
                        # Регистрируем агента (только метаданные, без оркестратора)
                        connected_agents[agent_id] = {
                            "ws": ws,
                            "device_id": device_id,
                            "agent_version": data.get("agent_version", "unknown"),
                            "modules": data.get("modules", []),
                            "connected_at": time.time(),
                            "last_seen": time.time(),
                            "status": "online",
                            "pending_futures": {},  # Dict[str, asyncio.Future] для параллельных запросов
                            "user": token_info["user"],
                            "token": token
                        }
                        
                        logger.success(f"✅ Агент зарегистрирован: {device_id}")
                        logger.info(f"   Пользователь: {token_info['user']}")
                        logger.info(f"   Модули: {data.get('modules', [])}")
                        handshake_ack = {
                            "type": "handshake_ack",
                            "request_id": data.get("request_id"),
                            "device_id": device_id,
                            "payload": {
                                "status": "success",
                                "message": "Handshake accepted"
                            }
                        }
                        await ws.send_json(handshake_ack)
                        logger.debug(f"📤 Отправлен handshake_ack агенту {device_id}")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # b) type == "pong"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "pong":
                        # Обновляем статус агента при получении pong
                        if agent_id and agent_id in connected_agents:
                            connected_agents[agent_id]["last_seen"] = time.time()
                            connected_agents[agent_id]["status"] = "online"
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # c) type == "command_result"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "command_result":
                        # Это результат на ранее отправленную команду
                        if agent_id and agent_id in connected_agents:
                            connected_agents[agent_id]["last_seen"] = time.time()
                            connected_agents[agent_id]["last_response"] = data
                            
                            req_id = data.get("request_id")
                            if req_id:
                                pending_futures = connected_agents[agent_id]["pending_futures"]
                                future = pending_futures.get(req_id)
                                
                                if future and not future.done():
                                    future.set_result(data)
                                    del pending_futures[req_id]
                                    
                                    # Логирование
                                    payload = data.get("payload", {})
                                    meta = payload.get("meta", {})
                                    cmd = meta.get("command", "unknown")
                                    status = payload.get("status", "unknown")
                                    logger.info(f"[SERVER] RX command_result request_id={req_id} status={status} meta.command={cmd}")
                                else:
                                    logger.warning(f"[SERVER] No pending future for request_id={req_id}")
                            else:
                                logger.warning(f"[SERVER] command_result without request_id from agent {agent_id}")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # d) type == "command" - команды от агента к серверу
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "command":
                        # Это команда от агента к серверу
                        if agent_id and agent_id in connected_agents:
                            connected_agents[agent_id]["last_seen"] = time.time()
                            
                            req_id = data.get("request_id")
                            payload = data.get("payload", {})
                            command = payload.get("command")
                            params = payload.get("params", {})
                            
                            logger.info(f"[SERVER] RX command from agent {agent_id}: command={command} request_id={req_id}")
                            
                            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                            # Обработка команды chat_raise от агента
                            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                            if command == "chat_raise":
                                title = params.get("title", "Agent Support Request")
                                reason = params.get("reason", "agent_initiated")
                                severity = params.get("severity", "warning")
                                context = params.get("context", {})
                                
                                # Генерируем chat_job_id
                                chat_job_id = str(uuid.uuid4())
                                
                                # Создаем ChatSession
                                chat_sessions[chat_job_id] = {
                                    "chat_job_id": chat_job_id,
                                    "device_id": agent_id,  # агент, который инициировал
                                    "owner_uuid": connected_agents[agent_id].get("user", "unknown"),
                                    "created_by": "agent",
                                    "status": "active",
                                    "created_at": time.time(),
                                    "subscribers": set(),
                                    "events": []
                                }
                                
                                # Инициализируем job_events
                                if chat_job_id not in job_events:
                                    job_events[chat_job_id] = []
                                
                                # ВАЖНО: Немедленно отправляем ответ агенту ПЕРЕД запуском длительных операций
                                # Это предотвращает таймаут на стороне агента
                                response_envelope = {
                                    "type": "command_result",
                                    "request_id": req_id,
                                    "device_id": agent_id,
                                    "payload": {
                                        "status": "success",
                                        "data": {
                                            "observations": {
                                                "job_id": chat_job_id,
                                                "message": "Chat session created"
                                            }
                                        }
                                    }
                                }
                                
                                await ws.send_json(response_envelope)
                                logger.success(f"[chat_raise] agent_id={agent_id} job_id={chat_job_id} → success response sent IMMEDIATELY")
                                
                                # PUSH invite в веб-UI (поддержка) - НЕ блокирует
                                invite_event = {
                                    "event": "chat_invite",
                                    "job_id": chat_job_id,
                                    "device_id": agent_id,
                                    "from": "agent",
                                    "title": title,
                                    "reason": reason,
                                    "severity": severity,
                                    "context": context,
                                    "ts": time.time()
                                }
                                await push_chat_event_to_ui(chat_job_id, invite_event)
                                logger.info(f"[chat_raise] invite pushed to UI for job_id={chat_job_id}")
                                
                                # Запускаем start_job и ui_notify асинхронно в background (не ждем ответа)
                                async def _background_notify():
                                    """Фоновая задача для отправки start_job и ui_notify"""
                                    try:
                                        # Стартуем support_chat на агенте
                                        try:
                                            await send_ws_command(
                                                device_id=agent_id,
                                                command="start_job",
                                                params={"job_type": "support_chat", "params": {"job_id": chat_job_id}},
                                                actor_role="agent"
                                            )
                                            logger.info(f"[chat_raise] start_job sent to agent {agent_id}")
                                        except Exception as e:
                                            logger.error(f"[chat_raise] Failed to send start_job to agent: {e}")
                                        
                                        # PUSH invite в локальный GUI агента через ui_notify
                                        try:
                                            await send_ws_command(
                                                device_id=agent_id,
                                                command="ui_notify",
                                                params={"event": invite_event},
                                                actor_role="agent"
                                            )
                                            logger.info(f"[chat_raise] ui_notify sent to agent {agent_id}")
                                        except Exception as e:
                                            logger.error(f"[chat_raise] Failed to send ui_notify to agent: {e}")
                                    except Exception as e:
                                        logger.error(f"[chat_raise] Background notify failed: {e}")
                                
                                # Запускаем в background, не ждем завершения
                                asyncio.create_task(_background_notify())
                            
                            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                            # Неизвестная команда от агента
                            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                            else:
                                logger.warning(f"[SERVER] Unknown command from agent {agent_id}: {command}")
                                
                                # Отправляем ошибку агенту
                                error_envelope = {
                                    "type": "command_result",
                                    "request_id": req_id,
                                    "device_id": agent_id,
                                    "payload": {
                                        "status": "error",
                                        "error": {
                                            "code": "UNKNOWN_COMMAND",
                                            "message": f"Unknown command: {command}"
                                        }
                                    }
                                }
                                
                                await ws.send_json(error_envelope)
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # e) type == "outbox_item"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "outbox_item":
                        # Это доставка данных из outbox агента
                        if agent_id and agent_id in connected_agents:
                            connected_agents[agent_id]["last_seen"] = time.time()
                            
                            payload = data.get("payload", {})
                            outbox_id = payload.get("outbox_id")
                            item_type = payload.get("item_type", "unknown")
                            
                            # Обработка job_event
                            if item_type == "job_event":
                                job_id = payload.get("job_id")
                                event = payload.get("event", {})
                                
                                if job_id:
                                    # 1. Сохраняем в job_events (для истории)
                                    if job_id not in job_events:
                                        job_events[job_id] = []
                                    job_events[job_id].append(event)
                                    
                                    # 2. PUSH в UI (новая логика)
                                    await push_chat_event_to_ui(job_id, event)
                                    
                                    logger.info(f"[SERVER] job_event job_id={job_id} event={event.get('event')} → pushed to UI")
                                    
                                    # 3. Обработка ticket-related событий
                                    ticket_id = event.get("ticket_id")
                                    if ticket_id:
                                        # Проверяем существование тикета
                                        if ticket_id not in tickets:
                                            logger.warning(f"[SERVER] unknown_ticket_event: ticket_id={ticket_id} not found")
                                        else:
                                            event_type = event.get("event")
                                            
                                            # Обработка chat_message от агента
                                            if event_type == "chat_message":
                                                message_id = event.get("message_id")
                                                if message_id:
                                                    # Дедупликация
                                                    if not is_duplicate_ticket_message(ticket_id, message_id):
                                                        # Инициализация хранилища сообщений для тикета
                                                        if ticket_id not in ticket_messages:
                                                            ticket_messages[ticket_id] = []
                                                        
                                                        # Сохраняем сообщение от агента
                                                        message_record = {
                                                            "ticket_id": ticket_id,
                                                            "message_id": message_id,
                                                            "from_role": event.get("from", "agent"),
                                                            "text": event.get("text", ""),
                                                            "ts": now_iso(),
                                                            "direction": "from_agent"
                                                        }
                                                        ticket_messages[ticket_id].append(message_record)
                                                        
                                                        # Ограничение размера: сохраняем только последние 500 сообщений
                                                        MAX_MESSAGES = 500
                                                        if len(ticket_messages[ticket_id]) > MAX_MESSAGES:
                                                            ticket_messages[ticket_id] = ticket_messages[ticket_id][-MAX_MESSAGES:]
                                                        
                                                        # Добавляем событие
                                                        append_ticket_event(ticket_id, {
                                                            "type": "chat_message_received",
                                                            "ticket_id": ticket_id,
                                                            "message_id": message_id,
                                                            "from_role": event.get("from", "agent"),
                                                            "ts": now_iso()
                                                        })
                                                        
                                                        logger.info(f"[TICKET] chat_message received: ticket_id={ticket_id} message_id={message_id}")
                                                    else:
                                                        logger.debug(f"[TICKET] duplicate chat_message: ticket_id={ticket_id} message_id={message_id}")
                                                else:
                                                    logger.warning(f"[TICKET] chat_message without message_id for ticket_id={ticket_id}")
                                            
                                            # Обработка chat_ended - СПЕЦИАЛЬНАЯ ОБРАБОТКА (PROMPT 7)
                                            elif event_type == "chat_ended":
                                                # Нормализация события перед сохранением
                                                event_record = {**event}
                                                
                                                # Добавляем ts если отсутствует
                                                if "ts" not in event_record:
                                                    event_record["ts"] = now_iso()
                                                
                                                # Добавляем device_id из envelope (если есть)
                                                if agent_id:
                                                    event_record["device_id"] = agent_id
                                                
                                                append_ticket_event(ticket_id, event_record)
                                                logger.info(f"[TICKET] chat_ended received: ticket_id={ticket_id} reason={event.get('reason')}")
                                                
                                                # Проверяем статус тикета
                                                ticket = tickets.get(ticket_id)
                                                if ticket:
                                                    if ticket.status == "closed":
                                                        # Тикет уже закрыт - приоритет сервера, ничего не делаем
                                                        logger.info(f"[TICKET] chat_ended ignored: ticket {ticket_id} already closed (server priority)")
                                                    else:
                                                        # Тикет ещё открыт - автоматически закрываем его
                                                        reason = event.get("reason", "agent_chat_ended")
                                                        logger.info(f"[TICKET] Auto-closing ticket {ticket_id} due to chat_ended, reason={reason}")
                                                        
                                                        # Закрываем тикет
                                                        ticket.status = "closed"
                                                        ticket.updated_at = now_iso()
                                                        
                                                        # Закрываем сессию
                                                        session = sessions_by_ticket.get(ticket_id)
                                                        if session:
                                                            session.status = "closed"
                                                            session.updated_at = now_iso()
                                                            session.last_activity_at = now_iso()
                                                        
                                                        # Добавляем событие auto-закрытия
                                                        append_ticket_event(ticket_id, {
                                                            "type": "ticket_closed",
                                                            "ticket_id": ticket_id,
                                                            "closed_by_role": "support",
                                                            "reason": f"agent_chat_ended:{reason}",
                                                            "auto_closed": True,
                                                            "device_id": agent_id,
                                                            "job_id": event.get("job_id"),
                                                            "ts": now_iso()
                                                        })
                                            
                                            # Обработка event_delivered, agent_action, tool_call_*
                                            elif event_type in ("event_delivered", "agent_action", "tool_call_started", "tool_call_result"):
                                                # Нормализация события перед сохранением
                                                event_record = {**event}
                                                
                                                # Добавляем ts если отсутствует
                                                if "ts" not in event_record:
                                                    event_record["ts"] = now_iso()
                                                
                                                # Добавляем device_id из envelope (если есть)
                                                if agent_id:
                                                    event_record["device_id"] = agent_id
                                                
                                                append_ticket_event(ticket_id, event_record)
                                                logger.info(f"[TICKET] event stored: ticket_id={ticket_id} event_type={event_type}")
                                    else:
                                        # job_event без ticket_id - это нормально для других типов job'ов
                                        logger.debug(f"[SERVER] job_event without ticket_id: job_id={job_id} event={event_type}")
                                else:
                                    logger.warning(f"[SERVER] job_event without job_id from agent {agent_id}")
                            
                            if outbox_id:
                                logger.info(f"[SERVER] RX outbox_item agent_id={agent_id} outbox_id={outbox_id} item_type={item_type}")
                                
                                # Отправляем ACK
                                ack_request_id = str(uuid.uuid4())
                                agent_device_id = connected_agents[agent_id].get("device_id", agent_id)
                                
                                ack_envelope = {
                                    "type": "ack",
                                    "request_id": ack_request_id,
                                    "device_id": agent_device_id,
                                    "payload": {
                                        "outbox_ids": [outbox_id]
                                    }
                                }
                                
                                try:
                                    await ws.send_json(ack_envelope)
                                    logger.info(f"[SERVER] TX ack outbox_id={outbox_id}")
                                except Exception as e:
                                    logger.error(f"[SERVER] Failed to send ACK for outbox_id={outbox_id}: {e}")
                            else:
                                logger.error(f"[SERVER] outbox_item without outbox_id from agent {agent_id}")
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # f) Любой другой type / неизвестный формат
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    else:
                        # Старый формат без type - логируем и игнорируем
                        if msg_type is None:
                            logger.warning(f"[SERVER] Received message without type from agent {agent_id}, ignoring")
                        else:
                            logger.warning(f"[SERVER] Unknown message type '{msg_type}' from agent {agent_id}, ignoring")
                
                except json.JSONDecodeError:
                    logger.warning(f"⚠️  Получено не-JSON сообщение: {msg.data}")
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки сообщения: {e}")
                    # Не валим соединение при ошибке обработки
            
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"❌ Ошибка WebSocket: {ws.exception()}")
                break
    
    finally:
        # Отключение агента - просто удаляем из списка
        if agent_id and agent_id in connected_agents:
            connected_agents[agent_id]["status"] = "offline"
            del connected_agents[agent_id]
            logger.warning(f"🔴 Агент отключен: {agent_id}")
    
    return ws

async def websocket_ui_handler(request):
    """
    WebSocket обработчик для веб-UI (поддержка).
    
    Протокол:
    - ui_hello: аутентификация UI клиента
    - subscribe_chat: подписка на чат по job_id
    - unsubscribe_chat: отписка от чата
    - chat_send: отправка сообщения в чат
    - run_tool: вызов инструмента на агенте
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    connection_id = str(uuid.uuid4())
    user_role = None  # "support" после ui_hello
    subscribed_chats: set = set()  # Set[chat_job_id]
    
    # Регистрируем UI connection
    ui_connections[connection_id] = {
        "ws": ws,
        "role": user_role,
        "subscribed_chats": subscribed_chats,
        "connected_at": time.time()
    }
    
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
                        role = data.get("role", "support")
                        user_role = role
                        ui_connections[connection_id]["role"] = role
                        
                        logger.success(f"✅ UI аутентифицирован: connection_id={connection_id} role={role}")
                        
                        await ws.send_json({
                            "type": "ui_hello_ack",
                            "connection_id": connection_id,
                            "role": role
                        })
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # b) type == "subscribe_chat"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "subscribe_chat":
                        job_id = data.get("job_id")
                        if job_id:
                            subscribed_chats.add(job_id)
                            
                            # Инициализируем chat_session если его еще нет
                            if job_id not in chat_sessions:
                                chat_sessions[job_id] = {
                                    "chat_job_id": job_id,
                                    "device_id": None,  # будет заполнено позже
                                    "owner_uuid": None,
                                    "created_by": user_role or "unknown",
                                    "status": "active",
                                    "created_at": time.time(),
                                    "subscribers": set(),
                                    "events": []
                                }
                            
                            # Добавляем ws в chat_session.subscribers
                            chat_sessions[job_id]["subscribers"].add(ws)
                            
                            logger.info(f"📋 UI подписан на чат: connection_id={connection_id} job_id={job_id}")
                            
                            await ws.send_json({
                                "type": "subscribe_ack",
                                "job_id": job_id
                            })
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # c) type == "unsubscribe_chat"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "unsubscribe_chat":
                        job_id = data.get("job_id")
                        if job_id in subscribed_chats:
                            subscribed_chats.remove(job_id)
                            
                            # Удаляем ws из chat_session.subscribers
                            if job_id in chat_sessions:
                                chat_sessions[job_id]["subscribers"].discard(ws)
                            
                            logger.info(f"📋 UI отписан от чата: connection_id={connection_id} job_id={job_id}")
                            
                            await ws.send_json({
                                "type": "unsubscribe_ack",
                                "job_id": job_id
                            })
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # d) type == "chat_send"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "chat_send":
                        job_id = data.get("job_id")
                        text = data.get("text")
                        from_user = data.get("from", "support")
                        
                        if not job_id or not text:
                            await ws.send_json({
                                "type": "error",
                                "error": "Missing job_id or text"
                            })
                            continue
                        
                        # Получаем device_id из chat_session
                        if job_id not in chat_sessions:
                            await ws.send_json({
                                "type": "error",
                                "error": f"Chat session {job_id} not found"
                            })
                            continue
                        
                        device_id = chat_sessions[job_id].get("device_id")
                        if not device_id:
                            await ws.send_json({
                                "type": "error",
                                "error": "device_id not set for chat session"
                            })
                            continue
                        
                        # Формируем событие
                        event = {
                            "event": "chat_message",
                            "job_id": job_id,
                            "message_id": str(uuid.uuid4()),
                            "from": from_user,
                            "text": text,
                            "ts": time.time()
                        }
                        
                        logger.info(f"💬 UI отправляет сообщение: job_id={job_id} from={from_user} text_len={len(text)}")
                        
                        # Отправляем агенту через job_send_event
                        try:
                            await send_ws_command(
                                device_id=device_id,
                                command="job_send_event",
                                params={"job_id": job_id, "event": event},
                                actor_role=user_role or "support"
                            )
                            
                            await ws.send_json({
                                "type": "chat_send_ack",
                                "job_id": job_id,
                                "message_id": event["message_id"]
                            })
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки сообщения в чат: {e}")
                            await ws.send_json({
                                "type": "error",
                                "error": f"Failed to send message: {str(e)}"
                            })
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # e) type == "run_tool"
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    elif msg_type == "run_tool":
                        device_id = data.get("device_id")
                        tool = data.get("tool")
                        params = data.get("params", {})
                        chat_job_id = data.get("chat_job_id")  # ОБЯЗАТЕЛЬНО
                        
                        if not device_id or not tool:
                            await ws.send_json({
                                "type": "error",
                                "error": "Missing device_id or tool"
                            })
                            continue
                        
                        # ВАЖНО: передаем chat_job_id в агент
                        agent_params = {
                            "tool": tool,
                            "params": params
                        }
                        
                        if chat_job_id:
                            agent_params["chat_job_id"] = chat_job_id  # ← ключевой момент
                        
                        logger.info(f"🔧 UI запускает tool: device_id={device_id} tool={tool} chat_job_id={chat_job_id}")
                        
                        try:
                            await send_ws_command(
                                device_id=device_id,
                                command="run_tool",
                                params=agent_params,
                                actor_role=user_role or "support"
                            )
                            
                            await ws.send_json({
                                "type": "run_tool_ack",
                                "device_id": device_id,
                                "tool": tool
                            })
                        except Exception as e:
                            logger.error(f"❌ Ошибка запуска tool: {e}")
                            await ws.send_json({
                                "type": "error",
                                "error": f"Failed to run tool: {str(e)}"
                            })
                    
                    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    # f) Неизвестный тип
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
                    logger.error(f"❌ Ошибка обработки сообщения UI: {e}")
            
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"❌ Ошибка WebSocket UI: {ws.exception()}")
                break
    
    finally:
        # Очистка при отключении
        if connection_id in ui_connections:
            # Отписываемся от всех чатов
            for job_id in subscribed_chats:
                if job_id in chat_sessions:
                    chat_sessions[job_id]["subscribers"].discard(ws)
            del ui_connections[connection_id]
        
        logger.warning(f"🔴 UI WebSocket отключен: connection_id={connection_id}")
    
    return ws

async def handle_index(request):
    """
    Возвращает HTML страницу с панелью управления агентами и техподдержкой.
    """
    # Читаем HTML из файла
    web_interface_path = Path(__file__).parent / "web_interface.html"
    try:
        html_content = web_interface_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"File not found: {web_interface_path}")
        return web.Response(
            text="<h1>Error: web_interface.html not found</h1>",
            content_type='text/html',
            status=500
        )
    except Exception as e:
        logger.error(f"Error reading web_interface.html: {e}")
        return web.Response(
            text=f"<h1>Error reading web_interface.html: {e}</h1>",
            content_type='text/html',
            status=500
        )
    
    return web.Response(text=html_content, content_type='text/html')

async def handle_chat_debug(request):
    """
    Возвращает HTML страницу для тестирования чата.
    """
    # Читаем HTML из файла
    chat_debug_path = Path(__file__).parent / "chat_debug.html"
    try:
        html_content = chat_debug_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"File not found: {chat_debug_path}")
        return web.Response(
            text="<h1>Error: chat_debug.html not found</h1>",
            content_type='text/html',
            status=500
        )
    except Exception as e:
        logger.error(f"Error reading chat_debug.html: {e}")
        return web.Response(
            text=f"<h1>Error reading chat_debug.html: {e}</h1>",
            content_type='text/html',
            status=500
        )
    
    return web.Response(text=html_content, content_type='text/html')

async def handle_chat_ws(request):
    """
    Возвращает HTML страницу с единым интерфейсом чата (chat_ws.html).
    Это главная точка входа для чата support-специалистов.
    """
    # Читаем HTML из файла
    chat_ws_path = Path(__file__).parent / "chat_ws.html"
    try:
        html_content = chat_ws_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"File not found: {chat_ws_path}")
        return web.Response(
            text="<h1>Error: chat_ws.html not found</h1>",
            content_type='text/html',
            status=500
        )
    except Exception as e:
        logger.error(f"Error reading chat_ws.html: {e}")
        return web.Response(
            text=f"<h1>Error reading chat_ws.html: {e}</h1>",
            content_type='text/html',
            status=500
        )
    
    return web.Response(text=html_content, content_type='text/html')

async def handle_test_simple(request):
    html_path = Path(__file__).parent / "test_web_simple.html"
    if html_path.exists():
        return web.FileResponse(html_path)
    return web.Response(text="Test page not found", status=404)

async def handle_ticket_page(request):
    """
    Возвращает HTML страницу для отображения тикета (ticket.html).
    URL: /ticket.html?ticket_id=xxx
    """
    html_path = Path(__file__).parent / "ticket.html"
    try:
        html_content = html_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"File not found: {html_path}")
        return web.Response(
            text="<h1>Error: ticket.html not found</h1>",
            content_type='text/html',
            status=500
        )
    except Exception as e:
        logger.error(f"Error reading ticket.html: {e}")
        return web.Response(
            text=f"<h1>Error reading ticket.html: {e}</h1>",
            content_type='text/html',
            status=500
        )
    
    return web.Response(text=html_content, content_type='text/html')

async def handle_ticket_page_by_id(request):
    """
    Возвращает HTML страницу для отображения тикета (ticket.html).
    URL: /ticket/{ticket_id}
    """
    html_path = Path(__file__).parent / "ticket.html"
    try:
        html_content = html_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"File not found: {html_path}")
        return web.Response(
            text="<h1>Error: ticket.html not found</h1>",
            content_type='text/html',
            status=500
        )
    except Exception as e:
        logger.error(f"Error reading ticket.html: {e}")
        return web.Response(
            text=f"<h1>Error reading ticket.html: {e}</h1>",
            content_type='text/html',
            status=500
        )
    
    return web.Response(text=html_content, content_type='text/html')

async def handle_admin_page(request):
    """
    Возвращает HTML страницу админской панели (admin.html).
    URL: /admin
    """
    html_path = Path(__file__).parent / "admin.html"
    try:
        html_content = html_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"File not found: {html_path}")
        return web.Response(
            text="<h1>Error: admin.html not found</h1>",
            content_type='text/html',
            status=500
        )
    except Exception as e:
        logger.error(f"Error reading admin.html: {e}")
        return web.Response(
            text=f"<h1>Error reading admin.html: {e}</h1>",
            content_type='text/html',
            status=500
        )
    
    return web.Response(text=html_content, content_type='text/html')

async def handle_ws_ui_test(request):
    """
    Возвращает HTML страницу для тестирования WebSocket UI.
    """
    html_path = Path(__file__).parent / "ws_ui_test.html"
    try:
        html_content = html_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"File not found: {html_path}")
        return web.Response(
            text="<h1>Error: ws_ui_test.html not found</h1>",
            content_type='text/html',
            status=500
        )
    except Exception as e:
        logger.error(f"Error reading ws_ui_test.html: {e}")
        return web.Response(
            text=f"<h1>Error reading ws_ui_test.html: {e}</h1>",
            content_type='text/html',
            status=500
        )
    
    return web.Response(text=html_content, content_type='text/html')

async def send_ws_command(
    device_id: str,
    command: str,
    params: dict,
    actor_role: str = "user",
    timeout: int = 30
) -> dict:
    """
    Универсальная функция для отправки команд агенту через WebSocket.
    
    Args:
        device_id: ID устройства агента
        command: Имя команды
        params: Параметры команды
        actor_role: Роль актора (по умолчанию "user")
        timeout: Таймаут ожидания ответа в секундах
    
    Returns:
        dict: Ответ от агента (command_result)
    
    Raises:
        ValueError: Если агент не подключен
        asyncio.TimeoutError: Если агент не ответил в течение timeout
    """
    if device_id not in connected_agents:
        raise ValueError(f"Agent {device_id} not connected")
    
    agent = connected_agents[device_id]
    ws = agent["ws"]
    agent_device_id = agent.get("device_id", device_id)
    
    # Генерируем request_id для этой команды
    request_id = str(uuid.uuid4())
    
    # Создаём Future для ожидания ответа от агента
    future = asyncio.get_event_loop().create_future()
    agent["pending_futures"][request_id] = future
    
    # Формируем команду в формате envelope
    # Двойная прокидка actor_role: в payload и в params для совместимости
    command_envelope = {
        "type": "command",
        "request_id": request_id,
        "device_id": agent_device_id,
        "payload": {
            "command": command,
            "params": {**params, "actor_role": actor_role},  # Добавляем actor_role в params
            "actor_role": actor_role  # И в payload для совместимости
        }
    }
    
    logger.info(f"[SERVER] TX command {command} request_id={request_id}")
    logger.debug(f"📦 Данные команды: {json.dumps(command_envelope, ensure_ascii=False, indent=2)}")
    
    # Пересылаем команду агенту через WebSocket
    await ws.send_json(command_envelope)
    
    try:
        # Ожидаем ответ от агента
        response = await asyncio.wait_for(future, timeout=timeout)
        logger.info(f"[SERVER] RX command_result request_id={request_id} status={response.get('payload', {}).get('status', 'unknown')}")
        return response
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды '{command}' для агента {device_id} (request_id={request_id})")
        # Удаляем future из pending_futures
        if request_id in agent["pending_futures"]:
            del agent["pending_futures"][request_id]
        raise
    except Exception as e:
        # Удаляем future из pending_futures при любой ошибке
        if request_id in agent["pending_futures"]:
            del agent["pending_futures"][request_id]
        raise

async def handle_get_agents(request):
    """
    API эндпоинт для получения списка подключённых агентов: GET /api/agents
    
    Возвращает информацию обо всех активных агентах, включая:
    - device_id, версию агента, список модулей
    - статус, uptime, время последней активности
    """
    agents_list = []
    current_time = time.time()
    
    for agent_id, agent_data in connected_agents.items():
        uptime = current_time - agent_data["connected_at"]
        last_seen = current_time - agent_data["last_seen"]
        
        agents_list.append({
            "device_id": agent_data["device_id"],
            "agent_version": agent_data["agent_version"],
            "modules": agent_data["modules"],
            "status": agent_data["status"],
            "uptime": round(uptime, 2),
            "last_seen": round(last_seen, 2),
        })
    
    return web.json_response({"agents": agents_list})

async def handle_get_devices(request):
    """
    API эндпоинт для получения списка подключённых device_id: GET /api/devices
    
    Возвращает простой список device_id для использования в dropdown UI.
    """
    devices = []
    for agent_id, agent_data in connected_agents.items():
        device_id = agent_data.get("device_id", agent_id)
        if device_id not in devices:
            devices.append(device_id)
    
    return web.json_response({
        "status": "success",
        "devices": sorted(devices),
        "count": len(devices)
    })

async def handle_send_command(request):
    """
    API эндпоинт для отправки команд агенту (relay-архитектура).
    
    Сервер пересылает команду агенту через WebSocket и ожидает ответ.
    Агент обрабатывает команду через свой AgentOrchestrator и возвращает результат.
    
    Поддерживаемые команды (обрабатываются на стороне агента):
    - ping: проверка статуса агента
    - collect: сбор данных с модулей
    - list_modules: список загруженных модулей
    - install_module: установка динамического модуля
    - exec_script: выполнение скрипта в памяти
    - get_status: расширенный статус агента
    - get_info: системная информация
    - get_history: история событий из БД
    """
    try:
        logger.debug("🔍 Получен запрос /api/send_command")
        data = await request.json()
        logger.debug(f"📥 Данные запроса: {data}")
        
        device_id = data.get("device_id")
        command = data.get("command")
        params = data.get("params", {})
        actor_role = data.get("actor_role", "user")
        
        logger.debug(f"🔧 device_id={device_id}, command={command}, params={params}, actor_role={actor_role}")
        
        if not device_id or not command:
            logger.warning("⚠️  Отсутствует device_id или command")
            return web.json_response({
                "status": "error",
                "error": "Missing device_id or command"
            }, status=400)
        
        # Используем универсальную функцию send_ws_command
        response = await send_ws_command(device_id, command, params, actor_role=actor_role, timeout=30)
        
        # Возвращаем payload из command_result (или весь response, если payload нет)
        if isinstance(response, dict) and "payload" in response:
            return web.json_response(response["payload"])
        else:
            return web.json_response(response)
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки команды: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_check_functions(request):
    """
    API эндпоинт для проверки доступных функций агента: POST /api/check_functions
    
    Проверяет существующие функции ПК агента через команды:
    - get_manifest - получение манифеста всех модулей и их методов
    - list_tools - список всех доступных инструментов
    - list_modules - список загруженных модулей
    
    Returns:
        JSON с информацией о доступных функциях агента
    """
    try:
        logger.debug("🔍 Получен запрос /api/check_functions")
        data = await request.json()
        logger.debug(f"📥 Данные запроса: {data}")
        
        device_id = data.get("device_id")
        
        if not device_id:
            logger.warning("⚠️  Отсутствует device_id")
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if device_id not in connected_agents:
            logger.warning(f"⚠️  Агент {device_id} не подключен")
            return web.json_response({
                "status": "error",
                "error": f"Agent {device_id} not connected"
            }, status=404)
        
        agent = connected_agents[device_id]
        ws = agent["ws"]
        agent_device_id = agent.get("device_id", device_id)
        
        logger.debug(f"🔗 WebSocket агента найден: {ws}")
        
        # Собираем информацию о функциях через несколько команд
        functions_info = {
            "device_id": device_id,
            "core_commands": [],
            "modules": [],
            "tools": [],
            "manifest": None
        }
        
        # 1. Получаем манифест (полная информация о модулях и методах)
        request_id = None
        try:
            logger.info(f"📋 Запрос манифеста от агента {device_id}")
            
            # Генерируем request_id для этой команды
            request_id = str(uuid.uuid4())
            future = asyncio.get_event_loop().create_future()
            agent["pending_futures"][request_id] = future
            
            # Формируем команду в формате envelope
            command_envelope = {
                "type": "command",
                "request_id": request_id,
                "device_id": agent_device_id,
                "payload": {
                    "command": "get_manifest",
                    "params": {}
                }
            }
            
            logger.info(f"[SERVER] TX command get_manifest request_id={request_id}")
            await ws.send_json(command_envelope)
            response = await asyncio.wait_for(future, timeout=30.0)
            
            # Извлекаем payload из command_result
            if isinstance(response, dict) and "payload" in response:
                response_payload = response["payload"]
            else:
                response_payload = response
            
            if response_payload.get("status") == "success" and "data" in response_payload:
                manifest = response_payload["data"].get("observations", {}).get("manifest", {})
                functions_info["manifest"] = manifest
                
                # Извлекаем список модулей из манифеста
                for module_name, module_info in manifest.items():
                    if module_name == "core":
                        # Core команды
                        methods = module_info.get("methods", {})
                        for method_name, method_info in methods.items():
                            functions_info["core_commands"].append({
                                "name": method_name,
                                "description": method_info.get("description", ""),
                                "module": "core"
                            })
                    else:
                        # Модули
                        methods = module_info.get("methods", {})
                        module_tools = []
                        for method_name, method_info in methods.items():
                            tool_name = method_info.get("tool_name", method_name)
                            module_tools.append({
                                "name": tool_name,
                                "description": method_info.get("description", ""),
                                "risk_level": method_info.get("risk_level", "safe_readonly"),
                                "async": method_info.get("async", False)
                            })
                        
                        functions_info["modules"].append({
                            "name": module_name,
                            "description": module_info.get("description", ""),
                            "tools": module_tools
                        })
                
                logger.success(f"✅ Манифест получен: {len(manifest)} разделов")
            
        except asyncio.TimeoutError:
            logger.warning(f"⏱️  Таймаут получения манифеста от агента {device_id}")
            if request_id and request_id in agent["pending_futures"]:
                del agent["pending_futures"][request_id]
        except Exception as e:
            logger.error(f"❌ Ошибка получения манифеста: {e}")
            if request_id and request_id in agent["pending_futures"]:
                del agent["pending_futures"][request_id]
        
        # 2. Получаем список инструментов (плоский список)
        request_id = None
        try:
            logger.info(f"📋 Запрос списка инструментов от агента {device_id}")
            
            # Генерируем request_id для этой команды
            request_id = str(uuid.uuid4())
            future = asyncio.get_event_loop().create_future()
            agent["pending_futures"][request_id] = future
            
            # Формируем команду в формате envelope
            command_envelope = {
                "type": "command",
                "request_id": request_id,
                "device_id": agent_device_id,
                "payload": {
                    "command": "list_tools",
                    "params": {}
                }
            }
            
            logger.info(f"[SERVER] TX command list_tools request_id={request_id}")
            await ws.send_json(command_envelope)
            response = await asyncio.wait_for(future, timeout=30.0)
            
            # Извлекаем payload из command_result
            if isinstance(response, dict) and "payload" in response:
                response_payload = response["payload"]
            else:
                response_payload = response
            
            if response_payload.get("status") == "success" and "data" in response_payload:
                tools = response_payload["data"].get("observations", {}).get("tools", [])
                functions_info["tools"] = tools
                logger.success(f"✅ Список инструментов получен: {len(tools)} инструментов")
            
        except asyncio.TimeoutError:
            logger.warning(f"⏱️  Таймаут получения списка инструментов от агента {device_id}")
            if request_id and request_id in agent["pending_futures"]:
                del agent["pending_futures"][request_id]
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка инструментов: {e}")
            if request_id and request_id in agent["pending_futures"]:
                del agent["pending_futures"][request_id]
        
        # 3. Получаем список модулей (для проверки)
        request_id = None
        try:
            logger.info(f"📋 Запрос списка модулей от агента {device_id}")
            
            # Генерируем request_id для этой команды
            request_id = str(uuid.uuid4())
            future = asyncio.get_event_loop().create_future()
            agent["pending_futures"][request_id] = future
            
            # Формируем команду в формате envelope
            command_envelope = {
                "type": "command",
                "request_id": request_id,
                "device_id": agent_device_id,
                "payload": {
                    "command": "list_modules",
                    "params": {}
                }
            }
            
            logger.info(f"[SERVER] TX command list_modules request_id={request_id}")
            await ws.send_json(command_envelope)
            response = await asyncio.wait_for(future, timeout=30.0)
            
            # Извлекаем payload из command_result
            if isinstance(response, dict) and "payload" in response:
                response_payload = response["payload"]
            else:
                response_payload = response
            
            if response_payload.get("status") == "success" and "data" in response_payload:
                modules_list = response_payload["data"].get("observations", {}).get("modules", [])
                # Обновляем информацию о модулях, если она есть
                if modules_list:
                    logger.success(f"✅ Список модулей получен: {len(modules_list)} модулей")
            
        except asyncio.TimeoutError:
            logger.warning(f"⏱️  Таймаут получения списка модулей от агента {device_id}")
            if request_id and request_id in agent["pending_futures"]:
                del agent["pending_futures"][request_id]
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка модулей: {e}")
            if request_id and request_id in agent["pending_futures"]:
                del agent["pending_futures"][request_id]
        
        # Формируем итоговый ответ
        return web.json_response({
            "status": "success",
            "data": functions_info
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка проверки функций: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_install_module_package(request):
    """
    API эндпоинт для установки модульного пакета (ZIP) на агент.
    
    Принимает ZIP файл через multipart/form-data, вычисляет SHA256,
    конвертирует в base64 и отправляет агенту через WebSocket.
    
    Поля формы:
    - device_id: string (обязательно)
    - name: string (обязательно) - имя модуля
    - version: string (обязательно) - версия модуля
    - actor_role: string (optional, default "admin")
    - sha256: string (optional) - ожидаемый хэш для проверки
    - file: бинарный ZIP (обязательно) - архив модуля
    
    Ограничение размера: 20MB
    """
    try:
        # Ограничение размера файла (20MB)
        MAX_FILE_SIZE = 20 * 1024 * 1024
        
        logger.info("[SERVER] install_module_package RX")
        
        # Читаем multipart/form-data
        reader = await request.multipart()
        
        device_id = None
        name = None
        version = None
        actor_role = "admin"
        expected_sha256 = None
        zip_bytes = None
        
        async for field in reader:
            if field.name == "device_id":
                device_id = await field.read()
                device_id = device_id.decode('utf-8').strip()
            elif field.name == "name":
                name = await field.read()
                name = name.decode('utf-8').strip()
            elif field.name == "version":
                version = await field.read()
                version = version.decode('utf-8').strip()
            elif field.name == "actor_role":
                actor_role = await field.read()
                actor_role = actor_role.decode('utf-8').strip()
            elif field.name == "sha256":
                expected_sha256 = await field.read()
                expected_sha256 = expected_sha256.decode('utf-8').strip()
            elif field.name == "file":
                # Читаем файл чанками
                zip_bytes = b""
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    zip_bytes += chunk
                    if len(zip_bytes) > MAX_FILE_SIZE:
                        logger.error(f"[SERVER] install_module_package ZIP too large: {len(zip_bytes)} bytes")
                        return web.json_response({
                            "status": "error",
                            "error": f"File too large (max {MAX_FILE_SIZE} bytes)"
                        }, status=413)
        
        # Проверка обязательных полей
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not name:
            return web.json_response({
                "status": "error",
                "error": "Missing name"
            }, status=400)
        
        if not version:
            return web.json_response({
                "status": "error",
                "error": "Missing version"
            }, status=400)
        
        if not zip_bytes:
            return web.json_response({
                "status": "error",
                "error": "Missing file"
            }, status=400)
        
        logger.info(f"[SERVER] install_module_package RX device_id={device_id} name={name} version={version} bytes={len(zip_bytes)}")
        
        # Проверка подключения агента
        if device_id not in connected_agents:
            logger.warning(f"[SERVER] install_module_package agent {device_id} not connected")
            return web.json_response({
                "status": "error",
                "error": f"Agent {device_id} not connected"
            }, status=404)
        
        # Вычисляем SHA256
        computed_sha256 = hashlib.sha256(zip_bytes).hexdigest()
        logger.info(f"[SERVER] computed sha256={computed_sha256}")
        
        # Проверка ожидаемого хэша, если был передан
        if expected_sha256 and expected_sha256 != computed_sha256:
            logger.error(f"[SERVER] install_module_package HASH_MISMATCH expected={expected_sha256} computed={computed_sha256}")
            return web.json_response({
                "status": "error",
                "error": "HASH_MISMATCH",
                "expected_sha256": expected_sha256,
                "computed_sha256": computed_sha256
            }, status=400)
        
        # Конвертируем в base64
        package_b64 = base64.b64encode(zip_bytes).decode('utf-8')
        
        # Формируем параметры команды
        params = {
            "name": name,
            "version": version,
            "package_b64": package_b64,
            "sha256": computed_sha256
        }
        
        # Отправляем команду агенту
        request_id = str(uuid.uuid4())
        logger.info(f"[SERVER] TX command install_module_package request_id={request_id}")
        
        try:
            response = await send_ws_command(
                device_id=device_id,
                command="install_module_package",
                params=params,
                actor_role=actor_role,
                timeout=60  # Увеличенный таймаут для установки модулей
            )
            
            # Извлекаем payload из ответа
            agent_response = response.get("payload", response) if isinstance(response, dict) else response
            
            logger.info(f"[SERVER] RX command_result request_id={request_id} status={agent_response.get('status', 'unknown')}")
            
            return web.json_response({
                "status": "success" if agent_response.get("status") == "success" else "error",
                "request_id": request_id,
                "agent_response": agent_response,
                "sha256": computed_sha256,
                "bytes_len": len(zip_bytes)
            })
        
        except asyncio.TimeoutError:
            logger.error(f"[SERVER] install_module_package timeout request_id={request_id}")
            return web.json_response({
                "status": "error",
                "error": "Command timeout",
                "request_id": request_id,
                "sha256": computed_sha256,
                "bytes_len": len(zip_bytes)
            }, status=504)
        except ValueError as e:
            logger.error(f"[SERVER] install_module_package error: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e),
                "sha256": computed_sha256,
                "bytes_len": len(zip_bytes)
            }, status=404)
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки install_module_package: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

PROTOCOL_DOC = """
WebSocket Envelope Format:
{
    "type": "command" | "command_result" | "handshake" | "handshake_ack" | "outbox_item" | "ack" | "pong",
    "request_id": "<uuid4>",
    "device_id": "<device_id>",
    "payload": { ... }
}

Commands:
1. install_module_package:
   Request:
   {
     "type": "command",
     "request_id": "<uuid4>",
     "device_id": "<device_id>",
     "payload": {
       "command": "install_module_package",
       "params": {
         "name": "<module_name>",
         "version": "<module_version>",
         "package_b64": "<base64_encoded_zip>",
         "sha256": "<sha256_hash>",
         "actor_role": "admin"
       },
       "actor_role": "admin"
     }
   }
   
   Response:
   {
     "type": "command_result",
     "request_id": "<uuid4>",
     "device_id": "<device_id>",
     "payload": {
       "status": "success" | "error",
       "data": { ... },
       "error": { ... }
     }
   }

2. run_tool:
   Request:
   {
     "type": "command",
     "request_id": "<uuid4>",
     "device_id": "<device_id>",
     "payload": {
       "command": "run_tool",
       "params": {
         "tool": "<module.tool>",
         "params": { ... }
       },
       "actor_role": "admin"
     }
   }
   
   Response:
   {
     "type": "command_result",
     "request_id": "<uuid4>",
     "device_id": "<device_id>",
     "payload": {
       "status": "success" | "error",
       "data": { ... },
       "error": { ... }
     }
   }
   
   Примеры:
   - diag.logs.collect:
     params: {
       "tool": "diag.logs.collect",
       "params": {
         "preset": "system",
         "max_total_bytes": 3000000,
         "max_files": 30,
         "include_journal": false
       }
     }
   
   - diag.hello (тестовый):
     params: {
       "tool": "diag.hello",
       "params": {}
     }

3. list_tools:
   Request:
   {
     "type": "command",
     "request_id": "<uuid4>",
     "device_id": "<device_id>",
     "payload": {
       "command": "list_tools",
       "params": {},
       "actor_role": "admin"
     }
   }
   
   Response:
   {
     "type": "command_result",
     "request_id": "<uuid4>",
     "device_id": "<device_id>",
     "payload": {
       "status": "success",
       "data": {
         "observations": {
           "tools": [
             {
               "name": "diag.hello",
               "module": "diag",
               "description": "...",
               "risk_level": "safe_readonly"
             }
           ]
         }
       }
     }
   }

4. collect:
   Request:
   {
     "type": "command",
     "request_id": "<uuid4>",
     "device_id": "<device_id>",
     "payload": {
       "command": "collect",
       "params": {
         "modules": ["module1", "module2"]
       }
     }
   }

Outbox ACK:
{
  "type": "ack",
  "request_id": "<uuid4>",
  "device_id": "<device_id>",
  "payload": {
    "outbox_ids": ["<outbox_id>"]
  }
}
"""

async def handle_list_installed_modules(request):
    """
    API эндпоинт для получения списка установленных модулей: POST /api/list_installed_modules
    
    POST JSON:
    { "device_id": "...", "actor_role": "admin" }
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        logger.info(f"[SERVER] list_installed_modules device_id={device_id}")
        
        res = await send_ws_command(device_id, "list_installed_modules", params={}, actor_role=actor_role)
        
        # Возвращаем payload из command_result
        if isinstance(res, dict) and "payload" in res:
            return web.json_response(res["payload"])
        else:
            return web.json_response(res)
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды list_installed_modules")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки list_installed_modules: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_activate_module(request):
    """
    API эндпоинт для активации модуля: POST /api/activate_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "version": "0.1.0", "actor_role": "admin" }
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        version = data.get("version")
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not name:
            return web.json_response({
                "status": "error",
                "error": "Missing name"
            }, status=400)
        
        if not version:
            return web.json_response({
                "status": "error",
                "error": "Missing version"
            }, status=400)
        
        logger.info(f"[SERVER] activate_module device_id={device_id} name={name} version={version}")
        
        params = {"name": name, "version": version}
        res = await send_ws_command(device_id, "activate_module", params, actor_role=actor_role)
        
        # Возвращаем полный результат
        if isinstance(res, dict) and "payload" in res:
            return web.json_response(res["payload"])
        else:
            return web.json_response(res)
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды activate_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки activate_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_rollback_module(request):
    """
    API эндпоинт для отката модуля: POST /api/rollback_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "actor_role": "admin" }
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not name:
            return web.json_response({
                "status": "error",
                "error": "Missing name"
            }, status=400)
        
        logger.info(f"[SERVER] rollback_module device_id={device_id} name={name}")
        
        params = {"name": name}
        res = await send_ws_command(device_id, "rollback_module", params, actor_role=actor_role)
        
        # Возвращаем полный результат
        if isinstance(res, dict) and "payload" in res:
            return web.json_response(res["payload"])
        else:
            return web.json_response(res)
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды rollback_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки rollback_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_deactivate_module(request):
    """
    API эндпоинт для деактивации модуля: POST /api/deactivate_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "actor_role": "admin" }
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not name:
            return web.json_response({
                "status": "error",
                "error": "Missing name"
            }, status=400)
        
        logger.info(f"[SERVER] deactivate_module device_id={device_id} name={name}")
        
        params = {"name": name}
        res = await send_ws_command(device_id, "deactivate_module", params, actor_role=actor_role)
        
        # Возвращаем полный результат
        if isinstance(res, dict) and "payload" in res:
            return web.json_response(res["payload"])
        else:
            return web.json_response(res)
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды deactivate_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки deactivate_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_smoke_install_and_run(request):
    """
    API эндпоинт для smoke-теста: установка модуля и проверка функционала.
    
    POST multipart/form-data:
    - device_id (str) ОБЯЗАТЕЛЬНО
    - name (str) ОБЯЗАТЕЛЬНО
    - version (str) ОБЯЗАТЕЛЬНО
    - actor_role (str) optional, default "admin"
    - file (zip) ОБЯЗАТЕЛЬНО
    
    Алгоритм:
    1. install_module_package
    2. list_tools (проверка появления инструмента)
    3. run_tool "diag.hello" (если появился)
    """
    try:
        MAX_FILE_SIZE = 20 * 1024 * 1024
        
        logger.info("[SERVER] smoke_install_and_run RX")
        
        reader = await request.multipart()
        
        device_id = None
        name = None
        version = None
        actor_role = "admin"
        zip_bytes = None
        
        async for field in reader:
            if field.name == "device_id":
                device_id = await field.read()
                device_id = device_id.decode('utf-8').strip()
            elif field.name == "name":
                name = await field.read()
                name = name.decode('utf-8').strip()
            elif field.name == "version":
                version = await field.read()
                version = version.decode('utf-8').strip()
            elif field.name == "actor_role":
                actor_role = await field.read()
                actor_role = actor_role.decode('utf-8').strip()
            elif field.name == "file":
                zip_bytes = b""
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    zip_bytes += chunk
                    if len(zip_bytes) > MAX_FILE_SIZE:
                        return web.json_response({
                            "status": "error",
                            "error": f"File too large (max {MAX_FILE_SIZE} bytes)"
                        }, status=413)
        
        if not device_id or not name or not version or not zip_bytes:
            return web.json_response({
                "status": "error",
                "error": "Missing required fields"
            }, status=400)
        
        logger.info(f"[SERVER] smoke_install_and_run device_id={device_id} name={name} version={version}")
        
        summary = {
            "device_id": device_id,
            "name": name,
            "version": version,
            "steps": []
        }
        
        # Шаг 1: install_module_package
        try:
            computed_sha256 = hashlib.sha256(zip_bytes).hexdigest()
            package_b64 = base64.b64encode(zip_bytes).decode('utf-8')
            
            params = {
                "name": name,
                "version": version,
                "package_b64": package_b64,
                "sha256": computed_sha256
            }
            
            install_res = await send_ws_command(device_id, "install_module_package", params, actor_role=actor_role, timeout=60)
            install_payload = install_res.get("payload", install_res) if isinstance(install_res, dict) else install_res
            
            summary["steps"].append({
                "step": "install_module_package",
                "status": install_payload.get("status", "unknown"),
                "result": install_payload
            })
            
            if install_payload.get("status") != "success":
                return web.json_response({
                    "status": "error",
                    "error": "Install failed",
                    "summary": summary
                }, status=500)
        
        except Exception as e:
            summary["steps"].append({
                "step": "install_module_package",
                "status": "error",
                "error": str(e)
            })
            return web.json_response({
                "status": "error",
                "error": f"Install failed: {str(e)}",
                "summary": summary
            }, status=500)
        
        # Шаг 2: list_tools
        try:
            tools_res = await send_ws_command(device_id, "list_tools", params={}, actor_role=actor_role)
            tools_payload = tools_res.get("payload", tools_res) if isinstance(tools_res, dict) else tools_res
            
            tools = []
            if tools_payload.get("status") == "success":
                observations = tools_payload.get("data", {}).get("observations", {})
                tools = observations.get("tools", [])
            
            # Ищем инструмент с префиксом модуля (например, "diag.hello" или "hello.hello")
            expected_tool_prefix = f"{name}." if name else None
            found_tool = None
            for tool in tools:
                tool_name = tool.get("name", "")
                if expected_tool_prefix and tool_name.startswith(expected_tool_prefix):
                    found_tool = tool_name
                    break
                elif name and tool_name == name:
                    found_tool = tool_name
                    break
            
            summary["steps"].append({
                "step": "list_tools",
                "status": tools_payload.get("status", "unknown"),
                "tools_count": len(tools),
                "found_tool": found_tool,
                "result": tools_payload
            })
            
            # Шаг 3: run_tool (если инструмент найден)
            if found_tool:
                try:
                    run_res = await send_ws_command(device_id, "run_tool", params={"tool_name": found_tool, "args": {}}, actor_role=actor_role)
                    run_payload = run_res.get("payload", run_res) if isinstance(run_res, dict) else run_res
                    
                    summary["steps"].append({
                        "step": "run_tool",
                        "tool_name": found_tool,
                        "status": run_payload.get("status", "unknown"),
                        "result": run_payload
                    })
                except Exception as e:
                    summary["steps"].append({
                        "step": "run_tool",
                        "tool_name": found_tool,
                        "status": "error",
                        "error": str(e)
                    })
            else:
                summary["steps"].append({
                    "step": "run_tool",
                    "status": "skipped",
                    "reason": f"Tool with prefix '{expected_tool_prefix}' not found"
                })
        
        except Exception as e:
            summary["steps"].append({
                "step": "list_tools",
                "status": "error",
                "error": str(e)
            })
        
        return web.json_response({
            "status": "success",
            "summary": summary
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки smoke_install_and_run: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_run_tool(request):
    """
    API эндпоинт для вызова инструмента на агенте: POST /api/run_tool
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "tool": "diag.logs.collect",
      "params": { ... },          # опционально
      "chat_job_id": "job_123",  # опционально
      "actor_role": "admin",      # опционально (default admin)
      "timeout": 30               # опционально
    }
    """
    try:
        logger.info("[SERVER] /api/run_tool RX")
        data = await request.json()
        
        device_id = data.get("device_id")
        tool = data.get("tool")
        params = data.get("params", {})
        chat_job_id = data.get("chat_job_id")
        actor_role = data.get("actor_role", "admin")
        timeout = data.get("timeout", 30)
        
        logger.info(f"[SERVER] /api/run_tool RX device_id={device_id} tool={tool} actor_role={actor_role}")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not tool:
            return web.json_response({
                "status": "error",
                "error": "Missing tool"
            }, status=400)
        
        # Формируем params для агента в формате, который поддерживает оба варианта
        agent_params = {
            "tool": tool,
            "params": params
        }
        if chat_job_id:
            agent_params["chat_job_id"] = chat_job_id
        
        logger.info(f"[SERVER] run_tool -> agent params keys={list(agent_params.keys())} chat_job_id_in_params={'chat_job_id' in agent_params}")
        
        chat_job_id = data.get("chat_job_id")
        logger.info(f"[SERVER] run_tool device_id={device_id} tool={tool} chat_job_id={chat_job_id}")
        
        # Отправляем команду агенту
        res = await send_ws_command(
            device_id=device_id,
            command="run_tool",
            params=agent_params,
            actor_role=actor_role,
            timeout=timeout
        )
        
        logger.info(f"[SERVER] /api/run_tool RX command_result request_id={res.get('request_id')} status={res.get('payload', {}).get('status', 'unknown')}")
        
        return web.json_response({
            "status": "ok",
            "device_id": device_id,
            "tool": tool,
            "request_id": res.get("request_id"),
            "agent_result": res
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды run_tool")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки run_tool: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_list_tools(request):
    """
    API эндпоинт для получения списка инструментов: POST /api/list_tools
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "actor_role": "admin"  # опционально
    }
    """
    try:
        logger.info("[SERVER] /api/list_tools RX")
        data = await request.json()
        
        device_id = data.get("device_id")
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        logger.info(f"[SERVER] /api/list_tools device_id={device_id}")
        
        res = await send_ws_command(device_id, "list_tools", params={}, actor_role=actor_role)
        
        # Возвращаем payload из command_result
        if isinstance(res, dict) and "payload" in res:
            return web.json_response(res["payload"])
        else:
            return web.json_response(res)
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды list_tools")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки list_tools: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_smoke_run(request):
    """
    API эндпоинт для smoke-теста: проверка работоспособности через list_tools и run_tool.
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "tool": "diag.hello",
      "params": {},
      "actor_role": "admin"
    }
    """
    try:
        logger.info("[SERVER] /api/smoke_run RX")
        data = await request.json()
        
        device_id = data.get("device_id")
        tool = data.get("tool")
        params = data.get("params", {})
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not tool:
            return web.json_response({
                "status": "error",
                "error": "Missing tool"
            }, status=400)
        
        logger.info(f"[SERVER] /api/smoke_run device_id={device_id} tool={tool}")
        
        # Шаг 1: list_tools
        tools_res = await send_ws_command(device_id, "list_tools", params={}, actor_role=actor_role)
        tools_payload = tools_res.get("payload", tools_res) if isinstance(tools_res, dict) else tools_res
        
        # Проверяем, что tool в списке
        tool_exists = False
        tools_list = []
        if tools_payload.get("status") == "success":
            observations = tools_payload.get("data", {}).get("observations", {})
            tools_list = observations.get("tools", [])
            tool_exists = any(t.get("name") == tool for t in tools_list)
        
        if not tool_exists:
            return web.json_response({
                "status": "error",
                "error": f"Tool '{tool}' not found in tools list",
                "device_id": device_id,
                "tool_exists": False,
                "list_tools": tools_payload
            }, status=409)
        
        # Шаг 2: run_tool
        agent_params = {
            "tool": tool,
            "params": params
        }
        run_res = await send_ws_command(
            device_id=device_id,
            command="run_tool",
            params=agent_params,
            actor_role=actor_role
        )
        
        return web.json_response({
            "status": "success",
            "device_id": device_id,
            "tool_exists": True,
            "list_tools": tools_payload,
            "run_tool": run_res
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды smoke_run")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки smoke_run: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_get_job_events(request):
    """
    API эндпоинт для получения событий job: GET /api/job_events?job_id=...
    
    Возвращает список событий для указанного job_id.
    """
    try:
        job_id = request.query.get("job_id")
        
        if not job_id:
            return web.json_response({
                "status": "error",
                "error": "Missing job_id parameter"
            }, status=400)
        
        # Получаем события для job_id
        events = job_events.get(job_id, [])
        
        return web.json_response({
            "job_id": job_id,
            "events": events,
            "count": len(events)
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения job_events: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_start_job(request):
    """
    API эндпоинт для запуска тестового job: POST /api/start_job
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "job_type": "chat_echo",
      "params": {},
      "actor_role": "admin"
    }
    
    Вызывает send_ws_command с командой "start_job".
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        job_type = data.get("job_type")
        params = data.get("params", {})
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not job_type:
            return web.json_response({
                "status": "error",
                "error": "Missing job_type"
            }, status=400)
        
        logger.info(f"[SERVER] start_job device_id={device_id} job_type={job_type} actor_role={actor_role}")
        
        # Формируем параметры команды start_job
        command_params = {
            "job_type": job_type,
            "params": params
        }
        
        # Отправляем команду агенту
        response = await send_ws_command(
            device_id=device_id,
            command="start_job",
            params=command_params,
            actor_role=actor_role,
            timeout=60
        )
        
        # Извлекаем payload из ответа
        if isinstance(response, dict) and "payload" in response:
            response_payload = response["payload"]
        else:
            response_payload = response
        
        return web.json_response({
            "status": "success" if response_payload.get("status") == "success" else "error",
            "device_id": device_id,
            "job_type": job_type,
            "response": response_payload
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды start_job")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки start_job: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_chat_start(request):
    """
    API эндпоинт для запуска чат-job: POST /api/chat_start
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "actor_role": "admin"
    }
    
    Запускает support_chat job и возвращает job_id.
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        logger.info(f"[SERVER] chat_start device_id={device_id} actor_role={actor_role}")
        
        # Генерируем chat_job_id на сервере
        chat_job_id = str(uuid.uuid4())
        
        # Инициализируем job_events для chat_job_id
        job_events.setdefault(chat_job_id, [])
        
        # Создаем chat_session
        chat_sessions[chat_job_id] = {
            "chat_job_id": chat_job_id,
            "device_id": device_id,
            "owner_uuid": None,  # TODO: можно получить из connected_agents
            "created_by": "support",
            "status": "active",
            "created_at": time.time(),
            "subscribers": set(),
            "events": []
        }
        
        # Отправляем команду start_job с job_type="support_chat" и переданным job_id
        res = await send_ws_command(
            device_id=device_id,
            command="start_job",
            params={"job_type": "support_chat", "params": {"job_id": chat_job_id}},
            actor_role=actor_role,
            timeout=60
        )
        
        logger.info(f"[SERVER] chat_start success job_id={chat_job_id}")
        
        # Создаем invite событие
        invite_event = {
            "event": "chat_invite",
            "job_id": chat_job_id,
            "device_id": device_id,
            "from": "support",
            "title": "Support Chat",
            "ts": time.time(),
        }
        
        # PUSH invite в UI (через WebSocket подписчиков)
        await push_chat_event_to_ui(chat_job_id, invite_event)
        logger.info(f"[SERVER] TX chat_invite to UI subscribers job_id={chat_job_id}")
        
        # PUSH invite в локальный GUI агента (через EventBus -> /ui/events)
        try:
            await send_ws_command(
                device_id=device_id,
                command="ui_notify",
                params={"event": invite_event},
                actor_role=actor_role,
                timeout=10
            )
            logger.info(f"[SERVER] TX ui_notify chat_invite job_id={chat_job_id} device_id={device_id}")
        except Exception as e:
            # invite не должен ломать chat_start
            logger.warning(f"[SERVER] Failed to send chat_invite to agent UI: {e}")
        
        return web.json_response({
            "status": "success",
            "job_id": chat_job_id,
            "device_id": device_id
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды chat_start")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки chat_start: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_chat_raise(request):
    """
    API эндпоинт для инициации чата агентом: POST /api/chat_raise
    
    POST JSON:
    {
      "device_id": "test_pc_01"
    }
    
    Агент инициирует чат, сервер стартует support_chat job и отправляет chat_invite в GUI агента.
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if device_id not in connected_agents:
            return web.json_response({
                "status": "error",
                "error": f"Agent {device_id} not connected"
            }, status=404)
        
        logger.info(f"[SERVER] chat_raise device_id={device_id}")
        
        # Генерируем chat_job_id
        chat_job_id = str(uuid.uuid4())
        
        # Инициализируем job_events для chat_job_id
        job_events.setdefault(chat_job_id, [])
        
        # Создаем chat_session
        chat_sessions[chat_job_id] = {
            "chat_job_id": chat_job_id,
            "device_id": device_id,
            "owner_uuid": None,  # TODO: можно получить из connected_agents
            "created_by": "agent",
            "status": "active",
            "created_at": time.time(),
            "subscribers": set(),
            "events": []
        }
        
        # Отправляем команду start_job с job_type="support_chat" и переданным job_id
        res = await send_ws_command(
            device_id=device_id,
            command="start_job",
            params={"job_type": "support_chat", "params": {"job_id": chat_job_id}},
            actor_role="agent",
            timeout=60
        )
        
        logger.info(f"[SERVER] chat_raise success job_id={chat_job_id}")
        
        # Создаем invite событие
        invite_event = {
            "event": "chat_invite",
            "job_id": chat_job_id,
            "device_id": device_id,
            "from": "agent",
            "title": "Agent Chat",
            "ts": time.time(),
        }
        
        # PUSH invite в UI (через WebSocket подписчиков)
        await push_chat_event_to_ui(chat_job_id, invite_event)
        logger.info(f"[SERVER] TX chat_invite to UI subscribers job_id={chat_job_id}")
        
        # PUSH invite в локальный GUI агента (через EventBus -> /ui/events)
        try:
            await send_ws_command(
                device_id=device_id,
                command="ui_notify",
                params={"event": invite_event},
                actor_role="agent",
                timeout=10
            )
            logger.info(f"[SERVER] TX ui_notify chat_invite job_id={chat_job_id} device_id={device_id}")
        except Exception as e:
            # invite не должен ломать chat_raise
            logger.warning(f"[SERVER] Failed to send chat_invite to agent UI: {e}")
        
        return web.json_response({
            "status": "success",
            "job_id": chat_job_id,
            "device_id": device_id
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды chat_raise")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки chat_raise: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_chat_send(request):
    """
    API эндпоинт для отправки сообщения в чат-job: POST /api/chat_send
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "job_id": "<job_id>",
      "text": "hello",
      "from": "support",
      "actor_role": "support"
    }
    
    Отправляет chat_message событие в job через job_send_event.
    """
    try:
        data = await request.json()
        device_id = data.get("device_id")
        job_id = data.get("job_id")
        text = data.get("text")
        from_ = data.get("from")
        actor_role = data.get("actor_role", "support")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not job_id:
            return web.json_response({
                "status": "error",
                "error": "Missing job_id"
            }, status=400)
        
        if not text:
            return web.json_response({
                "status": "error",
                "error": "Missing text"
            }, status=400)
        
        if not from_:
            return web.json_response({
                "status": "error",
                "error": "Missing from"
            }, status=400)
        
        # Формируем событие chat_message
        event = {
            "event": "chat_message",
            "job_id": job_id,
            "message_id": str(uuid.uuid4()),
            "from": from_,
            "text": text,
            "ts": time.time()
        }
        
        # Логируем отправку (truncate длинный текст)
        text_preview = text[:50] + "..." if len(text) > 50 else text
        logger.info(f"[SERVER] chat_send job_id={job_id} text_len={len(text)} text_preview={text_preview}")
        
        # Отправляем команду job_send_event
        res = await send_ws_command(
            device_id=device_id,
            command="job_send_event",
            params={"job_id": job_id, "event": event},
            actor_role=actor_role,
            timeout=30
        )
        
        # Валидация ответа (опционально, но рекомендовано для отладки)
        validated = False
        try:
            observations = res.get("payload", {}).get("data", {}).get("observations", {})
            if observations:
                obs_job_id = observations.get("chat_job_id")
                obs_message_id = observations.get("message_id")
                validated = (
                    obs_job_id == job_id and
                    obs_message_id == event["message_id"]
                )
        except Exception:
            pass  # Валидация не критична, просто пропускаем
        
        # Возвращаем результат
        return web.json_response({
            "status": "success",
            "job_id": job_id,
            "message_id": event["message_id"],
            "validated": validated,
            "response": res
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды chat_send")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки chat_send: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_active_chats(request):
    """
    API эндпоинт для получения списка активных чатов: GET /api/active_chats
    
    Возвращает все активные чат-сессии с информацией о них.
    """
    try:
        active_chats = []
        
        for chat_job_id, session in chat_sessions.items():
            if session.get("status") != "active":
                continue
            
            device_id = session.get("device_id", "unknown")
            agent_info = connected_agents.get(device_id, {})
            
            active_chats.append({
                "job_id": chat_job_id,
                "device_id": device_id,
                "created_by": session.get("created_by", "unknown"),
                "created_at": session.get("created_at", 0),
                "subscribers_count": len(session.get("subscribers", set())),
                "agent_status": agent_info.get("status", "offline"),
                "agent_version": agent_info.get("agent_version", "unknown")
            })
        
        # Сортируем по времени создания (новые сверху)
        active_chats.sort(key=lambda x: x["created_at"], reverse=True)
        
        return web.json_response({
            "status": "success",
            "chats": active_chats,
            "total": len(active_chats)
        })
        
    except Exception as e:
        logger.error(f"[handle_active_chats] Error: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_chat_events(request):
    """
    API эндпоинт для получения истории событий чат-job: GET /api/chat_events?job_id=...
    
    Query params:
    - job_id: обязательный
    - since_ts: optional float - фильтр событий где ts > since_ts
    - limit: optional int (default 200) - максимальное количество событий (последние N)
    - format: optional str - "raw" (по умолчанию) или "normalized" - формат ответа
    - wait: optional bool ("1"/"true"/"True"/"yes") - включить long-polling
    - timeout_ms: optional int (default 25000) - таймаут long-polling в миллисекундах
    
    Возвращает список событий для указанного job_id из хранилища job_events.
    При включённом wait и заданном since_ts ожидает новые события до таймаута.
    """
    try:
        job_id = request.query.get("job_id")
        
        if not job_id:
            return web.json_response({
                "status": "error",
                "error": "Missing job_id parameter"
            }, status=400)
        
        # Получаем события для job_id
        events = job_events.get(job_id, [])
        
        # Инициализируем events_with_ts сразу после получения events
        events_with_ts = [(float(e.get("ts", 0.0) or 0.0), e) for e in events]
        
        # Парсим since_ts
        since_ts_value = None
        since_ts = request.query.get("since_ts")
        if since_ts is not None:
            try:
                since_ts_value = float(since_ts)
            except (ValueError, TypeError):
                return web.json_response({
                    "status": "error",
                    "error": "Invalid since_ts parameter (must be float)"
                }, status=400)
        
        # Парсим параметры long-polling
        wait = request.query.get("wait", "0")
        wait_enabled = wait in ("1", "true", "True", "yes")
        
        timeout_ms = 25000  # default
        timeout_ms_param = request.query.get("timeout_ms")
        if timeout_ms_param is not None:
            try:
                timeout_ms = int(timeout_ms_param)
                if timeout_ms < 0:
                    return web.json_response({
                        "status": "error",
                        "error": "Invalid timeout_ms parameter (must be >= 0)"
                    }, status=400)
            except (ValueError, TypeError):
                return web.json_response({
                    "status": "error",
                    "error": "Invalid timeout_ms parameter (must be int)"
                }, status=400)
        
        deadline = time.time() + (timeout_ms / 1000.0)
        
        # Long-poll режим
        while True:
            filtered = events_with_ts
            if since_ts_value is not None:
                filtered = [(ts, e) for (ts, e) in filtered if ts > since_ts_value and ts > 0]
            
            # если нашли события — выходим
            if filtered:
                events = [e for (ts, e) in filtered]
                break
            
            # если не wait — сразу отдаём пусто
            if not wait_enabled:
                events = []
                break
            
            # wait включен — ждём до дедлайна
            if time.time() >= deadline:
                events = []
                break
            
            await asyncio.sleep(0.25)
            # важно: обновить events_with_ts, потому что job_events мог пополниться
            events = job_events.get(job_id, [])
            events_with_ts = [(float(e.get("ts", 0.0) or 0.0), e) for e in events]
        
        # Применяем limit
        limit = request.query.get("limit")
        limit_int = None
        if limit is not None:
            try:
                limit_int = int(limit)
                if limit_int < 0:
                    return web.json_response({
                        "status": "error",
                        "error": "Invalid limit parameter (must be >= 0)"
                    }, status=400)
            except (ValueError, TypeError):
                return web.json_response({
                    "status": "error",
                    "error": "Invalid limit parameter (must be int)"
                }, status=400)
        
        if limit_int is not None:
            # Сортируем по ts перед применением limit (для корректного "последних N")
            events.sort(key=lambda e: float(e.get("ts", 0.0) or 0.0))
            events = events[-limit_int:] if limit_int > 0 else []
        else:
            # Default limit = 200
            events.sort(key=lambda e: float(e.get("ts", 0.0) or 0.0))
            events = events[-200:] if len(events) > 200 else events
        
        # Параметр формата (raw или normalized)
        fmt = request.query.get("format", "raw")
        
        # Вспомогательные функции для обогащения событий
        def _event_type(e):
            return e.get("type") or e.get("event") or (e.get("payload", {}) if isinstance(e.get("payload"), dict) else {}).get("type") or "unknown"
        
        # Применяем формат
        if fmt == "normalized":
            normalized_events = []
            for e in events:
                et = _event_type(e)
                # Используем стабильный ts из события (или 0.0, не подставляем now)
                ts = float(e.get("ts", 0.0) or 0.0)
                
                normalized_events.append({
                    "ts": ts,
                    "type": et,
                    "job_id": job_id,
                    "payload": e,
                })
            events = normalized_events
        else:
            # raw mode: гарантируем ts и type-подсказку, не ломая существующие поля
            for e in events:
                if not isinstance(e.get("ts"), (int, float)):
                    # Если ts отсутствует, используем 0.0 (не now)
                    e["ts"] = 0.0
                if "type" not in e and "event" in e:
                    # старый формат: оставляем event, но добавим type для унификации
                    e["type"] = e.get("event")
        
        return web.json_response({
            "status": "ok",
            "job_id": job_id,
            "count": len(events),
            "events": events,
            "server_ts": time.time()
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения chat_events: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def handle_protocol(request):
    """
    API эндпоинт для получения документации протокола: GET /api/protocol
    
    Возвращает JSON с описанием формата WS envelope и примеры команд.
    """
    return web.json_response({
        "ws_envelope": {
            "type": "command | command_result | handshake | handshake_ack | outbox_item | ack | pong",
            "request_id": "uuid",
            "device_id": "string",
            "payload": {}
        },
        "http_endpoints": {
            "/api/install_module_package": {
                "method": "POST multipart/form-data",
                "fields": ["device_id", "name", "version", "actor_role", "file", "expected_sha256"],
                "description": "Uploads ZIP, computes sha256, sends install_module_package to agent"
            },
            "/api/list_installed_modules": {
                "method": "POST JSON",
                "fields": ["device_id", "actor_role"],
                "description": "Returns list of installed module packages"
            },
            "/api/activate_module": {
                "method": "POST JSON",
                "fields": ["device_id", "name", "version", "actor_role"],
                "description": "Activates a specific version of a module"
            },
            "/api/rollback_module": {
                "method": "POST JSON",
                "fields": ["device_id", "name", "actor_role"],
                "description": "Rolls back a module to the previous version"
            },
            "/api/deactivate_module": {
                "method": "POST JSON",
                "fields": ["device_id", "name", "actor_role"],
                "description": "Deactivates a module"
            },
            "/api/smoke_install_and_run": {
                "method": "POST multipart/form-data",
                "fields": ["device_id", "name", "version", "actor_role", "file"],
                "description": "Smoke test: install module, list tools, run test tool"
            },
            "/api/run_tool": {
                "method": "POST JSON",
                "fields": ["device_id", "tool", "params", "actor_role", "timeout"],
                "description": "Calls run_tool command on agent, waits for command_result, returns to client"
            },
            "/api/list_tools": {
                "method": "POST JSON",
                "fields": ["device_id", "actor_role"],
                "description": "Returns list of available tools from agent"
            },
            "/api/smoke_run": {
                "method": "POST JSON",
                "fields": ["device_id", "tool", "params", "actor_role"],
                "description": "Smoke test: list_tools -> run_tool -> return summary"
            }
        },
        "examples": {
            "install_module_package_command_params": {
                "name": "hello",
                "version": "0.1.0",
                "package_b64": "<base64>",
                "sha256": "<sha256>",
                "actor_role": "admin"
            },
            "activate_module_request": {
                "device_id": "test_pc_01",
                "name": "hello",
                "version": "0.1.0",
                "actor_role": "admin"
            },
            "rollback_module_request": {
                "device_id": "test_pc_01",
                "name": "hello",
                "actor_role": "admin"
            },
            "deactivate_module_request": {
                "device_id": "test_pc_01",
                "name": "hello",
                "actor_role": "admin"
            },
            "run_tool_request": {
                "device_id": "test_pc_01",
                "tool": "diag.logs.collect",
                "params": {
                    "preset": "system",
                    "max_total_bytes": 3000000,
                    "max_files": 30,
                    "include_journal": False
                },
                "actor_role": "admin",
                "timeout": 30
            },
            "run_tool_request_hello": {
                "device_id": "test_pc_01",
                "tool": "diag.hello",
                "params": {},
                "actor_role": "admin"
            },
            "list_tools_request": {
                "device_id": "test_pc_01",
                "actor_role": "admin"
            },
            "smoke_run_request": {
                "device_id": "test_pc_01",
                "tool": "diag.hello",
                "params": {},
                "actor_role": "admin"
            }
        },
        "protocol_doc": PROTOCOL_DOC
    })

async def handle_upload(request):
    """
    API эндпоинт для загрузки файлов (скриншоты, логи): POST /api/upload
    
    Агенты отправляют файлы через multipart/form-data.
    Сервер сохраняет файл с уникальным именем и возвращает URL для доступа.
    
    Требует аутентификации через заголовок Authorization.
    """
    try:
        # Аутентификация через заголовок Authorization
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            logger.warning("⚠️  Попытка загрузки файла без токена")
            return web.json_response({
                "status": "error",
                "error": "Missing Authorization header"
            }, status=401)
        
        # Извлекаем токен (формат: "Bearer token-xxx" или просто "token-xxx")
        token = auth_header.replace("Bearer ", "").strip()
        
        if token not in TOKENS:
            logger.warning(f"⚠️  Попытка загрузки с невалидным токеном: {token}")
            return web.json_response({
                "status": "error",
                "error": "Invalid or expired token"
            }, status=401)
        
        token_info = TOKENS[token]
        user = token_info["user"]
        agent_uuid = token_info["uuid"]
        
        # Читаем multipart/form-data
        reader = await request.multipart()
        file_field = None
        
        async for field in reader:
            if field.name == "file":
                file_field = field
                break
        
        if not file_field:
            logger.warning("⚠️  Отсутствует поле 'file' в multipart-запросе")
            return web.json_response({
                "status": "error",
                "error": "Missing 'file' field in request"
            }, status=400)
        
        # Получаем оригинальное имя файла
        original_filename = file_field.filename or "unnamed_file"
        
        # Генерируем уникальное имя файла
        timestamp = int(time.time())
        uuid_short = uuid.uuid4().hex[:8]
        unique_filename = f"{timestamp}_{uuid_short}_{original_filename}"
        
        # Путь для сохранения
        file_path = UPLOAD_DIR / unique_filename
        
        # Сохраняем файл чанками (для больших файлов)
        file_size = 0
        with open(file_path, "wb") as f:
            while True:
                chunk = await file_field.read_chunk()
                if not chunk:
                    break
                file_size += len(chunk)
                f.write(chunk)
        
        # Формируем URL для доступа к файлу
        file_url = f"http://localhost:8666/uploads/{unique_filename}"
        
        logger.success(f"✅ Файл загружен: {unique_filename}")
        logger.info(f"   Пользователь: {user} (UUID: {agent_uuid})")
        logger.info(f"   Размер: {file_size / 1024:.2f} KB")
        logger.info(f"   URL: {file_url}")
        
        return web.json_response({
            "status": "success",
            "file_id": unique_filename,
            "filename": original_filename,
            "url": file_url,
            "size": file_size
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки файла: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


# ============================================================================
# Ticket API Handlers
# ============================================================================

async def handle_tickets_create(request):
    """
    HTTP API для создания тикета: POST /api/tickets/create
    
    Создаёт новый тикет и сессию одновременно.
    """
    try:
        data = await request.json()
        
        # Валидация обязательных полей
        device_id = data.get("device_id", "").strip()
        user_display_name = data.get("user_display_name", "").strip()
        description = data.get("description", "").strip()
        title = data.get("title", "").strip()
        tags = data.get("tags", [])
        
        validation_errors = {}
        
        if not device_id:
            validation_errors["device_id"] = "Device ID is required and cannot be empty"
        
        if not user_display_name:
            validation_errors["user_display_name"] = "User display name is required and cannot be empty"
        
        if not description:
            validation_errors["description"] = "Description is required and cannot be empty"
        
        if validation_errors:
            return web.json_response({
                "status": "error",
                "error": "validation_error",
                "details": validation_errors
            }, status=400)
        
        # Установка значения по умолчанию для title
        if not title:
            title = "Untitled"
        
        # Генерация идентификаторов
        ticket_id = new_ticket_id()
        session_id = new_session_id()
        
        # Временные метки
        timestamp = now_iso()
        
        # Создание тикета
        ticket = Ticket(
            ticket_id=ticket_id,
            title=title,
            description=description,
            user_display_name=user_display_name,
            device_id=device_id,
            created_at=timestamp,
            updated_at=timestamp,
            assigned_to=None,
            tags=tags,
            status="open"
        )
        
        # Создание сессии
        session = Session(
            session_id=session_id,
            ticket_id=ticket_id,
            device_id=device_id,
            job_id=None,
            status="open",
            created_at=timestamp,
            updated_at=timestamp,
            last_activity_at=timestamp
        )
        
        # Сохранение в хранилища
        tickets[ticket_id] = ticket
        sessions_by_ticket[ticket_id] = session
        sessions_by_id[session_id] = session
        
        # Инициализация логов
        ticket_events[ticket_id] = []
        ticket_messages[ticket_id] = []
        
        # Запись событий в лог
        append_ticket_event(ticket_id, {
            "type": "ticket_created",
            "ticket_id": ticket_id,
            "session_id": session_id,
            "device_id": device_id,
            "ts": timestamp
        })
        
        append_ticket_event(ticket_id, {
            "type": "session_opened",
            "ticket_id": ticket_id,
            "session_id": session_id,
            "device_id": device_id,
            "ts": timestamp
        })
        
        # PROMPT 6: Создаём первичное сообщение из description
        initial_message_id = str(uuid.uuid4())
        initial_message_record = {
            "ticket_id": ticket_id,
            "message_id": initial_message_id,
            "from_role": "user",
            "text": description,
            "ts": timestamp,
            "direction": "to_agent",
            "is_initial": True
        }
        ticket_messages[ticket_id].append(initial_message_record)
        
        # Событие создания начального сообщения
        append_ticket_event(ticket_id, {
            "type": "initial_message_created",
            "ticket_id": ticket_id,
            "message_id": initial_message_id,
            "ts": timestamp
        })
        
        logger.info(f"✅ Создан тикет {ticket_id} для устройства {device_id}")
        logger.info(f"   Пользователь: {user_display_name}")
        logger.info(f"   Сессия: {session_id}")
        logger.info(f"   Начальное сообщение: {initial_message_id}")
        
        # PROMPT 6: Если агент online и job_id есть — отправляем сообщение в job
        if session.job_id:
            # Проверяем, что агент online
            if device_id in connected_agents:
                # Отправляем начальное сообщение агенту
                try:
                    event_to_send = {
                        "event": "chat_message",
                        "ticket_id": ticket_id,
                        "message_id": initial_message_id,
                        "from": "user",
                        "text": description
                    }
                    
                    command_result = await send_ws_command(
                        device_id=device_id,
                        command="job_send_event",
                        params={
                            "job_id": session.job_id,
                            "event": event_to_send
                        },
                        actor_role="user",
                        timeout=10
                    )
                    
                    # Проверяем результат команды
                    payload = command_result.get("payload", {})
                    status = payload.get("status")
                    
                    if status == "error":
                        error_info = payload.get("error", {})
                        logger.error(f"❌ Ошибка отправки начального сообщения агенту: {error_info}")
                        append_ticket_event(ticket_id, {
                            "type": "initial_message_send_failed",
                            "ticket_id": ticket_id,
                            "message_id": initial_message_id,
                            "error": error_info,
                            "ts": now_iso()
                        })
                    else:
                        logger.success(f"✅ Начальное сообщение отправлено агенту: ticket_id={ticket_id}")
                        append_ticket_event(ticket_id, {
                            "type": "initial_message_sent_to_agent",
                            "ticket_id": ticket_id,
                            "message_id": initial_message_id,
                            "ts": now_iso()
                        })
                
                except Exception as e:
                    logger.error(f"❌ Исключение при отправке начального сообщения: {e}")
                    append_ticket_event(ticket_id, {
                        "type": "initial_message_send_failed",
                        "ticket_id": ticket_id,
                        "message_id": initial_message_id,
                        "error": str(e),
                        "ts": now_iso()
                    })
            else:
                # Агент offline
                logger.info(f"⏳ Агент {device_id} offline — начальное сообщение в ожидании доставки")
                append_ticket_event(ticket_id, {
                    "type": "initial_message_pending_delivery",
                    "ticket_id": ticket_id,
                    "message_id": initial_message_id,
                    "reason": "agent_offline",
                    "ts": timestamp
                })
        else:
            # job_id еще не назначен
            logger.info(f"⏳ job_id не назначен для тикета {ticket_id} — начальное сообщение в ожидании")
            append_ticket_event(ticket_id, {
                "type": "initial_message_pending_delivery",
                "ticket_id": ticket_id,
                "message_id": initial_message_id,
                "reason": "no_job_id",
                "ts": timestamp
            })
        
        return web.json_response({
            "status": "ok",
            "ticket": ticket.to_dict(),
            "session": session.to_dict(),
            "initial_message_id": initial_message_id
        })
    
    except json.JSONDecodeError:
        return web.json_response({
            "status": "error",
            "error": "Invalid JSON"
        }, status=400)
    
    except Exception as e:
        logger.error(f"❌ Ошибка создания тикета: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_ticket_get(request):
    """
    HTTP API для получения тикета: GET /api/tickets/{ticket_id}
    
    Возвращает информацию о тикете, сессии, сообщения и события.
    """
    try:
        ticket_id = request.match_info.get("ticket_id")
        
        if not ticket_id:
            return web.json_response({
                "status": "error",
                "error": "Ticket ID is required"
            }, status=400)
        
        # Проверка существования тикета
        if ticket_id not in tickets:
            return web.json_response({
                "status": "error",
                "error": "not_found"
            }, status=404)
        
        ticket = tickets[ticket_id]
        session = sessions_by_ticket.get(ticket_id)
        messages = ticket_messages.get(ticket_id, [])
        events = ticket_events.get(ticket_id, [])
        
        # Определяем, онлайн ли агент для этого тикета
        agent_online = False
        if ticket.device_id:
            # Проверяем, есть ли активное подключение от этого device_id
            for agent_id, agent_data in connected_agents.items():
                if agent_data.get("device_id") == ticket.device_id:
                    agent_online = True
                    break
        
        return web.json_response({
            "status": "ok",
            "ticket": ticket.to_dict(),
            "session": session.to_dict() if session else None,
            "messages": messages,
            "events": events,
            "agent_online": agent_online
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения тикета: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_tickets_list(request):
    """
    HTTP API для получения списка тикетов: GET /api/tickets
    
    Возвращает все тикеты, отсортированные по дате создания (новые сверху).
    """
    try:
        # Создаём список тикетов с их сессиями
        tickets_list = []
        
        for ticket_id, ticket in tickets.items():
            session = sessions_by_ticket.get(ticket_id)
            
            # Определяем, онлайн ли агент для этого тикета
            agent_online = False
            if ticket.device_id:
                # Проверяем, есть ли активное подключение от этого device_id
                for agent_id, agent_data in connected_agents.items():
                    if agent_data.get("device_id") == ticket.device_id:
                        agent_online = True
                        break
            
            ticket_dict = ticket.to_dict()
            ticket_dict["agent_online"] = agent_online
            
            tickets_list.append({
                "ticket": ticket_dict,
                "session": session.to_dict() if session else None
            })
        
        # Сортировка по created_at убыванию (новые сверху)
        tickets_list.sort(key=lambda x: x["ticket"]["created_at"], reverse=True)
        
        return web.json_response({
            "status": "ok",
            "tickets": tickets_list
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка тикетов: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_ticket_send_message(request):
    """
    HTTP API для отправки сообщения в тикет: POST /api/tickets/{ticket_id}/message
    
    Позволяет отправить сообщение в существующий тикет.
    Сообщение проксируется через WS на агента через команду job_send_event.
    """
    try:
        ticket_id = request.match_info.get("ticket_id")
        
        if not ticket_id:
            return web.json_response({
                "status": "error",
                "error": "Ticket ID is required"
            }, status=400)
        
        # Проверка существования тикета
        if ticket_id not in tickets:
            return web.json_response({
                "status": "error",
                "error": "not_found"
            }, status=404)
        
        ticket = tickets[ticket_id]
        
        # Получение данных запроса для валидации
        data = await request.json()
        
        # PROMPT 7 - Часть B: Проверка статуса тикета (запрет отправки в closed ticket)
        if ticket.status == "closed":
            # Логируем попытку отправки в закрытый тикет
            append_ticket_event(ticket_id, {
                "type": "message_rejected_ticket_closed",
                "ticket_id": ticket_id,
                "from_role": data.get("from_role", "unknown"),
                "ts": now_iso()
            })
            
            return web.json_response({
                "status": "error",
                "error": "ticket_closed"
            }, status=409)
        
        message_id = data.get("message_id", "").strip()
        from_role = data.get("from_role", "").strip()
        text = data.get("text", "").strip()
        
        validation_errors = {}
        
        if not message_id:
            validation_errors["message_id"] = "Message ID is required"
        
        if not from_role:
            validation_errors["from_role"] = "from_role is required"
        elif from_role not in ["user", "admin", "support"]:
            validation_errors["from_role"] = "from_role must be one of: user, admin, support"
        
        if not text:
            validation_errors["text"] = "Message text is required and cannot be empty"
        
        if validation_errors:
            return web.json_response({
                "status": "error",
                "error": "validation_error",
                "details": validation_errors
            }, status=400)
        
        # Проверка на дубликат
        if is_duplicate_ticket_message(ticket_id, message_id):
            logger.info(f"📬 Дубликат сообщения: ticket_id={ticket_id} message_id={message_id}")
            return web.json_response({
                "status": "ok",
                "ticket_id": ticket_id,
                "queued": True,
                "dedup": True
            })
        
        timestamp = now_iso()
        
        # Инициализация хранилища сообщений для тикета, если нужно
        if ticket_id not in ticket_messages:
            ticket_messages[ticket_id] = []
        
        # Сохраняем сообщение локально как "to_agent"
        message_record = {
            "ticket_id": ticket_id,
            "message_id": message_id,
            "from_role": from_role,
            "text": text,
            "ts": timestamp,
            "direction": "to_agent"
        }
        ticket_messages[ticket_id].append(message_record)
        
        # Добавляем событие message_queued
        append_ticket_event(ticket_id, {
            "type": "message_queued",
            "ticket_id": ticket_id,
            "message_id": message_id,
            "from_role": from_role,
            "ts": timestamp
        })
        
        logger.info(f"📬 Сообщение сохранено локально: ticket_id={ticket_id} message_id={message_id}")
        
        # Проверяем наличие сессии и job_id
        session = sessions_by_ticket.get(ticket_id)
        
        if not session:
            logger.warning(f"⚠️  Нет активной сессии для тикета {ticket_id}")
            append_ticket_event(ticket_id, {
                "type": "no_active_job",
                "ticket_id": ticket_id,
                "message_id": message_id,
                "reason": "no_session",
                "ts": timestamp
            })
            return web.json_response({
                "status": "ok",
                "ticket_id": ticket_id,
                "queued": False,
                "warning": "no_active_job"
            })
        
        if not session.job_id:
            logger.warning(f"⚠️  Нет job_id для тикета {ticket_id}")
            append_ticket_event(ticket_id, {
                "type": "no_active_job",
                "ticket_id": ticket_id,
                "message_id": message_id,
                "reason": "no_job_id",
                "ts": timestamp
            })
            return web.json_response({
                "status": "ok",
                "ticket_id": ticket_id,
                "queued": False,
                "warning": "no_active_job"
            })
        
        # Проверяем, что агент online
        device_id = session.device_id
        if device_id not in connected_agents:
            logger.warning(f"⚠️  Агент {device_id} не подключен для тикета {ticket_id}")
            append_ticket_event(ticket_id, {
                "type": "no_active_job",
                "ticket_id": ticket_id,
                "message_id": message_id,
                "reason": "agent_offline",
                "ts": timestamp
            })
            return web.json_response({
                "status": "ok",
                "ticket_id": ticket_id,
                "queued": False,
                "warning": "no_active_job"
            })
        
        # Отправляем команду job_send_event агенту
        try:
            event_to_send = {
                "event": "chat_message",
                "ticket_id": ticket_id,
                "message_id": message_id,
                "from": from_role,
                "text": text
            }
            
            command_result = await send_ws_command(
                device_id=device_id,
                command="job_send_event",
                params={
                    "job_id": session.job_id,
                    "event": event_to_send
                },
                actor_role=from_role,
                timeout=10
            )
            
            # Проверяем результат команды
            payload = command_result.get("payload", {})
            status = payload.get("status")
            
            if status == "error":
                error_info = payload.get("error", {})
                logger.error(f"❌ Ошибка отправки сообщения агенту: {error_info}")
                append_ticket_event(ticket_id, {
                    "type": "message_send_failed",
                    "ticket_id": ticket_id,
                    "message_id": message_id,
                    "error": error_info,
                    "ts": now_iso()
                })
            else:
                logger.success(f"✅ Сообщение отправлено агенту: ticket_id={ticket_id} message_id={message_id}")
                append_ticket_event(ticket_id, {
                    "type": "message_sent_to_agent",
                    "ticket_id": ticket_id,
                    "message_id": message_id,
                    "ts": now_iso()
                })
        
        except asyncio.TimeoutError:
            logger.error(f"⏱️  Таймаут отправки сообщения агенту: ticket_id={ticket_id}")
            append_ticket_event(ticket_id, {
                "type": "message_send_failed",
                "ticket_id": ticket_id,
                "message_id": message_id,
                "error": "timeout",
                "ts": now_iso()
            })
        
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения агенту: {e}")
            append_ticket_event(ticket_id, {
                "type": "message_send_failed",
                "ticket_id": ticket_id,
                "message_id": message_id,
                "error": str(e),
                "ts": now_iso()
            })
        
        # Возвращаем успех в любом случае (сообщение сохранено локально)
        return web.json_response({
            "status": "ok",
            "ticket_id": ticket_id,
            "queued": True,
            "dedup": False
        })
    
    except json.JSONDecodeError:
        return web.json_response({
            "status": "error",
            "error": "Invalid JSON"
        }, status=400)
    
    except Exception as e:
        logger.error(f"❌ Ошибка отправки сообщения в тикет: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_ticket_close(request):
    """
    HTTP API для закрытия тикета: POST /api/tickets/{ticket_id}/close
    
    PROMPT 7: Server source of truth - сервер закрывает тикет и отправляет end_session агенту.
    
    Request JSON:
    {
        "closed_by_role": "user|admin|support",
        "reason": "string"
    }
    
    Поведение:
    - Если тикет уже closed: возвращает 200 {already_closed:true}
    - Если тикет open: закрывает тикет и сессию, пытается отправить end_session агенту
    - Идемпотентно: повторный вызов безопасен
    """
    try:
        ticket_id = request.match_info.get("ticket_id")
        
        if not ticket_id:
            return web.json_response({
                "status": "error",
                "error": "Ticket ID is required"
            }, status=400)
        
        # Проверка существования тикета
        if ticket_id not in tickets:
            return web.json_response({
                "status": "error",
                "error": "not_found"
            }, status=404)
        
        ticket = tickets[ticket_id]
        
        # Получение и валидация данных запроса
        data = await request.json()
        
        closed_by_role = data.get("closed_by_role", "").strip()
        reason = data.get("reason", "").strip()
        
        # Валидация closed_by_role
        if not closed_by_role:
            return web.json_response({
                "status": "error",
                "error": "closed_by_role is required"
            }, status=400)
        
        if closed_by_role not in ["user", "admin", "support"]:
            return web.json_response({
                "status": "error",
                "error": "closed_by_role must be one of: user, admin, support"
            }, status=400)
        
        # Если reason пустой, подставляем дефолт
        if not reason:
            reason = "closed"
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ИДЕМПОТЕНТНОСТЬ: Если тикет уже закрыт
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        if ticket.status == "closed":
            logger.info(f"[TICKET] Close idempotent: ticket {ticket_id} already closed")
            
            # Можно залогировать событие close_idempotent (опционально)
            append_ticket_event(ticket_id, {
                "type": "close_idempotent",
                "ticket_id": ticket_id,
                "closed_by_role": closed_by_role,
                "reason": reason,
                "ts": now_iso()
            })
            
            return web.json_response({
                "status": "ok",
                "ticket_id": ticket_id,
                "closed": True,
                "already_closed": True
            })
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ЗАКРЫТИЕ ТИКЕТА: Server source of truth
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        timestamp = now_iso()
        
        # Закрываем тикет
        ticket.status = "closed"
        ticket.updated_at = timestamp
        
        # Закрываем сессию
        session = sessions_by_ticket.get(ticket_id)
        if session:
            session.status = "closed"
            session.updated_at = timestamp
            session.last_activity_at = timestamp
        
        # Добавляем событие ticket_closed
        append_ticket_event(ticket_id, {
            "type": "ticket_closed",
            "ticket_id": ticket_id,
            "closed_by_role": closed_by_role,
            "reason": reason,
            "device_id": ticket.device_id if session else None,
            "job_id": session.job_id if session else None,
            "ts": timestamp
        })
        
        logger.info(f"[TICKET] Ticket closed: ticket_id={ticket_id} closed_by_role={closed_by_role} reason={reason}")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ОТПРАВКА end_session АГЕНТУ (если есть активный job и агент online)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        if session and session.job_id:
            device_id = session.device_id
            
            # Проверяем, что агент online
            if device_id in connected_agents:
                logger.info(f"[TICKET] Sending end_session to agent: device_id={device_id} job_id={session.job_id}")
                
                try:
                    # Отправляем end_session событие агенту через job_send_event
                    # НЕ ЖДЕМ синхронно завершения job (не блокируем HTTP)
                    event_to_send = {
                        "event": "end_session",
                        "ticket_id": ticket_id,
                        "reason": f"closed_by_{closed_by_role}"
                    }
                    
                    command_result = await send_ws_command(
                        device_id=device_id,
                        command="job_send_event",
                        params={
                            "job_id": session.job_id,
                            "event": event_to_send
                        },
                        actor_role=closed_by_role,
                        timeout=5  # Короткий таймаут, не блокируем надолго
                    )
                    
                    # Проверяем результат команды
                    payload = command_result.get("payload", {})
                    status = payload.get("status")
                    
                    if status == "success":
                        logger.info(f"[TICKET] end_session sent successfully: ticket_id={ticket_id}")
                        append_ticket_event(ticket_id, {
                            "type": "end_session_sent",
                            "ticket_id": ticket_id,
                            "job_id": session.job_id,
                            "device_id": device_id,
                            "ts": now_iso()
                        })
                    else:
                        # job_send_event вернул ошибку
                        error_msg = payload.get("error", "unknown")
                        logger.warning(f"[TICKET] end_session send failed: ticket_id={ticket_id} error={error_msg}")
                        append_ticket_event(ticket_id, {
                            "type": "end_session_send_failed",
                            "ticket_id": ticket_id,
                            "job_id": session.job_id,
                            "device_id": device_id,
                            "error": error_msg,
                            "ts": now_iso()
                        })
                
                except asyncio.TimeoutError:
                    logger.warning(f"[TICKET] end_session send timeout: ticket_id={ticket_id}")
                    append_ticket_event(ticket_id, {
                        "type": "end_session_send_failed",
                        "ticket_id": ticket_id,
                        "job_id": session.job_id,
                        "device_id": device_id,
                        "error": "timeout",
                        "ts": now_iso()
                    })
                
                except Exception as e:
                    logger.error(f"[TICKET] end_session send error: ticket_id={ticket_id} error={e}")
                    append_ticket_event(ticket_id, {
                        "type": "end_session_send_failed",
                        "ticket_id": ticket_id,
                        "job_id": session.job_id,
                        "device_id": device_id,
                        "error": str(e),
                        "ts": now_iso()
                    })
            
            else:
                # Агент offline
                logger.info(f"[TICKET] Agent offline, end_session not sent: ticket_id={ticket_id} device_id={device_id}")
                append_ticket_event(ticket_id, {
                    "type": "end_session_not_sent",
                    "ticket_id": ticket_id,
                    "job_id": session.job_id,
                    "device_id": device_id,
                    "reason": "agent_offline",
                    "ts": now_iso()
                })
        
        else:
            # Нет активного job
            logger.info(f"[TICKET] No active job, end_session not sent: ticket_id={ticket_id}")
            append_ticket_event(ticket_id, {
                "type": "end_session_not_sent",
                "ticket_id": ticket_id,
                "reason": "no_active_job",
                "ts": now_iso()
            })
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ВОЗВРАТ УСПЕШНОГО ОТВЕТА
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        return web.json_response({
            "status": "ok",
            "ticket_id": ticket_id,
            "closed": True,
            "already_closed": False
        })
    
    except json.JSONDecodeError:
        return web.json_response({
            "status": "error",
            "error": "Invalid JSON"
        }, status=400)
    
    except Exception as e:
        logger.error(f"❌ Ошибка закрытия тикета: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


# ============================================================================
# Tools API Handlers
# ============================================================================

async def handle_get_tools(request):
    """
    HTTP API для получения списка tools: GET /api/tools
    
    Проксирует list_tools к агенту по WS, кеширует результат на 10-30 сек.
    """
    try:
        # Получаем device_id из query параметров
        device_id = request.query.get("device_id")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "device_id is required"
            }, status=400)
        
        # Проверяем, подключен ли агент
        if device_id not in connected_agents:
            return web.json_response({
                "status": "error",
                "error": "agent_offline"
            }, status=503)
        
        # Проверяем cache
        current_time = time.time()
        cache_valid = (
            tools_cache["data"] is not None and
            (current_time - tools_cache["ts"]) < tools_cache["ttl_sec"]
        )
        
        if cache_valid:
            logger.info(f"[TOOLS] Returning cached tools list (age: {current_time - tools_cache['ts']:.1f}s)")
            return web.json_response({
                "status": "ok",
                "tools": tools_cache["data"]
            })
        
        # Cache устарел или пуст - запрашиваем у агента
        logger.info(f"[TOOLS] Requesting tools list from agent {device_id}")
        
        try:
            command_result = await send_ws_command(
                device_id=device_id,
                command="list_tools",
                params={},
                actor_role="admin",
                timeout=30
            )
            
            payload = command_result.get("payload", {})
            status = payload.get("status")
            
            if status == "success":
                # Извлекаем список tools из payload.data.observations
                data = payload.get("data", {})
                observations = data.get("observations", {})
                tools_list = observations.get("tools", [])
                
                # Сохраняем в cache
                tools_cache["data"] = tools_list
                tools_cache["ts"] = current_time
                
                logger.success(f"✅ Получен список tools от агента: {len(tools_list)} tools")
                
                return web.json_response({
                    "status": "ok",
                    "tools": tools_list
                })
            else:
                error_info = payload.get("error", {})
                logger.error(f"❌ Ошибка получения списка tools: {error_info}")
                return web.json_response({
                    "status": "error",
                    "error": error_info
                }, status=500)
        
        except asyncio.TimeoutError:
            logger.error(f"❌ Таймаут при получении списка tools от агента {device_id}")
            return web.json_response({
                "status": "error",
                "error": "timeout"
            }, status=504)
        
        except Exception as e:
            logger.error(f"❌ Исключение при получении списка tools: {e}")
            logger.exception(e)
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки запроса GET /api/tools: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_admin_run_tool(request):
    """
    HTTP API для выполнения tool: POST /api/admin/run_tool
    
    Выполняет tool (raw JSON / structured), логирует в system ticket.
    
    Request JSON:
    {
        "device_id": "...",
        "tool_name": "module.tool",
        "params": { ... },
        "mode": "in_ticket" | "system_ticket",  // default: "system_ticket"
        "ticket_id": "optional if in_ticket",
        "raw_command": { ... }   // optional, если админ шлёт полностью
    }
    
    Response:
    {
        "status": "ok",
        "ticket_id": "...",
        "call_id": "...",
        "result": { ... }
    }
    """
    try:
        data = await request.json()
        
        # Валидация обязательных полей
        device_id = data.get("device_id", "").strip()
        tool_name = data.get("tool_name", "").strip()
        params = data.get("params", {})
        mode = data.get("mode", "system_ticket")
        ticket_id = data.get("ticket_id")
        raw_command = data.get("raw_command")
        
        validation_errors = {}
        
        if not device_id:
            validation_errors["device_id"] = "Device ID is required"
        
        if not tool_name:
            validation_errors["tool_name"] = "Tool name is required"
        
        if mode not in ["in_ticket", "system_ticket"]:
            validation_errors["mode"] = "Mode must be 'in_ticket' or 'system_ticket'"
        
        if mode == "in_ticket" and not ticket_id:
            validation_errors["ticket_id"] = "Ticket ID is required for mode 'in_ticket'"
        
        if validation_errors:
            return web.json_response({
                "status": "error",
                "error": "validation_error",
                "details": validation_errors
            }, status=400)
        
        # Проверяем, подключен ли агент
        if device_id not in connected_agents:
            return web.json_response({
                "status": "error",
                "error": "agent_offline"
            }, status=503)
        
        # Определяем ticket context
        if mode == "system_ticket":
            # Создаём системный тикет
            ticket_id, session_id = create_system_ticket_for_admin_action(
                device_id=device_id,
                tool_name=tool_name,
                params=params
            )
            logger.info(f"[ADMIN_RUN_TOOL] Создан системный тикет: ticket_id={ticket_id}")
        else:
            # Используем существующий тикет
            if ticket_id not in tickets:
                return web.json_response({
                    "status": "error",
                    "error": "ticket_not_found"
                }, status=404)
            logger.info(f"[ADMIN_RUN_TOOL] Используется существующий тикет: ticket_id={ticket_id}")
        
        # Генерируем call_id для отслеживания вызова
        call_id = str(uuid.uuid4())
        
        # Добавляем события в ticket
        append_ticket_event(ticket_id, {
            "kind": "agent_action",
            "type": "tool_call",
            "title": "Admin requested tool call",
            "tool_name": tool_name,
            "call_id": call_id,
            "ts": now_iso()
        })
        
        append_ticket_event(ticket_id, {
            "type": "tool_call_started",
            "call_id": call_id,
            "tool_name": tool_name,
            "params": params,
            "ts": now_iso()
        })
        
        # Формируем команду для агента
        command_params = {
            "tool_name": tool_name,
            "args": params,
            "ticket_id": ticket_id,  # Важно: передаём ticket_id агенту
            "call_id": call_id
        }
        
        # Если есть raw_command, используем его
        if raw_command:
            command_params = raw_command
        
        logger.info(f"[ADMIN_RUN_TOOL] Отправка команды run_tool агенту {device_id}")
        
        try:
            command_result = await send_ws_command(
                device_id=device_id,
                command="run_tool",
                params=command_params,
                actor_role="admin",
                timeout=60  # Увеличенный таймаут для выполнения tool
            )
            
            payload = command_result.get("payload", {})
            status = payload.get("status")
            
            # Извлекаем результат
            tool_result = payload.get("data", {})
            tool_status = "success" if status == "success" else "error"
            
            # Ограничиваем размер результата (max 10KB JSON)
            result_str = json.dumps(tool_result, ensure_ascii=False)
            max_result_size = 10 * 1024  # 10KB
            if len(result_str) > max_result_size:
                tool_result = {
                    "truncated": True,
                    "original_size": len(result_str),
                    "preview": result_str[:max_result_size] + "..."
                }
                logger.warning(f"[ADMIN_RUN_TOOL] Результат tool был усечён: {len(result_str)} -> {max_result_size} bytes")
            
            # Формируем summary
            if status == "success":
                summary = f"Tool {tool_name} executed successfully"
            else:
                error_info = payload.get("error", {})
                summary = f"Tool {tool_name} failed: {error_info.get('message', 'unknown error')}"
            
            # Добавляем событие с результатом
            append_ticket_event(ticket_id, {
                "type": "tool_call_result",
                "call_id": call_id,
                "tool_name": tool_name,
                "status": tool_status,
                "summary": summary,
                "result": tool_result,
                "ts": now_iso()
            })
            
            logger.success(f"✅ Tool {tool_name} выполнен: status={tool_status}")
            
            return web.json_response({
                "status": "ok",
                "ticket_id": ticket_id,
                "call_id": call_id,
                "result": tool_result,
                "tool_status": tool_status
            })
        
        except asyncio.TimeoutError:
            logger.error(f"❌ Таймаут при выполнении tool {tool_name}")
            
            # Добавляем событие об ошибке
            append_ticket_event(ticket_id, {
                "type": "tool_call_result",
                "call_id": call_id,
                "tool_name": tool_name,
                "status": "error",
                "summary": f"Tool {tool_name} execution timeout",
                "error": "timeout",
                "ts": now_iso()
            })
            
            return web.json_response({
                "status": "error",
                "error": "timeout",
                "ticket_id": ticket_id,
                "call_id": call_id
            }, status=504)
        
        except Exception as e:
            logger.error(f"❌ Исключение при выполнении tool {tool_name}: {e}")
            logger.exception(e)
            
            # Добавляем событие об ошибке
            append_ticket_event(ticket_id, {
                "type": "tool_call_result",
                "call_id": call_id,
                "tool_name": tool_name,
                "status": "error",
                "summary": f"Tool {tool_name} execution error",
                "error": str(e),
                "ts": now_iso()
            })
            
            return web.json_response({
                "status": "error",
                "error": str(e),
                "ticket_id": ticket_id,
                "call_id": call_id
            }, status=500)
    
    except json.JSONDecodeError:
        return web.json_response({
            "status": "error",
            "error": "Invalid JSON"
        }, status=400)
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки запроса POST /api/admin/run_tool: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_tools_run(request):
    """
    HTTP API для запуска tool из интерфейса тикета: POST /api/tools/run
    
    Поддерживает запуск как с пресетом, так и с кастомными параметрами.
    
    Request JSON:
    {
        "device_id": "...",
        "ticket_id": "...",          // обязательно - привязка к тикету
        "tool_name": "module.tool",
        "preset_id": "basic",         // опционально - ID пресета
        "params": { ... }             // опционально - кастомные параметры (приоритет над пресетом)
    }
    
    Response:
    {
        "status": "ok",
        "ticket_id": "...",
        "call_id": "...",
        "result": { ... },
        "tool_status": "success" | "error"
    }
    """
    try:
        data = await request.json()
        
        # Валидация обязательных полей
        device_id = data.get("device_id", "").strip()
        ticket_id = data.get("ticket_id", "").strip()
        tool_name = data.get("tool_name", "").strip()
        preset_id = data.get("preset_id")
        params = data.get("params")
        
        validation_errors = {}
        
        if not device_id:
            validation_errors["device_id"] = "Device ID is required"
        
        if not ticket_id:
            validation_errors["ticket_id"] = "Ticket ID is required"
        
        if not tool_name:
            validation_errors["tool_name"] = "Tool name is required"
        
        if validation_errors:
            return web.json_response({
                "status": "error",
                "error": "validation_error",
                "details": validation_errors
            }, status=400)
        
        # Если указан preset_id, но нет params, получаем параметры из пресета
        if preset_id and not params:
            logger.info(f"[TOOLS_RUN] Запрос параметров пресета {preset_id} для tool {tool_name}")
            
            # Получаем список tools от агента для поиска пресета
            try:
                command_result = await send_ws_command(
                    device_id=device_id,
                    command="list_tools",
                    params={},
                    actor_role="admin",
                    timeout=10
                )
                
                payload = command_result.get("payload", {})
                if payload.get("status") == "success":
                    tools_data = payload.get("data", {})
                    observations = tools_data.get("observations", {})
                    tools_list = observations.get("tools", [])
                    
                    # Ищем нужный tool
                    tool_found = None
                    for tool in tools_list:
                        if tool.get("tool") == tool_name:
                            tool_found = tool
                            break
                    
                    if tool_found:
                        # Ищем пресет в spec
                        spec = tool_found.get("spec", {})
                        presets = spec.get("presets", [])
                        
                        preset_found = None
                        for preset in presets:
                            if preset.get("id") == preset_id:
                                preset_found = preset
                                break
                        
                        if preset_found:
                            params = preset_found.get("params", {})
                            logger.info(f"[TOOLS_RUN] Найден пресет {preset_id}, параметры: {params}")
                        else:
                            logger.warning(f"[TOOLS_RUN] Пресет {preset_id} не найден для tool {tool_name}")
                            return web.json_response({
                                "status": "error",
                                "error": "preset_not_found",
                                "details": {"preset_id": preset_id}
                            }, status=404)
                    else:
                        logger.warning(f"[TOOLS_RUN] Tool {tool_name} не найден")
                        return web.json_response({
                            "status": "error",
                            "error": "tool_not_found",
                            "details": {"tool_name": tool_name}
                        }, status=404)
            except Exception as e:
                logger.error(f"[TOOLS_RUN] Ошибка получения пресета: {e}")
                return web.json_response({
                    "status": "error",
                    "error": "preset_fetch_error",
                    "details": str(e)
                }, status=500)
        
        # Если нет ни preset_id, ни params, используем пустой dict
        if params is None:
            params = {}
        
        # Делегируем выполнение в handle_admin_run_tool логику
        # Формируем команду для агента
        call_id = str(uuid.uuid4())
        
        # Добавляем события в ticket
        append_ticket_event(ticket_id, {
            "kind": "agent_action",
            "type": "tool_call",
            "title": f"Running {tool_name}" + (f" with preset {preset_id}" if preset_id else ""),
            "tool_name": tool_name,
            "call_id": call_id,
            "preset_id": preset_id if preset_id else None,
            "ts": now_iso()
        })
        
        append_ticket_event(ticket_id, {
            "type": "tool_call_started",
            "call_id": call_id,
            "tool_name": tool_name,
            "params": params,
            "preset_id": preset_id if preset_id else None,
            "ts": now_iso()
        })
        
        # TODO: Отправка уведомления в UI через SSE (будет реализовано позже)
        # broadcast_ticket_event(ticket_id, {
        #     "event": "tool_call_started",
        #     "call_id": call_id,
        #     "tool_name": tool_name
        # })
        
        # Формируем команду для агента
        command_params = {
            "tool_name": tool_name,
            "args": params,
            "ticket_id": ticket_id,
            "call_id": call_id
        }
        
        logger.info(f"[TOOLS_RUN] Отправка команды run_tool агенту {device_id}: tool={tool_name}, preset={preset_id}")
        
        try:
            command_result = await send_ws_command(
                device_id=device_id,
                command="run_tool",
                params=command_params,
                actor_role="admin",
                timeout=60
            )
            
            payload = command_result.get("payload", {})
            status = payload.get("status")
            
            # Извлекаем результат
            tool_result = payload.get("data", {})
            tool_status = "success" if status == "success" else "error"
            
            # Ограничиваем размер результата
            result_str = json.dumps(tool_result, ensure_ascii=False)
            max_result_size = 10 * 1024  # 10KB
            if len(result_str) > max_result_size:
                tool_result = {
                    "truncated": True,
                    "original_size": len(result_str),
                    "preview": result_str[:max_result_size] + "..."
                }
            
            # Формируем summary
            if status == "success":
                summary = f"Tool {tool_name} executed successfully"
            else:
                error_info = payload.get("error", {})
                summary = f"Tool {tool_name} failed: {error_info.get('message', 'unknown error')}"
            
            # Добавляем событие с результатом
            append_ticket_event(ticket_id, {
                "type": "tool_call_result",
                "call_id": call_id,
                "tool_name": tool_name,
                "status": tool_status,
                "summary": summary,
                "result": tool_result,
                "ts": now_iso()
            })
            
            # TODO: Отправка уведомления в UI через SSE (будет реализовано позже)
            # broadcast_ticket_event(ticket_id, {
            #     "event": "tool_call_completed",
            #     "call_id": call_id,
            #     "tool_name": tool_name,
            #     "status": tool_status,
            #     "summary": summary
            # })
            
            logger.success(f"✅ Tool {tool_name} выполнен из тикета {ticket_id}: status={tool_status}")
            
            return web.json_response({
                "status": "ok",
                "ticket_id": ticket_id,
                "call_id": call_id,
                "result": tool_result,
                "tool_status": tool_status
            })
        
        except asyncio.TimeoutError:
            logger.error(f"❌ Таймаут при выполнении tool {tool_name}")
            
            append_ticket_event(ticket_id, {
                "type": "tool_call_result",
                "call_id": call_id,
                "tool_name": tool_name,
                "status": "error",
                "summary": f"Tool {tool_name} execution timeout",
                "error": "timeout",
                "ts": now_iso()
            })
            
            # TODO: Отправка уведомления в UI через SSE (будет реализовано позже)
            # broadcast_ticket_event(ticket_id, {
            #     "event": "tool_call_completed",
            #     "call_id": call_id,
            #     "tool_name": tool_name,
            #     "status": "error",
            #     "summary": "Timeout"
            # })
            
            return web.json_response({
                "status": "error",
                "error": "timeout",
                "ticket_id": ticket_id,
                "call_id": call_id
            }, status=504)
        
        except Exception as e:
            logger.error(f"❌ Исключение при выполнении tool {tool_name}: {e}")
            logger.exception(e)
            
            append_ticket_event(ticket_id, {
                "type": "tool_call_result",
                "call_id": call_id,
                "tool_name": tool_name,
                "status": "error",
                "summary": f"Tool {tool_name} execution error",
                "error": str(e),
                "ts": now_iso()
            })
            
            # TODO: Отправка уведомления в UI через SSE (будет реализовано позже)
            # broadcast_ticket_event(ticket_id, {
            #     "event": "tool_call_completed",
            #     "call_id": call_id,
            #     "tool_name": tool_name,
            #     "status": "error",
            #     "summary": str(e)
            # })
            
            return web.json_response({
                "status": "error",
                "error": str(e),
                "ticket_id": ticket_id,
                "call_id": call_id
            }, status=500)
    
    except json.JSONDecodeError:
        return web.json_response({
            "status": "error",
            "error": "Invalid JSON"
        }, status=400)
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки запроса POST /api/tools/run: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


app = web.Application()
app.add_routes([
    web.get('/ws', websocket_handler),
    web.get('/ws_ui', websocket_ui_handler),
    web.get('/', handle_index),
    web.get('/chat_ws.html', handle_chat_ws),
    web.get('/chat_debug.html', handle_chat_debug),
    web.get('/ticket.html', handle_ticket_page),
    web.get('/ticket/{ticket_id}', handle_ticket_page_by_id),
    web.get('/admin', handle_admin_page),
    web.get('/test', handle_test_simple),
    web.get('/ws_ui_test.html', handle_ws_ui_test),
    web.post('/api/login', handle_login),
    web.get('/api/agents', handle_get_agents),
    web.get('/api/devices', handle_get_devices),
    web.get('/api/list_devices', handle_get_devices),  # Alias for chat_ws.html compatibility
    web.post('/api/send_command', handle_send_command),
    web.post('/api/check_functions', handle_check_functions),
    web.post('/api/upload', handle_upload),
    web.post('/api/install_module_package', handle_install_module_package),
    web.post('/api/list_installed_modules', handle_list_installed_modules),
    web.post('/api/activate_module', handle_activate_module),
    web.post('/api/rollback_module', handle_rollback_module),
    web.post('/api/deactivate_module', handle_deactivate_module),
    web.post('/api/smoke_install_and_run', handle_smoke_install_and_run),
    web.post('/api/run_tool', handle_run_tool),
    web.post('/api/list_tools', handle_list_tools),
    web.post('/api/smoke_run', handle_smoke_run),
    web.get('/api/job_events', handle_get_job_events),
    web.post('/api/start_job', handle_start_job),
    web.get('/api/active_chats', handle_active_chats),  # Новый эндпоинт для списка чатов
    web.post('/api/chat_start', handle_chat_start),
    web.post('/api/chat_raise', handle_chat_raise),
    web.post('/api/chat_send', handle_chat_send),
    web.get('/api/chat_events', handle_chat_events),
    web.get('/api/protocol', handle_protocol),
    # Ticket API endpoints
    web.post('/api/tickets/create', handle_tickets_create),
    web.get('/api/tickets/{ticket_id}', handle_ticket_get),
    web.get('/api/tickets', handle_tickets_list),
    web.post('/api/tickets/{ticket_id}/message', handle_ticket_send_message),
    web.post('/api/tickets/{ticket_id}/close', handle_ticket_close),
    # Tools API endpoints
    web.get('/api/tools', handle_get_tools),
    web.post('/api/tools/run', handle_tools_run),
    web.post('/api/admin/run_tool', handle_admin_run_tool),
])

# Добавляем статическую раздачу файлов из папки uploads
app.router.add_static('/uploads/', path=UPLOAD_DIR, name='uploads')

if __name__ == '__main__':
    # Настраиваем логирование
    logger.remove()  # Удаляем стандартный обработчик
    logger.add(
        sys.stderr,
        level="DEBUG",  # Изменено на DEBUG для детального логирования
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    # Создаём папку для загрузок, если её нет
    logger.info(f"📁 Папка загрузок: {UPLOAD_DIR.absolute()}")
    
    logger.info("=" * 70)
    logger.info("🚀 PC Agent WebSocket Server")
    logger.info("📡 WebSocket: ws://localhost:8666/ws")
    logger.info("🌐 Web Interface: http://localhost:8666/")
    logger.info("🔧 API: http://localhost:8666/api/")
    logger.info("📤 File Upload: http://localhost:8666/api/upload")
    logger.info("📂 Uploaded Files: http://localhost:8666/uploads/")
    logger.info("📚 Docs: GET /api/protocol")
    logger.info("📦 Install ZIP: POST /api/install_module_package multipart/form-data")
    logger.info("📋 List Modules: POST /api/list_installed_modules")
    logger.info("✅ Activate Module: POST /api/activate_module")
    logger.info("⏪ Rollback Module: POST /api/rollback_module")
    logger.info("❌ Deactivate Module: POST /api/deactivate_module")
    logger.info("🧪 Smoke Test: POST /api/smoke_install_and_run")
    logger.info("=" * 70)
    
    web.run_app(app, host='0.0.0.0', port=8666)