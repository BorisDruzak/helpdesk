from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeSearchEvent
from knowledge.search_analytics_service import KnowledgeSearchAnalyticsService


pytestmark = pytest.mark.db_cleanup("knowledge")

@pytest.mark.asyncio
async def test_search_event_records_hash_and_redacted_query(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        event = await KnowledgeSearchAnalyticsService(session).record_search_event(
            actor_role="requester",
            surface="requester_portal",
            query_text="VPN for ivan@example.com device_id=abc requester_id=secret",
            service_code="network",
            offering_code="network.vpn_issue",
            result_count=0,
        )
        await session.commit()

    assert event["query_text_hash"]
    assert "ivan@example.com" not in (event["query_text_redacted"] or "")
    assert "device_id=abc" not in (event["query_text_redacted"] or "")

    async with session_maker() as session:
        row = (await session.execute(select(KnowledgeSearchEvent))).scalar_one()
        assert row.result_count == 0
        assert row.query_text_redacted == event["query_text_redacted"]
