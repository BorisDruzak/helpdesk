"""
Stage 9: Репозиторий для ticket_admin_audit — аудит изменений admin-config.
"""
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TicketAdminAudit


class TicketAdminAuditRepo:
    """Запись и чтение audit-событий admin-config."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str,
        actor_role: str,
        before_json: Optional[dict] = None,
        after_json: Optional[dict] = None,
        trace_id: Optional[str] = None,
    ) -> TicketAdminAudit:
        rec = TicketAdminAudit(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=before_json,
            after_json=after_json,
            trace_id=trace_id,
        )
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def list_audit(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TicketAdminAudit]:
        stmt = select(TicketAdminAudit)
        if entity_type is not None:
            stmt = stmt.where(TicketAdminAudit.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(TicketAdminAudit.entity_id == str(entity_id))
        if actor_id is not None:
            stmt = stmt.where(TicketAdminAudit.actor_id == actor_id)
        stmt = stmt.order_by(TicketAdminAudit.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
