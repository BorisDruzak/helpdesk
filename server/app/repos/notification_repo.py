"""
Репозиторий для ticket_notifications (Stage 6). In-app уведомления.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TicketNotification


class NotificationRepo:
    """CRUD для таблицы ticket_notifications."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        actor_id: str,
        ticket_id: str,
        event_type: str,
        payload: dict,
    ) -> TicketNotification:
        """Создать запись уведомления."""
        n = TicketNotification(
            actor_id=actor_id,
            ticket_id=ticket_id,
            event_type=event_type,
            payload=payload or {},
        )
        self.session.add(n)
        await self.session.flush()
        return n

    async def list_by_actor(
        self,
        actor_id: str,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> List[TicketNotification]:
        """Список уведомлений пользователя, новые первые."""
        stmt = (
            select(TicketNotification)
            .where(TicketNotification.actor_id == actor_id)
            .order_by(TicketNotification.created_at.desc())
        )
        if unread_only:
            stmt = stmt.where(TicketNotification.is_read.is_(False))
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, notification_id: int, actor_id: str) -> Optional[TicketNotification]:
        """Получить уведомление по id, только если оно принадлежит actor_id."""
        stmt = select(TicketNotification).where(
            TicketNotification.id == notification_id,
            TicketNotification.actor_id == actor_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def mark_read(self, notification_id: int, actor_id: str) -> bool:
        """Отметить уведомление прочитанным. Возвращает True если обновлено."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(TicketNotification)
            .where(
                TicketNotification.id == notification_id,
                TicketNotification.actor_id == actor_id,
            )
            .values(is_read=True, read_at=now)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def mark_all_read(self, actor_id: str) -> int:
        """Отметить все уведомления пользователя прочитанными. Возвращает количество обновлённых."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(TicketNotification)
            .where(TicketNotification.actor_id == actor_id)
            .where(TicketNotification.is_read.is_(False))
            .values(is_read=True, read_at=now)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def unread_count(self, actor_id: str) -> int:
        """Количество непрочитанных уведомлений пользователя."""
        stmt = select(func.count(TicketNotification.id)).where(
            TicketNotification.actor_id == actor_id,
            TicketNotification.is_read.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
