from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.graph_service import KnowledgeGraphService


@pytest.mark.asyncio
async def test_knowledge_graph_binding_creates_service_offering_edges_and_filters_visibility(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "it",
                "slug": "vpn-fix",
                "item_type": "article",
                "title": "VPN fix",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        version = await repo.create_version(item["item_id"], {"title": "VPN fix", "body": "Fix VPN", "body_format": "markdown"}, actor_id="support")
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        graph = KnowledgeGraphService(session)
        await graph.ensure_item_binding_edges(item["item_id"], service_code="network", offering_code="network.vpn_issue", actor_id="support")
        await session.commit()

    async with session_maker() as session:
        graph = KnowledgeGraphService(session)
        neighborhood = await graph.neighborhood(stable_key="knowledge_item:vpn-fix", actor_role="requester", depth=2)

    relation_types = {edge["relation_type"] for edge in neighborhood["edges"]}
    assert {"belongs_to_service", "belongs_to_offering"} <= relation_types
    assert all(node["visibility"] in {"public", "requester", "agent_requester_safe"} for node in neighborhood["nodes"])


@pytest.mark.asyncio
async def test_knowledge_graph_depth_is_capped(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        graph = KnowledgeGraphService(session)
        with pytest.raises(ValueError, match="depth"):
            await graph.neighborhood(stable_key="missing", actor_role="admin", depth=3)
