from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketQualityReview, TicketReopenEvent
from quality.reopen_service import TicketReopenService


def _closed_ticket(ticket_id: str) -> Ticket:
    now = datetime.now(timezone.utc)
    return Ticket(
        ticket_id=ticket_id,
        device_id=f"dev-{ticket_id.replace('-', '')[:28]}",
        title="Printer issue",
        description="Printer offline",
        status="closed",
        requester_id="requester-1",
        service_code="workplace",
        offering_code="workplace.printer_issue",
        resolved_at=now,
        closed_at=now,
        reopen_count=0,
    )


@pytest.mark.asyncio
async def test_reopen_requires_structured_reason_and_creates_review(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_closed_ticket(ticket_id))
        await session.commit()

        result = await TicketReopenService(session).reopen_ticket(
            ticket_id,
            reason_code="problem_returned",
            reason_comment="After closure the printer went offline again",
            actor_id="requester-1",
            actor_role="requester",
        )
        await session.commit()

        ticket = await session.get(Ticket, ticket_id)
        reopen_event = (
            await session.execute(select(TicketReopenEvent).where(TicketReopenEvent.ticket_id == ticket_id))
        ).scalar_one()
        review = (
            await session.execute(
                select(TicketQualityReview).where(
                    TicketQualityReview.ticket_id == ticket_id,
                    TicketQualityReview.review_type == "reopened",
                    TicketQualityReview.status == "open",
                )
            )
        ).scalar_one()

    assert result["status"] == "in_progress"
    assert ticket.status == "in_progress"
    assert ticket.reopen_count == 1
    assert reopen_event.previous_status == "closed"
    assert reopen_event.new_status == "in_progress"
    assert reopen_event.reason_code == "problem_returned"
    assert reopen_event.service_code == "workplace"
    assert review.severity in {"medium", "high"}


@pytest.mark.asyncio
async def test_reopen_other_requires_comment(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_closed_ticket(ticket_id))
        await session.commit()

        with pytest.raises(ValueError, match="reason_comment"):
            await TicketReopenService(session).reopen_ticket(
                ticket_id,
                reason_code="other",
                reason_comment="",
                actor_id="requester-1",
                actor_role="requester",
            )
