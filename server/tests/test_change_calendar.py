from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.calendar_service import ChangeCalendarService
from change.change_service import ChangeService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_blackout_blocks_schedule_unless_override_has_justification(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)
    async with session_maker() as session:
        change = await ChangeService(session).create_change(
            {
                "title": "VPN route update",
                "description": "Schedule route update",
                "change_type": "normal",
                "service_code": "network",
            },
            actor_id="support-1",
        )
        await ChangeCalendarService(session).create_window(
            {
                "title": "Network blackout",
                "window_type": "blackout",
                "service_code": "network",
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
            },
            actor_id="admin-1",
        )
        with pytest.raises(ValueError, match="blackout"):
            await ChangeCalendarService(session).schedule_change(
                change["change_id"],
                planned_start_at=start.isoformat(),
                planned_end_at=end.isoformat(),
                actor_id="support-1",
            )
        scheduled = await ChangeCalendarService(session).schedule_change(
            change["change_id"],
            planned_start_at=start.isoformat(),
            planned_end_at=end.isoformat(),
            actor_id="admin-1",
            blackout_override=True,
            override_justification="Emergency security fix",
        )
        await session.commit()

    assert scheduled["status"] == "scheduled"
    assert scheduled["blackout_override"] is True


@pytest.mark.asyncio
async def test_recurring_blackout_blocks_matching_occurrence(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    start = datetime(2026, 5, 18, 22, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    next_week_start = start + timedelta(days=7)
    next_week_end = next_week_start + timedelta(hours=1)
    async with session_maker() as session:
        change = await ChangeService(session).create_change(
            {
                "title": "Weekly database patch",
                "description": "Patch during blackout candidate",
                "change_type": "normal",
                "service_code": "platform",
            },
            actor_id="support-1",
        )
        await ChangeCalendarService(session).create_window(
            {
                "title": "Weekly platform blackout",
                "window_type": "blackout",
                "service_code": "platform",
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
                "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO;COUNT=4",
            },
            actor_id="admin-1",
        )

        with pytest.raises(ValueError, match="blackout"):
            await ChangeCalendarService(session).schedule_change(
                change["change_id"],
                planned_start_at=next_week_start.isoformat(),
                planned_end_at=next_week_end.isoformat(),
                actor_id="support-1",
            )


@pytest.mark.asyncio
async def test_schedule_detects_overlapping_change_for_same_service(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    start = datetime.now(timezone.utc) + timedelta(days=3)
    end = start + timedelta(hours=2)
    async with session_maker() as session:
        first = await ChangeService(session).create_change(
            {"title": "Network firewall update", "description": "First window", "change_type": "normal", "service_code": "network"},
            actor_id="support-1",
        )
        second = await ChangeService(session).create_change(
            {"title": "Network VPN update", "description": "Second window", "change_type": "normal", "service_code": "network"},
            actor_id="support-2",
        )
        await ChangeCalendarService(session).schedule_change(
            first["change_id"],
            planned_start_at=start.isoformat(),
            planned_end_at=end.isoformat(),
            actor_id="support-1",
        )

        with pytest.raises(ValueError, match="overlap"):
            await ChangeCalendarService(session).schedule_change(
                second["change_id"],
                planned_start_at=(start + timedelta(minutes=30)).isoformat(),
                planned_end_at=(end + timedelta(minutes=30)).isoformat(),
                actor_id="support-2",
            )

