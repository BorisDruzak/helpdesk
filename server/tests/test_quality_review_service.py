from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketQualityReview
from quality.review_service import QualityReviewService


@pytest.mark.asyncio
async def test_review_lifecycle_assign_start_complete_and_dismiss(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=f"dev-{ticket_id.replace('-', '')[:28]}",
                title="Quality review target",
                description="target",
                status="resolved",
                requester_id="requester-1",
                service_code="network",
                offering_code="network.vpn_issue",
            )
        )
        service = QualityReviewService(session)
        review = await service.create_review(ticket_id, review_type="missing_evidence", severity="high", actor_id="qa-lead")
        await service.assign_review(review["review_id"], assigned_to_actor_id="qa-1", actor_id="qa-lead")
        await service.start_review(review["review_id"], actor_id="qa-1")
        completed = await service.complete_review(
            review["review_id"],
            findings={
                "evidence_present": False,
                "requester_communication_ok": True,
                "improvement_needed": True,
            },
            score=62,
            actor_id="qa-1",
        )
        await session.commit()

        row = await session.get(TicketQualityReview, review["review_id"])

    assert completed["status"] == "action_required"
    assert row.status == "action_required"
    assert row.assigned_to_actor_id == "qa-1"
    assert row.score == 62
    assert row.findings_json["improvement_needed"] is True


@pytest.mark.asyncio
async def test_review_trigger_deduplicates_open_review(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(Ticket(ticket_id=ticket_id, device_id="device-review-dedup", title="T", description="D", status="resolved", requester_id="requester-1"))
        service = QualityReviewService(session)
        first = await service.ensure_review_for_signal(ticket_id, review_type="reopened", severity="medium", actor_id="system")
        second = await service.ensure_review_for_signal(ticket_id, review_type="reopened", severity="medium", actor_id="system")
        await session.commit()

    assert first["review_id"] == second["review_id"]
