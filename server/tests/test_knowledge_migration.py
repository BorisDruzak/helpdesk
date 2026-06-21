from __future__ import annotations

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.db_cleanup("knowledge")

@pytest.mark.asyncio
async def test_knowledge_platform_tables_exist_after_migration(test_engine) -> None:
    expected = {
        "knowledge_spaces",
        "knowledge_items",
        "knowledge_item_versions",
        "knowledge_chunks",
        "knowledge_bindings",
        "knowledge_nodes",
        "knowledge_edges",
        "knowledge_entity_mentions",
        "knowledge_feedback_events",
        "knowledge_ingestion_jobs",
        "knowledge_content_packs",
        "knowledge_content_pack_items",
        "knowledge_rollout_policies",
        "knowledge_review_tasks",
        "knowledge_review_comments",
        "knowledge_quality_snapshots",
        "knowledge_gap_findings",
        "knowledge_search_events",
        "knowledge_audience_rules",
        "ticket_knowledge_links",
    }
    async with test_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name LIKE 'knowledge_%' "
                    "UNION SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'ticket_knowledge_links'"
                )
            )
        ).scalars().all()

    assert expected <= set(rows)
