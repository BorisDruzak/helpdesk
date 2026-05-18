from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.analytics_service import ChangeAnalyticsService
from change.change_service import ChangeService


@pytest.mark.asyncio
async def test_change_analytics_groups_by_type_status_and_service_without_pii(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await ChangeService(session).create_change(
            {
                "title": "VPN update",
                "description": "Update VPN",
                "change_type": "normal",
                "service_code": "network",
                "metadata": {"requester_id": "alice"},
            },
            actor_id="support-1",
        )
        summary = await ChangeAnalyticsService(session).summary()
        await session.commit()

    assert summary["change_count"] == 1
    assert summary["changes_by_type"]["normal"] == 1
    assert summary["changes_by_service"]["network"] == 1
    assert "requester_id" not in str(summary)

