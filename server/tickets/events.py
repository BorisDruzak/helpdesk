"""
Управление событиями тикетов через PostgreSQL.

TicketEventsManager теперь является DB-backed сервисом:
- Все записи событий идут через TicketEventsRepo (PostgreSQL)
- Source of Truth: PostgreSQL, не StateManager
- Server-originated события имеют agent_seq=None
- Дедупликация через event_id для server-originated событий
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
import uuid
from utils import now_iso
from loguru import logger

try:
    from app.db import get_session
    from app.repos.ticket_events_repo import TicketEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database modules not available, TicketEventsManager will not work")


class TicketEventsManager:
    """
    Менеджер для работы с событиями тикетов через PostgreSQL.
    
    КРИТИЧНО: Больше не зависит от StateManager для SoT.
    StateManager используется только для опциональных runtime-хуков.
    """
    
    def __init__(self, state_manager):
        """
        Инициализация менеджера событий.
        
        Args:
            state_manager: StateManager (используется только для runtime данных, не для SoT)
        """
        self.state = state_manager  # Опционально для runtime, не для SoT
    
    async def append_event(
        self,
        ticket_id: str,
        event: Dict[str, Any],
        *,
        device_id: Optional[str] = None,
        agent_seq: Optional[int] = None,  # None для server-originated событий
        trace_id: Optional[str] = None,
        event_id: Optional[str] = None,
        operation_id: Optional[str] = None,  # КРИТИЧНО: для связи с операцией
    ) -> None:
        """
        Добавляет событие в журнал тикета через PostgreSQL.
        
        КРИТИЧНО:
        - agent_seq=None для server-originated событий (support/user messages, tool calls)
        - agent_seq=int для agent-originated событий (от агента)
        - Для server-originated событий генерируется event_id если не передан
        
        Args:
            ticket_id: ID тикета
            event: Словарь с данными события
            device_id: Optional - device_id (если не указан, будет получен из тикета)
            agent_seq: Optional - agent_seq для agent-originated событий (None для server-originated)
            trace_id: Optional - trace ID для корреляции
            event_id: Optional - event_id для дедупликации server-originated событий
                        (генерируется автоматически если agent_seq=None и event_id=None)
        
        Raises:
            ValueError: Если тикет не найден или device_id не совпадает
            Exception: Если операция БД не удалась
        """
        if not DB_AVAILABLE:
            logger.error("Database not available, cannot append event")
            return
        
        # Добавляем ts, если нет
        if 'ts' not in event:
            event['ts'] = now_iso()
        
        try:
            async with get_session() as session:
                repo = TicketEventsRepo(session)
                
                # 1) Получаем тикет из БД для проверки существования и device_id
                ticket = await repo.get_ticket(ticket_id)
                if not ticket:
                    logger.error(f"Ticket {ticket_id} not found, cannot append event")
                    raise ValueError(f"Ticket not found: {ticket_id}")
                
                # 2) Определяем device_id
                bound_device_id = device_id or ticket.device_id
                
                # 3) Валидация device binding (если device_id передан явно)
                if device_id and device_id != ticket.device_id:
                    logger.error(
                        f"Device mismatch for ticket {ticket_id}: "
                        f"provided={device_id} bound={ticket.device_id}"
                    )
                    raise ValueError(
                        f"Device mismatch for ticket {ticket_id}: "
                        f"{device_id} != {ticket.device_id}"
                    )
                
                # 4) Определяем event_type
                event_type = event.get("event") or event.get("event_type") or event.get("type") or "unknown"
                
                # 5) Для ticket-bound событий trace_id канонизируется через observer root trace тикета
                resolved_trace_id = await repo.resolve_ticket_trace_id(
                    ticket_id,
                    trace_id=trace_id or event.get("trace_id"),
                    operation_id=operation_id or event.get("operation_id"),
                    agent_seq=agent_seq,
                )
                if resolved_trace_id:
                    trace_id = resolved_trace_id
                    event["trace_id"] = resolved_trace_id

                if agent_seq is None and event_id is None and 'event_id' not in event:
                    # Используем message_id из payload как event_id, если есть
                    event_id = event.get('message_id') or str(uuid.uuid4())
                    event['event_id'] = event_id
                    logger.debug(f"Generated event_id for server-originated event: {event_id}")
                
                # 6) Добавляем событие через репозиторий
                # КРИТИЧНО: operation_id может быть в event или передан отдельно
                event_operation_id = operation_id or event.get('operation_id')
                result = await repo.add_event(
                    ticket_id=ticket_id,
                    device_id=bound_device_id,
                    agent_seq=agent_seq,  # None для server-originated
                    event_type=event_type,
                    payload=event,
                    trace_id=trace_id or event.get('trace_id'),
                    event_id=event_id or event.get('event_id'),
                    operation_id=event_operation_id
                )
                
                if result:
                    await session.commit()
                    inserted_id, created_at = result
                    logger.debug(
                        f"📝 Событие добавлено в тикет {ticket_id}: "
                        f"{event_type} (id={inserted_id}, agent_seq={agent_seq})"
                    )
                    
                    # КРИТИЧНО: Push использует данные из INSERT RETURNING, без дополнительного SELECT
                    if self.state and self.state.subscription_registry:
                        from websocket.ui_handler import push_ticket_event_committed
                        await push_ticket_event_committed(
                            self.state,
                            ticket_id=ticket_id,
                            event_id=inserted_id,
                            event_type=event_type,
                            operation_id=event_operation_id,
                            agent_seq=agent_seq,
                            created_at=created_at,
                            payload=event
                        )
                else:
                    # Stage 7: rollback при идемпотентном дубликате
                    await session.rollback()
                    logger.debug(
                        f"📝 Дубликат события в тикете {ticket_id}: "
                        f"{event_type} (agent_seq={agent_seq})"
                    )
                    
        except Exception as e:
            logger.error(f"Failed to append event to ticket {ticket_id}: {e}", exc_info=True)
            raise
    
    async def get_events(self, ticket_id: str) -> List[dict]:
        """
        Возвращает все события тикета из PostgreSQL.
        
        Args:
            ticket_id: ID тикета
        
        Returns:
            Список событий в формате dict
        """
        if not DB_AVAILABLE:
            logger.error("Database not available, cannot get events")
            return []
        
        try:
            async with get_session() as session:
                repo = TicketEventsRepo(session)
                events = await repo.get_events(ticket_id)
                
                # Конвертируем в dict формат
                return [
                    {
                        "id": e.id,
                        "ticket_id": e.ticket_id,
                        "device_id": e.device_id,
                        "agent_seq": e.agent_seq,
                        "event_type": e.event_type,
                        "payload": e.payload,
                        "trace_id": e.trace_id,
                        "event_id": e.event_id,
                        "created_at": e.created_at.isoformat() if e.created_at else None
                    }
                    for e in events
                ]
        except Exception as e:
            logger.error(f"Failed to get events for ticket {ticket_id}: {e}", exc_info=True)
            return []
    
    async def create_ticket_created_event(
        self, 
        ticket_id: str, 
        session_id: str, 
        device_id: str
    ) -> None:
        """Создаёт событие о создании тикета."""
        await self.append_event(
            ticket_id, 
            {
                "event": "ticket_created",
                "ticket_id": ticket_id,
                "session_id": session_id,
                "device_id": device_id
            },
            device_id=device_id,
            agent_seq=None  # server-originated
        )
    
    async def create_session_opened_event(
        self, 
        ticket_id: str, 
        session_id: str, 
        device_id: str
    ) -> None:
        """Создаёт событие об открытии сессии."""
        await self.append_event(
            ticket_id,
            {
                "event": "session_opened",
                "ticket_id": ticket_id,
                "session_id": session_id,
                "device_id": device_id
            },
            device_id=device_id,
            agent_seq=None  # server-originated
        )
    
    async def create_message_event(
        self, 
        ticket_id: str, 
        message_id: str, 
        from_role: str
    ) -> None:
        """Создаёт событие о новом сообщении."""
        await self.append_event(
            ticket_id,
            {
                "event": "message_received",
                "ticket_id": ticket_id,
                "message_id": message_id,
                "from_role": from_role
            },
            agent_seq=None  # server-originated
        )
    
    async def create_ticket_closed_event(
        self, 
        ticket_id: str, 
        closed_by_role: str, 
        reason: str
    ) -> None:
        """Создаёт событие о закрытии тикета."""
        await self.append_event(
            ticket_id,
            {
                "event": "ticket_closed",
                "ticket_id": ticket_id,
                "closed_by_role": closed_by_role,
                "reason": reason
            },
            agent_seq=None  # server-originated
        )
    
    async def create_initial_message_created_event(
        self, 
        ticket_id: str, 
        message_id: str
    ) -> None:
        """Создаёт событие о создании начального сообщения."""
        await self.append_event(
            ticket_id,
            {
                "event": "initial_message_created",
                "ticket_id": ticket_id,
                "message_id": message_id
            },
            agent_seq=None  # server-originated
        )
    
    async def create_message_sent_to_agent_event(
        self, 
        ticket_id: str, 
        message_id: str
    ) -> None:
        """Создаёт событие об отправке сообщения агенту."""
        await self.append_event(
            ticket_id,
            {
                "event": "message_sent_to_agent",
                "ticket_id": ticket_id,
                "message_id": message_id
            },
            agent_seq=None  # server-originated
        )
    
    async def create_message_send_failed_event(
        self, 
        ticket_id: str, 
        message_id: str, 
        error: str
    ) -> None:
        """Создаёт событие об ошибке отправки сообщения."""
        await self.append_event(
            ticket_id,
            {
                "event": "message_send_failed",
                "ticket_id": ticket_id,
                "message_id": message_id,
                "error": error
            },
            agent_seq=None  # server-originated
        )
