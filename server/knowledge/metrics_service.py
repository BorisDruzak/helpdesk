from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeFeedbackEvent


class KnowledgeMetricsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def summary(self, *, actor_role: str = "admin") -> dict[str, Any]:
        rows = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent.event_type, func.count(KnowledgeFeedbackEvent.event_id)).group_by(KnowledgeFeedbackEvent.event_type)
            )
        ).all()
        counts = {event_type: int(count) for event_type, count in rows}
        deflected = counts.get("deflected", 0)
        created_after_view = counts.get("ticket_created_after_view", 0)
        helpful = counts.get("helpful", 0)
        not_helpful = counts.get("not_helpful", 0)
        viewed = counts.get("viewed", 0)
        suggested = counts.get("suggested", 0)
        feedback_total = sum(counts.values())
        deflection_denominator = deflected + created_after_view
        helpfulness_denominator = helpful + not_helpful
        return {
            "deflection": {
                "deflected_count": deflected,
                "ticket_created_after_view_count": created_after_view,
                "deflection_rate": (deflected / deflection_denominator) if deflection_denominator else 0.0,
            },
            "helpfulness": {
                "helpful_count": helpful,
                "not_helpful_count": not_helpful,
                "helpfulness_rate": (helpful / helpfulness_denominator) if helpfulness_denominator else 0.0,
            },
            "totals": {
                "suggested_count": suggested,
                "viewed_count": viewed,
                "feedback_count": feedback_total,
            },
            "events_by_type": counts,
            "deflection_events": deflected,
            "helpful_events": helpful,
            "not_helpful_events": not_helpful,
            "ticket_created_after_view_events": created_after_view,
        }
