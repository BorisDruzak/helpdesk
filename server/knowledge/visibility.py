from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeItem
from app.repos.knowledge_repo import serialize_item
from knowledge.contracts import actor_visible_visibilities


class KnowledgeVisibilityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def can_read_item(self, item_id_or_slug: str, *, actor_role: str) -> bool:
        allowed = actor_visible_visibilities(actor_role)
        row = (
            await self.session.execute(
                select(KnowledgeItem).where(
                    ((KnowledgeItem.item_id == item_id_or_slug) | (KnowledgeItem.slug == item_id_or_slug)),
                    KnowledgeItem.visibility.in_(allowed),
                    KnowledgeItem.status == "published",
                )
            )
        ).scalar_one_or_none()
        return row is not None

    async def list_visible_items(self, *, actor_role: str) -> list[dict[str, Any]]:
        allowed = actor_visible_visibilities(actor_role)
        rows = (
            await self.session.execute(
                select(KnowledgeItem)
                .where(KnowledgeItem.visibility.in_(allowed), KnowledgeItem.status == "published")
                .order_by(KnowledgeItem.updated_at.desc(), KnowledgeItem.slug.asc())
            )
        ).scalars().all()
        return [serialize_item(row) for row in rows]
