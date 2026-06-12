from __future__ import annotations

import pytest


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-auditor-token"}


def _requester_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-user:knowledge-metadata"}


@pytest.mark.asyncio
async def test_knowledge_metadata_model_lifecycle_and_quality_scoring(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "meta-it", "title": "Meta IT", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    space = (await space_resp.json())["space"]

    restricted_space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": "meta-admin-only", "title": "Admin Only Metadata", "visibility": "admin_internal", "lifecycle_status": "active"},
    )
    assert restricted_space_resp.status == 200
    restricted_space = (await restricted_space_resp.json())["space"]

    support_restricted_resp = await test_client.post(
        "/api/web/knowledge/taxonomy",
        headers=_support_headers(),
        json={"space_id": restricted_space["space_id"], "term_type": "tag", "code": "admin-only", "title": "Admin only"},
    )
    assert support_restricted_resp.status in {400, 403}

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_admin_headers(),
        json={
            "space_code": "meta-it",
            "slug": "meta-vpn",
            "item_type": "article",
            "title": "Meta VPN",
            "summary": "Requester safe metadata article",
            "visibility": "requester",
            "owner_actor_id": "owner-meta",
            "reviewer_actor_id": "reviewer-meta",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    taxonomy_resp = await test_client.post(
        "/api/web/knowledge/taxonomy",
        headers=_admin_headers(),
        json={
            "space_id": space["space_id"],
            "term_type": "product",
            "code": "vpn",
            "title": "VPN",
            "description": "Remote access product family",
            "visibility": "requester",
            "status": "active",
        },
    )
    assert taxonomy_resp.status == 200
    term = (await taxonomy_resp.json())["term"]
    assert term["code"] == "vpn"

    property_resp = await test_client.post(
        "/api/web/knowledge/properties",
        headers=_admin_headers(),
        json={
            "space_id": space["space_id"],
            "code": "audience",
            "title": "Audience",
            "value_type": "select",
            "required": True,
            "allowed_values": ["requester", "support"],
            "applies_to_item_types": ["article"],
            "quality_weight": 12,
        },
    )
    assert property_resp.status == 200
    prop = (await property_resp.json())["property"]
    assert prop["required"] is True

    invalid_metadata_resp = await test_client.put(
        f"/api/web/knowledge/items/{item['item_id']}/metadata",
        headers=_support_headers(),
        json={"properties": {"audience": "invalid"}, "taxonomy_term_ids": [term["term_id"]]},
    )
    assert invalid_metadata_resp.status == 400

    metadata_resp = await test_client.put(
        f"/api/web/knowledge/items/{item['item_id']}/metadata",
        headers=_support_headers(),
        json={"properties": {"audience": "requester"}, "taxonomy_term_ids": [term["term_id"]]},
    )
    assert metadata_resp.status == 200
    item_metadata = (await metadata_resp.json())["item_metadata"]
    assert item_metadata["properties"]["audience"] == "requester"
    assert item_metadata["taxonomy_terms"][0]["code"] == "vpn"

    applicability_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/applicability",
        headers=_support_headers(),
        json={
            "rules": [
                {"scope_type": "service", "scope_ref": "network", "include_mode": "include", "priority": 10},
                {"scope_type": "role", "scope_ref": "support", "include_mode": "exclude", "priority": 20},
            ]
        },
    )
    assert applicability_resp.status == 200
    assert [rule["include_mode"] for rule in (await applicability_resp.json())["rules"]] == ["include", "exclude"]

    model_resp = await test_client.post(
        "/api/web/knowledge/quality-models",
        headers=_admin_headers(),
        json={
            "space_id": space["space_id"],
            "code": "metadata-required",
            "title": "Metadata required",
            "is_default": True,
            "weights": {"properties": 12, "applicability": 8, "taxonomy": 5},
            "thresholds": {"good": 80, "review": 65},
        },
    )
    assert model_resp.status == 200
    model = (await model_resp.json())["quality_model"]
    assert model["is_default"] is True

    bundle_resp = await test_client.get("/api/web/knowledge/metadata", headers=_auditor_headers())
    assert bundle_resp.status == 200
    bundle = await bundle_resp.json()
    assert bundle["status"] == "ok"
    assert any(row["code"] == "vpn" for row in bundle["metadata"]["taxonomy_terms"])
    assert any(row["code"] == "audience" for row in bundle["metadata"]["property_definitions"])
    assert any(row["item_id"] == item["item_id"] for row in bundle["metadata"]["item_metadata"])
    assert any(row["code"] == "metadata-required" for row in bundle["metadata"]["quality_models"])

    quality_resp = await test_client.get("/api/web/knowledge/quality", headers=_admin_headers())
    assert quality_resp.status == 200
    quality = (await quality_resp.json())["quality"]
    scored = next(row for row in quality["items"] if row["item_id"] == item["item_id"])
    assert quality["quality_model"]["code"] == "metadata-required"
    assert scored["dimensions"]["properties"] == 12
    assert scored["dimensions"]["applicability"] == 8
    assert scored["dimensions"]["taxonomy"] == 5
    assert "missing_required_property:audience" not in scored["issues"]


@pytest.mark.asyncio
async def test_knowledge_metadata_mutation_forbidden_for_requester_and_public_projection_safe(test_client) -> None:
    requester_post = await test_client.post(
        "/api/web/knowledge/taxonomy",
        headers=_requester_headers(),
        json={"space_id": "missing", "term_type": "tag", "code": "leak", "title": "Leak"},
    )
    assert requester_post.status in {401, 403}

    public_search = await test_client.post(
        "/api/knowledge/search",
        headers=_requester_headers(),
        json={"query": "metadata", "surface": "requester_portal"},
    )
    assert public_search.status == 200
    payload = await public_search.json()
    assert "metadata" not in payload
    assert "quality_model" not in payload
