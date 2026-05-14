from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.search_service import KnowledgeSearchService


@pytest.mark.asyncio
async def test_knowledge_search_filters_visibility_and_boosts_offering_binding(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        for slug, title, visibility, service_code, offering_code in (
            ("vpn-reconnect", "VPN не подключается", "requester", "network", "network.vpn_issue"),
            ("vpn-internal-runbook", "VPN internal escalation", "support_internal", "network", "network.vpn_issue"),
            ("printer-reset", "Сброс принтера", "requester", "workplace", "workplace.printer_issue"),
        ):
            item = await repo.create_item_draft(
                {
                    "space_code": "it",
                    "slug": slug,
                    "item_type": "article",
                    "title": title,
                    "summary": title,
                    "visibility": visibility,
                    "owner_actor_id": "owner",
                    "reviewer_actor_id": "reviewer",
                },
                actor_id="support",
            )
            version = await repo.create_version(
                item["item_id"],
                {"title": title, "body_format": "markdown", "body": f"Решение: {title}"},
                actor_id="support",
            )
            await repo.add_binding(item["item_id"], {"service_code": service_code, "offering_code": offering_code}, actor_id="support")
            await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        await session.commit()

    async with session_maker() as session:
        search = KnowledgeSearchService(session)
        requester_results = await search.search(
            query="vpn",
            actor_role="requester",
            service_code="network",
            offering_code="network.vpn_issue",
        )
        support_results = await search.search(query="vpn", actor_role="support", service_code="network")

    assert [item["slug"] for item in requester_results][:1] == ["vpn-reconnect"]
    assert "vpn-internal-runbook" not in {item["slug"] for item in requester_results}
    assert "vpn-internal-runbook" in {item["slug"] for item in support_results}
    assert requester_results[0]["version_id"]
    assert requester_results[0]["snippet"]
