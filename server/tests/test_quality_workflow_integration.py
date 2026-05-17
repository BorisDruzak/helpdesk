from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketFeedback, TicketReopenEvent
from quality.feedback_service import TicketFeedbackService
from quality.reopen_service import TicketReopenService


@pytest.mark.asyncio
async def test_low_csat_feedback_can_link_to_reopen_event(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(Ticket(ticket_id=ticket_id, device_id="device-quality-flow", title="VPN", description="VPN", status="resolved", requester_id="alice", resolved_at=datetime.now(timezone.utc)))
        feedback = await TicketFeedbackService(session).submit_feedback(
            {"ticket_id": ticket_id, "rating": 1, "problem_resolved": False, "reason_codes": ["problem_returned"], "source_surface": "requester_portal"},
            actor_id="alice",
            actor_role="requester",
        )
        reopened = await TicketReopenService(session).reopen_ticket(
            ticket_id,
            reason_code="problem_returned",
            reason_comment="The issue returned",
            actor_id="alice",
            actor_role="requester",
            linked_feedback_id=feedback["feedback_id"],
        )
        await session.commit()

        feedback_row = await session.get(TicketFeedback, feedback["feedback_id"])
        reopen_row = (await session.execute(select(TicketReopenEvent).where(TicketReopenEvent.ticket_id == ticket_id))).scalar_one()

    assert reopened["linked_feedback_id"] == feedback["feedback_id"]
    assert reopen_row.linked_feedback_id == feedback["feedback_id"]
    assert feedback_row.is_latest is True
