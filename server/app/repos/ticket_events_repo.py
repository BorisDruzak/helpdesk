"""
Repository for ticket_events table operations.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, select, and_, or_, text, func, delete, case, update, literal
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import (
    TicketEvent,
    Ticket,
    TicketQueue,
    TicketQueueMember,
    TicketRoutingRule,
    TicketSlaPolicy,
    TicketSlaTarget,
    TicketPriorityMatrix,
    TicketWorklog,
    TicketLink,
    TicketWatcher,
    TicketResolutionCode,
    TicketKbLink,
    UiUser,
)
from tickets.statuses import ACTIVE_OPERATOR_STATUSES, TERMINAL_STATUSES


class TicketEventsRepo:
    """
    Repository for managing ticket events in the database.
    
    Provides methods for:
    - Adding events with automatic deduplication
    - Retrieving event history for replay
    - Validating device binding
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a database session.
        
        Args:
            session: Async SQLAlchemy session
        """
        self.session = session
    
    async def add_event(
        self,
        ticket_id: str,
        device_id: str,
        agent_seq: Optional[int],  # КРИТИЧНО: nullable для server-originated событий
        event_type: str,
        payload: dict,
        trace_id: Optional[str] = None,
        event_id: Optional[str] = None,
        operation_id: Optional[str] = None  # КРИТИЧНО: для связи с операцией
    ) -> Optional[tuple]:
        """
        Add a ticket event to the database with automatic deduplication.
        
        КРИТИЧНО: Поддерживает agent_seq = NULL для server-originated событий.
        
        Deduplication:
        - Agent events (agent_seq IS NOT NULL): дедупликация через UNIQUE constraint
        - Server events (agent_seq IS NULL): дедупликация через message_id
        
        Args:
            ticket_id: Ticket identifier
            device_id: Device identifier
            agent_seq: Agent sequence number (monotonic per-ticket) OR NULL for server events.
                       - int: Agent-originated event (монотонный seq от агента)
                       - None: Server-originated event (support/user message)
            event_type: Type of event (e.g., "chat_message", "chat_started")
            payload: Full event payload as dict.
                     For server events should include "message_id" for deduplication.
            trace_id: Optional trace ID for correlation
            event_id: Optional event ID from agent
        
        Returns:
            Tuple (event_id, created_at) if inserted, None if duplicate
        
        Raises:
            Exception: If database operation fails
        
        Example:
            # Agent event (with agent_seq)
            await repo.add_event(
                ticket_id="123",
                device_id="device-1",
                agent_seq=5,  # from agent
                event_type="chat_message",
                payload={"message_id": "msg-1", "text": "Hello"}
            )
            
            # Server event (agent_seq = None)
            await repo.add_event(
                ticket_id="123",
                device_id="device-1",
                agent_seq=None,  # server-originated
                event_type="chat_message",
                payload={"message_id": "msg-2", "text": "Support reply"}
            )
        """
        
        # КРИТИЧНО: Для server events (agent_seq = None) проверяем дубликат
        # Приоритет: event_id > message_id (если оба присутствуют)
        if agent_seq is None:
            # Проверка по event_id (приоритетный способ дедупликации)
            if event_id:
                existing_by_event_id = await self._check_duplicate_by_event_id(
                    ticket_id=ticket_id,
                    event_id=event_id
                )
                if existing_by_event_id:
                    logger.debug(
                        f"[TicketEventsRepo] Duplicate server event by event_id: "
                        f"ticket_id={ticket_id} event_id={event_id}"
                    )
                    return None
            
            # Fallback: проверка по message_id (для обратной совместимости)
            if not event_id and payload.get("message_id"):
                existing_by_message_id = await self._check_duplicate_server_event(
                    ticket_id=ticket_id,
                    event_type=event_type,
                    message_id=payload["message_id"]
                )
                if existing_by_message_id:
                    logger.debug(
                        f"[TicketEventsRepo] Duplicate server event by message_id: "
                        f"ticket_id={ticket_id} message_id={payload['message_id']}"
                    )
                    return None
        
        # КРИТИЧНО: Для событий с operation_id проверяем идемпотентность через UNIQUE индекс
        # (ticket_id, operation_id, event_type) WHERE operation_id IS NOT NULL
        if operation_id is not None:
            existing_by_operation = await self._check_duplicate_by_operation_id(
                ticket_id=ticket_id,
                operation_id=operation_id,
                event_type=event_type
            )
            if existing_by_operation:
                logger.debug(
                    f"[TicketEventsRepo] Duplicate event by operation_id: "
                    f"ticket_id={ticket_id} operation_id={operation_id} event_type={event_type}"
                )
                return None
        
        # Create insert statement
        stmt = insert(TicketEvent).values(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=agent_seq,
            event_type=event_type,
            payload=payload,
            trace_id=trace_id,
            event_id=event_id,
            operation_id=operation_id,  # КРИТИЧНО: связь с операцией
            created_at=datetime.now(timezone.utc)
        )
        
        # КРИТИЧНО: ON CONFLICT работает только для agent events (agent_seq IS NOT NULL)
        # Для server events (agent_seq = NULL) дедупликация уже выполнена выше
        # В миграции 005 dedupe реализован как partial UNIQUE INDEX, а не CONSTRAINT.
        if agent_seq is not None:
            # Add ON CONFLICT clause for agent events deduplication
            stmt = stmt.on_conflict_do_nothing(
                index_elements=[
                    TicketEvent.device_id,
                    TicketEvent.ticket_id,
                    TicketEvent.agent_seq,
                ],
                index_where=TicketEvent.agent_seq.isnot(None),
            )
        
        # КРИТИЧНО: Execute with RETURNING to get both id and created_at
        # Это позволяет избежать дополнительного SELECT для push
        stmt = stmt.returning(TicketEvent.id, TicketEvent.created_at)
        
        try:
            result = await self.session.execute(stmt)
            row = result.first()
            
            if row is None:
                # Duplicate detected (only possible for agent events with ON CONFLICT)
                logger.debug(
                    f"[TicketEventsRepo] Duplicate agent event detected: "
                    f"ticket_id={ticket_id} device_id={device_id} agent_seq={agent_seq}"
                )
                return None
            
            # New event inserted - return (id, created_at)
            event_id_result, created_at_result = row[0], row[1]
            logger.debug(
                f"[TicketEventsRepo] Inserted event: "
                f"id={event_id_result} ticket_id={ticket_id} "
                f"event_type={event_type} agent_seq={agent_seq} created_at={created_at_result}"
            )
            
            return (event_id_result, created_at_result)
        
        except IntegrityError as e:
            # КРИТИЧНО: IntegrityError обрабатывается внутри repo; rollback выполняется здесь (Stage 8 контракт).
            # Может возникнуть при нарушении UNIQUE индекса uq_ticket_events_ticket_operation_type.
            if 'uq_ticket_events_ticket_operation_type' in str(e.orig) or 'operation_id' in str(e.orig):
                logger.warning(
                    f"[TicketEventsRepo] IntegrityError (idempotent): "
                    f"ticket_id={ticket_id} operation_id={operation_id} event_type={event_type}. "
                    f"Event already exists, treating as duplicate."
                )
                await self.session.rollback()
                return None
            await self.session.rollback()
            raise
        except SQLAlchemyError:
            # Не оставляем session в failed-transaction состоянии,
            # если вызывающий код решит продолжить обработку после исключения.
            await self.session.rollback()
            raise
    
    async def _check_duplicate_server_event(
        self,
        ticket_id: str,
        event_type: str,
        message_id: str
    ) -> bool:
        """
        Проверяет наличие server event с таким же message_id.
        
        Используется для дедупликации server-originated событий (agent_seq = NULL).
        
        Args:
            ticket_id: Ticket identifier
            event_type: Event type (e.g., "chat_message")
            message_id: Message ID from payload
        
        Returns:
            True если событие с таким message_id уже существует, False иначе
        """
        stmt = select(TicketEvent).where(
            and_(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.event_type == event_type,
                TicketEvent.agent_seq.is_(None),  # Only server events
                TicketEvent.payload['message_id'].astext == message_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def _check_duplicate_by_event_id(
        self,
        ticket_id: str,
        event_id: str
    ) -> bool:
        """
        Проверяет наличие server event с таким же event_id.
        
        Используется для дедупликации server-originated событий (agent_seq = NULL).
        Приоритетный способ дедупликации для server events.
        
        Args:
            ticket_id: Ticket identifier
            event_id: Event ID (UUID)
        
        Returns:
            True если событие с таким event_id уже существует, False иначе
        """
        stmt = select(TicketEvent).where(
            and_(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.event_id == event_id,
                TicketEvent.agent_seq.is_(None)  # Only server events
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def _check_duplicate_by_operation_id(
        self,
        ticket_id: str,
        operation_id: str,
        event_type: str
    ) -> bool:
        """
        Проверяет наличие события с таким же (ticket_id, operation_id, event_type).
        
        Используется для дедупликации событий с operation_id (например, tool_call_started).
        Идемпотентность гарантируется UNIQUE индексом uq_ticket_events_ticket_operation_type.
        
        Args:
            ticket_id: Ticket identifier
            operation_id: Operation identifier
            event_type: Event type (e.g., "tool_call_started")
        
        Returns:
            True если событие с таким operation_id уже существует, False иначе
        """
        stmt = select(TicketEvent).where(
            and_(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.operation_id == operation_id,
                TicketEvent.event_type == event_type
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def get_ticket_device_id(self, ticket_id: str) -> Optional[str]:
        """
        Get the device_id bound to a ticket.
        
        Args:
            ticket_id: Ticket identifier
        
        Returns:
            device_id if ticket exists, None otherwise
        """
        stmt = select(Ticket.device_id).where(Ticket.ticket_id == ticket_id)
        result = await self.session.execute(stmt)
        row = result.first()
        
        if row is None:
            return None
        
        return row[0]
    
    async def get_events(
        self,
        ticket_id: str,
        since_agent_seq: Optional[int] = None,
        limit: int = 1000,
        event_types: Optional[List[str]] = None
    ) -> List[TicketEvent]:
        """
        Get events for a ticket, optionally filtered by agent_seq and event_types.
        
        КРИТИЧНО: Server-originated события имеют agent_seq = NULL.
        Сортировка: agent_seq NULLS LAST, затем created_at, затем id.
        Это гарантирует, что server events идут после agent events в хронологическом порядке.
        
        Args:
            ticket_id: Ticket identifier
            since_agent_seq: Optional - get events with agent_seq > this value.
                             Events with agent_seq = NULL always included (server events).
            limit: Maximum number of events to return (default: 1000)
            event_types: Optional - filter by event_type IN (event_types).
                         Example: ["chat_message"] - only chat messages.
        
        Returns:
            List of TicketEvent objects ordered by:
            1. agent_seq ASC NULLS LAST (agent events first, ordered by seq)
            2. created_at ASC (server events in chronological order)
            3. id ASC (tie-breaker for same timestamp)
        
        Example:
            # Get all chat messages
            messages = await repo.get_events(
                ticket_id="123",
                event_types=["chat_message"]
            )
            
            # Get events since agent_seq=5 (includes server events)
            events = await repo.get_events(
                ticket_id="123",
                since_agent_seq=5
            )
        """
        stmt = select(TicketEvent).where(TicketEvent.ticket_id == ticket_id)
        
        if since_agent_seq is not None:
            # КРИТИЧНО: Include events with agent_seq > since_agent_seq OR agent_seq IS NULL
            # Server events (agent_seq = NULL) always included for replay
            stmt = stmt.where(
                or_(
                    TicketEvent.agent_seq > since_agent_seq,
                    TicketEvent.agent_seq.is_(None)
                )
            )
        
        # Filter by event_types if provided
        if event_types:
            stmt = stmt.where(TicketEvent.event_type.in_(event_types))
        
        # КРИТИЧНО: Сортировка с учетом NULL agent_seq
        # Agent events (с agent_seq) первыми в порядке seq
        # Server events (с NULL) затем в хронологическом порядке
        stmt = stmt.order_by(
            TicketEvent.agent_seq.asc().nulls_last(),  # Agent events first (ordered by seq)
            TicketEvent.created_at.asc(),               # Then by timestamp (server events)
            TicketEvent.id.asc()                        # Tie-breaker
        ).limit(limit)
        
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        
        logger.info(
            f"[TicketEventsRepo] Retrieved {len(events)} events for ticket_id={ticket_id} "
            f"since_agent_seq={since_agent_seq} event_types={event_types}"
        )
        
        return list(events)
    
    async def get_last_agent_seq(self, ticket_id: str) -> Optional[int]:
        """
        Get the last agent_seq for a ticket.
        
        КРИТИЧНО: Возвращает только agent events (agent_seq IS NOT NULL).
        Server events (agent_seq = NULL) игнорируются.
        
        Args:
            ticket_id: Ticket identifier
        
        Returns:
            Last agent_seq if agent events exist, None otherwise
            (None означает что нет agent events, только server events)
        """
        stmt = (
            select(TicketEvent.agent_seq)
            .where(
                and_(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.agent_seq.isnot(None)  # Только agent events
                )
            )
            .order_by(TicketEvent.agent_seq.desc())
            .limit(1)
        )
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if row is None:
            return None
        
        return row[0]

    async def get_last_event(
        self, ticket_id: str
    ) -> Optional[tuple]:
        """
        Последнее событие тикета по id (для push в WS после commit).
        Returns:
            (id, event_type, created_at, payload) или None
        """
        stmt = (
            select(TicketEvent.id, TicketEvent.event_type, TicketEvent.created_at, TicketEvent.payload)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        return (row[0], row[1], row[2], row[3])

    async def get_event_by_id(self, ticket_id: str, event_id: int) -> Optional[TicketEvent]:
        """Get a specific ticket event by numeric id."""
        stmt = select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.id == event_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_chat_message_by_message_id(self, ticket_id: str, message_id: str) -> Optional[TicketEvent]:
        """Resolve a chat_message by payload.message_id within a ticket."""
        stmt = select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "chat_message",
            TicketEvent.payload["message_id"].astext == message_id,
        ).order_by(TicketEvent.id.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_message_read_cursor(self, ticket_id: str, scope: str) -> Dict[str, Any]:
        """Return the latest persisted read cursor for requester or staff."""
        if scope not in {"requester", "staff"}:
            raise ValueError(f"Unsupported read scope: {scope}")

        actor_roles = ["user", "agent"] if scope == "requester" else ["support", "admin"]
        stmt = text(
            """
            SELECT
                id,
                COALESCE(NULLIF(payload->>'last_read_event_id', ''), '0')::bigint AS last_read_event_id,
                NULLIF(payload->>'last_read_message_id', '') AS last_read_message_id,
                NULLIF(payload->>'message_preview', '') AS message_preview,
                COALESCE(NULLIF(payload->>'messages_read_count', ''), '0')::int AS messages_read_count,
                COALESCE(NULLIF(payload->>'tool_calls_read_count', ''), '0')::int AS tool_calls_read_count
            FROM ticket_events
            WHERE ticket_id = :ticket_id
              AND event_type = 'message_read'
              AND COALESCE(payload->>'actor_role', '') IN :actor_roles
            ORDER BY id DESC
            LIMIT 1
            """
        ).bindparams(bindparam("actor_roles", expanding=True))
        result = await self.session.execute(
            stmt,
            {"ticket_id": ticket_id, "actor_roles": actor_roles},
        )
        row = result.first()
        if row is None:
            return {
                "event_id": None,
                "last_read_event_id": 0,
                "last_read_message_id": None,
                "message_preview": None,
                "messages_read_count": 0,
                "tool_calls_read_count": 0,
            }
        return {
            "event_id": int(row[0]) if row[0] is not None else None,
            "last_read_event_id": int(row[1] or 0),
            "last_read_message_id": row[2],
            "message_preview": row[3],
            "messages_read_count": int(row[4] or 0),
            "tool_calls_read_count": int(row[5] or 0),
        }

    async def summarize_read_window(
        self,
        ticket_id: str,
        scope: str,
        from_event_id: int,
        to_event_id: int,
    ) -> Dict[str, Any]:
        """Summarize unread items that are being marked as read."""
        if scope not in {"requester", "staff"}:
            raise ValueError(f"Unsupported read scope: {scope}")

        incoming_roles = ["support", "agent", "admin"] if scope == "requester" else ["user"]
        summary_stmt = text(
            """
            SELECT
                count(*) FILTER (
                    WHERE event_type = 'chat_message'
                      AND COALESCE(payload->>'visibility', 'public') = 'public'
                      AND COALESCE(payload->>'sender_role', payload->>'from', '') IN :incoming_roles
                ) AS messages_read_count,
                count(*) FILTER (
                    WHERE event_type = 'tool_call_started'
                ) AS tool_calls_read_count
            FROM ticket_events
            WHERE ticket_id = :ticket_id
              AND id > :from_event_id
              AND id <= :to_event_id
            """
        ).bindparams(bindparam("incoming_roles", expanding=True))
        summary_result = await self.session.execute(
            summary_stmt,
            {
                "ticket_id": ticket_id,
                "from_event_id": int(from_event_id),
                "to_event_id": int(to_event_id),
                "incoming_roles": incoming_roles,
            },
        )
        summary_row = summary_result.first()
        messages_read_count = int(summary_row[0] or 0) if summary_row else 0
        tool_calls_read_count = int(summary_row[1] or 0) if summary_row else 0

        latest_message_stmt = text(
            """
            SELECT
                NULLIF(payload->>'message_id', '') AS message_id,
                NULLIF(payload->>'text', '') AS text
            FROM ticket_events
            WHERE ticket_id = :ticket_id
              AND id > :from_event_id
              AND id <= :to_event_id
              AND event_type = 'chat_message'
              AND COALESCE(payload->>'visibility', 'public') = 'public'
              AND COALESCE(payload->>'sender_role', payload->>'from', '') IN :incoming_roles
            ORDER BY id DESC
            LIMIT 1
            """
        ).bindparams(bindparam("incoming_roles", expanding=True))
        latest_message_result = await self.session.execute(
            latest_message_stmt,
            {
                "ticket_id": ticket_id,
                "from_event_id": int(from_event_id),
                "to_event_id": int(to_event_id),
                "incoming_roles": incoming_roles,
            },
        )
        latest_message_row = latest_message_result.first()
        return {
            "messages_read_count": messages_read_count,
            "tool_calls_read_count": tool_calls_read_count,
            "last_read_message_id": latest_message_row[0] if latest_message_row else None,
            "message_preview": latest_message_row[1] if latest_message_row else None,
        }

    async def get_ticket_chat_counters_batch(self, ticket_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate unread/pending counters for ticket lists and snapshots.

        The counters are intentionally denormalized at query time so both UIs can
        consume the same payload without storing a second source of truth.
        """
        normalized_ids = [str(ticket_id).strip() for ticket_id in ticket_ids if str(ticket_id).strip()]
        if not normalized_ids:
            return {}

        counters_stmt = text(
            """
            WITH base AS (
                SELECT ticket_id, id, event_type, payload, created_at
                FROM ticket_events
                WHERE ticket_id IN :ticket_ids
            ),
            tickets_set AS (
                SELECT DISTINCT ticket_id FROM base
            ),
            requester_cursor AS (
                SELECT DISTINCT ON (ticket_id)
                    ticket_id,
                    COALESCE(NULLIF(payload->>'last_read_event_id', ''), '0')::bigint AS last_read_event_id
                FROM base
                WHERE event_type = 'message_read'
                  AND COALESCE(payload->>'actor_role', '') IN ('user', 'agent')
                ORDER BY ticket_id, id DESC
            ),
            staff_cursor AS (
                SELECT DISTINCT ON (ticket_id)
                    ticket_id,
                    COALESCE(NULLIF(payload->>'last_read_event_id', ''), '0')::bigint AS last_read_event_id
                FROM base
                WHERE event_type = 'message_read'
                  AND COALESCE(payload->>'actor_role', '') IN ('support', 'admin')
                ORDER BY ticket_id, id DESC
            ),
            staff_last_public_reply AS (
                SELECT
                    ticket_id,
                    max(id) AS last_staff_message_id
                FROM base
                WHERE event_type = 'chat_message'
                  AND COALESCE(payload->>'visibility', 'public') = 'public'
                  AND COALESCE(payload->>'sender_role', payload->>'from', '') IN ('support', 'agent', 'admin')
                GROUP BY ticket_id
            ),
            latest_user_message AS (
                SELECT DISTINCT ON (ticket_id)
                    ticket_id,
                    id AS last_user_message_event_id,
                    NULLIF(payload->>'message_id', '') AS last_user_message_id,
                    NULLIF(payload->>'text', '') AS last_user_message_text,
                    created_at AS last_user_message_at
                FROM base
                WHERE event_type = 'chat_message'
                  AND COALESCE(payload->>'visibility', 'public') = 'public'
                  AND COALESCE(payload->>'sender_role', payload->>'from', '') = 'user'
                ORDER BY ticket_id, id DESC
            ),
            requester_counts AS (
                SELECT
                    b.ticket_id,
                    count(*) FILTER (
                        WHERE b.event_type = 'chat_message'
                          AND COALESCE(b.payload->>'visibility', 'public') = 'public'
                          AND COALESCE(b.payload->>'sender_role', b.payload->>'from', '') IN ('support', 'agent', 'admin')
                          AND b.id > COALESCE(rc.last_read_event_id, 0)
                    ) AS requester_unread_messages,
                    count(*) FILTER (
                        WHERE b.event_type = 'tool_call_started'
                          AND b.id > COALESCE(rc.last_read_event_id, 0)
                    ) AS requester_unread_tool_calls,
                    max(b.id) FILTER (
                        WHERE b.id > COALESCE(rc.last_read_event_id, 0)
                          AND (
                            (
                                b.event_type = 'chat_message'
                                AND COALESCE(b.payload->>'visibility', 'public') = 'public'
                            )
                            OR b.event_type IN (
                                'tool_call_started',
                                'tool_call_result',
                                'status_changed',
                                'priority_changed',
                                'assignee_changed',
                                'queue_changed',
                                'device_changed'
                            )
                          )
                    ) AS requester_latest_unread_event_id
                FROM base b
                LEFT JOIN requester_cursor rc ON rc.ticket_id = b.ticket_id
                GROUP BY b.ticket_id, rc.last_read_event_id
            ),
            staff_counts AS (
                SELECT
                    b.ticket_id,
                    count(*) FILTER (
                        WHERE b.event_type = 'chat_message'
                          AND COALESCE(b.payload->>'visibility', 'public') = 'public'
                          AND COALESCE(b.payload->>'sender_role', b.payload->>'from', '') = 'user'
                          AND b.id > COALESCE(sc.last_read_event_id, 0)
                    ) AS support_unread_user_messages,
                    count(*) FILTER (
                        WHERE b.event_type = 'chat_message'
                          AND COALESCE(b.payload->>'visibility', 'public') = 'public'
                          AND COALESCE(b.payload->>'sender_role', b.payload->>'from', '') = 'user'
                          AND b.id > COALESCE(sr.last_staff_message_id, 0)
                    ) AS support_pending_user_messages
                FROM base b
                LEFT JOIN staff_cursor sc ON sc.ticket_id = b.ticket_id
                LEFT JOIN staff_last_public_reply sr ON sr.ticket_id = b.ticket_id
                GROUP BY b.ticket_id, sc.last_read_event_id, sr.last_staff_message_id
            )
            SELECT
                t.ticket_id,
                COALESCE(rc.last_read_event_id, 0) AS requester_last_read_event_id,
                COALESCE(sc.last_read_event_id, 0) AS support_last_read_event_id,
                COALESCE(rqc.requester_unread_messages, 0) AS requester_unread_messages,
                COALESCE(rqc.requester_unread_tool_calls, 0) AS requester_unread_tool_calls,
                rqc.requester_latest_unread_event_id AS requester_latest_unread_event_id,
                COALESCE(stc.support_unread_user_messages, 0) AS support_unread_user_messages,
                COALESCE(stc.support_pending_user_messages, 0) AS support_pending_user_messages,
                lum.last_user_message_event_id AS last_user_message_event_id,
                lum.last_user_message_id AS last_user_message_id,
                lum.last_user_message_text AS last_user_message_text,
                lum.last_user_message_at AS last_user_message_at
            FROM tickets_set t
            LEFT JOIN requester_cursor rc ON rc.ticket_id = t.ticket_id
            LEFT JOIN staff_cursor sc ON sc.ticket_id = t.ticket_id
            LEFT JOIN requester_counts rqc ON rqc.ticket_id = t.ticket_id
            LEFT JOIN staff_counts stc ON stc.ticket_id = t.ticket_id
            LEFT JOIN latest_user_message lum ON lum.ticket_id = t.ticket_id
            """
        ).bindparams(bindparam("ticket_ids", expanding=True))
        result = await self.session.execute(counters_stmt, {"ticket_ids": normalized_ids})

        counters: Dict[str, Dict[str, Any]] = {
            ticket_id: {
                "requester_last_read_event_id": 0,
                "support_last_read_event_id": 0,
                "requester_unread_messages": 0,
                "requester_unread_tool_calls": 0,
                "requester_latest_unread_event_id": None,
                "support_unread_user_messages": 0,
                "support_pending_user_messages": 0,
                "last_user_message_event_id": None,
                "last_user_message_id": None,
                "last_user_message_text": None,
                "last_user_message_at": None,
            }
            for ticket_id in normalized_ids
        }
        for row in result.fetchall():
            counters[row[0]] = {
                "requester_last_read_event_id": int(row[1] or 0),
                "support_last_read_event_id": int(row[2] or 0),
                "requester_unread_messages": int(row[3] or 0),
                "requester_unread_tool_calls": int(row[4] or 0),
                "requester_latest_unread_event_id": int(row[5]) if row[5] is not None else None,
                "support_unread_user_messages": int(row[6] or 0),
                "support_pending_user_messages": int(row[7] or 0),
                "last_user_message_event_id": int(row[8]) if row[8] is not None else None,
                "last_user_message_id": row[9],
                "last_user_message_text": row[10],
                "last_user_message_at": row[11].isoformat() if row[11] is not None else None,
            }
        return counters
    
    async def create_ticket(
        self,
        ticket_id: str,
        device_id: str,
        title: str,
        description: str,
        status: str = "in_progress",
        requester_id: Optional[str] = None,
        ticket_type: str = "request",
    ) -> Ticket:
        """
        Create a new ticket.
        
        Args:
            ticket_id: Ticket identifier (UUID)
            device_id: Device identifier
            title: Ticket title
            description: Ticket description
            status: Initial status (default: "in_progress")
            requester_id: Optional requester (actor_id) for RBAC; if not set, list_tickets
                          for non-admin may exclude this ticket.
        
        Returns:
            Created Ticket object
        """
        now = datetime.now(timezone.utc)
        
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title=title,
            description=description,
            status=status,
            ticket_type=ticket_type,
            created_at=now,
            updated_at=now,
            requester_id=requester_id,
        )
        
        self.session.add(ticket)
        await self.session.flush()
        await self.session.refresh(ticket)  # загрузить ticket_code (server default)
        logger.info(
            f"[TicketEventsRepo] Created ticket: "
            f"ticket_id={ticket_id} ticket_code={getattr(ticket, 'ticket_code', None)} device_id={device_id} status={status}"
        )
        return ticket
    
    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """
        Get a ticket by ID.
        
        Args:
            ticket_id: Ticket identifier
        
        Returns:
            Ticket object if found, None otherwise
        """
        stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
        result = await self.session.execute(stmt)
        ticket = result.scalar_one_or_none()
        
        return ticket

    async def ticket_contains_artifact(self, ticket_id: str, artifact_id: str) -> bool:
        """
        Проверяет, есть ли в тикете событие с данным artifact_id:
        - tool_call_result: payload.artifacts[].artifact_id
        - chat_message: payload.attachments[].artifact_id или payload.attachment_refs[].

        Используется для доступа к артефактам без ticket_id в БД (старые загрузки).
        
        Args:
            ticket_id: Идентификатор тикета
            artifact_id: Идентификатор артефакта
        
        Returns:
            True если тикет содержит событие с этим артефактом
        """
        stmt = text("""
            SELECT EXISTS (
                SELECT 1 FROM ticket_events
                WHERE ticket_id = :ticket_id
                  AND (
                    ( event_type = 'tool_call_result'
                      AND jsonb_typeof(COALESCE(payload->'artifacts', '[]'::jsonb)) = 'array'
                      AND EXISTS (
                        SELECT 1 FROM jsonb_array_elements(COALESCE(payload->'artifacts', '[]'::jsonb)) AS elem
                        WHERE elem->>'artifact_id' = :artifact_id
                      )
                    )
                    OR
                    ( event_type = 'chat_message'
                      AND (
                        ( jsonb_typeof(COALESCE(payload->'attachments', '[]'::jsonb)) = 'array'
                          AND EXISTS (
                            SELECT 1 FROM jsonb_array_elements(COALESCE(payload->'attachments', '[]'::jsonb)) AS elem
                            WHERE elem->>'artifact_id' = :artifact_id
                          )
                        )
                        OR
                        ( jsonb_typeof(COALESCE(payload->'attachment_refs', '[]'::jsonb)) = 'array'
                          AND EXISTS (
                            SELECT 1 FROM jsonb_array_elements_text(COALESCE(payload->'attachment_refs', '[]'::jsonb)) AS elem
                            WHERE elem = :artifact_id
                          )
                        )
                      )
                    )
                  )
            )
        """)
        result = await self.session.execute(stmt, {"ticket_id": ticket_id, "artifact_id": artifact_id})
        row = result.scalar_one()
        return bool(row)
    
    async def update_ticket_status(
        self,
        ticket_id: str,
        status: str
    ) -> bool:
        """
        Update ticket status.
        
        Args:
            ticket_id: Ticket identifier
            status: New status
        
        Returns:
            True if updated, False if ticket not found
        """
        ticket = await self.get_ticket(ticket_id)
        if ticket is None:
            return False
        
        ticket.status = status
        ticket.updated_at = datetime.now(timezone.utc)
        
        logger.info(
            f"[TicketEventsRepo] Updated ticket status: "
            f"ticket_id={ticket_id} status={status}"
        )
        
        return True

    async def update_ticket(
        self,
        ticket_id: str,
        **fields
    ) -> bool:
        """
        Обновить произвольные поля тикета.
        
        Args:
            ticket_id: Идентификатор тикета
            **fields: Поля для обновления (queue_id, status, custom_fields,
                first_response_at, resolution_at, first_response_due_at,
                resolution_due_at, first_response_breached_at, resolution_breached_at,
                sla_paused_at, sla_paused_seconds, reopen_count, priority, impact, urgency,
                category_id, service_id, subcategory_id, assignee_id, requester_id и т.д.)
        
        Returns:
            True если тикет найден и обновлён, False иначе
        """
        ticket = await self.get_ticket(ticket_id)
        if ticket is None:
            return False
        now = datetime.now(timezone.utc)
        allowed = {
            "device_id", "queue_id", "status", "title", "description", "custom_fields", "first_response_at", "resolution_at",
            "first_response_due_at", "resolution_due_at", "first_response_breached_at",
            "resolution_breached_at", "sla_paused_at", "sla_paused_seconds", "reopen_count",
            "priority", "impact", "urgency", "importance", "urgency_reason", "importance_reason",
            "category_id", "service_id", "subcategory_id",
            "assignee_id", "requester_id", "sla_policy_id", "resolved_at", "closed_at",
            "resolution_code", "root_cause", "parent_ticket_id",
            "manual_rank", "manual_rank_updated_at", "manual_rank_updated_by",
            "ticket_type",
            "archived_at",
        }
        for key, value in fields.items():
            if key in allowed and hasattr(ticket, key):
                setattr(ticket, key, value)
        ticket.updated_at = now
        logger.debug(f"[TicketEventsRepo] Updated ticket {ticket_id} fields: {list(fields.keys())}")
        return True

    async def get_queue_by_code(self, code: str) -> Optional[TicketQueue]:
        """Получить очередь по коду (например servicedesk_l1)."""
        stmt = select(TicketQueue).where(
            TicketQueue.code == code,
            TicketQueue.is_active.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_queue(self, queue_id: int) -> Optional[TicketQueue]:
        stmt = select(TicketQueue).where(TicketQueue.id == queue_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_routing_rules_ordered(self) -> List[TicketRoutingRule]:
        """Активные правила маршрутизации, отсортированные по priority_order."""
        stmt = (
            select(TicketRoutingRule)
            .where(TicketRoutingRule.enabled.is_(True))
            .order_by(TicketRoutingRule.priority_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_default_sla_policy(self) -> Optional[TicketSlaPolicy]:
        """Политика SLA по умолчанию (is_default=true, is_active=true)."""
        stmt = select(TicketSlaPolicy).where(
            and_(TicketSlaPolicy.is_default.is_(True), TicketSlaPolicy.is_active.is_(True))
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_sla_targets(self, policy_id: int) -> List[TicketSlaTarget]:
        """Цели SLA по приоритету для политики."""
        stmt = select(TicketSlaTarget).where(TicketSlaTarget.policy_id == policy_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_priority_from_matrix(
        self,
        policy_id: int,
        impact: Optional[int],
        urgency: Optional[int]
    ) -> Optional[str]:
        """Приоритет по матрице impact × urgency. При отсутствии данных возвращает None."""
        if impact is None or urgency is None:
            return None
        stmt = select(TicketPriorityMatrix).where(
            and_(
                TicketPriorityMatrix.policy_id == policy_id,
                TicketPriorityMatrix.impact == impact,
                TicketPriorityMatrix.urgency == urgency,
            )
        )
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        return row.priority if row else None

    async def get_tickets_sla_breach_candidates(
        self,
        limit: int = 100,
    ) -> List[Ticket]:
        """
        Тикеты с истёкшим SLA (для watchdog).
        Учитывает sla_paused_seconds: эффективный due = due_at + paused_seconds.
        Исключает Resolved/Closed.
        """
        # Выбираем тикеты не в терминальном статусе с due_at не NULL
        stmt = select(Ticket).where(
            and_(
                Ticket.status.notin_(list(TERMINAL_STATUSES)),
                or_(
                    Ticket.first_response_due_at.isnot(None),
                    Ticket.resolution_due_at.isnot(None),
                ),
            )
        ).limit(limit * 2)  # берём с запасом, фильтр по времени в Python
        result = await self.session.execute(stmt)
        tickets = list(result.scalars().all())
        now = datetime.now(timezone.utc)
        out = []
        for t in tickets:
            paused = t.sla_paused_seconds or 0
            if t.first_response_due_at and t.first_response_at is None:
                effective_fr = t.first_response_due_at + timedelta(seconds=paused)
                if now >= effective_fr:
                    out.append(t)
                    continue
            if t.resolution_due_at and t.resolution_at is None:
                effective_res = t.resolution_due_at + timedelta(seconds=paused)
                if now >= effective_res:
                    out.append(t)
        return out[:limit]

    async def get_tickets_auto_close_candidates(
        self,
        resolved_before: datetime,
        limit: int = 100,
    ) -> List[Ticket]:
        """
        Тикеты в статусе Resolved с resolved_at <= resolved_before (для auto-close watchdog).
        Рекомендуется индекс (status, resolved_at) для производительности.
        """
        stmt = (
            select(Ticket)
            .where(
                and_(
                    Ticket.status == "resolved",
                    Ticket.resolved_at.isnot(None),
                    Ticket.resolved_at <= resolved_before,
                )
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_open_tickets_for_device(
        self,
        device_id: str
    ) -> List[dict]:
        """
        Get open tickets for a device with their last agent_seq.
        
        Used during handshake to sync agent with server state.
        
        Args:
            device_id: Device identifier
        
        Returns:
            List of dicts with ticket_id and last_agent_seq
            Example: [
                {"ticket_id": "...", "last_agent_seq": 123},
                ...
            ]
        """
        # Get all open tickets for device
        # Открытые тикеты: не Resolved и не Closed (совместимость с новой моделью статусов)
        stmt = select(Ticket.ticket_id).where(
            and_(
                Ticket.device_id == device_id,
                Ticket.status.notin_(list(TERMINAL_STATUSES))
            )
        )
        
        result = await self.session.execute(stmt)
        ticket_ids = [row[0] for row in result.all()]
        
        if not ticket_ids:
            return []
        
        # For each ticket, get last agent_seq
        open_tickets = []
        for ticket_id in ticket_ids:
            last_seq = await self.get_last_agent_seq(ticket_id)
            open_tickets.append({
                "ticket_id": ticket_id,
                "last_agent_seq": last_seq if last_seq is not None else 0
            })
        
        logger.info(
            f"[TicketEventsRepo] Found {len(open_tickets)} open tickets "
            f"for device_id={device_id}"
        )
        
        return open_tickets
    
    async def list_tickets(
        self,
        order_by: str = "created_at",
        order_direction: str = "desc",
        limit: int = 100,
        offset: int = 0,
        filters: Optional[dict] = None
    ) -> List[Ticket]:
        """
        List tickets with pagination and optional filters.
        
        Args:
            order_by: Field to order by (default: "created_at")
                Supported: "created_at", "updated_at", "status", "ticket_id"
            order_direction: "asc" or "desc" (default: "desc")
            limit: Maximum number of tickets (default: 100)
            offset: Offset for pagination (default: 0)
            filters: Optional dict with filters:
                - status: str - filter by status
                - device_id: str - filter by device_id
                - status__in: List[str] - filter by multiple statuses
        
        Returns:
            List of Ticket objects
        
        Example:
            # Get all open tickets, newest first
            tickets = await repo.list_tickets(
                filters={"status": "In Progress"},
                order_by="created_at",
                order_direction="desc",
                limit=50
            )
        """
        stmt = select(Ticket)
        
        # Apply filters
        if filters:
            if "status" in filters:
                stmt = stmt.where(Ticket.status == filters["status"])
            if "device_id" in filters:
                stmt = stmt.where(Ticket.device_id == filters["device_id"])
            if "status__in" in filters:
                stmt = stmt.where(Ticket.status.in_(filters["status__in"]))
            if "queue_id" in filters:
                stmt = stmt.where(Ticket.queue_id == filters["queue_id"])
            if "priority" in filters:
                stmt = stmt.where(Ticket.priority == filters["priority"])
            if filters.get("assignee_id__none") is True:
                stmt = stmt.where(Ticket.assignee_id.is_(None))
            elif "assignee_id" in filters:
                stmt = stmt.where(Ticket.assignee_id == filters["assignee_id"])
            if "requester_id" in filters:
                stmt = stmt.where(Ticket.requester_id == filters["requester_id"])
            if "watching_actor_id" in filters:
                stmt = stmt.join(TicketWatcher, Ticket.ticket_id == TicketWatcher.ticket_id).where(
                    TicketWatcher.actor_id == filters["watching_actor_id"]
                )
            if "support_actor_id" in filters:
                support_actor_id = filters["support_actor_id"]
                queue_membership_exists = (
                    select(TicketQueueMember.queue_id)
                    .where(
                        TicketQueueMember.queue_id == Ticket.queue_id,
                        TicketQueueMember.actor_id == support_actor_id,
                    )
                    .exists()
                )
                stmt = stmt.where(
                    or_(
                        Ticket.assignee_id == support_actor_id,
                        queue_membership_exists,
                        and_(
                            Ticket.queue_id.is_(None),
                            Ticket.status.notin_(list(TERMINAL_STATUSES)),
                        ),
                    )
                )
            if filters.get("first_response_breached") is True:
                stmt = stmt.where(Ticket.first_response_breached_at.isnot(None))
            if filters.get("resolution_breached") is True:
                stmt = stmt.where(Ticket.resolution_breached_at.isnot(None))
            if "ticket_code" in filters:
                val = filters["ticket_code"].strip()
                if val:
                    # Точное совпадение для полного кода (T-000001), иначе поиск по началу/подстроке
                    if val.startswith("T-") and len(val) >= 9 and val.replace("T-", "").isdigit():
                        stmt = stmt.where(Ticket.ticket_code == val)
                    else:
                        stmt = stmt.where(Ticket.ticket_code.ilike(f"%{val}%"))
            if filters.get("exclude_archived") is True:
                stmt = stmt.where(Ticket.archived_at.is_(None))
        
        # Ordering
        order_field = getattr(Ticket, order_by, Ticket.created_at)
        if order_direction.lower() == "desc":
            stmt = stmt.order_by(order_field.desc())
        else:
            stmt = stmt.order_by(order_field.asc())
        
        # Pagination
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.session.execute(stmt)
        tickets = result.scalars().all()
        
        logger.info(
            f"[TicketEventsRepo] Listed {len(tickets)} tickets "
            f"(filters={filters}, order_by={order_by}, limit={limit}, offset={offset})"
        )
        
        return list(tickets)

    async def list_open_tickets_for_queue(self, queue_id: int) -> List[Ticket]:
        """
        Список открытых тикетов очереди (status NOT IN Resolved, Closed) для Position Engine.
        Без сортировки — порядок вычисляет queue_position_service.
        """
        stmt = (
            select(Ticket)
            .where(Ticket.queue_id == queue_id)
            .where(Ticket.status.notin_(list(TERMINAL_STATUSES)))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_events_since_id(
        self,
        ticket_id: str,
        since_event_id: int,
        limit: int = 500
    ) -> List[TicketEvent]:
        """
        Get ticket events with id > since_event_id.
        
        Used for UI catch-up after reconnect.
        
        Args:
            ticket_id: Ticket identifier
            since_event_id: Get events with id > this value
            limit: Maximum number of events to return (default: 500)
        
        Returns:
            List of TicketEvent objects ordered by id ASC
        """
        stmt = (
            select(TicketEvent)
            .where(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.id > since_event_id
            )
            .order_by(TicketEvent.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        
        logger.debug(
            f"[TicketEventsRepo] Retrieved {len(events)} events for ticket_id={ticket_id} "
            f"since_event_id={since_event_id}"
        )
        
        return list(events)    # ---------- Worklog (Stage 4) ----------

    async def get_events_before_id(
        self,
        ticket_id: str,
        before_event_id: Optional[int],
        limit: int = 100,
    ) -> tuple[List[TicketEvent], bool]:
        """
        Get the latest ticket events page in chronological order, optionally before a cursor.

        Args:
            ticket_id: Ticket identifier
            before_event_id: If set, return events with id < this value.
                             If None, return the latest page for the ticket.
            limit: Maximum number of events in the returned page

        Returns:
            Tuple (events, has_older) where:
            - events: chronological list ordered by id ASC
            - has_older: True if older events exist before the returned page
        """
        effective_limit = max(int(limit or 0), 1)
        stmt = select(TicketEvent).where(TicketEvent.ticket_id == ticket_id)
        if before_event_id is not None:
            stmt = stmt.where(TicketEvent.id < before_event_id)
        stmt = (
            stmt.order_by(TicketEvent.id.desc())
            .limit(effective_limit + 1)
        )

        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        has_older = len(rows) > effective_limit
        if has_older:
            rows = rows[:effective_limit]
        rows.reverse()

        logger.debug(
            f"[TicketEventsRepo] Retrieved {len(rows)} events for ticket_id={ticket_id} "
            f"before_event_id={before_event_id} has_older={has_older}"
        )

        return rows, has_older

    async def add_worklog(
        self,
        ticket_id: str,
        actor_id: str,
        spent_minutes: int,
        note: Optional[str] = None,
    ) -> Optional[TicketWorklog]:
        """Append-only worklog. Returns created worklog or None on failure."""
        if spent_minutes <= 0:
            return None
        wl = TicketWorklog(
            ticket_id=ticket_id,
            actor_id=actor_id,
            spent_minutes=spent_minutes,
            note=(note or "").strip() or None,
        )
        self.session.add(wl)
        await self.session.flush()
        logger.debug(f"[TicketEventsRepo] Added worklog id={wl.id} ticket_id={ticket_id} spent_minutes={spent_minutes}")
        return wl

    async def list_worklogs(
        self,
        ticket_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TicketWorklog]:
        """List worklogs for ticket (support/admin). Ordered by created_at desc."""
        stmt = (
            select(TicketWorklog)
            .where(TicketWorklog.ticket_id == ticket_id)
            .order_by(TicketWorklog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_worklog_total(self, ticket_id: str) -> int:
        """Sum of spent_minutes for ticket (for requester view and snapshot)."""
        stmt = text(
            "SELECT COALESCE(SUM(spent_minutes), 0)::int FROM ticket_worklogs WHERE ticket_id = :ticket_id"
        )
        result = await self.session.execute(stmt, {"ticket_id": ticket_id})
        row = result.first()
        return row[0] if row else 0

    # ---------- Stage 5: Links ----------

    async def add_ticket_link(
        self,
        src_ticket_id: str,
        dst_ticket_id: str,
        link_type: str,
        created_by: Optional[str] = None,
    ) -> Optional[TicketLink]:
        """Add link (duplicate or related). Returns created link or None on constraint violation."""
        link = TicketLink(
            src_ticket_id=src_ticket_id,
            dst_ticket_id=dst_ticket_id,
            link_type=link_type,
            created_by=created_by,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def list_ticket_links(
        self,
        ticket_id: str,
        link_type: Optional[str] = None,
    ) -> List[TicketLink]:
        """List links where ticket is src or dst."""
        stmt = select(TicketLink).where(
            or_(
                TicketLink.src_ticket_id == ticket_id,
                TicketLink.dst_ticket_id == ticket_id,
            )
        )
        if link_type:
            stmt = stmt.where(TicketLink.link_type == link_type)
        stmt = stmt.order_by(TicketLink.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_ticket_link(self, link_id: int, ticket_id: str) -> bool:
        """Delete link by id if it belongs to ticket_id (src or dst). Returns True if deleted."""
        stmt = delete(TicketLink).where(
            TicketLink.id == link_id,
            or_(
                TicketLink.src_ticket_id == ticket_id,
                TicketLink.dst_ticket_id == ticket_id,
            ),
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def exists_ticket_link(
        self,
        src_ticket_id: str,
        dst_ticket_id: str,
        link_type: str,
    ) -> bool:
        """Check if link (src, dst, type) exists (any direction for related)."""
        stmt = select(TicketLink).where(
            and_(
                TicketLink.link_type == link_type,
                or_(
                    and_(
                        TicketLink.src_ticket_id == src_ticket_id,
                        TicketLink.dst_ticket_id == dst_ticket_id,
                    ),
                    and_(
                        TicketLink.src_ticket_id == dst_ticket_id,
                        TicketLink.dst_ticket_id == src_ticket_id,
                    ),
                ),
            )
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    # ---------- Stage 5: Parent ----------

    async def set_parent_ticket(self, ticket_id: str, parent_ticket_id: Optional[str]) -> bool:
        """Set tickets.parent_ticket_id. Use None to clear. Returns True if ticket exists."""
        return await self.update_ticket(ticket_id, parent_ticket_id=parent_ticket_id)

    async def clear_parent_ticket(self, ticket_id: str) -> bool:
        """Clear parent_ticket_id for ticket."""
        return await self.set_parent_ticket(ticket_id, None)

    async def list_child_tickets(self, ticket_id: str) -> List[Ticket]:
        """List tickets that have parent_ticket_id = ticket_id."""
        stmt = select(Ticket).where(Ticket.parent_ticket_id == ticket_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ---------- Stage 5: Watchers ----------

    async def add_watcher(self, ticket_id: str, actor_id: str) -> bool:
        """Add watcher. Returns True if added, False if already exists (idempotent)."""
        w = TicketWatcher(ticket_id=ticket_id, actor_id=actor_id)
        self.session.add(w)
        await self.session.flush()
        return True

    async def remove_watcher(self, ticket_id: str, actor_id: str) -> bool:
        """Remove watcher. Returns True if removed."""
        stmt = delete(TicketWatcher).where(
            TicketWatcher.ticket_id == ticket_id,
            TicketWatcher.actor_id == actor_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def list_watchers(self, ticket_id: str) -> List[TicketWatcher]:
        """List watchers for ticket."""
        stmt = select(TicketWatcher).where(TicketWatcher.ticket_id == ticket_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def is_watcher(self, ticket_id: str, actor_id: str) -> bool:
        """Check if actor is watcher of ticket."""
        stmt = select(TicketWatcher).where(
            TicketWatcher.ticket_id == ticket_id,
            TicketWatcher.actor_id == actor_id,
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def list_queue_member_actor_ids(self, queue_id: int) -> List[str]:
        """Список actor_id участников очереди (для уведомлений Stage 6)."""
        stmt = select(TicketQueueMember.actor_id).where(TicketQueueMember.queue_id == queue_id)
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]

    async def count_active_tickets_for_assignee(self, assignee_id: str) -> int:
        stmt = (
            select(func.count(Ticket.ticket_id))
            .where(Ticket.assignee_id == assignee_id)
            .where(Ticket.status.in_(list(ACTIVE_OPERATOR_STATUSES)))
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def list_assignable_users_with_load(self, queue_id: Optional[int] = None) -> List[Dict[str, Any]]:
        role_expr = literal(None).label("role_in_queue")
        active_count_subq = (
            select(
                Ticket.assignee_id.label("assignee_id"),
                func.count(Ticket.ticket_id).label("active_count"),
            )
            .where(Ticket.assignee_id.isnot(None))
            .where(Ticket.status.in_(list(ACTIVE_OPERATOR_STATUSES)))
            .group_by(Ticket.assignee_id)
            .subquery()
        )
        stmt = (
            select(
                UiUser.user_login,
                UiUser.actor_role,
                UiUser.is_active,
                UiUser.last_ticket_assigned_at,
                func.coalesce(active_count_subq.c.active_count, 0).label("active_count"),
                role_expr,
            )
            .outerjoin(active_count_subq, active_count_subq.c.assignee_id == UiUser.user_login)
            .where(UiUser.is_active.is_(True))
            .where(UiUser.actor_role.in_(("admin", "support")))
        )
        if queue_id is not None:
            role_expr = TicketQueueMember.role_in_queue.label("role_in_queue")
            stmt = (
                select(
                    UiUser.user_login,
                    UiUser.actor_role,
                    UiUser.is_active,
                    UiUser.last_ticket_assigned_at,
                    func.coalesce(active_count_subq.c.active_count, 0).label("active_count"),
                    role_expr,
                )
                .outerjoin(active_count_subq, active_count_subq.c.assignee_id == UiUser.user_login)
                .where(UiUser.is_active.is_(True))
                .where(UiUser.actor_role.in_(("admin", "support")))
            )
            stmt = stmt.join(
                TicketQueueMember,
                and_(
                    TicketQueueMember.actor_id == UiUser.user_login,
                    TicketQueueMember.queue_id == queue_id,
                ),
            )
        stmt = stmt.order_by(
            func.coalesce(active_count_subq.c.active_count, 0).asc(),
            case(
                (UiUser.last_ticket_assigned_at.is_(None), 0),
                else_=1,
            ).asc(),
            UiUser.last_ticket_assigned_at.asc(),
            UiUser.user_login.asc(),
        )
        result = await self.session.execute(stmt)
        rows = []
        for row in result.all():
            rows.append(
                {
                    "user_login": row[0],
                    "actor_role": row[1],
                    "is_active": row[2],
                    "last_ticket_assigned_at": row[3],
                    "active_count": int(row[4] or 0),
                    "role_in_queue": row[5],
                }
            )
        return rows

    async def is_actor_in_queue(self, queue_id: Optional[int], actor_id: str) -> bool:
        if queue_id is None or not actor_id:
            return False
        stmt = select(TicketQueueMember.actor_id).where(
            and_(
                TicketQueueMember.queue_id == queue_id,
                TicketQueueMember.actor_id == actor_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def touch_user_last_assignment(self, user_login: str, assigned_at: datetime) -> bool:
        stmt = (
            update(UiUser)
            .where(UiUser.user_login == user_login)
            .values(last_ticket_assigned_at=assigned_at)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def select_assignee_for_update(self, max_active: int, queue_id: Optional[int] = None) -> Optional[str]:
        """Выбирает первого доступного кандидата с блокировкой FOR UPDATE SKIP LOCKED.

        Запрашивает упорядоченный список кандидатов, затем для каждого пытается
        заблокировать строку в ui_users (SKIP LOCKED — пропускает уже заблокированных
        конкурирующими транзакциями). После блокировки перепроверяет счётчик активных
        тикетов, чтобы исключить гонку между параллельными запросами auto-assign.
        """
        candidates = await self.list_assignable_users_with_load(queue_id=queue_id)
        for candidate in candidates:
            if int(candidate.get("active_count") or 0) >= max_active:
                continue
            user_login = candidate["user_login"]
            lock_stmt = (
                select(UiUser)
                .where(UiUser.user_login == user_login)
                .with_for_update(skip_locked=True)
            )
            result = await self.session.execute(lock_stmt)
            locked_user = result.scalar_one_or_none()
            if locked_user is None:
                continue
            actual_count = await self.count_active_tickets_for_assignee(user_login)
            if actual_count < max_active:
                return user_login
        return None

    # ---------- Stage 5: KB links ----------

    async def add_kb_link(
        self,
        ticket_id: str,
        article_ref: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> TicketKbLink:
        """Add KB link. Returns created record."""
        kb = TicketKbLink(
            ticket_id=ticket_id,
            article_ref=article_ref.strip(),
            title=(title or "").strip() or None,
            source=(source or "").strip() or None,
            created_by=created_by,
        )
        self.session.add(kb)
        await self.session.flush()
        return kb

    async def list_kb_links(self, ticket_id: str) -> List[TicketKbLink]:
        """List KB links for ticket."""
        stmt = select(TicketKbLink).where(TicketKbLink.ticket_id == ticket_id).order_by(TicketKbLink.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_kb_link(self, kb_link_id: int, ticket_id: str) -> bool:
        """Delete KB link by id if it belongs to ticket_id. Returns True if deleted."""
        stmt = delete(TicketKbLink).where(
            TicketKbLink.id == kb_link_id,
            TicketKbLink.ticket_id == ticket_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    # ---------- Stage 5: Resolution codes ----------

    async def list_resolution_codes(self, active_only: bool = True) -> List[TicketResolutionCode]:
        """List resolution codes, optionally only active."""
        stmt = select(TicketResolutionCode).order_by(TicketResolutionCode.sort_order)
        if active_only:
            stmt = stmt.where(TicketResolutionCode.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ---------- Stage 5: Metrics ----------

    async def get_metrics_backlog(
        self,
        queue_id: Optional[int] = None,
    ) -> List[dict]:
        """Open tickets (NOT IN resolved, closed) grouped by queue_id, priority."""
        stmt = (
            select(Ticket.queue_id, Ticket.priority, func.count(Ticket.ticket_id).label("count"))
            .where(Ticket.status.notin_(["resolved", "closed"]))
        )
        if queue_id is not None:
            stmt = stmt.where(Ticket.queue_id == queue_id)
        stmt = stmt.group_by(Ticket.queue_id, Ticket.priority)
        result = await self.session.execute(stmt)
        return [{"queue_id": r[0], "priority": r[1], "count": r[2]} for r in result.all()]

    async def get_metrics_aging(
        self,
        queue_id: Optional[int] = None,
    ) -> List[dict]:
        """Open tickets by age buckets from created_at. Buckets: 0-1d, 2-3d, 4-7d, 8-14d, 15-30d, 31+d."""
        stmt = text("""
            SELECT
                CASE
                    WHEN (NOW() - created_at) <= interval '1 day' THEN '0-1d'
                    WHEN (NOW() - created_at) <= interval '3 days' THEN '2-3d'
                    WHEN (NOW() - created_at) <= interval '7 days' THEN '4-7d'
                    WHEN (NOW() - created_at) <= interval '14 days' THEN '8-14d'
                    WHEN (NOW() - created_at) <= interval '30 days' THEN '15-30d'
                    ELSE '31+d'
                END AS bucket,
                count(*)::int AS count
            FROM tickets
            WHERE status NOT IN ('resolved', 'closed')
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
            GROUP BY 1
        """)
        result = await self.session.execute(stmt, {"qid": queue_id})
        return [{"bucket": r[0], "count": r[1]} for r in result.all()]

    async def get_metrics_sla(
        self,
        period_start: datetime,
        period_end: datetime,
        queue_id: Optional[int] = None,
    ) -> dict:
        """SLA compliance: tickets created in period; fr_breached_rate, resolution_breached_rate."""
        # Tickets created in period with FRT due
        stmt_fr = text("""
            SELECT
                count(*) FILTER (WHERE first_response_breached_at IS NOT NULL)::int AS breached,
                count(*) FILTER (WHERE first_response_due_at IS NOT NULL AND first_response_at IS NULL AND first_response_breached_at IS NULL)::int AS pending,
                count(*) FILTER (WHERE first_response_due_at IS NOT NULL)::int AS total_with_due
            FROM tickets
            WHERE created_at >= :start AND created_at < :end
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
        """)
        result_fr = await self.session.execute(
            stmt_fr, {"start": period_start, "end": period_end, "qid": queue_id}
        )
        row_fr = result_fr.first()
        breached_frt = row_fr[0] if row_fr else 0
        total_with_frt = row_fr[2] if row_fr else 0
        fr_breached_rate = (breached_frt / total_with_frt) if total_with_frt else None

        stmt_res = text("""
            SELECT
                count(*) FILTER (WHERE resolution_breached_at IS NOT NULL)::int AS breached,
                count(*) FILTER (WHERE resolution_due_at IS NOT NULL)::int AS total_with_due
            FROM tickets
            WHERE created_at >= :start AND created_at < :end
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
        """)
        result_res = await self.session.execute(
            stmt_res, {"start": period_start, "end": period_end, "qid": queue_id}
        )
        row_res = result_res.first()
        breached_res = row_res[0] if row_res else 0
        total_with_res = row_res[1] if row_res else 0
        resolution_breached_rate = (breached_res / total_with_res) if total_with_res else None

        return {
            "fr_breached_rate": fr_breached_rate,
            "resolution_breached_rate": resolution_breached_rate,
            "tickets_with_frt_due": total_with_frt,
            "tickets_with_resolution_due": total_with_res,
            "breached_frt": breached_frt,
            "breached_resolution": breached_res,
        }

    async def get_metrics_reopen_rate(
        self,
        period_start: datetime,
        period_end: datetime,
        queue_id: Optional[int] = None,
    ) -> dict:
        """Reopen rate: tickets resolved or closed in period with reopen_count > 0 / total resolved_or_closed in period."""
        stmt = text("""
            SELECT
                count(*)::int AS total,
                count(*) FILTER (WHERE reopen_count > 0)::int AS with_reopen
            FROM tickets
            WHERE (
                (resolved_at >= :start AND resolved_at < :end)
                OR (closed_at >= :start AND closed_at < :end)
            )
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
        """)
        result = await self.session.execute(stmt, {"start": period_start, "end": period_end, "qid": queue_id})
        row = result.first()
        total = row[0] if row else 0
        with_reopen = row[1] if row else 0
        rate = (with_reopen / total) if total else None
        return {"reopen_rate": rate, "tickets_resolved_or_closed": total, "tickets_with_reopen": with_reopen}

    async def get_metrics_top(
        self,
        period_start: datetime,
        period_end: datetime,
        queue_id: Optional[int] = None,
        top_n: int = 10,
    ) -> dict:
        """Top categories, devices, requesters by ticket count in period."""
        stmt_cat = text("""
            SELECT category_id, count(*)::int AS cnt
            FROM tickets
            WHERE created_at >= :start AND created_at < :end
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
            AND category_id IS NOT NULL
            GROUP BY category_id ORDER BY cnt DESC LIMIT :n
        """)
        result_cat = await self.session.execute(
            stmt_cat, {"start": period_start, "end": period_end, "qid": queue_id, "n": top_n}
        )
        top_categories = [{"category_id": r[0], "count": r[1]} for r in result_cat.all()]

        stmt_dev = text("""
            SELECT device_id, count(*)::int AS cnt
            FROM tickets
            WHERE created_at >= :start AND created_at < :end
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
            GROUP BY device_id ORDER BY cnt DESC LIMIT :n
        """)
        result_dev = await self.session.execute(
            stmt_dev, {"start": period_start, "end": period_end, "qid": queue_id, "n": top_n}
        )
        top_devices = [{"device_id": r[0], "count": r[1]} for r in result_dev.all()]

        stmt_req = text("""
            SELECT requester_id, count(*)::int AS cnt
            FROM tickets
            WHERE created_at >= :start AND created_at < :end
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
            AND requester_id IS NOT NULL
            GROUP BY requester_id ORDER BY cnt DESC LIMIT :n
        """)
        result_req = await self.session.execute(
            stmt_req, {"start": period_start, "end": period_end, "qid": queue_id, "n": top_n}
        )
        top_requesters = [{"requester_id": r[0], "count": r[1]} for r in result_req.all()]

        return {
            "top_categories": top_categories,
            "top_devices": top_devices,
            "top_requesters": top_requesters,
        }

    async def get_metrics_status_age(
        self,
        queue_id: Optional[int] = None,
    ) -> List[dict]:
        """For open tickets: avg(now - updated_at) per status."""
        stmt = text("""
            SELECT status,
                   count(*)::int AS count,
                   EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC' - updated_at))::int AS avg_age_seconds
            FROM tickets
            WHERE status NOT IN ('resolved', 'closed')
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
            GROUP BY status, updated_at
        """)
        # Actually we need avg per status - one row per status with avg age
        stmt = text("""
            SELECT status,
                   count(*)::int AS count,
                   avg(EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC' - updated_at)))::int AS avg_age_seconds
            FROM tickets
            WHERE status NOT IN ('resolved', 'closed')
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
            GROUP BY status
        """)
        result = await self.session.execute(stmt, {"qid": queue_id})
        return [{"status": r[0], "count": r[1], "avg_age_seconds": r[2]} for r in result.all()]

    async def get_metrics_closed_count(
        self,
        period_start: datetime,
        period_end: datetime,
        queue_id: Optional[int] = None,
    ) -> int:
        """Количество тикетов, закрытых в периоде (closed_at в [start, end))."""
        stmt = text("""
            SELECT count(*)::int FROM tickets
            WHERE closed_at >= :start AND closed_at < :end
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
        """)
        result = await self.session.execute(stmt, {"start": period_start, "end": period_end, "qid": queue_id})
        row = result.first()
        return row[0] if row else 0

    async def get_metrics_avg_resolution_minutes(
        self,
        period_start: datetime,
        period_end: datetime,
        queue_id: Optional[int] = None,
    ) -> Optional[float]:
        """Среднее время до закрытия (closed_at - created_at) в минутах по тикетам, закрытым в периоде."""
        stmt = text("""
            SELECT avg(EXTRACT(EPOCH FROM (closed_at - created_at)) / 60.0)::float
            FROM tickets
            WHERE closed_at >= :start AND closed_at < :end
            AND (CAST(:qid AS bigint) IS NULL OR queue_id = :qid)
        """)
        result = await self.session.execute(stmt, {"start": period_start, "end": period_end, "qid": queue_id})
        row = result.first()
        return row[0] if row and row[0] is not None else None

    async def get_top_queue_load(self, limit: int = 10) -> List[dict]:
        """Топ очередей по количеству открытых тикетов (для public KPI)."""
        stmt = text("""
            SELECT queue_id, count(*)::int AS open_count
            FROM tickets
            WHERE status NOT IN ('resolved', 'closed') AND queue_id IS NOT NULL
            GROUP BY queue_id
            ORDER BY open_count DESC
            LIMIT :n
        """)
        result = await self.session.execute(stmt, {"n": limit})
        return [{"queue_id": r[0], "open_count": r[1]} for r in result.all()]
