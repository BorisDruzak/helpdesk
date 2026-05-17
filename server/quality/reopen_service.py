from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.models import TicketEvent, TicketReopenEvent
from app.repos.ticket_events_repo import TicketEventsRepo
from quality.contracts import validate_reopen_reason
from quality.review_service import QualityReviewService
from quality.serializers import primitive
from tickets.workflow_service import TicketWorkflowService


class TicketReopenService:
    def __init__(self, session) -> None:
        self.session = session
        self.repo = TicketEventsRepo(session)

    async def reopen_ticket(
        self,
        ticket_id: str,
        *,
        reason_code: str,
        reason_comment: str | None,
        actor_id: str | None,
        actor_role: str | None,
        linked_feedback_id: str | None = None,
        linked_knowledge_item_id: str | None = None,
    ) -> dict[str, Any]:
        code = validate_reopen_reason(reason_code, reason_comment)
        ticket = await self.repo.get_ticket(ticket_id)
        if ticket is None:
            raise ValueError("ticket not found")
        previous_status = ticket.status
        if previous_status not in {"resolved", "closed"}:
            raise ValueError("ticket can be reopened only from resolved or closed")
        target_status = "in_progress"
        workflow = TicketWorkflowService(self.session, self.repo)
        transition = await workflow.apply_status_transition(
            ticket_id=ticket.ticket_id,
            from_status=previous_status,
            to_status=target_status,
            actor_id=actor_id or "quality-requester",
            actor_role=actor_role or "requester",
            reason=code,
            public_comment=reason_comment,
            source="quality_reopen",
        )
        reopened = await self.repo.get_ticket(ticket_id)
        reopen_row = TicketReopenEvent(
            reopen_id=str(uuid.uuid4()),
            ticket_id=ticket.ticket_id,
            reopened_by_actor_id=actor_id,
            reopened_by_role=actor_role,
            previous_status=previous_status,
            new_status=target_status,
            reason_code=code,
            reason_comment=str(reason_comment or "").strip() or None,
            linked_feedback_id=linked_feedback_id,
            linked_knowledge_item_id=linked_knowledge_item_id,
            service_code=ticket.service_code,
            offering_code=ticket.offering_code,
            created_at=datetime.now(timezone.utc),
            metadata_json={},
        )
        self.session.add(reopen_row)
        reopened.reopen_count = int(getattr(reopened, "reopen_count", 0) or 0) + 1
        self.session.add(
            TicketEvent(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=None,
                event_type="ticket_reopened",
                payload={
                    "reopen_id": reopen_row.reopen_id,
                    "previous_status": previous_status,
                    "new_status": target_status,
                    "reason_code": code,
                    "reason_comment": reopen_row.reason_comment,
                    "linked_feedback_id": linked_feedback_id,
                    "actor_id": actor_id,
                    "actor_role": actor_role,
                },
                trace_id=str(uuid.uuid4()),
            )
        )
        review = await QualityReviewService(self.session).ensure_review_for_signal(
            ticket.ticket_id,
            review_type="reopened",
            severity="high" if previous_status == "closed" else "medium",
            actor_id=actor_id,
            trigger_payload={"reopen_id": reopen_row.reopen_id, "reason_code": code},
        )
        await self.session.flush()
        return {
            "ok": True,
            "ticket_id": ticket.ticket_id,
            "status": target_status,
            "reopen_id": reopen_row.reopen_id,
            "linked_feedback_id": linked_feedback_id,
            "review_id": review["review_id"],
            "transition": primitive(transition.get("event_payload") or {}),
        }

