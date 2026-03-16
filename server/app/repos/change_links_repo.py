"""
Stage 7: Репозиторий для ticket_change_links.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TicketChangeLink


class ChangeLinksRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, ticket_id: str, change_ref: str, change_system: str, created_by: str) -> TicketChangeLink:
        link = TicketChangeLink(
            ticket_id=ticket_id,
            change_ref=change_ref,
            change_system=change_system,
            created_by=created_by,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def list_by_ticket(self, ticket_id: str) -> List[TicketChangeLink]:
        stmt = (
            select(TicketChangeLink)
            .where(TicketChangeLink.ticket_id == ticket_id)
            .order_by(TicketChangeLink.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, link_id: int, ticket_id: str) -> Optional[TicketChangeLink]:
        stmt = select(TicketChangeLink).where(
            TicketChangeLink.id == link_id,
            TicketChangeLink.ticket_id == ticket_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, link_id: int, ticket_id: str) -> bool:
        stmt = delete(TicketChangeLink).where(
            TicketChangeLink.id == link_id,
            TicketChangeLink.ticket_id == ticket_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0
