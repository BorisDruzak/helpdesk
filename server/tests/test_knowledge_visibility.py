from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.visibility import KnowledgeVisibilityService


pytestmark = pytest.mark.db_cleanup("knowledge")

@pytest.mark.asyncio
async def test_knowledge_visibility_filters_by_actor_role_before_projection(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        requester_item = await repo.create_item_draft(
            {
                "space_code": "it",
                "slug": "requester-vpn",
                "item_type": "article",
                "title": "VPN для пользователя",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        requester_version = await repo.create_version(
            requester_item["item_id"],
            {"title": "VPN для пользователя", "body_format": "markdown", "body": "Requester-safe body."},
            actor_id="support",
        )
        await repo.publish_item(requester_item["item_id"], requester_version["version_id"], actor_id="admin")
        internal_item = await repo.create_item_draft(
            {
                "space_code": "it",
                "slug": "support-runbook",
                "item_type": "runbook",
                "title": "Внутренний runbook",
                "visibility": "support_internal",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        internal_version = await repo.create_version(
            internal_item["item_id"],
            {"title": "Внутренний runbook", "body_format": "markdown", "body": "Internal body."},
            actor_id="support",
        )
        await repo.publish_item(internal_item["item_id"], internal_version["version_id"], actor_id="admin")
        await session.commit()

    async with session_maker() as session:
        visibility = KnowledgeVisibilityService(session)
        requester_items = await visibility.list_visible_items(actor_role="requester")
        support_items = await visibility.list_visible_items(actor_role="support")

    assert {item["slug"] for item in requester_items} == {"requester-vpn"}
    assert {item["slug"] for item in support_items} >= {"requester-vpn", "support-runbook"}


@pytest.mark.asyncio
async def test_requester_direct_id_access_denies_internal_item(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "sec", "title": "Security", "visibility": "support_internal", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "sec",
                "slug": "secret-runbook",
                "item_type": "runbook",
                "title": "Secret runbook",
                "visibility": "support_internal",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": "Secret runbook", "body_format": "markdown", "body": "Internal body."},
            actor_id="support",
        )
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        await session.commit()

    async with session_maker() as session:
        visibility = KnowledgeVisibilityService(session)
        assert await visibility.can_read_item(item["item_id"], actor_role="requester") is False
        assert await visibility.can_read_item(item["item_id"], actor_role="support") is True
