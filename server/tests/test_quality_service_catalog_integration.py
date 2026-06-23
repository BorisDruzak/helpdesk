from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket
from quality.feedback_service import TicketFeedbackService
from quality.analytics_service import ServiceQualityAnalyticsService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_quality_signals_snapshot_service_catalog_fields(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-quality-catalog",
                title="Laptop broken",
                description="Laptop does not power on",
                status="closed",
                requester_id="alice",
                service_code="workplace",
                offering_code="workplace.laptop_broken",
                request_type="incident",
                reporting_category="workplace",
                resolved_at=now,
                closed_at=now,
            )
        )
        feedback = await TicketFeedbackService(session).submit_feedback(
            {"ticket_id": ticket_id, "rating": 5, "source_surface": "requester_portal"},
            actor_id="alice",
            actor_role="requester",
        )
        summary = await ServiceQualityAnalyticsService(session).service_quality(
            period_start=now - timedelta(hours=1),
            period_end=now + timedelta(hours=1),
            bucket="day",
        )
        await session.commit()

    assert feedback["service_code"] == "workplace"
    assert feedback["offering_code"] == "workplace.laptop_broken"
    row = summary["rows"][0]
    assert row["service_code"] == "workplace"
    assert row["offering_code"] == "workplace.laptop_broken"
