from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ContinuousImprovementAction, Ticket, TicketQualityReview, TicketReopenEvent
from quality.analytics_service import ServiceQualityAnalyticsService
from quality.feedback_service import TicketFeedbackService
from quality.improvement_service import ContinuousImprovementService
from quality.reopen_service import TicketReopenService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_p3_quality_smoke_low_csat_reopen_action_and_private_analytics(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-quality-smoke",
                title="VPN issue",
                description="VPN",
                status="resolved",
                requester_id="secret-requester",
                service_code="network",
                offering_code="network.vpn_issue",
                resolved_at=now,
            )
        )
        feedback = await TicketFeedbackService(session).submit_feedback(
            {
                "ticket_id": ticket_id,
                "rating": 2,
                "problem_resolved": False,
                "reason_codes": ["not_resolved"],
                "comment": "contains requester details",
                "source_surface": "requester_portal",
            },
            actor_id="secret-requester",
            actor_role="requester",
        )
        reopened = await TicketReopenService(session).reopen_ticket(
            ticket_id,
            reason_code="problem_returned",
            reason_comment="The issue returned",
            actor_id="secret-requester",
            actor_role="requester",
            linked_feedback_id=feedback["feedback_id"],
        )
        action = await ContinuousImprovementService(session).create_action(
            {
                "source_kind": "qa_review",
                "ticket_id": ticket_id,
                "source_ref": reopened["reopen_id"],
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "action_type": "process_review",
                "title": "Review repeated VPN resolution",
                "description": "P3 smoke action",
                "priority": "high",
            },
            actor_id="qa-lead",
        )
        await ContinuousImprovementService(session).update_action(
            action["action_id"],
            {"status": "assigned", "owner_actor_id": "quality-owner"},
            actor_id="qa-lead",
        )
        closed = await ContinuousImprovementService(session).close_action(
            action["action_id"],
            outcome_notes="Reviewed and updated the playbook.",
            actor_id="quality-owner",
        )
        summary = await ServiceQualityAnalyticsService(session).service_quality(
            period_start=now - timedelta(days=1),
            period_end=now + timedelta(days=1),
            bucket="day",
        )
        await session.commit()

        reviews = (await session.execute(select(TicketQualityReview).where(TicketQualityReview.ticket_id == ticket_id))).scalars().all()
        reopen_events = (await session.execute(select(TicketReopenEvent).where(TicketReopenEvent.ticket_id == ticket_id))).scalars().all()
        action_row = await session.get(ContinuousImprovementAction, action["action_id"])

    assert feedback["reopen_available"] is True
    assert {review.review_type for review in reviews} >= {"low_csat", "reopened"}
    assert len(reopen_events) == 1
    assert closed["status"] == "done"
    assert action_row is not None
    assert action_row.owner_actor_id == "quality-owner"
    assert "secret-requester" not in repr(summary)
    assert "contains requester details" not in repr(summary)
