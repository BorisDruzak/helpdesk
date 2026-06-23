from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Change, ChangePIRRecord
from change.analytics_service import ChangeAnalyticsService
from change.change_service import ChangeService
from change.policy_service import ChangePolicyService

pytestmark = pytest.mark.db_cleanup("full")


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


@pytest.mark.asyncio
async def test_change_analytics_reports_failure_rollback_lead_time_and_emergency_retro(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        await ChangePolicyService(session).save_policy(
            {
                "code": "emergency-retro",
                "title": "Emergency retrospective",
                "scope_type": "change_type",
                "change_type": "emergency",
                "max_emergency_retro_hours": 24,
            },
            actor_id="admin-1",
        )
        successful = await ChangeService(session).create_change(
            {"title": "Successful change", "description": "Closed with PIR", "change_type": "normal"},
            actor_id="support-1",
        )
        failed = await ChangeService(session).create_change(
            {"title": "Failed change", "description": "Failed during implementation", "change_type": "normal"},
            actor_id="support-1",
        )
        rolled_back = await ChangeService(session).create_change(
            {"title": "Rolled back change", "description": "Rollback used", "change_type": "normal"},
            actor_id="support-1",
        )
        emergency = await ChangeService(session).create_change(
            {
                "title": "Emergency hotfix",
                "description": "Emergency implementation",
                "change_type": "emergency",
                "emergency_justification": "production outage",
            },
            actor_id="support-1",
        )
        all_rows = (await session.execute(select(Change))).scalars().all()
        by_id = {row.change_id: row for row in all_rows}
        by_id[successful["change_id"]].status = "closed"
        by_id[successful["change_id"]].submitted_at = now - timedelta(hours=10)
        by_id[successful["change_id"]].implementation_started_at = now - timedelta(hours=4)
        by_id[successful["change_id"]].actual_start_at = now - timedelta(hours=4)
        by_id[successful["change_id"]].actual_end_at = now - timedelta(hours=2)
        by_id[successful["change_id"]].closed_at = now
        by_id[failed["change_id"]].status = "failed"
        by_id[rolled_back["change_id"]].status = "rolled_back"
        by_id[emergency["change_id"]].status = "pir_required"
        by_id[emergency["change_id"]].implemented_at = now - timedelta(hours=30)
        session.add(
            ChangePIRRecord(
                pir_id="pir-approved",
                change_id=successful["change_id"],
                status="approved",
                implementation_successful=True,
                approved_at=now,
            )
        )
        summary = await ChangeAnalyticsService(session).summary()
        await session.commit()

    assert summary["failure_rate"] == pytest.approx(0.25)
    assert summary["rollback_rate"] == pytest.approx(0.25)
    assert summary["average_lead_time_hours"] == pytest.approx(6.0)
    assert summary["average_implementation_duration_hours"] == pytest.approx(2.0)
    assert summary["pir_completion_rate"] == pytest.approx(1.0)
    assert summary["emergency_retrospective_overdue_count"] == 1

