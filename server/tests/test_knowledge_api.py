from __future__ import annotations

from typing import Any
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeAudienceRule, RegistryDepartment, RegistryPerson, RegistryPersonIdentity, UiUser
from app.repos.knowledge_repo import KnowledgeRepo


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _requester_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-user:requester-knowledge"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-auditor-token"}


FORBIDDEN_SAFE_KEYS = {
    "source_ticket_id",
    "source_passport_id",
    "requester_id",
    "device_id",
    "custom_fields",
    "raw_chunks",
    "metadata_json",
    "trace_id",
    "operation_id",
}


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_SAFE_KEYS:
                found.append(child_path)
            found.extend(_forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, f"{path}[{index}]"))
    return found


async def _seed_requester_identity(session, *, login: str, department_code: str) -> dict[str, str]:
    department = RegistryDepartment(
        department_id=str(uuid.uuid4()),
        code=department_code,
        name=department_code.upper(),
        status="active",
        source="manual",
    )
    person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name=f"{department_code.upper()} Requester",
        email=login,
        department_id=department.department_id,
        source="manual",
        status="active",
    )
    session.add_all(
        [
            department,
            person,
            UiUser(user_login=login, password_hash="test", actor_role="user", is_active=True),
            RegistryPersonIdentity(
                person_id=person.person_id,
                provider="ui_login",
                identifier=login,
                normalized_identifier=login,
                verified=True,
                source="admin_manual",
            ),
        ]
    )
    await session.flush()
    return {"department_id": department.department_id, "person_id": person.person_id}


@pytest.mark.asyncio
async def test_knowledge_space_rejects_requester_portal_flag_for_internal_visibility(test_client) -> None:
    resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={
            "code": "internal-portal-flag",
            "title": "Internal portal flag",
            "visibility": "support_internal",
            "lifecycle_status": "active",
            "metadata": {"show_in_requester_portal": True},
        },
    )
    assert resp.status == 400
    payload = await resp.json()
    assert payload["error"] == "validation_error"
    assert "show_in_requester_portal" in payload["details"]


async def _seed_requester_article(session, *, slug: str, title: str) -> dict[str, str]:
    repo = KnowledgeRepo(session)
    await repo.upsert_space(
        {"code": "audience-api-search", "title": "Audience API Search", "visibility": "requester", "lifecycle_status": "active"},
        actor_id="admin",
    )
    item = await repo.create_item_draft(
        {
            "space_code": "audience-api-search",
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
    return {"item_id": item["item_id"]}


@pytest.mark.asyncio
async def test_public_search_applies_registry_audience_rules_before_projection(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _seed_requester_identity(session, login="requester-knowledge", department_code="it")
        finance = await _seed_requester_identity(session, login="finance-knowledge", department_code="finance")
        await _seed_requester_article(session, slug="it-search-audience-visible", title="Department marker IT visible")
        hidden = await _seed_requester_article(
            session,
            slug="finance-search-audience-hidden",
            title="Department marker Finance hidden",
        )
        session.add(
            KnowledgeAudienceRule(
                rule_id="rule-api-finance-hidden",
                subject_type="item",
                subject_id=hidden["item_id"],
                target_type="department",
                target_id=finance["department_id"],
                effect="allow",
                status="active",
            )
        )
        await session.commit()

    response = await test_client.post(
        "/api/knowledge/search",
        headers=_requester_headers(),
        json={"query": "department marker", "limit": 10, "surface": "requester_portal"},
    )

    assert response.status == 200
    payload = await response.json()
    slugs = {item["slug"] for item in payload["results"]}
    assert "it-search-audience-visible" in slugs
    assert "finance-search-audience-hidden" not in slugs
    assert "Finance hidden" not in str(payload)
    assert _forbidden_paths(payload) == []


@pytest.mark.asyncio
async def test_public_suggestions_apply_registry_audience_rules_before_projection(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _seed_requester_identity(session, login="requester-knowledge", department_code="it")
        finance = await _seed_requester_identity(session, login="finance-knowledge", department_code="finance")
        await _seed_requester_article(session, slug="it-suggest-audience-visible", title="Suggest marker IT visible")
        hidden = await _seed_requester_article(
            session,
            slug="finance-suggest-audience-hidden",
            title="Suggest marker Finance hidden",
        )
        session.add(
            KnowledgeAudienceRule(
                rule_id="rule-suggest-finance-hidden",
                subject_type="item",
                subject_id=hidden["item_id"],
                target_type="department",
                target_id=finance["department_id"],
                effect="allow",
                status="active",
            )
        )
        await session.commit()

    response = await test_client.post(
        "/api/knowledge/suggest",
        headers=_requester_headers(),
        json={"query": "suggest marker", "limit": 10, "surface": "requester_portal"},
    )

    assert response.status == 200
    payload = await response.json()
    slugs = {item["slug"] for item in payload["suggestions"]}
    assert "it-suggest-audience-visible" in slugs
    assert "finance-suggest-audience-hidden" not in slugs
    assert "Finance hidden" not in str(payload)
    assert _forbidden_paths(payload) == []


@pytest.mark.asyncio
async def test_knowledge_ai_proposals_graph_review_lifecycle_and_observer_audit(test_client, test_engine) -> None:
    create_resp = await test_client.post(
        "/api/web/knowledge/ai/proposals",
        headers=_admin_headers(),
        json={
            "proposal_type": "graph_edge",
            "target_kind": "graph",
            "target_ref": "default",
            "title": "Connect AI proposal source",
            "rationale": "AI found related graph concepts.",
            "confidence_score": 0.82,
            "source_kind": "ai_enrichment",
            "source_ref": "test-run",
            "proposed_payload": {
                "graph": {
                    "nodes": [
                        {
                            "stable_key": "concept:ai-proposal-source",
                            "node_type": "concept",
                            "label": "AI proposal source",
                            "visibility": "support_internal",
                        },
                        {
                            "stable_key": "concept:ai-proposal-target",
                            "node_type": "concept",
                            "label": "AI proposal target",
                            "visibility": "support_internal",
                        },
                    ],
                    "edges": [
                        {
                            "source_stable_key": "concept:ai-proposal-source",
                            "target_stable_key": "concept:ai-proposal-target",
                            "relation_type": "similar_to",
                            "visibility": "support_internal",
                        }
                    ],
                },
                "metadata": {"source_ticket_id": "T-secret-should-not-leak"},
            },
        },
    )
    assert create_resp.status == 200
    created_payload = await create_resp.json()
    assert _forbidden_paths(created_payload) == []
    proposal = created_payload["proposal"]
    assert proposal["status"] == "pending"
    assert proposal["proposal_type"] == "graph_edge"

    list_resp = await test_client.get(
        "/api/web/knowledge/ai/proposals?target_kind=graph&status=pending",
        headers=_admin_headers(),
    )
    assert list_resp.status == 200
    list_payload = await list_resp.json()
    assert any(row["proposal_id"] == proposal["proposal_id"] for row in list_payload["proposals"])
    assert _forbidden_paths(list_payload) == []

    auditor_review_resp = await test_client.post(
        f"/api/web/knowledge/ai/proposals/{proposal['proposal_id']}/review",
        headers=_auditor_headers(),
        json={"action": "approve", "note": "auditor cannot approve"},
    )
    assert auditor_review_resp.status == 403

    approve_resp = await test_client.post(
        f"/api/web/knowledge/ai/proposals/{proposal['proposal_id']}/review",
        headers=_admin_headers(),
        json={"action": "approve", "note": "approved by test"},
    )
    assert approve_resp.status == 200
    approved_payload = await approve_resp.json()
    assert approved_payload["proposal"]["status"] == "approved"
    assert approved_payload["proposal"]["review_note"] == "approved by test"
    assert approved_payload["proposal"]["applied_refs"]["edge_ids"]
    assert _forbidden_paths(approved_payload) == []

    search_resp = await test_client.get(
        "/api/web/knowledge/graph/search?q=ai-proposal-source",
        headers=_admin_headers(),
    )
    assert search_resp.status == 200
    graph_payload = await search_resp.json()
    assert any(node["stable_key"] == "concept:ai-proposal-source" for node in graph_payload["nodes"])
    assert any(edge["relation_type"] == "similar_to" for edge in graph_payload["edges"])

    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import AgentRuntimeAudit

    async with get_session() as session:
        rows = (
            await session.execute(
                select(AgentRuntimeAudit)
                .where(AgentRuntimeAudit.source == "knowledge_ai_proposals")
                .order_by(AgentRuntimeAudit.created_at.asc())
            )
        ).scalars().all()
    event_types = [row.event_type for row in rows]
    assert "knowledge.ai_proposal.created" in event_types
    assert "knowledge.ai_proposal.approved" in event_types
    assert all((row.details_json or {}).get("proposal_id") for row in rows)


@pytest.mark.asyncio
async def test_knowledge_api_admin_crud_and_requester_safe_suggest(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "it-api", "title": "IT API", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_admin_headers(),
        json={
            "space_code": "it-api",
            "slug": "vpn-api",
            "item_type": "article",
            "title": "VPN API",
            "summary": "Requester safe VPN article",
            "visibility": "requester",
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
            "bindings": [{"service_code": "network", "offering_code": "network.vpn_issue"}],
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    version_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=_admin_headers(),
        json={"title": "VPN API", "body_format": "markdown", "body": "VPN reconnect steps."},
    )
    assert version_resp.status == 200
    version = (await version_resp.json())["version"]

    versions_resp = await test_client.get(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=_admin_headers(),
    )
    assert versions_resp.status == 200
    versions_payload = await versions_resp.json()
    assert versions_payload["versions"][0]["version_id"] == version["version_id"]

    publish_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/publish",
        headers=_admin_headers(),
        json={"version_id": version["version_id"]},
    )
    assert publish_resp.status == 200

    spaces_resp = await test_client.get("/api/web/knowledge/spaces", headers=_admin_headers())
    assert spaces_resp.status == 200
    spaces_payload = await spaces_resp.json()
    assert any(space["code"] == "it-api" for space in spaces_payload["spaces"])

    items_resp = await test_client.get("/api/web/knowledge/items", headers=_admin_headers())
    assert items_resp.status == 200
    items_payload = await items_resp.json()
    listed_item = next(entry for entry in items_payload["items"] if entry["slug"] == "vpn-api")
    assert listed_item["current_version"]["version_id"] == version["version_id"]

    suggest_resp = await test_client.post(
        "/api/knowledge/suggest",
        headers=_requester_headers(),
        json={"service_code": "network", "offering_code": "network.vpn_issue", "query": "VPN", "surface": "requester_portal"},
    )
    assert suggest_resp.status == 200
    payload = await suggest_resp.json()
    assert payload["status"] == "ok"
    assert payload["suggestions"][0]["slug"] == "vpn-api"
    assert _forbidden_paths(payload) == []

    public_suggest_resp = await test_client.post(
        "/api/knowledge/suggest",
        json={"service_code": "network", "offering_code": "network.vpn_issue", "query": "VPN", "surface": "requester_portal"},
    )
    assert public_suggest_resp.status == 200
    public_payload = await public_suggest_resp.json()
    assert public_payload["suggestions"][0]["slug"] == "vpn-api"
    assert _forbidden_paths(public_payload) == []

    public_feedback_resp = await test_client.post(
        "/api/knowledge/feedback",
        json={
            "item_id": item["item_id"],
            "version_id": version["version_id"],
            "event_type": "deflected",
            "service_code": "network",
            "offering_code": "network.vpn_issue",
            "surface": "requester_portal",
        },
    )
    assert public_feedback_resp.status == 200
    feedback_payload = await public_feedback_resp.json()
    assert feedback_payload["event"]["actor_role"] == "requester"
    assert _forbidden_paths(feedback_payload) == []


@pytest.mark.asyncio
async def test_knowledge_api_adds_helpdesk_binding_to_existing_article(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "binding-api", "title": "Binding API", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_admin_headers(),
        json={
            "space_code": "binding-api",
            "slug": "binding-api-article",
            "item_type": "article",
            "title": "Binding API article",
            "summary": "Draft before binding",
            "visibility": "requester",
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    binding_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/bindings",
        headers=_admin_headers(),
        json={
            "service_code": "network",
            "offering_code": "network.vpn_issue",
            "request_template_key": "network",
            "ticket_type": "incident",
            "metadata": {"surfaces": ["requester_pre_submit", "support_ticket_workspace"]},
        },
    )
    assert binding_resp.status == 200, await binding_resp.text()
    payload = await binding_resp.json()
    assert payload["binding"]["service_code"] == "network"
    assert payload["binding"]["offering_code"] == "network.vpn_issue"
    assert payload["binding"]["request_template_key"] == "network"
    assert payload["binding"]["metadata"]["surfaces"] == ["requester_pre_submit", "support_ticket_workspace"]

    list_resp = await test_client.get(
        f"/api/web/knowledge/items/{item['item_id']}/bindings",
        headers=_admin_headers(),
    )
    assert list_resp.status == 200
    list_payload = await list_resp.json()
    assert [binding["request_template_key"] for binding in list_payload["bindings"]] == ["network"]

    duplicate_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/bindings",
        headers=_admin_headers(),
        json={
            "service_code": "network",
            "offering_code": "network.vpn_issue",
            "request_template_key": "network",
            "ticket_type": "incident",
            "weight": 2,
            "metadata": {"surfaces": ["support_ticket_workspace"]},
        },
    )
    assert duplicate_resp.status == 200, await duplicate_resp.text()
    duplicate_payload = await duplicate_resp.json()
    assert duplicate_payload["binding"]["binding_id"] == payload["binding"]["binding_id"]
    assert duplicate_payload["binding"]["weight"] == 2
    assert duplicate_payload["binding"]["metadata"]["surfaces"] == ["support_ticket_workspace"]

    patch_resp = await test_client.patch(
        f"/api/web/knowledge/items/{item['item_id']}/bindings/{payload['binding']['binding_id']}",
        headers=_admin_headers(),
        json={"queue_code": "network-l2", "metadata": {"surfaces": ["ai_rag"]}},
    )
    assert patch_resp.status == 200, await patch_resp.text()
    patched_payload = await patch_resp.json()
    assert patched_payload["binding"]["queue_code"] == "network-l2"
    assert patched_payload["binding"]["metadata"]["surfaces"] == ["ai_rag"]

    requester_list_resp = await test_client.get(
        f"/api/web/knowledge/items/{item['item_id']}/bindings",
        headers=_requester_headers(),
    )
    assert requester_list_resp.status in {401, 403}

    delete_resp = await test_client.delete(
        f"/api/web/knowledge/items/{item['item_id']}/bindings/{payload['binding']['binding_id']}",
        headers=_admin_headers(),
    )
    assert delete_resp.status == 200, await delete_resp.text()
    assert (await delete_resp.json())["binding"]["binding_id"] == payload["binding"]["binding_id"]

    empty_list_resp = await test_client.get(
        f"/api/web/knowledge/items/{item['item_id']}/bindings",
        headers=_admin_headers(),
    )
    assert empty_list_resp.status == 200
    assert (await empty_list_resp.json())["bindings"] == []


@pytest.mark.asyncio
async def test_knowledge_api_updates_article_rag_policy_metadata(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "rag-policy-api", "title": "RAG Policy API", "visibility": "requester", "lifecycle_status": "active", "allow_rag": True},
    )
    assert space_resp.status == 200

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_admin_headers(),
        json={
            "space_code": "rag-policy-api",
            "slug": "rag-policy-api-article",
            "item_type": "article",
            "title": "RAG policy API article",
            "summary": "Draft before AI/RAG policy",
            "visibility": "requester",
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    patch_resp = await test_client.patch(
        f"/api/web/knowledge/items/{item['item_id']}",
        headers=_admin_headers(),
        json={
            "title": "RAG policy API article",
            "summary": "Updated AI/RAG policy",
            "visibility": "requester",
            "metadata": {"ai_rag_policy": "staff_only"},
        },
    )
    assert patch_resp.status == 200
    patch_payload = await patch_resp.json()
    assert patch_payload["item"]["summary"] == "Updated AI/RAG policy"
    assert patch_payload["item"]["metadata"]["ai_rag_policy"] == "staff_only"

    detail_resp = await test_client.get(f"/api/web/knowledge/items/{item['item_id']}", headers=_admin_headers())
    assert detail_resp.status == 200
    assert (await detail_resp.json())["item"]["metadata"]["ai_rag_policy"] == "staff_only"


@pytest.mark.asyncio
async def test_knowledge_authoring_studio_records_editor_history(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "studio-history", "title": "Studio History", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_admin_headers(),
        json={
            "space_code": "studio-history",
            "slug": "studio-history-vpn",
            "item_type": "article",
            "title": "Studio history VPN",
            "summary": "History-enabled draft",
            "visibility": "requester",
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    version_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=_admin_headers(),
        json={
            "title": "Studio history VPN",
            "summary": "History-enabled version",
            "body_format": "markdown",
            "body": "# VPN\n\nReconnect VPN safely.",
            "change_summary": "Initial authoring version",
        },
    )
    assert version_resp.status == 200
    version = (await version_resp.json())["version"]

    publish_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/publish",
        headers=_admin_headers(),
        json={"version_id": version["version_id"], "review_note": "Publish from Studio"},
    )
    assert publish_resp.status == 200

    review_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/review-action",
        headers=_admin_headers(),
        json={"action": "submit_review", "note": "Ready for review"},
    )
    assert review_resp.status == 200

    comment_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/review-action",
        headers=_admin_headers(),
        json={"action": "comment", "note": "Reviewer comment only"},
    )
    assert comment_resp.status == 200

    approve_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/review-action",
        headers=_admin_headers(),
        json={"action": "approve", "note": "Approved by reviewer"},
    )
    assert approve_resp.status == 200

    history_resp = await test_client.get(
        f"/api/web/knowledge/items/{item['item_id']}/editor-history",
        headers=_admin_headers(),
    )
    assert history_resp.status == 200
    history = await history_resp.json()
    assert history["status"] == "ok"
    event_types = [event["event_type"] for event in history["events"]]
    assert event_types[:6] == ["approved", "commented", "review_submitted", "published", "version_created", "draft_created"]
    assert history["events"][3]["summary"] == "Publish from Studio"
    assert history["diff_cache"][0]["to_version_id"] == version["version_id"]
    assert history["diff_cache"][0]["added_lines"] >= 1
    assert history["diff_cache"][0]["summary"]["change_summary"] == "Initial authoring version"
    assert _forbidden_paths(history) == []


@pytest.mark.asyncio
async def test_knowledge_api_denies_requester_mutation(test_client) -> None:
    resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_requester_headers(),
        json={"space_code": "it", "slug": "forbidden", "title": "Forbidden"},
    )
    assert resp.status in {401, 403}


@pytest.mark.asyncio
async def test_knowledge_graph_edges_reject_unknown_relation_type(test_client) -> None:
    source_resp = await test_client.post(
        "/api/web/knowledge/graph/nodes",
        headers=_admin_headers(),
        json={"stable_key": "concept:source-api", "node_type": "concept", "label": "Source API", "visibility": "support_internal"},
    )
    assert source_resp.status == 200
    target_resp = await test_client.post(
        "/api/web/knowledge/graph/nodes",
        headers=_admin_headers(),
        json={"stable_key": "concept:target-api", "node_type": "concept", "label": "Target API", "visibility": "support_internal"},
    )
    assert target_resp.status == 200

    invalid_resp = await test_client.post(
        "/api/web/knowledge/graph/edges",
        headers=_admin_headers(),
        json={
            "source_stable_key": "concept:source-api",
            "target_stable_key": "concept:target-api",
            "relation_type": "related_to",
            "visibility": "support_internal",
        },
    )
    assert invalid_resp.status == 400
    invalid_payload = await invalid_resp.json()
    assert invalid_payload["error"] == "validation_error"

    valid_resp = await test_client.post(
        "/api/web/knowledge/graph/edges",
        headers=_admin_headers(),
        json={
            "source_stable_key": "concept:source-api",
            "target_stable_key": "concept:target-api",
            "relation_type": "mentions",
            "visibility": "support_internal",
        },
    )
    assert valid_resp.status == 200
    valid_payload = await valid_resp.json()
    assert valid_payload["edge"]["relation_type"] == "mentions"


@pytest.mark.asyncio
async def test_knowledge_graph_layouts_save_and_load(test_client) -> None:
    before_resp = await test_client.get(
        "/api/web/knowledge/graph/layouts/default",
        headers=_admin_headers(),
    )
    assert before_resp.status == 200
    before_payload = await before_resp.json()
    assert before_payload["status"] == "ok"
    assert before_payload["layout"]["scope_ref"] == "default"

    layout_json = {
        "nodes": {
            "concept:vpn": {"x": 120, "y": 240},
            "knowledge_item:vpn-access": {"x": 520, "y": 260},
        },
        "viewport": {"zoom": 1, "pan_x": 0, "pan_y": 0},
    }
    save_resp = await test_client.post(
        "/api/web/knowledge/graph/layouts/default",
        headers=_admin_headers(),
        json={"layout_json": layout_json},
    )
    assert save_resp.status == 200
    saved_payload = await save_resp.json()
    assert saved_payload["status"] == "ok"
    assert saved_payload["layout"]["layout_json"] == layout_json
    assert saved_payload["layout"]["scope_type"] == "graph"
    assert saved_payload["layout"]["scope_ref"] == "default"
    assert _forbidden_paths(saved_payload) == []

    load_resp = await test_client.get(
        "/api/web/knowledge/graph/layouts/default",
        headers=_admin_headers(),
    )
    assert load_resp.status == 200
    loaded_payload = await load_resp.json()
    assert loaded_payload["layout"]["layout_json"] == layout_json

    auditor_save_resp = await test_client.post(
        "/api/web/knowledge/graph/layouts/default",
        headers=_auditor_headers(),
        json={"layout_json": {"nodes": {}}},
    )
    assert auditor_save_resp.status == 403


@pytest.mark.asyncio
async def test_knowledge_graph_crud_search_and_archive(test_client) -> None:
    source_resp = await test_client.post(
        "/api/web/knowledge/graph/nodes",
        headers=_admin_headers(),
        json={
            "stable_key": "concept:crud-source",
            "node_type": "concept",
            "label": "CRUD source",
            "description": "Initial graph CRUD source",
            "visibility": "support_internal",
        },
    )
    assert source_resp.status == 200
    target_resp = await test_client.post(
        "/api/web/knowledge/graph/nodes",
        headers=_admin_headers(),
        json={
            "stable_key": "concept:crud-target",
            "node_type": "concept",
            "label": "CRUD target",
            "visibility": "support_internal",
        },
    )
    assert target_resp.status == 200

    search_resp = await test_client.get(
        "/api/web/knowledge/graph/search?q=crud-source",
        headers=_admin_headers(),
    )
    assert search_resp.status == 200
    search_payload = await search_resp.json()
    assert [node["stable_key"] for node in search_payload["nodes"]] == ["concept:crud-source"]
    assert _forbidden_paths(search_payload) == []

    patch_node_resp = await test_client.patch(
        "/api/web/knowledge/graph/nodes/concept:crud-source",
        headers=_admin_headers(),
        json={"label": "CRUD source updated", "description": "Updated safely", "status": "confirmed"},
    )
    assert patch_node_resp.status == 200
    patched_node = (await patch_node_resp.json())["node"]
    assert patched_node["label"] == "CRUD source updated"
    assert patched_node["description"] == "Updated safely"

    edge_resp = await test_client.post(
        "/api/web/knowledge/graph/edges",
        headers=_admin_headers(),
        json={
            "source_stable_key": "concept:crud-source",
            "target_stable_key": "concept:crud-target",
            "relation_type": "mentions",
            "visibility": "support_internal",
        },
    )
    assert edge_resp.status == 200
    edge_id = (await edge_resp.json())["edge"]["edge_id"]

    get_edge_resp = await test_client.get(
        f"/api/web/knowledge/graph/edges/{edge_id}",
        headers=_admin_headers(),
    )
    assert get_edge_resp.status == 200
    assert (await get_edge_resp.json())["edge"]["relation_type"] == "mentions"

    patch_edge_resp = await test_client.patch(
        f"/api/web/knowledge/graph/edges/{edge_id}",
        headers=_admin_headers(),
        json={"relation_type": "supersedes", "weight": 2, "status": "confirmed"},
    )
    assert patch_edge_resp.status == 200
    patched_edge = (await patch_edge_resp.json())["edge"]
    assert patched_edge["relation_type"] == "supersedes"
    assert patched_edge["weight"] == 2

    auditor_patch_resp = await test_client.patch(
        f"/api/web/knowledge/graph/edges/{edge_id}",
        headers=_auditor_headers(),
        json={"status": "archived"},
    )
    assert auditor_patch_resp.status == 403

    delete_edge_resp = await test_client.delete(
        f"/api/web/knowledge/graph/edges/{edge_id}",
        headers=_admin_headers(),
    )
    assert delete_edge_resp.status == 200
    assert (await delete_edge_resp.json())["edge"]["status"] == "archived"

    delete_node_resp = await test_client.delete(
        "/api/web/knowledge/graph/nodes/concept:crud-source",
        headers=_admin_headers(),
    )
    assert delete_node_resp.status == 200
    assert (await delete_node_resp.json())["node"]["status"] == "archived"

    archived_search_resp = await test_client.get(
        "/api/web/knowledge/graph/search?q=crud-source",
        headers=_admin_headers(),
    )
    assert archived_search_resp.status == 200
    archived_payload = await archived_search_resp.json()
    assert archived_payload["nodes"] == []


@pytest.mark.asyncio
async def test_knowledge_operations_api_exposes_real_packs_quality_gaps_and_rollout(test_client) -> None:
    pack = {
        "code": "it-self-service-api",
        "version": 1,
        "title": "IT Self-Service API",
        "spaces": [{"code": "it-self-service-api", "title": "IT Self-Service API", "visibility": "requester", "lifecycle_status": "active"}],
        "items": [
            {
                "slug": "vpn-api-pack",
                "type": "article",
                "space": "it-self-service-api",
                "title": "VPN API Pack",
                "summary": "Requester safe",
                "visibility": "requester",
                "status": "published",
                "owner": "servicedesk",
                "reviewer": "servicedesk",
                "review_due_days": 90,
                "bindings": [{"service_code": "network", "offering_code": "network.vpn_issue"}],
                "body_format": "markdown",
                "body": "## Steps\nReconnect VPN safely.",
            }
        ],
    }
    dry_run = await test_client.post("/api/web/knowledge/content-packs/apply", headers=_admin_headers(), json={"pack": pack, "dry_run": True})
    assert dry_run.status == 200
    dry_payload = await dry_run.json()
    assert dry_payload["result"]["status"] == "dry_run"
    assert dry_payload["result"]["summary"]["created"] == 1

    install = await test_client.post("/api/web/knowledge/content-packs/apply", headers=_admin_headers(), json={"pack": pack})
    assert install.status == 200
    install_payload = await install.json()
    assert install_payload["result"]["summary"]["created"] == 1

    templates = await test_client.get("/api/web/knowledge/templates", headers=_admin_headers())
    assert templates.status == 200
    template_payload = await templates.json()
    assert any(entry["type"] == "runbook" for entry in template_payload["templates"])

    quality = await test_client.get("/api/web/knowledge/quality", headers=_admin_headers())
    assert quality.status == 200
    quality_payload = await quality.json()
    assert any(entry["slug"] == "vpn-api-pack" for entry in quality_payload["quality"]["items"])

    review = await test_client.get("/api/web/knowledge/review-queue", headers=_admin_headers())
    assert review.status == 200
    assert "items" in (await review.json())["review_queue"]

    rollout = await test_client.post(
        "/api/web/knowledge/rollout-policies",
        headers=_admin_headers(),
        json={"service_code": "network", "offering_code": "network.vpn_issue", "surface": "requester_portal", "enabled": False},
    )
    assert rollout.status == 200

    suggest = await test_client.post(
        "/api/knowledge/suggest",
        headers=_requester_headers(),
        json={"service_code": "network", "offering_code": "network.vpn_issue", "surface": "requester_portal"},
    )
    assert suggest.status == 200
    suggest_payload = await suggest.json()
    assert suggest_payload["suggestions"] == []
    assert suggest_payload["rollout"]["enabled"] is False
