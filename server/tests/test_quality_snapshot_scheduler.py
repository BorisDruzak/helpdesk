from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ServiceQualitySnapshot, Ticket, TicketFeedback
from app.services.quality_snapshot_scheduler import QualitySnapshotScheduler


@pytest.mark.asyncio
async def test_quality_snapshot_scheduler_recomputes_daily_and_weekly_snapshots(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-quality-scheduler",
                title="VPN issue",
                description="VPN",
                status="closed",
                requester_id="requester-1",
                service_code="network",
                offering_code="network.vpn_issue",
                resolved_at=now - timedelta(hours=2),
                closed_at=now - timedelta(hours=1),
            )
        )
        await session.flush()
        session.add(
            TicketFeedback(
                feedback_id=str(uuid.uuid4()),
                ticket_id=ticket_id,
                requester_id="requester-1",
                actor_role="requester",
                rating=2,
                sentiment="negative",
                problem_resolved=False,
                reason_codes=["not_resolved"],
                visibility="requester_visible",
                source_surface="requester_portal",
                service_code="network",
                offering_code="network.vpn_issue",
                submitted_at=now,
                is_latest=True,
            )
        )
        await session.commit()

    scheduler = QualitySnapshotScheduler(session_maker=session_maker, interval_seconds=3600)
    result = await scheduler.run_once(now=now)

    async with session_maker() as session:
        snapshots = (await session.execute(select(ServiceQualitySnapshot))).scalars().all()

    assert set(result["buckets"]) == {"day", "week"}
    assert result["last_computed_at"]
    assert {snapshot.bucket for snapshot in snapshots} == {"day", "week"}
    assert all(snapshot.computed_at is not None for snapshot in snapshots)
