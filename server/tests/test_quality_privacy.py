from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ContinuousImprovementAction, Ticket, TicketQualityReview

pytestmark = pytest.mark.db_cleanup("full")


def _user_headers(user_login: str) -> dict[str, str]:
    return {"Authorization": f"Bearer test-ui-user:{user_login}"}


@pytest.mark.asyncio
async def test_requester_ticket_detail_does_not_expose_internal_quality_objects(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(Ticket(ticket_id=ticket_id, device_id="device-quality-privacy", title="VPN", description="VPN", status="resolved", requester_id="alice", resolved_at=datetime.now(timezone.utc)))
        await session.flush()
        session.add(
            TicketQualityReview(
                review_id=str(uuid.uuid4()),
                ticket_id=ticket_id,
                review_type="low_csat",
                severity="high",
                status="open",
                review_notes="internal root cause and queue evidence",
                queue_id=42,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            ContinuousImprovementAction(
                action_id=str(uuid.uuid4()),
                source_kind="qa_review",
                ticket_id=ticket_id,
                action_type="train_support",
                title="Internal training",
                description="Internal process action",
                status="open",
                priority="medium",
                created_by="qa",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    response = await test_client.get(f"/api/tickets/{ticket_id}", headers=_user_headers("alice"))

    assert response.status == 200, await response.text()
    payload = await response.json()
    text = repr(payload)
    assert "internal root cause" not in text
    assert "queue evidence" not in text
    assert "ContinuousImprovementAction" not in text
    assert "quality_reviews" not in text
    assert "improvement_actions" not in text
