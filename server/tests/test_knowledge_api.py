from __future__ import annotations

from typing import Any

import pytest


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _requester_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-user:requester-knowledge"}


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
async def test_knowledge_api_denies_requester_mutation(test_client) -> None:
    resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_requester_headers(),
        json={"space_code": "it", "slug": "forbidden", "title": "Forbidden"},
    )
    assert resp.status in {401, 403}
