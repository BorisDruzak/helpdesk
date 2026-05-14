from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.suggestion_service import KnowledgeSuggestionService


@pytest.mark.asyncio
async def test_knowledge_suggestions_return_requester_safe_bound_items(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "it",
                "slug": "vpn-reconnect",
                "item_type": "article",
                "title": "Как переподключить VPN",
                "summary": "Подходит для проблем с VPN",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": "Как переподключить VPN", "body_format": "markdown", "body": "1. Отключите VPN.\n2. Подключите снова."},
            actor_id="support",
        )
        await repo.add_binding(item["item_id"], {"service_code": "network", "offering_code": "network.vpn_issue", "request_template_key": "vpn_issue"}, actor_id="support")
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        await session.commit()

    async with session_maker() as session:
        suggestions = await KnowledgeSuggestionService(session).suggest(
            {
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "request_template_key": "vpn_issue",
                "query": "VPN не подключается",
                "surface": "requester_portal",
            },
            actor_role="requester",
        )

    assert suggestions["suggestions"][0]["slug"] == "vpn-reconnect"
    assert suggestions["suggestions"][0]["reason"]
    assert "source_ticket_id" not in suggestions["suggestions"][0]


@pytest.mark.asyncio
async def test_support_suggestions_can_include_internal_runbooks(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "ops", "title": "Ops", "visibility": "support_internal", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "ops",
                "slug": "vpn-escalation-runbook",
                "item_type": "runbook",
                "title": "VPN escalation runbook",
                "visibility": "support_internal",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": "VPN escalation runbook", "body_format": "markdown", "body": "Internal escalation."},
            actor_id="support",
        )
        await repo.add_binding(item["item_id"], {"service_code": "network", "offering_code": "network.vpn_issue"}, actor_id="support")
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        await session.commit()

    async with session_maker() as session:
        suggestions = await KnowledgeSuggestionService(session).suggest(
            {"service_code": "network", "offering_code": "network.vpn_issue", "query": "vpn", "surface": "support_workspace"},
            actor_role="support",
        )

    assert "vpn-escalation-runbook" in {item["slug"] for item in suggestions["suggestions"]}
