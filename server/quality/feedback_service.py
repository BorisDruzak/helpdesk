from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update

from app.db.models import Ticket, TicketEvent, TicketFeedback
from quality.contracts import validate_feedback_payload
from quality.improvement_service import ContinuousImprovementService
from quality.policy_service import QualityPolicyService
from quality.review_service import QualityReviewService
from quality.serializers import feedback_to_dict


DEFAULT_FEEDBACK_WINDOW_DAYS = 14


class TicketFeedbackService:
    def __init__(self, session) -> None:
        self.session = session

    async def submit_feedback(self, payload: dict[str, Any], *, actor_id: str | None, actor_role: str | None) -> dict[str, Any]:
        data = validate_feedback_payload(payload)
        ticket = await self.session.get(Ticket, data["ticket_id"])
        if ticket is None:
            raise ValueError("ticket not found")
        if ticket.status not in {"resolved", "closed"}:
            raise ValueError("feedback allowed only for resolved or closed tickets")
        self._validate_feedback_window(ticket)
        if actor_role in {"requester", "user"} and actor_id and actor_id != ticket.requester_id:
            raise ValueError("requester cannot submit feedback for another ticket")

        await self.session.execute(
            update(TicketFeedback)
            .where(TicketFeedback.ticket_id == ticket.ticket_id)
            .where(TicketFeedback.requester_id == ticket.requester_id)
            .where(TicketFeedback.is_latest.is_(True))
            .values(is_latest=False, updated_at=datetime.now(timezone.utc))
        )
        now = datetime.now(timezone.utc)
        feedback = TicketFeedback(
            feedback_id=str(uuid.uuid4()),
            ticket_id=ticket.ticket_id,
            requester_id=ticket.requester_id,
            actor_id=actor_id,
            actor_role=actor_role,
            rating=data["rating"],
            sentiment=data["sentiment"],
            resolution_confirmed=data["resolution_confirmed"],
            problem_resolved=data["problem_resolved"],
            response_time_satisfaction=data["response_time_satisfaction"],
            communication_satisfaction=data["communication_satisfaction"],
            quality_satisfaction=data["quality_satisfaction"],
            reason_codes=data["reason_codes"],
            comment=data["comment"],
            visibility="support_internal" if data["source_surface"] == "support_entered" else data["visibility"],
            source_surface=data["source_surface"],
            service_code=ticket.service_code,
            offering_code=ticket.offering_code,
            submitted_at=now,
            updated_at=now,
            metadata_json=data["metadata"],
            is_latest=True,
        )
        self.session.add(feedback)
        await self.session.flush()
        await self._record_event(ticket, feedback, actor_id=actor_id, actor_role=actor_role)

        low_csat = await self._is_low_csat(ticket, feedback)
        review = None
        if low_csat:
            review = await QualityReviewService(self.session).ensure_review_for_signal(
                ticket.ticket_id,
                review_type="low_csat",
                severity="high" if feedback.rating <= 2 else "medium",
                actor_id=actor_id,
                trigger_payload={"feedback_id": feedback.feedback_id, "rating": feedback.rating},
            )

        improvement_action_id = None
        if "knowledge_article_failed" in (feedback.reason_codes or []):
            action = await ContinuousImprovementService(self.session).create_action(
                {
                    "source_kind": "csat",
                    "ticket_id": ticket.ticket_id,
                    "feedback_id": feedback.feedback_id,
                    "source_ref": data["metadata"].get("knowledge_item_id"),
                    "service_code": ticket.service_code,
                    "offering_code": ticket.offering_code,
                    "action_type": "update_kb_article" if data["metadata"].get("knowledge_item_id") else "create_kb_article",
                    "title": "Improve knowledge after negative CSAT",
                    "description": "Requester feedback indicates the knowledge article or self-service path did not resolve the issue.",
                    "priority": "high",
                },
                actor_id="quality-system",
            )
            improvement_action_id = action["action_id"]

        result = feedback_to_dict(feedback)
        result.update(
            {
                "ok": True,
                "message": "Спасибо, оценка сохранена",
                "reopen_available": low_csat,
                "review_id": review["review_id"] if review else None,
                "improvement_action_id": improvement_action_id,
            }
        )
        return result

    def _validate_feedback_window(self, ticket: Ticket) -> None:
        anchor = ticket.closed_at or ticket.resolved_at
        if anchor is None:
            return
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - anchor > timedelta(days=DEFAULT_FEEDBACK_WINDOW_DAYS):
            raise ValueError("feedback window is closed")

    async def _is_low_csat(self, ticket: Ticket, feedback: TicketFeedback) -> bool:
        policy = await QualityPolicyService(self.session).effective_policy(
            service_code=ticket.service_code,
            offering_code=ticket.offering_code,
            queue_id=ticket.queue_id,
        )
        threshold = int(policy.get("low_csat_threshold", 3))
        return feedback.rating <= threshold or feedback.problem_resolved is False

    async def _record_event(self, ticket: Ticket, feedback: TicketFeedback, *, actor_id: str | None, actor_role: str | None) -> None:
        self.session.add(
            TicketEvent(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=None,
                event_type="feedback_submitted",
                payload={
                    "feedback_id": feedback.feedback_id,
                    "rating": feedback.rating,
                    "sentiment": feedback.sentiment,
                    "reason_codes": feedback.reason_codes,
                    "source_surface": feedback.source_surface,
                    "actor_id": actor_id,
                    "actor_role": actor_role,
                },
                trace_id=str(uuid.uuid4()),
            )
        )
