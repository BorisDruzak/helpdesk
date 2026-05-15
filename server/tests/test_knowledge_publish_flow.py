from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo


async def _create_item_with_version(session, *, slug: str, metadata: dict | None = None) -> tuple[dict, dict]:
    repo = KnowledgeRepo(session)
    await repo.upsert_space(
        {"code": f"space-{slug}", "title": f"Space {slug}", "visibility": "support_internal", "lifecycle_status": "active"},
        actor_id="admin-test",
    )
    item = await repo.create_item_draft(
        {
            "space_code": f"space-{slug}",
            "slug": slug,
            "item_type": "article",
            "title": f"Item {slug}",
            "visibility": "support_internal",
            "owner_actor_id": "owner-test",
            "reviewer_actor_id": "reviewer-test",
            "metadata": metadata or {},
        },
        actor_id="support-test",
    )
    version = await repo.create_version(
        item["item_id"],
        {"title": f"Item {slug}", "body": "Publishable body", "body_format": "markdown"},
        actor_id="support-test",
    )
    return item, version


@pytest.mark.asyncio
async def test_draft_item_can_publish_explicit_new_version_without_current_version(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        item, version = await _create_item_with_version(session, slug="publish-flow")

        assert item["current_version_id"] is None
        published = await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin-test")
        await session.commit()

    assert published["status"] == "published"
    assert published["current_version_id"] == version["version_id"]


@pytest.mark.asyncio
async def test_publish_requires_explicit_version_and_matching_item(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        item, _version = await _create_item_with_version(session, slug="publish-source")
        _other_item, other_version = await _create_item_with_version(session, slug="publish-other")

        with pytest.raises(ValueError, match="version_id"):
            await repo.publish_item(item["item_id"], None, actor_id="admin-test")
        with pytest.raises(ValueError, match="version"):
            await repo.publish_item(item["item_id"], other_version["version_id"], actor_id="admin-test")


@pytest.mark.asyncio
async def test_stale_passport_draft_publish_requires_acknowledgement(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        item, version = await _create_item_with_version(
            session,
            slug="stale-passport-draft",
            metadata={
                "passport_stale": True,
                "review_required": True,
                "warnings": [{"code": "passport_stale", "message": "Passport source is stale"}],
            },
        )

        with pytest.raises(ValueError, match="stale"):
            await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin-test")

        published = await repo.publish_item(
            item["item_id"],
            version["version_id"],
            actor_id="admin-test",
            acknowledge_stale_passport=True,
            review_note="Reviewed stale passport source.",
        )
        await session.commit()

    assert published["status"] == "published"
