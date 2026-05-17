from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeFeedbackEvent, ServiceQualitySnapshot, Ticket, TicketFeedback, TicketReopenEvent
from quality.analytics_service import ServiceQualityAnalyticsService


@pytest.mark.asyncio
async def test_service_quality_analytics_aggregates_without_requester_pii(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-quality-analytics",
                title="VPN issue",
                description="VPN",
                status="closed",
                requester_id="secret-requester",
                service_code="network",
                offering_code="network.vpn_issue",
                request_type="incident",
                resolved_at=now - timedelta(days=1),
                closed_at=now,
                first_response_breached_at=now,
                resolution_breached_at=now,
            )
        )
        await session.flush()
        session.add(
            TicketFeedback(
                feedback_id=str(uuid.uuid4()),
                ticket_id=ticket_id,
                requester_id="secret-requester",
                actor_role="requester",
                rating=2,
                sentiment="negative",
                problem_resolved=False,
                reason_codes=["knowledge_article_failed"],
                comment="contains requester details",
                visibility="requester_visible",
                source_surface="requester_portal",
                service_code="network",
                offering_code="network.vpn_issue",
                submitted_at=now,
                is_latest=True,
            )
        )
        session.add(
            TicketReopenEvent(
                reopen_id=str(uuid.uuid4()),
                ticket_id=ticket_id,
                reopened_by_actor_id="secret-requester",
                reopened_by_role="requester",
                previous_status="closed",
                new_status="in_progress",
                reason_code="knowledge_article_failed",
                service_code="network",
                offering_code="network.vpn_issue",
                created_at=now,
            )
        )
        session.add(
            KnowledgeFeedbackEvent(
                event_id=str(uuid.uuid4()),
                item_id=None,
                version_id=None,
                ticket_id=ticket_id,
                event_type="ticket_created_after_view",
                source_surface="requester_portal",
                actor_role="requester",
                service_code="network",
                offering_code="network.vpn_issue",
                metadata_json={"knowledge_attempts": [{"result": "not_helpful"}]},
                created_at=now,
            )
        )
        await session.commit()

        summary = await ServiceQualityAnalyticsService(session).service_quality(
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            bucket="week",
        )

    assert summary["rows"][0]["service_code"] == "network"
    assert summary["rows"][0]["avg_csat"] == 2.0
    assert summary["rows"][0]["negative_csat_count"] == 1
    assert summary["rows"][0]["reopen_count"] == 1
    assert summary["rows"][0]["sla_breach_count"] == 1
    assert summary["rows"][0]["ticket_after_failed_knowledge_count"] == 1
    assert "secret-requester" not in repr(summary)
    assert "contains requester details" not in repr(summary)


@pytest.mark.asyncio
async def test_service_quality_reports_latest_snapshot_timestamp(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-quality-snapshot-ts",
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
        await session.commit()
        service = ServiceQualityAnalyticsService(session)
        recomputed = await service.service_quality(
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            bucket="week",
            recompute_snapshot=True,
        )
        await session.commit()

        summary = await service.service_quality(
            period_start=now - timedelta(days=7),
            period_end=now + timedelta(days=1),
            bucket="week",
        )
        snapshots = (await session.execute(ServiceQualitySnapshot.__table__.select())).all()

    assert snapshots
    assert recomputed["last_computed_at"]
    assert summary["last_computed_at"] == recomputed["last_computed_at"]
