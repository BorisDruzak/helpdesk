from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeEdge, KnowledgeNode
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.graph_service import KnowledgeGraphService


pytestmark = pytest.mark.db_cleanup("knowledge")

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
async def test_graph_neighborhood_hides_edges_from_invisible_source(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        visible = KnowledgeNode(
            node_id="node-visible-target",
            stable_key="concept:visible-target",
            node_type="concept",
            label="Visible target",
            visibility="support_internal",
        )
        hidden = KnowledgeNode(
            node_id="node-hidden-source",
            stable_key="concept:hidden-source",
            node_type="concept",
            label="Hidden source",
            visibility="admin_internal",
        )
        session.add_all([visible, hidden])
        await session.flush()
        session.add(
            KnowledgeEdge(
                edge_id="edge-hidden-source",
                source_node_id=hidden.node_id,
                target_node_id=visible.node_id,
                relation_type="mentions",
                visibility="support_internal",
            )
        )
        await session.commit()

    async with session_maker() as session:
        neighborhood = await KnowledgeGraphService(session).neighborhood(
            stable_key="concept:visible-target",
            actor_role="support",
            depth=1,
        )

    assert [node["stable_key"] for node in neighborhood["nodes"]] == ["concept:visible-target"]
    assert neighborhood["edges"] == []


@pytest.mark.asyncio
async def test_graph_neighborhood_does_not_traverse_hidden_intermediate(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        root = KnowledgeNode(
            node_id="node-visible-root",
            stable_key="concept:visible-root",
            node_type="concept",
            label="Visible root",
            visibility="support_internal",
        )
        hidden = KnowledgeNode(
            node_id="node-hidden-middle",
            stable_key="concept:hidden-middle",
            node_type="concept",
            label="Hidden middle",
            visibility="admin_internal",
        )
        reachable = KnowledgeNode(
            node_id="node-visible-through-hidden",
            stable_key="concept:visible-through-hidden",
            node_type="concept",
            label="Visible through hidden",
            visibility="support_internal",
        )
        session.add_all([root, hidden, reachable])
        await session.flush()
        session.add_all(
            [
                KnowledgeEdge(
                    edge_id="edge-root-hidden",
                    source_node_id=root.node_id,
                    target_node_id=hidden.node_id,
                    relation_type="mentions",
                    visibility="support_internal",
                ),
                KnowledgeEdge(
                    edge_id="edge-hidden-reachable",
                    source_node_id=hidden.node_id,
                    target_node_id=reachable.node_id,
                    relation_type="mentions",
                    visibility="support_internal",
                ),
            ]
        )
        await session.commit()

    async with session_maker() as session:
        neighborhood = await KnowledgeGraphService(session).neighborhood(
            stable_key="concept:visible-root",
            actor_role="support",
            depth=2,
        )

    assert [node["stable_key"] for node in neighborhood["nodes"]] == ["concept:visible-root"]
    assert neighborhood["edges"] == []


@pytest.mark.asyncio
async def test_graph_neighborhood_edges_have_visible_endpoints_invariant(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        root = KnowledgeNode(
            node_id="node-visible-invariant-root",
            stable_key="concept:visible-invariant-root",
            node_type="concept",
            label="Visible invariant root",
            visibility="support_internal",
        )
        peer = KnowledgeNode(
            node_id="node-visible-invariant-peer",
            stable_key="concept:visible-invariant-peer",
            node_type="concept",
            label="Visible invariant peer",
            visibility="support_internal",
        )
        hidden = KnowledgeNode(
            node_id="node-hidden-invariant",
            stable_key="concept:hidden-invariant",
            node_type="concept",
            label="Hidden invariant",
            visibility="admin_internal",
        )
        session.add_all([root, peer, hidden])
        await session.flush()
        session.add_all(
            [
                KnowledgeEdge(
                    edge_id="edge-visible-invariant",
                    source_node_id=root.node_id,
                    target_node_id=peer.node_id,
                    relation_type="mentions",
                    visibility="support_internal",
                ),
                KnowledgeEdge(
                    edge_id="edge-hidden-invariant",
                    source_node_id=root.node_id,
                    target_node_id=hidden.node_id,
                    relation_type="mentions",
                    visibility="support_internal",
                ),
            ]
        )
        await session.commit()

    async with session_maker() as session:
        neighborhood = await KnowledgeGraphService(session).neighborhood(
            stable_key="concept:visible-invariant-root",
            actor_role="support",
            depth=2,
        )

    returned_node_ids = {node["node_id"] for node in neighborhood["nodes"]}
    assert "node-hidden-invariant" not in returned_node_ids
    for edge in neighborhood["edges"]:
        assert edge["source_node_id"] in returned_node_ids
        assert edge["target_node_id"] in returned_node_ids


@pytest.mark.asyncio
async def test_graph_neighborhood_admin_can_see_admin_internal_when_allowed(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        root = KnowledgeNode(
            node_id="node-admin-root",
            stable_key="concept:admin-root",
            node_type="concept",
            label="Admin root",
            visibility="support_internal",
        )
        admin_node = KnowledgeNode(
            node_id="node-admin-visible",
            stable_key="concept:admin-visible",
            node_type="concept",
            label="Admin visible",
            visibility="admin_internal",
        )
        session.add_all([root, admin_node])
        await session.flush()
        session.add(
            KnowledgeEdge(
                edge_id="edge-admin-visible",
                source_node_id=root.node_id,
                target_node_id=admin_node.node_id,
                relation_type="mentions",
                visibility="admin_internal",
            )
        )
        await session.commit()

    async with session_maker() as session:
        support_neighborhood = await KnowledgeGraphService(session).neighborhood(
            stable_key="concept:admin-root",
            actor_role="support",
            depth=1,
        )
        admin_neighborhood = await KnowledgeGraphService(session).neighborhood(
            stable_key="concept:admin-root",
            actor_role="admin",
            depth=1,
        )

    assert support_neighborhood["edges"] == []
    assert {node["stable_key"] for node in admin_neighborhood["nodes"]} == {
        "concept:admin-root",
        "concept:admin-visible",
    }
    assert [edge["edge_id"] for edge in admin_neighborhood["edges"]] == ["edge-admin-visible"]


@pytest.mark.asyncio
async def test_graph_neighborhood_api_does_not_return_hidden_edge_or_node_ids(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        root = KnowledgeNode(
            node_id="node-api-visible-root",
            stable_key="concept:api-visible-root",
            node_type="concept",
            label="API visible root",
            visibility="support_internal",
        )
        hidden = KnowledgeNode(
            node_id="node-api-hidden-target",
            stable_key="concept:api-hidden-target",
            node_type="concept",
            label="API hidden target",
            visibility="admin_internal",
        )
        session.add_all([root, hidden])
        await session.flush()
        session.add(
            KnowledgeEdge(
                edge_id="edge-api-hidden-target",
                source_node_id=root.node_id,
                target_node_id=hidden.node_id,
                relation_type="mentions",
                visibility="support_internal",
            )
        )
        await session.commit()

    response = await test_client.get(
        "/api/web/knowledge/graph/nodes/node-api-visible-root/neighborhood?depth=1",
        headers=_support_headers(),
    )
    assert response.status == 200
    payload = await response.json()
    assert {node["node_id"] for node in payload["nodes"]} == {"node-api-visible-root"}
    assert payload["edges"] == []
    assert "node-api-hidden-target" not in str(payload)
    assert "edge-api-hidden-target" not in str(payload)


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
