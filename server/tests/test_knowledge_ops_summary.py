from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeAudienceRule, KnowledgeIndexJob, KnowledgeItem, KnowledgeSearchEvent, ObserverIntegrityEvent, RegistryDepartment
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.ops_summary_service import KnowledgeOpsSummaryService


pytestmark = pytest.mark.db_cleanup("knowledge")

ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


async def _published_article(session, *, slug: str) -> dict:
    repo = KnowledgeRepo(session)
    await repo.upsert_space(
        {"code": f"{slug}-space", "title": f"{slug} space", "visibility": "requester", "lifecycle_status": "active"},
        actor_id="admin-test",
    )
    item = await repo.create_item_draft(
        {
            "space_code": f"{slug}-space",
            "slug": slug,
            "item_type": "article",
            "title": "VPN requester article",
            "summary": "Requester-safe VPN recovery steps",
            "visibility": "requester",
            "owner_actor_id": "owner-test",
            "reviewer_actor_id": "reviewer-test",
        },
        actor_id="admin-test",
        actor_role="admin",
    )
    version = await repo.create_version(
        item["item_id"],
        {"title": "VPN requester article", "body_format": "markdown", "body": "## Steps\nReconnect VPN and retry."},
        actor_id="admin-test",
        actor_role="admin",
    )
    return await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin-test", actor_role="admin")


@pytest.mark.asyncio
async def test_knowledge_ops_summary_aggregates_health_and_observer_degradations(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_article(session, slug=f"ops-summary-{uuid.uuid4().hex[:8]}")
        session.add_all(
            [
                KnowledgeSearchEvent(
                    event_id=str(uuid.uuid4()),
                    actor_role="support",
                    surface="support_workspace",
                    query_text_hash="hash-zero",
                    query_text_redacted="missing printer runbook",
                    result_count=0,
                    metadata_json={"fallback_mode": "keyword", "rag_no_answer": True},
                ),
                KnowledgeIndexJob(
                    job_id=str(uuid.uuid4()),
                    scope_type="all",
                    status="failed",
                    error_redacted="embedding provider unavailable",
                    stats_json={"failed_embeddings": 2},
                    metadata_json={},
                ),
                ObserverIntegrityEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="knowledge.indexing.failed",
                    severity="critical",
                    source="knowledge.indexing",
                    status="active",
                    dedupe_key=f"knowledge:indexing:{uuid.uuid4()}",
                    expected="Knowledge embeddings should index",
                    actual="Embedding provider unavailable",
                    evidence_json={"job_id": "job-knowledge-failed"},
                ),
            ]
        )
        await session.commit()

        summary = await KnowledgeOpsSummaryService(session).summary(actor_role="admin")

    assert summary["status"] == "degraded"
    assert summary["coverage"]["spaces"]["total"] >= 1
    assert summary["coverage"]["published_articles"]["total"] >= 1
    assert summary["search"]["zero_result_searches"]["total"] >= 1
    assert summary["search"]["fallback_count"]["total"] >= 1
    assert summary["rag"]["no_answer_count"]["total"] >= 1
    assert summary["indexing"]["failed"]["total"] >= 1
    assert any(item["code"] == "knowledge.indexing.failed" for item in summary["observer"]["degradations"])


@pytest.mark.asyncio
async def test_knowledge_ops_summary_returns_actionable_queues(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item = await _published_article(session, slug=f"ops-queue-{uuid.uuid4().hex[:8]}")
        row = (await session.execute(select(KnowledgeItem).where(KnowledgeItem.item_id == item["item_id"]))).scalar_one()
        row.owner_actor_id = None
        row.reviewer_actor_id = None
        row.review_due_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        department_id = str(uuid.uuid4())
        session.add(
            RegistryDepartment(
                department_id=department_id,
                code=f"empty-{uuid.uuid4().hex[:6]}",
                name="Empty audience department",
                status="active",
                source="test",
            )
        )
        session.add(
            KnowledgeAudienceRule(
                rule_id=str(uuid.uuid4()),
                subject_type="item",
                subject_id=item["item_id"],
                target_type="department",
                target_id=department_id,
                effect="allow",
                include_children=False,
                priority=10,
                status="active",
                reason="test zero audience",
                metadata_json={},
            )
        )
        session.add(
            KnowledgeSearchEvent(
                event_id=str(uuid.uuid4()),
                actor_role="requester",
                surface="requester_portal",
                query_text_hash="hash-zero-queue",
                query_text_redacted="missing vpn article",
                result_count=0,
                metadata_json={},
            )
        )
        session.add(
            KnowledgeIndexJob(
                job_id=str(uuid.uuid4()),
                scope_type="item",
                scope_ref=item["item_id"],
                status="failed",
                error_redacted="embedding provider unavailable",
                stats_json={"failed_embeddings": 1},
                metadata_json={},
            )
        )
        await session.commit()

        summary = await KnowledgeOpsSummaryService(session).summary(actor_role="admin")

    queues = summary["action_queues"]
    assert queues["no_audience_users"]["total"] >= 1
    assert queues["missing_helpdesk_binding"]["total"] >= 1
    assert queues["stale_article"]["total"] >= 1
    assert queues["indexing_failed"]["total"] >= 1
    assert queues["low_quality"]["total"] >= 1
    assert queues["zero_result_searches"]["total"] >= 1
    assert queues["missing_helpdesk_binding"]["items"][0]["action_url"].startswith("/app/admin/knowledge/studio?item=")
    assert queues["zero_result_searches"]["items"][0]["query"] == "missing vpn article"
    assert "body" not in str(queues)


@pytest.mark.asyncio
async def test_knowledge_ops_summary_api_returns_dashboard_payload(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_article(session, slug=f"ops-api-{uuid.uuid4().hex[:8]}")
        await session.commit()

    resp = await test_client.get("/api/web/knowledge/ops/summary", headers=ADMIN_HEADERS)

    assert resp.status == 200
    payload = await resp.json()
    assert payload["status"] == "ok"
    assert payload["summary"]["generated_at"]
    assert payload["summary"]["coverage"]["requester_safe"]["total"] >= 1
    assert "degradations" in payload["summary"]["observer"]
