from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.calendar_service import ChangeCalendarService
from change.change_service import ChangeService


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

