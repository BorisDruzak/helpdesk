"""
Централизованное управление состоянием сервера.

ВАЖНО: После миграции Protocol V3 (Phase F) StateManager содержит ТОЛЬКО runtime/эпемерные данные.
Все tickets, events, messages теперь хранятся ТОЛЬКО в PostgreSQL (Source of Truth).

Runtime данные (эпемерные, существуют только в памяти):
- sessions_by_ticket / sessions_by_id - активные сессии агентов
- connected_agents - подключенные агенты (WebSocket)
- ticket_seen_message_ids - cache для дедупликации сообщений
- chat_sessions - активные чат-сессии
- ui_connections - UI WebSocket подключения
- job_events - события job
- tools_cache - кеш инструментов
"""

from datetime import datetime, timezone
import time
from typing import Dict, Set, List, Optional, Any
from models import Session
from config import USERS
from loguru import logger


class StateManager:
    """
    Централизованный менеджер runtime состояния сервера.
    
    После миграции Protocol V3:
    - Source of Truth для tickets/events/messages: PostgreSQL
    - StateManager: ТОЛЬКО runtime/эпемерные данные
    """
    
    def __init__(self):
        # ============================================================================
        # Users (Config fallback only)
        # ============================================================================
        self.users: Dict[str, str] = USERS.copy()
        
        # ============================================================================
        # Agents (Runtime)
        # ============================================================================
        # Реестр подключённых агентов (device_id -> {ws, metadata})
        # RUNTIME: Эпемерные данные, очищаются при отключении агента
        self.connected_agents: Dict[str, dict] = {}
        # Реестр административных клиентов
        self.admin_clients: Set[Any] = set()
        
        # ============================================================================
        # Tickets Runtime Data (НЕ Source of Truth!)
        # ============================================================================
        # ВАЖНО: tickets/events/messages теперь ТОЛЬКО в PostgreSQL!
        # StateManager содержит только runtime данные для активных сессий.
        
        # Хранилище активных сессий по тикету (ticket_id -> Session)
        # RUNTIME: Создается при открытии тикета, удаляется при закрытии
        self.sessions_by_ticket: Dict[str, Session] = {}
        
        # Хранилище активных сессий по ID (session_id -> Session)
        # RUNTIME: Создается при открытии тикета, удаляется при закрытии
        self.sessions_by_id: Dict[str, Session] = {}
        
        # Хранилище для дедупликации сообщений по тикету (ticket_id -> set[message_id])
        # RUNTIME CACHE: Микрооптимизация для предотвращения дублей
        # Очищается при закрытии тикета или периодическим housekeeping
        self.ticket_seen_message_ids: Dict[str, Set[str]] = {}
        
        # ============================================================================
        # Chat Sessions (Runtime)
        # ============================================================================
        # Хранилище chat сессий (chat_job_id -> dict)
        # RUNTIME: Активные чат-сессии
        self.chat_sessions: Dict[str, dict] = {}
        
        # Хранилище UI WebSocket подключений (connection_id -> dict)
        # RUNTIME: Активные UI подключения
        self.ui_connections: Dict[str, dict] = {}
        
        # ============================================================================
        # Jobs (Runtime)
        # ============================================================================
        # Хранилище job событий (job_id -> list[event])
        # RUNTIME: События для текущих job
        self.job_events: Dict[str, list] = {}
        
        # ============================================================================
        # Tools Cache (Runtime)
        # ============================================================================
        # Кеш инструментов с TTL
        # RUNTIME CACHE: Временный кеш для оптимизации
        self.tools_cache: dict = {
            "ts": 0.0,
            "ttl_sec": 20.0,
            "data": None
        }
        
        # ============================================================================
        # UI Subscription Registry (Runtime)
        # ============================================================================
        # Subscription registry for UI WebSocket connections
        try:
            from websocket.subscription_registry import SubscriptionRegistry
            self.subscription_registry = SubscriptionRegistry()
        except ImportError:
            # Fallback if subscription_registry not available
            self.subscription_registry = None
            logger.warning("[StateManager] SubscriptionRegistry not available")
        
        # ============================================================================
        # UI Publisher (Runtime)
        # ============================================================================
        # UI Publisher for pushing operation updates to subscribers
        try:
            from websocket.ui_publisher import UiPublisherImpl
            self.ui_publisher = UiPublisherImpl(self)
        except ImportError:
            # Fallback if ui_publisher not available
            self.ui_publisher = None
            logger.warning("[StateManager] UiPublisher not available")

        # ============================================================================
        # Ticket viewer presence (Runtime)
        # ============================================================================
        # ticket_id -> {"requester": {presence_key: entry}, "support": {presence_key: entry}}
        self.ticket_presence: Dict[str, Dict[str, Dict[str, dict]]] = {}
        self.ticket_presence_ttl_sec: float = 20.0


    # ============================================================================
    # Agent Management Methods (Runtime)
    # ============================================================================
    
    def register_agent(self, device_id: str, ws: Any, metadata: dict) -> None:
        """Регистрирует подключённого агента (RUNTIME)."""
        self.connected_agents[device_id] = {
            "ws": ws,
            "metadata": metadata,
            "connected_at": metadata.get("connected_at")
        }
    
    def unregister_agent(self, device_id: str) -> None:
        """Удаляет агента из реестра (RUNTIME)."""
        if device_id in self.connected_agents:
            del self.connected_agents[device_id]
    
    def get_agent(self, device_id: str) -> Optional[dict]:
        """Возвращает информацию об агенте (RUNTIME)."""
        return self.connected_agents.get(device_id)
    
    def get_agent_ws(self, device_id: str) -> Optional[Any]:
        """Возвращает WebSocket подключение агента (RUNTIME)."""
        agent = self.connected_agents.get(device_id)
        return agent["ws"] if agent else None
    
    def list_agents(self) -> List[dict]:
        """Возвращает список всех подключённых агентов (RUNTIME)."""
        agents = []
        for device_id, info in self.connected_agents.items():
            metadata = info["metadata"]
            agents.append({
                "device_id": device_id,
                "user_display_name": metadata.get("user_display_name", "Unknown"),
                "os_type": metadata.get("os_type", "Unknown"),
                "os_version": metadata.get("os_version", "Unknown"),
                "connected_at": info.get("connected_at")
            })
        return agents
    
    def is_agent_online(self, device_id: str) -> bool:
        """
        Проверяет, подключён ли агент (RUNTIME).
        
        Выполняет более точную проверку:
        1. Проверяет наличие в connected_agents
        2. Проверяет, что WebSocket соединение открыто
        3. Проверяет статус в метаданных
        
        Args:
            device_id: ID устройства
            
        Returns:
            True если агент действительно подключен и WebSocket открыт
        """
        if device_id not in self.connected_agents:
            # Логируем без полного списка connected_agents, чтобы не спамить при списке тикетов
            logger.debug(f"[is_agent_online] Device {device_id} not in connected_agents")
            return False
        
        agent_info = self.connected_agents.get(device_id)
        if not agent_info:
            logger.debug(f"[is_agent_online] Device {device_id} agent_info is empty")
            return False
        
        # Проверяем WebSocket соединение
        ws = agent_info.get("ws")
        if ws is None:
            logger.debug(f"[is_agent_online] Device {device_id} ws is None")
            return False
        
        # Проверяем, что WebSocket не закрыт
        # aiohttp WebSocket имеет атрибут closed (свойство)
        try:
            if hasattr(ws, 'closed'):
                if ws.closed:
                    # WebSocket закрыт - удаляем агента из списка
                    logger.warning(
                        f"[is_agent_online] Device {device_id} WebSocket is closed, "
                        f"removing from connected_agents (caller will see agent as offline)"
                    )
                    self.unregister_agent(device_id)
                    return False
        except Exception as e:
            # Если проверка closed вызывает исключение, считаем соединение закрытым
            logger.warning(f"[is_agent_online] Error checking WebSocket closed status for {device_id}: {e}")
            return False
        
        # Проверяем статус в метаданных
        metadata = agent_info.get("metadata", {})
        status = metadata.get("status", "unknown")
        if status != "online":
            logger.debug(
                f"[is_agent_online] Device {device_id} metadata.status={status!r} (expected 'online')"
            )
            return False
        
        return True
    
    # ============================================================================
    # Session Management Methods (Runtime)
    # ============================================================================
    # ПРИМЕЧАНИЕ: Сессии - это runtime данные, они НЕ персистятся в БД.
    # Сессия существует только пока агент подключен и работает с тикетом.
    
    def create_session(self, session: Session) -> None:
        """Создаёт новую runtime сессию."""
        self.sessions_by_ticket[session.ticket_id] = session
        self.sessions_by_id[session.session_id] = session
    
    def get_session_by_ticket(self, ticket_id: str) -> Optional[Session]:
        """Возвращает runtime сессию по ticket_id."""
        return self.sessions_by_ticket.get(ticket_id)
    
    def get_session_by_id(self, session_id: str) -> Optional[Session]:
        """Возвращает runtime сессию по session_id."""
        return self.sessions_by_id.get(session_id)
    
    def update_session(self, session_id: str, **kwargs) -> None:
        """Обновляет поля runtime сессии."""
        if session_id in self.sessions_by_id:
            session = self.sessions_by_id[session_id]
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
    
    def cleanup_session(self, ticket_id: str) -> None:
        """
        Очищает runtime сессию при закрытии тикета или отключении агента.
        
        Вызывается из:
        - handle_ticket_close() - при закрытии тикета
        - agent disconnect handler - при отключении агента
        - housekeeping_cleanup_task() - периодическая очистка неактивных сессий
        """
        if ticket_id in self.sessions_by_ticket:
            session = self.sessions_by_ticket[ticket_id]
            # Удаляем из обоих индексов
            if session.session_id in self.sessions_by_id:
                del self.sessions_by_id[session.session_id]
            del self.sessions_by_ticket[ticket_id]
    
    # ============================================================================
    # Message Deduplication Cache (Runtime Optimization)
    # ============================================================================
    
    def is_duplicate_message(self, ticket_id: str, message_id: str) -> bool:
        """
        Проверяет, было ли сообщение уже обработано (RUNTIME CACHE).
        
        Это микрооптимизация для предотвращения дублей при повторных ACK.
        Не влияет на корректность работы, т.к. БД имеет UNIQUE constraint.
        """
        if ticket_id not in self.ticket_seen_message_ids:
            self.ticket_seen_message_ids[ticket_id] = set()
        
        if message_id in self.ticket_seen_message_ids[ticket_id]:
            return True
        
        self.ticket_seen_message_ids[ticket_id].add(message_id)
        return False
    
    def cleanup_message_cache(self, ticket_id: str) -> None:
        """
        Очищает cache дедупликации сообщений для тикета.
        
        Вызывается при закрытии тикета для освобождения памяти.
        """
        if ticket_id in self.ticket_seen_message_ids:
            del self.ticket_seen_message_ids[ticket_id]
    
    # ============================================================================
    # Chat Sessions Methods (Runtime)
    # ============================================================================
    
    def create_chat_session(self, chat_job_id: str, session_data: dict) -> None:
        """Создаёт новую runtime чат-сессию."""
        self.chat_sessions[chat_job_id] = session_data
    
    def get_chat_session(self, chat_job_id: str) -> Optional[dict]:
        """Возвращает runtime чат-сессию."""
        return self.chat_sessions.get(chat_job_id)
    
    def update_chat_session(self, chat_job_id: str, **kwargs) -> None:
        """Обновляет runtime чат-сессию."""
        if chat_job_id in self.chat_sessions:
            self.chat_sessions[chat_job_id].update(kwargs)
    
    def list_chat_sessions(self) -> List[dict]:
        """Возвращает список всех runtime чат-сессий."""
        return list(self.chat_sessions.values())
    
    def delete_chat_session(self, chat_job_id: str) -> None:
        """Удаляет runtime чат-сессию."""
        if chat_job_id in self.chat_sessions:
            del self.chat_sessions[chat_job_id]
    
    # ============================================================================
    # UI Connections Methods (Runtime)
    # ============================================================================
    
    def register_ui_connection(self, connection_id: str, connection_data: dict) -> None:
        """Регистрирует UI WebSocket подключение (RUNTIME)."""
        self.ui_connections[connection_id] = connection_data
    
    def unregister_ui_connection(self, connection_id: str) -> None:
        """Удаляет UI WebSocket подключение (RUNTIME)."""
        if connection_id in self.ui_connections:
            del self.ui_connections[connection_id]
    
    def get_ui_connection(self, connection_id: str) -> Optional[dict]:
        """Возвращает UI подключение (RUNTIME)."""
        return self.ui_connections.get(connection_id)
    
    def list_ui_connections(self) -> List[dict]:
        """Возвращает список всех UI подключений (RUNTIME)."""
        return list(self.ui_connections.values())

    # ============================================================================
    # Ticket Presence Methods (Runtime)
    # ============================================================================

    @staticmethod
    def _ticket_presence_scope(actor_role: str) -> Optional[str]:
        if actor_role in {"user", "agent"}:
            return "requester"
        if actor_role in {"support", "admin"}:
            return "support"
        return None

    def _prune_ticket_presence(self, ticket_id: str, now_ts: Optional[float] = None) -> None:
        bucket = self.ticket_presence.get(ticket_id)
        if not bucket:
            return
        current_ts = float(now_ts if now_ts is not None else time.time())
        stale_before = current_ts - float(self.ticket_presence_ttl_sec)
        for scope in ("requester", "support"):
            scope_entries = bucket.get(scope) or {}
            stale_keys = [
                presence_key
                for presence_key, entry in scope_entries.items()
                if float((entry or {}).get("last_seen_ts") or 0.0) < stale_before
            ]
            for presence_key in stale_keys:
                scope_entries.pop(presence_key, None)
            if not scope_entries:
                bucket.pop(scope, None)
        if not bucket:
            self.ticket_presence.pop(ticket_id, None)

    def touch_ticket_presence(
        self,
        ticket_id: str,
        actor_id: str,
        actor_role: str,
        *,
        presence_key: Optional[str] = None,
        now_ts: Optional[float] = None,
    ) -> None:
        normalized_ticket_id = str(ticket_id or "").strip()
        normalized_actor_id = str(actor_id or "").strip()
        scope = self._ticket_presence_scope(str(actor_role or "").strip().lower())
        if not normalized_ticket_id or not normalized_actor_id or scope is None:
            return
        key = str(presence_key or f"{scope}:{normalized_actor_id}").strip()
        if not key:
            return
        current_ts = float(now_ts if now_ts is not None else time.time())
        bucket = self.ticket_presence.setdefault(normalized_ticket_id, {})
        scope_entries = bucket.setdefault(scope, {})
        scope_entries[key] = {
            "actor_id": normalized_actor_id,
            "actor_role": str(actor_role or "").strip().lower(),
            "last_seen_ts": current_ts,
        }
        self._prune_ticket_presence(normalized_ticket_id, now_ts=current_ts)

    def remove_ticket_presence(self, ticket_id: str, presence_key: str) -> None:
        normalized_ticket_id = str(ticket_id or "").strip()
        key = str(presence_key or "").strip()
        if not normalized_ticket_id or not key:
            return
        bucket = self.ticket_presence.get(normalized_ticket_id)
        if not bucket:
            return
        for scope in ("requester", "support"):
            scope_entries = bucket.get(scope) or {}
            scope_entries.pop(key, None)
            if not scope_entries and scope in bucket:
                bucket.pop(scope, None)
        if not bucket:
            self.ticket_presence.pop(normalized_ticket_id, None)

    def clear_ticket_presence_key(self, presence_key: str) -> None:
        key = str(presence_key or "").strip()
        if not key:
            return
        for ticket_id in list(self.ticket_presence.keys()):
            self.remove_ticket_presence(ticket_id, key)

    def get_ticket_presence(self, ticket_id: str) -> Dict[str, Any]:
        normalized_ticket_id = str(ticket_id or "").strip()
        if not normalized_ticket_id:
            return {
                "requester_online": False,
                "requester_last_seen_at": None,
                "requester_actor_ids": [],
                "support_online": False,
                "support_last_seen_at": None,
                "support_actor_ids": [],
            }
        self._prune_ticket_presence(normalized_ticket_id)
        bucket = self.ticket_presence.get(normalized_ticket_id, {})

        def summarize(scope: str) -> Dict[str, Any]:
            scope_entries = bucket.get(scope) or {}
            if not scope_entries:
                return {
                    "online": False,
                    "last_seen_at": None,
                    "actor_ids": [],
                }
            newest_ts = max(float((entry or {}).get("last_seen_ts") or 0.0) for entry in scope_entries.values())
            actor_ids = sorted(
                {
                    str((entry or {}).get("actor_id") or "").strip()
                    for entry in scope_entries.values()
                    if str((entry or {}).get("actor_id") or "").strip()
                }
            )
            return {
                "online": True,
                "last_seen_at": datetime.fromtimestamp(newest_ts, tz=timezone.utc).isoformat() if newest_ts > 0 else None,
                "actor_ids": actor_ids,
            }

        requester = summarize("requester")
        support = summarize("support")
        return {
            "requester_online": requester["online"],
            "requester_last_seen_at": requester["last_seen_at"],
            "requester_actor_ids": requester["actor_ids"],
            "support_online": support["online"],
            "support_last_seen_at": support["last_seen_at"],
            "support_actor_ids": support["actor_ids"],
        }

    # ============================================================================
    # Job Events Methods (Runtime)
    # ============================================================================
    
    def append_job_event(self, job_id: str, event: dict) -> None:
        """Добавляет событие в runtime журнал job."""
        if job_id not in self.job_events:
            self.job_events[job_id] = []
        
        self.job_events[job_id].append(event)
    
    def get_job_events(self, job_id: str) -> List[dict]:
        """Возвращает все runtime события job."""
        return self.job_events.get(job_id, [])
    
    def clear_job_events(self, job_id: str) -> None:
        """Очищает runtime события job."""
        if job_id in self.job_events:
            del self.job_events[job_id]
    
    # ============================================================================
    # Tools Cache Methods (Runtime Cache)
    # ============================================================================
    
    def get_tools_cache(self) -> Optional[Any]:
        """Возвращает закешированные tools (RUNTIME CACHE)."""
        import time
        current_time = time.time()
        
        if self.tools_cache["data"] is None:
            return None
        
        # Проверяем актуальность кеша
        if current_time - self.tools_cache["ts"] > self.tools_cache["ttl_sec"]:
            return None
        
        return self.tools_cache["data"]
    
    def set_tools_cache(self, data: Any, ttl_sec: Optional[float] = None) -> None:
        """Сохраняет tools в runtime cache."""
        import time
        self.tools_cache["data"] = data
        self.tools_cache["ts"] = time.time()
        if ttl_sec is not None:
            self.tools_cache["ttl_sec"] = ttl_sec
    
    def clear_tools_cache(self) -> None:
        """Очищает runtime cache tools."""
        self.tools_cache["data"] = None
        self.tools_cache["ts"] = 0.0
