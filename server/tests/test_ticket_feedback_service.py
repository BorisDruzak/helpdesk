from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketFeedback, TicketQualityReview
from quality.feedback_service import TicketFeedbackService


def _ticket(ticket_id: str, *, status: str = "resolved", requester_id: str = "requester-1") -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        ticket_id=ticket_id,
        device_id=f"dev-{ticket_id.replace('-', '')[:28]}",
        title="Resolved VPN issue",
        description="VPN does not connect",
        status=status,
        requester_id=requester_id,
        service_code="network",
        offering_code="network.vpn_issue",
        request_type="incident",
        reporting_category="network",
        resolved_at=now,
        closed_at=now if status == "closed" else None,
    )


@pytest.mark.asyncio
async def test_requester_low_csat_creates_latest_feedback_event_and_review(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_ticket(ticket_id))
        await session.commit()

        result = await TicketFeedbackService(session).submit_feedback(
            {
                "ticket_id": ticket_id,
                "rating": 2,
                "problem_resolved": False,
                "resolution_confirmed": False,
                "reason_codes": ["not_resolved", "knowledge_article_failed"],
                "comment": "Problem returned after reboot",
                "source_surface": "requester_portal",
            },
            actor_id="requester-1",
            actor_role="requester",
        )
        await session.commit()

        feedback = await session.get(TicketFeedback, result["feedback_id"])
        reviews = (
            await session.execute(
                select(TicketQualityReview).where(
                    TicketQualityReview.ticket_id == ticket_id,
                    TicketQualityReview.review_type == "low_csat",
                    TicketQualityReview.status == "open",
                )
            )
        ).scalars().all()

    assert feedback is not None
    assert feedback.rating == 2
    assert feedback.sentiment == "negative"
    assert feedback.service_code == "network"
    assert feedback.offering_code == "network.vpn_issue"
    assert feedback.is_latest is True
    assert result["reopen_available"] is True
    assert len(reviews) == 1


@pytest.mark.asyncio
async def test_feedback_window_blocks_late_requester_updates(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    ticket = _ticket(ticket_id, status="closed")
    ticket.closed_at = datetime.now(timezone.utc) - timedelta(days=30)
    async with session_maker() as session:
        session.add(ticket)
        await session.commit()

        with pytest.raises(ValueError, match="feedback window"):
            await TicketFeedbackService(session).submit_feedback(
                {"ticket_id": ticket_id, "rating": 4, "source_surface": "requester_portal"},
                actor_id="requester-1",
                actor_role="requester",
            )


@pytest.mark.asyncio
async def test_second_feedback_marks_previous_not_latest(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_ticket(ticket_id))
        service = TicketFeedbackService(session)
        first = await service.submit_feedback(
            {"ticket_id": ticket_id, "rating": 5, "source_surface": "requester_portal"},
            actor_id="requester-1",
            actor_role="requester",
        )
        second = await service.submit_feedback(
            {"ticket_id": ticket_id, "rating": 3, "reason_codes": ["not_resolved"], "source_surface": "requester_portal"},
            actor_id="requester-1",
            actor_role="requester",
        )
        await session.commit()

        first_row = await session.get(TicketFeedback, first["feedback_id"])
        second_row = await session.get(TicketFeedback, second["feedback_id"])

    assert first_row.is_latest is False
    assert second_row.is_latest is True


@pytest.mark.asyncio
async def test_latest_feedback_db_invariant_rejects_two_latest_rows(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    requester_id = "requester-1"
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        session.add(_ticket(ticket_id, requester_id=requester_id))
        await session.flush()
        session.add(
            TicketFeedback(
                feedback_id=str(uuid.uuid4()),
                ticket_id=ticket_id,
                requester_id=requester_id,
                actor_role="requester",
                rating=4,
                sentiment="positive",
                reason_codes=[],
                visibility="requester_visible",
                source_surface="requester_portal",
                submitted_at=now,
                is_latest=True,
            )
        )
        await session.flush()
        session.add(
            TicketFeedback(
                feedback_id=str(uuid.uuid4()),
                ticket_id=ticket_id,
                requester_id=requester_id,
                actor_role="requester",
                rating=2,
                sentiment="negative",
                reason_codes=["not_resolved"],
                visibility="requester_visible",
                source_surface="requester_portal",
                submitted_at=now,
                is_latest=True,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_concurrent_feedback_submissions_leave_exactly_one_latest(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_ticket(ticket_id))
        await session.commit()

    async def submit(rating: int) -> str:
        async with session_maker() as session:
            result = await TicketFeedbackService(session).submit_feedback(
                {"ticket_id": ticket_id, "rating": rating, "source_surface": "requester_portal"},
                actor_id="requester-1",
                actor_role="requester",
            )
            await session.commit()
            return result["feedback_id"]

    feedback_ids = await asyncio.gather(submit(5), submit(2))

    async with session_maker() as session:
        rows = (
            await session.execute(
                select(TicketFeedback).where(
                    TicketFeedback.ticket_id == ticket_id,
                    TicketFeedback.feedback_id.in_(feedback_ids),
                )
            )
        ).scalars().all()

    assert len(rows) == 2
    assert sum(1 for row in rows if row.is_latest) == 1
