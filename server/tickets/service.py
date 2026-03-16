"""
Сервис управления тикетами.

После миграции Protocol V3 тикеты/события/сообщения хранятся в PostgreSQL.
StateManager не содержит get_ticket, get_ticket_messages, get_ticket_events, list_tickets.
Для чтения из БД используйте async-методы: get_ticket_async, get_messages_async, get_events_async, list_tickets_async.
"""

import json
import uuid
import asyncio
from typing import Dict, List, Optional, Tuple
from models import Ticket, Session
from utils import new_ticket_id, new_session_id, new_message_id, now_iso
from loguru import logger
from .events import TicketEventsManager

try:
    from app.db import get_session
    from app.repos import TicketEventsRepo
    _REPO_AVAILABLE = True
except ImportError:
    _REPO_AVAILABLE = False


def _safe_async_call(coro):
    """
    Безопасно вызывает async функцию из sync контекста.
    
    Если event loop запущен - создает task (fire-and-forget).
    Если нет - пытается запустить синхронно.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Event loop уже запущен - создаем task (fire-and-forget)
            asyncio.create_task(coro)
        else:
            # Event loop не запущен - запускаем синхронно
            loop.run_until_complete(coro)
    except RuntimeError:
        # Нет event loop - создаем новый (может быть проблематично)
        try:
            asyncio.run(coro)
        except RuntimeError:
            # Если и это не работает - просто логируем ошибку
            logger.warning(f"Failed to execute async call: {coro}", exc_info=True)


class TicketService:
    """Сервис для работы с тикетами."""
    
    def __init__(self, state_manager):
        self.state = state_manager
        self.events_manager = TicketEventsManager(state_manager)
    
    def create_ticket(
        self,
        device_id: str,
        user_display_name: str,
        description: str,
        title: str = "",
        tags: List[str] = None
    ) -> Tuple[Ticket, Session, str]:
        """
        Создаёт новый тикет и сессию.
        
        Args:
            device_id: ID устройства
            user_display_name: Имя пользователя
            description: Описание проблемы
            title: Заголовок тикета (опционально)
            tags: Теги тикета (опционально)
        
        Returns:
            Tuple[Ticket, Session, initial_message_id]
        """
        if not title:
            title = "Untitled"
        
        if tags is None:
            tags = []
        
        # Генерация идентификаторов
        ticket_id = new_ticket_id()
        session_id = new_session_id()
        job_id = str(uuid.uuid4())  # Генерируем job_id для событий
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
        
        # Создание сессии с job_id для поддержки событий в PostgreSQL
        session = Session(
            session_id=session_id,
            ticket_id=ticket_id,
            device_id=device_id,
            job_id=job_id,  # Теперь job_id генерируется автоматически
            status="open",
            created_at=timestamp,
            updated_at=timestamp,
            last_activity_at=timestamp
        )
        
        # Сохранение в state
        self.state.create_ticket(ticket)
        self.state.create_session(session)
        
        # Создание событий (async, но вызываем в фоне для синхронного метода)
        _safe_async_call(
            self.events_manager.create_ticket_created_event(ticket_id, session_id, device_id)
        )
        _safe_async_call(
            self.events_manager.create_session_opened_event(ticket_id, session_id, device_id)
        )
        
        # Создание начального сообщения из description
        initial_message_id = new_message_id()
        initial_message = {
            "ticket_id": ticket_id,
            "message_id": initial_message_id,
            "from_role": "user",
            "text": description,
            "ts": timestamp,
            "direction": "to_agent",
            "is_initial": True
        }
        self.state.append_ticket_message(ticket_id, initial_message)
        
        # Событие создания начального сообщения (async, но вызываем в фоне)
        _safe_async_call(
            self.events_manager.create_initial_message_created_event(ticket_id, initial_message_id)
        )
        
        logger.info(f"✅ Создан тикет {ticket_id} для устройства {device_id}")
        logger.info(f"   Пользователь: {user_display_name}")
        logger.info(f"   Сессия: {session_id}")
        logger.info(f"   Job ID: {job_id} (для событий в PostgreSQL)")
        
        return ticket, session, initial_message_id
    
    def create_system_ticket(
        self,
        device_id: str,
        tool_name: str,
        params: dict
    ) -> Tuple[str, str]:
        """
        Создаёт системный тикет для административных действий.
        
        Args:
            device_id: ID устройства
            tool_name: Имя tool
            params: Параметры tool
        
        Returns:
            Tuple[ticket_id, session_id]
        """
        # Формирование title и description
        title = f"Admin action: {tool_name}"
        params_str = json.dumps(params, ensure_ascii=False, indent=2)
        if len(params_str) > 500:
            params_str = params_str[:500] + "..."
        description = f"Run tool {tool_name} with params:\n{params_str}"
        
        ticket, session, initial_message_id = self.create_ticket(
            device_id=device_id,
            user_display_name="admin",
            description=description,
            title=title,
            tags=["admin", "tool"]
        )
        
        logger.info(f"✅ Создан системный тикет {ticket.ticket_id} для устройства {device_id}")
        logger.info(f"   Tool: {tool_name}")
        
        return ticket.ticket_id, session.session_id
    
    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Возвращает тикет по ID. После V3 в state нет тикетов — используйте get_ticket_async()."""
        if hasattr(self.state, "get_ticket"):
            return self.state.get_ticket(ticket_id)
        return None
    
    async def get_ticket_async(self, ticket_id: str) -> Optional[Ticket]:
        """Возвращает тикет по ID из БД (V3)."""
        if not _REPO_AVAILABLE:
            return None
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            return await repo.get_ticket(ticket_id)
    
    def get_session_by_ticket(self, ticket_id: str) -> Optional[Session]:
        """Возвращает сессию по ticket_id (runtime)."""
        return self.state.get_session_by_ticket(ticket_id)
    
    def get_messages(self, ticket_id: str) -> List[dict]:
        """Возвращает сообщения тикета. После V3 в state нет — используйте get_messages_async()."""
        if hasattr(self.state, "get_ticket_messages"):
            return self.state.get_ticket_messages(ticket_id)
        return []
    
    async def get_messages_async(self, ticket_id: str) -> List[dict]:
        """Возвращает сообщения тикета из БД (события chat_message)."""
        if not _REPO_AVAILABLE:
            return []
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            events = await repo.get_events(ticket_id, event_types=["chat_message"], limit=1000)
            return [
                {
                    "ticket_id": ticket_id,
                    "message_id": (e.payload or {}).get("message_id"),
                    "from_role": (e.payload or {}).get("from", "agent"),
                    "text": (e.payload or {}).get("text", ""),
                    "ts": e.created_at.isoformat() if e.created_at else None,
                    "direction": (e.payload or {}).get("direction", "from_agent"),
                }
                for e in events
                if e.payload
            ]
    
    def get_events(self, ticket_id: str) -> List[dict]:
        """Возвращает события тикета. После V3 в state нет — используйте get_events_async()."""
        if hasattr(self.state, "get_ticket_events"):
            return self.state.get_ticket_events(ticket_id)
        return []
    
    async def get_events_async(self, ticket_id: str, limit: int = 1000) -> List[dict]:
        """Возвращает события тикета из БД."""
        if not _REPO_AVAILABLE:
            return []
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            events = await repo.get_events(ticket_id, limit=limit)
            return [
                {"event_type": e.event_type, "payload": e.payload or {}, "created_at": e.created_at.isoformat() if e.created_at else None}
                for e in events
            ]
    
    def list_tickets(self) -> List[Ticket]:
        """Возвращает список тикетов. После V3 в state нет — используйте list_tickets_async()."""
        if hasattr(self.state, "list_tickets"):
            return self.state.list_tickets()
        return []
    
    async def list_tickets_async(self, limit: int = 100, offset: int = 0) -> List[Ticket]:
        """Возвращает список тикетов из БД."""
        if not _REPO_AVAILABLE:
            return []
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            return await repo.list_tickets(limit=limit, offset=offset)
    
    def send_message(
        self,
        ticket_id: str,
        message_id: str,
        from_role: str,
        text: str
    ) -> Dict:
        """
        Отправляет сообщение в тикет.
        
        Args:
            ticket_id: ID тикета
            message_id: ID сообщения
            from_role: Роль отправителя (user, admin, support)
            text: Текст сообщения
        
        Returns:
            Словарь с результатом операции
        """
        # Проверка на дубликат
        if self.state.is_duplicate_message(ticket_id, message_id):
            logger.info(f"📬 Дубликат сообщения: ticket_id={ticket_id} message_id={message_id}")
            return {
                "queued": True,
                "dedup": True
            }
        
        timestamp = now_iso()
        
        # Сохраняем сообщение
        message_record = {
            "ticket_id": ticket_id,
            "message_id": message_id,
            "from_role": from_role,
            "text": text,
            "ts": timestamp,
            "direction": "to_agent"
        }
        self.state.append_ticket_message(ticket_id, message_record)
        
        # Добавляем событие (async, но вызываем в фоне)
        _safe_async_call(
            self.events_manager.append_event(
                ticket_id,
                {
                    "event": "message_queued",
                    "ticket_id": ticket_id,
                    "message_id": message_id,
                    "from_role": from_role,
                    "ts": timestamp
                },
                agent_seq=None  # server-originated
            )
        )
        
        logger.info(f"📬 Сообщение сохранено: ticket_id={ticket_id} message_id={message_id}")
        
        return {
            "queued": True,
            "dedup": False
        }
    
    def close_ticket(
        self,
        ticket_id: str,
        closed_by_role: str,
        reason: str = ""
    ) -> Dict:
        """
        Закрывает тикет. После V3 тикеты в БД — используйте close_ticket_async().
        Если state не содержит тикеты, возвращает {"error": "not_found"}.
        """
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return {"error": "not_found"}
        if ticket.status in ("closed", "Closed"):
            logger.info(f"ℹ️  Тикет {ticket_id} уже закрыт")
            return {"already_closed": True}
        if not reason:
            reason = "closed"
        timestamp = now_iso()
        if hasattr(self.state, "update_ticket"):
            self.state.update_ticket(ticket_id, status="Closed", updated_at=timestamp)
        session = self.state.get_session_by_ticket(ticket_id)
        if session and hasattr(self.state, "update_session"):
            self.state.update_session(session.session_id, status="Closed", updated_at=timestamp)
        _safe_async_call(
            self.events_manager.create_ticket_closed_event(ticket_id, closed_by_role, reason)
        )
        logger.info(f"✅ Тикет {ticket_id} закрыт")
        return {"closed": True, "already_closed": False}

    async def close_ticket_async(
        self,
        ticket_id: str,
        closed_by_role: str,
        reason: str = ""
    ) -> Dict:
        """Закрывает тикет в БД (V3)."""
        if not _REPO_AVAILABLE:
            return {"error": "db_unavailable"}
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            ticket = await repo.get_ticket(ticket_id)
            if not ticket:
                return {"error": "not_found"}
            if str(ticket.status) in ("closed", "Closed"):
                return {"already_closed": True}
            if not reason:
                reason = "closed"
            await repo.update_ticket(ticket_id, status="Closed")
            await repo.add_event(
                ticket_id,
                getattr(ticket, "device_id", "") or "",
                None,
                "ticket_closed",
                {"closed_by": closed_by_role, "reason": reason, "ts": now_iso()},
                trace_id=str(uuid.uuid4()),
            )
            await session.commit()
        session_obj = self.state.get_session_by_ticket(ticket_id)
        if session_obj and hasattr(self.state, "update_session"):
            self.state.update_session(session_obj.session_id, status="Closed", updated_at=now_iso())
        logger.info(f"✅ Тикет {ticket_id} закрыт (БД)")
        return {"closed": True, "already_closed": False}
    
    def is_agent_online_for_ticket(self, ticket_id: str) -> bool:
        """Проверяет, онлайн ли агент для данного тикета. После V3 используйте get_ticket_async + is_agent_online."""
        ticket = self.get_ticket(ticket_id)
        if not ticket or not getattr(ticket, "device_id", None):
            return False
        return self.state.is_agent_online(ticket.device_id)
    
    def update_ticket_updated_at(self, ticket_id: str) -> None:
        """Обновляет updated_at для тикета. После V3 используйте репозиторий."""
        if hasattr(self.state, "update_ticket"):
            self.state.update_ticket(ticket_id, updated_at=now_iso())
    
    def create_system_ticket_for_admin_action(self, device_id: str, tool_name: str, params: dict) -> Tuple[str, str]:
        """
        Создаёт системный тикет для административных действий (например, запуск tool).
        
        Args:
            device_id: ID устройства
            tool_name: Имя вызываемого tool
            params: Параметры tool
        
        Returns:
            tuple[ticket_id, session_id]: ID созданного тикета и сессии
        """
        import uuid
        
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
        self.state.create_ticket(ticket)
        self.state.create_session(session)
        
        # Запись событий в лог
        self.state.append_ticket_event(ticket_id, {
            "type": "ticket_created",
            "ticket_id": ticket_id,
            "session_id": session_id,
            "device_id": device_id,
            "ts": timestamp
        })
        
        self.state.append_ticket_event(ticket_id, {
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
        self.state.append_ticket_message(ticket_id, initial_message_record)
        
        self.state.append_ticket_event(ticket_id, {
            "type": "initial_message_created",
            "ticket_id": ticket_id,
            "message_id": initial_message_id,
            "ts": timestamp
        })
        
        logger.info(f"✅ Создан системный тикет {ticket_id} для устройства {device_id}")
        logger.info(f"   Tool: {tool_name}")
        logger.info(f"   Сессия: {session_id}")
        
        return ticket_id, session_id

