from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeEdge, KnowledgeNode
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.graph_service import KnowledgeGraphService


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-auditor-token"}


async def _seed_acl_item(session, *, slug: str, visibility: str) -> dict:
    repo = KnowledgeRepo(session)
    await repo.upsert_space(
        {"code": f"acl-{slug}", "title": f"ACL {slug}", "visibility": visibility, "lifecycle_status": "active"},
        actor_id="admin-test",
    )
    return await repo.create_item_draft(
        {
            "space_code": f"acl-{slug}",
            "slug": slug,
            "title": f"Item {slug}",
            "visibility": visibility,
            "owner_actor_id": "owner-test",
            "reviewer_actor_id": "reviewer-test",
        },
        actor_id="admin-test",
    )


@pytest.mark.asyncio
async def test_support_list_and_direct_get_do_not_include_admin_or_security_items(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _seed_acl_item(session, slug="support-visible", visibility="support_internal")
        admin_item = await _seed_acl_item(session, slug="admin-hidden", visibility="admin_internal")
        security_item = await _seed_acl_item(session, slug="security-hidden", visibility="security_restricted")
        await session.commit()

    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        support_items = await repo.list_items(actor_role="support", include_archived=True)
        support_slugs = {item["slug"] for item in support_items}
        with pytest.raises(ValueError, match="not found"):
            await repo.get_item(admin_item["item_id"], actor_role="support")
        with pytest.raises(ValueError, match="not found"):
            await repo.get_item(security_item["item_id"], actor_role="support")

    assert "support-visible" in support_slugs
    assert "admin-hidden" not in support_slugs
    assert "security-hidden" not in support_slugs


@pytest.mark.asyncio
async def test_web_acl_denies_support_restricted_mutation_and_auditor_publish(test_client) -> None:
    support_create = await test_client.post(
        "/api/web/knowledge/items",
        headers=_support_headers(),
        json={
            "space_code": "missing-space",
            "slug": "support-security-attempt",
            "title": "Forbidden",
            "visibility": "security_restricted",
        },
    )
    assert support_create.status in {400, 403}

    auditor_publish = await test_client.post(
        "/api/web/knowledge/items/anything/publish",
        headers=_auditor_headers(),
        json={"version_id": "version"},
    )
    assert auditor_publish.status in {401, 403}


@pytest.mark.asyncio
async def test_graph_neighborhood_hides_edges_to_invisible_nodes(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        visible = KnowledgeNode(
            node_id="node-visible",
            stable_key="concept:visible",
            node_type="concept",
            label="Visible",
            visibility="support_internal",
        )
        hidden = KnowledgeNode(
            node_id="node-hidden",
            stable_key="concept:hidden",
            node_type="concept",
            label="Hidden",
            visibility="admin_internal",
        )
        session.add_all([visible, hidden])
        await session.flush()
        session.add(
            KnowledgeEdge(
                edge_id="edge-hidden-target",
                source_node_id=visible.node_id,
                target_node_id=hidden.node_id,
                relation_type="mentions",
                visibility="support_internal",
            )
        )
        await session.commit()

    async with session_maker() as session:
        neighborhood = await KnowledgeGraphService(session).neighborhood(
            stable_key="concept:visible",
            actor_role="support",
            depth=1,
        )

    assert [node["stable_key"] for node in neighborhood["nodes"]] == ["concept:visible"]
    assert neighborhood["edges"] == []


@pytest.mark.asyncio
async def test_graph_node_list_filters_by_actor_role(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                KnowledgeNode(node_id="node-support-list", stable_key="concept:support-list", node_type="concept", label="Support", visibility="support_internal"),
                KnowledgeNode(node_id="node-admin-list", stable_key="concept:admin-list", node_type="concept", label="Admin", visibility="admin_internal"),
            ]
        )
        await session.commit()

    support_resp = await test_client.get("/api/web/knowledge/graph/nodes", headers=_support_headers())
    assert support_resp.status == 200
    payload = await support_resp.json()
    stable_keys = {node["stable_key"] for node in payload["nodes"]}
    assert "concept:support-list" in stable_keys
    assert "concept:admin-list" not in stable_keys


@pytest.mark.asyncio
async def test_admin_can_still_read_admin_internal_item(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item = await _seed_acl_item(session, slug="admin-readable", visibility="admin_internal")
        await session.commit()

    async with session_maker() as session:
        loaded = await KnowledgeRepo(session).get_item(item["item_id"], actor_role="admin")

    assert loaded["slug"] == "admin-readable"
