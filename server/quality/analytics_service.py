from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    ContinuousImprovementAction,
    KnowledgeFeedbackEvent,
    ServiceQualitySnapshot,
    Ticket,
    TicketFeedback,
    TicketQualityReview,
    TicketReopenEvent,
)
from quality.serializers import primitive


class ServiceQualityAnalyticsService:
    def __init__(self, session) -> None:
        self.session = session

    async def service_quality(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
        bucket: str,
        recompute_snapshot: bool = False,
    ) -> dict[str, Any]:
        await self.session.flush()
        groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(self._empty_group)

        tickets = (
            await self.session.execute(
                select(Ticket).where(Ticket.created_at <= period_end)
            )
        ).scalars().all()
        ticket_ids: set[str] = set()
        for ticket in tickets:
            if not self._in_period(ticket, period_start, period_end):
                continue
            key = self._key(ticket.service_code, ticket.offering_code)
            row = groups[key]
            row["service_code"], row["offering_code"] = key
            row["ticket_count"] += 1
            ticket_ids.add(ticket.ticket_id)
            if ticket.status == "resolved" or ticket.resolved_at:
                row["resolved_count"] += 1
            if ticket.status == "closed" or ticket.closed_at:
                row["closed_count"] += 1
            if ticket.first_response_breached_at or ticket.resolution_breached_at:
                row["sla_breach_count"] += 1
            if ticket.first_response_breached_at:
                row["first_response_breach_count"] += 1
            if ticket.resolution_breached_at:
                row["resolution_breach_count"] += 1
            attempts = (ticket.custom_fields or {}).get("knowledge_attempts") if isinstance(ticket.custom_fields, dict) else None
            if isinstance(attempts, list):
                row["knowledge_attempt_count"] += len(attempts)

        feedback_rows = (
            await self.session.execute(
                select(TicketFeedback).where(TicketFeedback.submitted_at >= period_start, TicketFeedback.submitted_at <= period_end)
            )
        ).scalars().all()
        csat_values: dict[tuple[str, str], list[int]] = defaultdict(list)
        for feedback in feedback_rows:
            key = self._key(feedback.service_code, feedback.offering_code)
            row = groups[key]
            row["service_code"], row["offering_code"] = key
            row["feedback_count"] += 1
            csat_values[key].append(int(feedback.rating))
            if feedback.rating <= 3 or feedback.problem_resolved is False:
                row["negative_csat_count"] += 1

        reopen_rows = (
            await self.session.execute(
                select(TicketReopenEvent).where(TicketReopenEvent.created_at >= period_start, TicketReopenEvent.created_at <= period_end)
            )
        ).scalars().all()
        for reopen in reopen_rows:
            key = self._key(reopen.service_code, reopen.offering_code)
            row = groups[key]
            row["service_code"], row["offering_code"] = key
            row["reopen_count"] += 1

        reviews = (await self.session.execute(select(TicketQualityReview))).scalars().all()
        for review in reviews:
            if not (period_start <= review.created_at <= period_end):
                continue
            key = self._key(review.service_code, review.offering_code)
            row = groups[key]
            row["service_code"], row["offering_code"] = key
            row["qa_review_count"] += 1
            if review.status in {"failed", "action_required"}:
                row["qa_failed_count"] += 1

        actions = (await self.session.execute(select(ContinuousImprovementAction))).scalars().all()
        for action in actions:
            if not (period_start <= action.created_at <= period_end):
                continue
            key = self._key(action.service_code, action.offering_code)
            row = groups[key]
            row["service_code"], row["offering_code"] = key
            row["improvement_action_count"] += 1

        knowledge_events = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent).where(KnowledgeFeedbackEvent.created_at >= period_start, KnowledgeFeedbackEvent.created_at <= period_end)
            )
        ).scalars().all()
        for event in knowledge_events:
            key = self._key(event.service_code, event.offering_code)
            row = groups[key]
            row["service_code"], row["offering_code"] = key
            if event.event_type == "ticket_created_after_view":
                row["ticket_after_failed_knowledge_count"] += 1
            if event.event_type == "deflected":
                row["deflection_count"] = (row["deflection_count"] or 0) + 1

        result_rows = []
        for key, row in groups.items():
            values = csat_values.get(key) or []
            row["avg_csat"] = round(sum(values) / len(values), 2) if values else None
            denominator = row["resolved_count"] or row["closed_count"] or row["ticket_count"]
            row["reopen_rate"] = round(row["reopen_count"] / denominator, 4) if denominator else 0.0
            row["sla_breach_rate"] = round(row["sla_breach_count"] / (row["ticket_count"] or 1), 4) if row["ticket_count"] else 0.0
            result_rows.append(row)
            if recompute_snapshot:
                self.session.add(self._snapshot(row, period_start, period_end, bucket))
        if recompute_snapshot:
            await self.session.flush()
        return {"period_start": period_start.isoformat(), "period_end": period_end.isoformat(), "bucket": bucket, "rows": primitive(result_rows)}

    def _empty_group(self) -> dict[str, Any]:
        return {
            "service_code": "legacy",
            "offering_code": "uncategorized",
            "ticket_count": 0,
            "resolved_count": 0,
            "closed_count": 0,
            "feedback_count": 0,
            "avg_csat": None,
            "negative_csat_count": 0,
            "reopen_count": 0,
            "reopen_rate": 0.0,
            "sla_breach_count": 0,
            "sla_breach_rate": 0.0,
            "first_response_breach_count": 0,
            "resolution_breach_count": 0,
            "knowledge_attempt_count": 0,
            "ticket_after_failed_knowledge_count": 0,
            "deflection_count": 0,
            "qa_review_count": 0,
            "qa_failed_count": 0,
            "improvement_action_count": 0,
        }

    def _key(self, service_code: str | None, offering_code: str | None) -> tuple[str, str]:
        return (service_code or "legacy", offering_code or "uncategorized")

    def _in_period(self, ticket: Ticket, start: datetime, end: datetime) -> bool:
        for value in (ticket.closed_at, ticket.resolved_at, ticket.created_at):
            if value and start <= value <= end:
                return True
        return False

    def _snapshot(self, row: dict[str, Any], period_start: datetime, period_end: datetime, bucket: str) -> ServiceQualitySnapshot:
        now = datetime.now(timezone.utc)
        return ServiceQualitySnapshot(
            snapshot_id=str(uuid.uuid4()),
            period_start=period_start,
            period_end=period_end,
            bucket=bucket,
            service_code=row["service_code"],
            offering_code=row["offering_code"],
            ticket_count=row["ticket_count"],
            resolved_count=row["resolved_count"],
            closed_count=row["closed_count"],
            feedback_count=row["feedback_count"],
            avg_csat=row["avg_csat"],
            negative_csat_count=row["negative_csat_count"],
            reopen_count=row["reopen_count"],
            reopen_rate=row["reopen_rate"],
            sla_breach_count=row["sla_breach_count"],
            sla_breach_rate=row["sla_breach_rate"],
            first_response_breach_count=row["first_response_breach_count"],
            resolution_breach_count=row["resolution_breach_count"],
            knowledge_attempt_count=row["knowledge_attempt_count"],
            ticket_after_failed_knowledge_count=row["ticket_after_failed_knowledge_count"],
            deflection_count=row["deflection_count"],
            qa_review_count=row["qa_review_count"],
            qa_failed_count=row["qa_failed_count"],
            improvement_action_count=row["improvement_action_count"],
            computed_at=now,
            metadata_json={},
        )
