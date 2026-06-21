from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.content_lint import lint_knowledge_content
from knowledge.contracts import KnowledgePublicationBlockedError


pytestmark = pytest.mark.db_cleanup("knowledge")

def test_requester_unsafe_phrase_blocks_publication() -> None:
    result = lint_knowledge_content(
        item_type="article",
        visibility="requester",
        title="VPN",
        summary="Safe summary",
        body="Ask support to run command and inspect internal queue_id.",
        owner_actor_id="servicedesk",
        reviewer_actor_id="servicedesk",
        review_due_at=datetime.now(timezone.utc) + timedelta(days=30),
        bindings=[{"service_code": "network", "offering_code": "network.vpn_issue"}],
    )

    assert "unsafe_requester_content" in {issue["code"] for issue in result["errors"]}


def test_article_without_owner_reviewer_or_review_due_blocks_publish() -> None:
    result = lint_knowledge_content(
        item_type="article",
        visibility="requester",
        title="VPN",
        summary="Safe summary",
        body="## Назначение\nSafe\n## Когда использовать\nSafe\n## Шаги\nSafe",
        owner_actor_id=None,
        reviewer_actor_id=None,
        review_due_at=None,
        bindings=[],
    )

    codes = {issue["code"] for issue in result["errors"]}
    assert {"missing_owner", "missing_reviewer", "missing_review_due"} <= codes
    assert "missing_self_service_binding" in {issue["code"] for issue in result["warnings"]}


@pytest.mark.asyncio
async def test_publish_uses_content_lint_and_blocks_missing_governance(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "it",
                "slug": "vpn-no-owner",
                "item_type": "article",
                "title": "VPN",
                "summary": "Safe summary",
                "visibility": "requester",
            },
            actor_id="admin",
            actor_role="admin",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": "VPN", "summary": "Safe summary", "body_format": "markdown", "body": "## Назначение\nSafe steps."},
            actor_id="admin",
            actor_role="admin",
        )

        with pytest.raises(KnowledgePublicationBlockedError) as exc:
            await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin", actor_role="admin")

    assert "missing_owner" in {blocker["code"] for blocker in exc.value.blockers}
