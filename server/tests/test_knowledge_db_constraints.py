from __future__ import annotations

import pytest
import uuid
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


pytestmark = pytest.mark.db_cleanup("knowledge")

async def _assert_integrity_error(test_engine, sql: str) -> None:
    async with test_engine.connect() as conn:
        tx = await conn.begin()
        try:
            with pytest.raises(IntegrityError):
                await conn.execute(text(sql))
        finally:
            await tx.rollback()


@pytest.mark.asyncio
async def test_knowledge_graph_feedback_ingestion_check_constraints(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    await _assert_integrity_error(
        test_engine,
        f"""
        INSERT INTO knowledge_nodes (node_id, node_type, stable_key, label, visibility, status)
        VALUES ('bad-node-type-{suffix}', 'not_a_node_type', 'bad:node-type-{suffix}', 'Bad', 'support_internal', 'confirmed')
        """,
    )

    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO knowledge_nodes (node_id, node_type, stable_key, label, visibility, status)
                VALUES
                    (:node_a, 'concept', :stable_a, 'A', 'support_internal', 'confirmed'),
                    (:node_b, 'concept', :stable_b, 'B', 'support_internal', 'confirmed')
                """
            ),
            {"node_a": f"edge-node-a-{suffix}", "node_b": f"edge-node-b-{suffix}", "stable_a": f"constraint:edge-a-{suffix}", "stable_b": f"constraint:edge-b-{suffix}"},
        )
    await _assert_integrity_error(
        test_engine,
        f"""
        INSERT INTO knowledge_edges (edge_id, source_node_id, target_node_id, relation_type, visibility, status)
        VALUES ('bad-edge-relation-{suffix}', 'edge-node-a-{suffix}', 'edge-node-b-{suffix}', 'not_a_relation', 'support_internal', 'confirmed')
        """,
    )

    await _assert_integrity_error(
        test_engine,
        f"""
        INSERT INTO knowledge_feedback_events (event_id, source_surface, event_type)
        VALUES ('bad-feedback-type-{suffix}', 'requester_portal', 'not_an_event')
        """,
    )

    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO knowledge_spaces (space_id, code, title, visibility, lifecycle_status)
                VALUES (:space_id, :space_code, 'Constraint Space', 'support_internal', 'active')
                """
            ),
            {"space_id": f"constraint-space-{suffix}", "space_code": f"constraint-space-{suffix}"},
        )
    await _assert_integrity_error(
        test_engine,
        f"""
        INSERT INTO knowledge_ingestion_jobs (job_id, space_id, source_kind, source_name, status)
        VALUES ('bad-ingestion-status-{suffix}', 'constraint-space-{suffix}', 'markdown', 'Bad', 'not_a_status')
        """,
    )
