from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeAudienceRule
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.search_service import KnowledgeSearchService
from registry.audience_contracts import EffectiveAudience


pytestmark = pytest.mark.db_cleanup("knowledge")


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


@pytest.mark.asyncio
async def test_knowledge_search_applies_audience_rules_before_projection(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space(
            {"code": "audience-it", "title": "Audience IT", "visibility": "requester", "lifecycle_status": "active"},
            actor_id="admin",
        )
        for slug, title in (
            ("it-audience-visible", "Audience marker IT visible"),
            ("finance-audience-hidden", "Audience marker Finance hidden"),
        ):
            item = await repo.create_item_draft(
                {
                    "space_code": "audience-it",
                    "slug": slug,
                    "item_type": "article",
                    "title": title,
                    "summary": title,
                    "visibility": "requester",
                    "owner_actor_id": "owner",
                    "reviewer_actor_id": "reviewer",
                },
                actor_id="support",
            )
            version = await repo.create_version(
                item["item_id"],
                {"title": title, "body_format": "markdown", "body": f"Body for {title}"},
                actor_id="support",
            )
            await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
            if slug.startswith("finance"):
                session.add(
                    KnowledgeAudienceRule(
                        rule_id="rule-finance-hidden",
                        subject_type="item",
                        subject_id=item["item_id"],
                        target_type="department",
                        target_id="finance",
                        effect="allow",
                        status="active",
                    )
                )
        await session.commit()

    audience = EffectiveAudience(
        person_id="person-it",
        actor_id="requester-it@example.test",
        actor_role="requester",
        department_path=[{"department_id": "it", "code": "it"}],
    )
    async with session_maker() as session:
        results = await KnowledgeSearchService(session).search(
            query="audience marker",
            actor_role="requester",
            effective_audience=audience,
            limit=10,
        )

    slugs = {item["slug"] for item in results}
    assert "it-audience-visible" in slugs
    assert "finance-audience-hidden" not in slugs
    assert "Finance hidden" not in str(results)
