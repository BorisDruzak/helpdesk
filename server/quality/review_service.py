from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import Ticket, TicketQualityReview
from quality.contracts import QUALITY_REVIEW_TYPES, REVIEW_SEVERITIES
from quality.policy_service import QualityPolicyService
from quality.serializers import review_to_dict


class QualityReviewService:
    def __init__(self, session) -> None:
        self.session = session

    async def create_review(
        self,
        ticket_id: str,
        *,
        review_type: str,
        severity: str,
        actor_id: str | None,
        trigger_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if review_type not in QUALITY_REVIEW_TYPES:
            raise ValueError("review_type is invalid")
        if severity not in REVIEW_SEVERITIES:
            raise ValueError("severity is invalid")
        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError("ticket not found")
        policy = await QualityPolicyService(self.session).effective_policy(
            service_code=ticket.service_code,
            offering_code=ticket.offering_code,
            queue_id=ticket.queue_id,
        )
        now = datetime.now(timezone.utc)
        row = TicketQualityReview(
            review_id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            review_type=review_type,
            severity=severity,
            status="open",
            queue_id=ticket.queue_id,
            service_code=ticket.service_code,
            offering_code=ticket.offering_code,
            due_at=now + timedelta(hours=int(policy.get("qa_due_hours", 72))),
            created_at=now,
            updated_at=now,
            trigger_payload=trigger_payload or {"created_by": actor_id},
            findings_json={},
            metadata_json={},
        )
        self.session.add(row)
        await self.session.flush()
        return review_to_dict(row)

    async def ensure_review_for_signal(
        self,
        ticket_id: str,
        *,
        review_type: str,
        severity: str,
        actor_id: str | None,
        trigger_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = (
            await self.session.execute(
                select(TicketQualityReview)
                .where(TicketQualityReview.ticket_id == ticket_id)
                .where(TicketQualityReview.review_type == review_type)
                .where(TicketQualityReview.status.in_(["open", "assigned", "in_review", "action_required"]))
                .order_by(TicketQualityReview.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return review_to_dict(existing)
        return await self.create_review(
            ticket_id,
            review_type=review_type,
            severity=severity,
            actor_id=actor_id,
            trigger_payload=trigger_payload,
        )

    async def assign_review(self, review_id: str, *, assigned_to_actor_id: str, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(review_id)
        row.assigned_to_actor_id = str(assigned_to_actor_id or "").strip() or None
        if not row.assigned_to_actor_id:
            raise ValueError("assigned_to_actor_id is required")
        row.status = "assigned"
        row.owner_actor_id = row.assigned_to_actor_id
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return review_to_dict(row)

    async def start_review(self, review_id: str, *, actor_id: str | None) -> dict[str, Any]:
        row = await self._get(review_id)
        row.status = "in_review"
        row.reviewer_actor_id = actor_id
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return review_to_dict(row)

    async def complete_review(
        self,
        review_id: str,
        *,
        findings: dict[str, Any],
        score: int,
        actor_id: str | None,
    ) -> dict[str, Any]:
        if score < 0 or score > 100:
            raise ValueError("score must be 0..100")
        row = await self._get(review_id)
        row.findings_json = dict(findings or {})
        row.score = score
        row.reviewer_actor_id = actor_id
        row.status = "action_required" if row.findings_json.get("improvement_needed") or score < 70 else "passed"
        row.closed_at = datetime.now(timezone.utc) if row.status in {"passed", "failed", "dismissed"} else None
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return review_to_dict(row)

    async def dismiss_review(self, review_id: str, *, actor_id: str | None, reason: str | None = None) -> dict[str, Any]:
        row = await self._get(review_id)
        row.status = "dismissed"
        row.closed_at = datetime.now(timezone.utc)
        row.metadata_json = {**(row.metadata_json or {}), "dismissed_by": actor_id, "dismiss_reason": reason}
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return review_to_dict(row)

    async def list_reviews(self, *, status: str | None = None) -> list[dict[str, Any]]:
        stmt = select(TicketQualityReview).order_by(TicketQualityReview.created_at.desc())
        if status:
            stmt = stmt.where(TicketQualityReview.status == status)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [review_to_dict(row) for row in rows]

    async def _get(self, review_id: str) -> TicketQualityReview:
        row = await self.session.get(TicketQualityReview, review_id)
        if row is None:
            raise ValueError("review not found")
        return row

