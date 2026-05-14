from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeFeedbackEvent


class KnowledgeMetricsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def summary(self) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent.event_type, func.count(KnowledgeFeedbackEvent.event_id)).group_by(KnowledgeFeedbackEvent.event_type)
            )
        ).all()
        counts = {event_type: int(count) for event_type, count in rows}
        return {
            "deflection": {
                "deflected_count": counts.get("deflected", 0),
                "ticket_created_after_view_count": counts.get("ticket_created_after_view", 0),
            },
            "helpfulness": {
                "helpful_count": counts.get("helpful", 0),
                "not_helpful_count": counts.get("not_helpful", 0),
            },
        }
