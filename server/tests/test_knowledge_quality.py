from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeItemVersion
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.quality_service import KnowledgeQualityService


pytestmark = pytest.mark.db_cleanup("knowledge")

async def _article(session, *, slug: str, body: str, owner: str | None = "owner", reviewer: str | None = "reviewer") -> dict:
    repo = KnowledgeRepo(session)
    await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
    item = await repo.create_item_draft(
        {
            "space_code": "it",
            "slug": slug,
            "item_type": "article",
            "title": "VPN safe checks",
            "summary": "Safe checks before creating a ticket.",
            "visibility": "requester",
            "owner_actor_id": owner,
            "reviewer_actor_id": reviewer,
            "tags": ["vpn"],
        },
        actor_id="admin",
        actor_role="admin",
    )
    row = await repo.get_item_row(item["item_id"])
    row.review_due_at = datetime.now(timezone.utc) + timedelta(days=30)
    version = await repo.create_version(item["item_id"], {"title": "VPN safe checks", "summary": "Safe", "body": body}, actor_id="admin", actor_role="admin")
    await repo.add_binding(item["item_id"], {"service_code": "network", "offering_code": "network.vpn_issue"}, actor_id="admin", actor_role="admin")
    await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin", actor_role="admin")
    return item


@pytest.mark.asyncio
async def test_complete_article_has_explainable_high_quality_score(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item = await _article(
            session,
            slug="quality-good",
            body="## Назначение\nSafe.\n## Когда использовать\nBefore ticket.\n## Шаги\nCheck connection.\n## Проверка результата\nVPN connects.\n## Если не помогло\nCreate ticket.\n## Связанные услуги / типы обращения\nNetwork / VPN.",
        )
        score = await KnowledgeQualityService(session).score_item(item["item_id"])

    assert score["score"] >= 80
    assert score["grade"] in {"A", "B"}
    assert set(score["dimensions"]) == {"completeness", "governance", "safety", "usefulness", "freshness", "coverage"}


@pytest.mark.asyncio
async def test_missing_governance_unsafe_and_negative_feedback_lower_quality(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item = await _article(session, slug="quality-bad", body="Safe article body before later drift.", owner="owner", reviewer="reviewer")
        repo = KnowledgeRepo(session)
        row = await repo.get_item_row(item["item_id"])
        row.review_due_at = datetime.now(timezone.utc) - timedelta(days=10)
        version = await session.get(KnowledgeItemVersion, row.current_version_id)
        version.body = "Ask admin only to inspect device_id and queue_id."
        await KnowledgeFeedbackService(session).record_event({"item_id": item["item_id"], "event_type": "not_helpful"}, actor_role="requester", actor_id="requester")
        score = await KnowledgeQualityService(session).score_item(item["item_id"])

    codes = {issue["code"] for issue in score["issues"]}
    assert score["score"] < 80
    assert {"unsafe_requester_content", "review_overdue", "not_helpful_feedback"} <= codes


@pytest.mark.asyncio
async def test_review_disabled_quality_does_not_require_reviewer(test_engine, monkeypatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_REVIEW_REQUIRED", "false")
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item = await _article(
            session,
            slug="quality-no-reviewer-simplified",
            body="## Steps\nReconnect VPN.\n## Verification\nVPN connects.",
            owner="owner",
            reviewer="reviewer",
        )
        repo = KnowledgeRepo(session)
        row = await repo.get_item_row(item["item_id"])
        row.reviewer_actor_id = None
        score = await KnowledgeQualityService(session).score_item(item["item_id"])

    codes = {issue["code"] for issue in score["issues"]}
    assert "missing_reviewer" not in codes
