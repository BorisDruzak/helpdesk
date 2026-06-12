from __future__ import annotations

from typing import Any

import pytest


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
