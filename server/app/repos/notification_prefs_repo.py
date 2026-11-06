"""
Stage 8: Репозиторий для ticket_notification_prefs.
Default on read: при отсутствии записи возвращаются дефолтные значения.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TicketNotificationPref
from app.repos.ui_actor_memberships import ui_actor_membership_ids

DEFAULT_MUTE_INTERNAL = False
DEFAULT_MUTED_EVENT_TYPES: list = []
DEFAULT_SUPPRESS_SELF = True


class NotificationPrefsRepo:
    """CRUD для ticket_notification_prefs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, actor_id: str) -> Optional[TicketNotificationPref]:
        """Получить prefs для actor. None если записи нет."""
        actor_ids = await ui_actor_membership_ids(self.session, actor_id)
        if not actor_ids:
            return None
        # Prefer the stored account login if both historical spellings have
        # rows, so password and OIDC sessions observe the same preferences.
        stmt = select(TicketNotificationPref).where(
            TicketNotificationPref.actor_id.in_(actor_ids)
        ).order_by((TicketNotificationPref.actor_id == actor_ids[0]).desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_default(
        self,
        actor_id: str,
    ) -> tuple[bool, list, bool]:
        """
        Получить prefs или дефолты.
        Возвращает (mute_internal, muted_event_types, suppress_self).
        """
        row = await self.get(actor_id)
        if row is None:
            return (DEFAULT_MUTE_INTERNAL, list(DEFAULT_MUTED_EVENT_TYPES), DEFAULT_SUPPRESS_SELF)
        muted = row.muted_event_types
        if not isinstance(muted, list):
            muted = []
        return (bool(row.mute_internal), list(muted), bool(row.suppress_self))

    async def upsert(
        self,
        actor_id: str,
        mute_internal: Optional[bool] = None,
        muted_event_types: Optional[list] = None,
        suppress_self: Optional[bool] = None,
    ) -> TicketNotificationPref:
        """Upsert prefs. Непереданные поля сохраняют текущее значение или default."""
        now = datetime.now(timezone.utc)
        actor_ids = await ui_actor_membership_ids(self.session, actor_id)
        if not actor_ids:
            raise ValueError("Ambiguous notification preference owner")
        existing = await self.get(actor_id)
        if existing:
            if mute_internal is not None:
                existing.mute_internal = mute_internal
            if muted_event_types is not None:
                existing.muted_event_types = muted_event_types
            if suppress_self is not None:
                existing.suppress_self = suppress_self
            existing.updated_at = now
            await self.session.flush()
            return existing
        # Insert с defaults
        pref = TicketNotificationPref(
            actor_id=actor_ids[0],
            mute_internal=mute_internal if mute_internal is not None else DEFAULT_MUTE_INTERNAL,
            muted_event_types=muted_event_types if muted_event_types is not None else DEFAULT_MUTED_EVENT_TYPES,
            suppress_self=suppress_self if suppress_self is not None else DEFAULT_SUPPRESS_SELF,
            updated_at=now,
        )
        self.session.add(pref)
        await self.session.flush()
        return pref
