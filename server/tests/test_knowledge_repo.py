from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.contracts import KnowledgePublicationBlockedError


@pytest.mark.asyncio
async def test_knowledge_repo_creates_space_item_version_publish_and_bindings(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        space = await repo.upsert_space(
            {
                "code": "it-support",
                "title": "IT Support",
                "visibility": "requester",
                "lifecycle_status": "active",
                "allow_publication": True,
                "allow_ingestion": True,
                "allow_rag": False,
            },
            actor_id="admin-test",
        )
        item = await repo.create_item_draft(
            {
                "space_code": "it-support",
                "slug": "vpn-reconnect",
                "item_type": "article",
                "title": "Как переподключить VPN",
                "summary": "Короткая инструкция",
                "visibility": "requester",
                "owner_actor_id": "support-owner",
                "reviewer_actor_id": "support-reviewer",
                "tags": ["vpn", "network"],
            },
            actor_id="support-test",
        )
        version = await repo.create_version(
            item["item_id"],
            {
                "title": "Как переподключить VPN",
                "summary": "Короткая инструкция",
                "body_format": "markdown",
                "body": "## Шаги\n\n1. Отключите VPN.\n2. Подключите снова.",
                "change_summary": "Initial draft",
            },
            actor_id="support-test",
        )
        await repo.add_binding(
            item["item_id"],
            {"service_code": "network", "offering_code": "network.vpn_issue", "request_template_key": "vpn_issue"},
            actor_id="support-test",
        )
        published = await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin-test")
        await session.commit()

    assert space["code"] == "it-support"
    assert published["status"] == "published"
    assert published["current_version_id"] == version["version_id"]

    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        loaded = await repo.get_item(item["item_id"], actor_role="admin")
        bindings = await repo.list_bindings(item["item_id"])

    assert loaded["slug"] == "vpn-reconnect"
    assert loaded["current_version"]["version_number"] == 1
    assert bindings[0]["service_code"] == "network"


@pytest.mark.asyncio
async def test_knowledge_repo_requires_version_but_not_manual_reviewer(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space(
            {"code": "ops", "title": "Operations", "visibility": "support_internal", "lifecycle_status": "active"},
            actor_id="admin-test",
        )
        item = await repo.create_item_draft(
            {
                "space_code": "ops",
                "slug": "internal-runbook",
                "item_type": "runbook",
                "title": "Internal runbook",
                "visibility": "support_internal",
                "owner_actor_id": "support-owner",
            },
            actor_id="support-test",
        )
        version = await repo.create_version(
            item["item_id"],
            {
                "title": "Internal runbook",
                "summary": "Operational steps",
                "body_format": "markdown",
                "body": "## Steps\n\nRun the documented support procedure.",
            },
            actor_id="support-test",
        )

        with pytest.raises(KnowledgePublicationBlockedError) as exc:
            await repo.publish_item(item["item_id"], None, actor_id="support-test")
        assert {blocker["code"] for blocker in exc.value.blockers} == {"missing_version"}

        published = await repo.publish_item(item["item_id"], version["version_id"], actor_id="support-test")
        await session.commit()

    assert published["status"] == "published"
    assert published["reviewer_actor_id"] == "support-test"
