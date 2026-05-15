from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.metrics_service import KnowledgeMetricsService


@pytest.mark.asyncio
async def test_knowledge_metrics_count_deflection_and_no_pii(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = KnowledgeFeedbackService(session)
        await service.record_event({"event_type": "deflected", "service_code": "network", "offering_code": "network.vpn_issue", "surface": "requester_portal"}, actor_role="requester", actor_id="requester-secret")
        await service.record_event({"event_type": "ticket_created_after_view", "service_code": "network", "offering_code": "network.vpn_issue", "surface": "requester_portal"}, actor_role="requester", actor_id="requester-secret")
        await session.commit()

    async with session_maker() as session:
        summary = await KnowledgeMetricsService(session).summary()

    assert summary["deflection"]["deflected_count"] == 1
    assert summary["deflection"]["ticket_created_after_view_count"] == 1
    assert summary["helpfulness"]["helpful_count"] == 0
    assert summary["totals"]["feedback_count"] == 2
    assert summary["deflection_events"] == 1
    assert summary["ticket_created_after_view_events"] == 1
    assert summary["helpful_events"] == 0
    assert summary["not_helpful_events"] == 0
    assert "requester-secret" not in str(summary)
