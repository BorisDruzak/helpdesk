from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeQualityModel, KnowledgeSpace


def _unique_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


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


@pytest.mark.asyncio
async def test_support_cannot_create_admin_internal_taxonomy_in_support_visible_space(test_client) -> None:
    code = _unique_code("acl-space")
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": code, "title": "ACL Space", "visibility": "support_internal", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    space = (await space_resp.json())["space"]

    term_resp = await test_client.post(
        "/api/web/knowledge/taxonomy",
        headers=_support_headers(),
        json={
            "space_id": space["space_id"],
            "term_type": "tag",
            "code": _unique_code("restricted-term"),
            "title": "Restricted term",
            "visibility": "admin_internal",
            "status": "active",
        },
    )
    assert term_resp.status in {400, 403}


@pytest.mark.asyncio
async def test_support_cannot_escalate_existing_taxonomy_visibility(test_client) -> None:
    code = _unique_code("acl-escalate")
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": code, "title": "ACL Escalate", "visibility": "support_internal", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    space = (await space_resp.json())["space"]
    term_code = _unique_code("support-term")

    create_resp = await test_client.post(
        "/api/web/knowledge/taxonomy",
        headers=_admin_headers(),
        json={
            "space_id": space["space_id"],
            "term_type": "tag",
            "code": term_code,
            "title": "Support term",
            "visibility": "support_internal",
            "status": "active",
        },
    )
    assert create_resp.status == 200
    assert (await create_resp.json())["term"]["visibility"] == "support_internal"

    escalate_resp = await test_client.post(
        "/api/web/knowledge/taxonomy",
        headers=_support_headers(),
        json={
            "space_id": space["space_id"],
            "term_type": "tag",
            "code": term_code,
            "title": "Support term escalated",
            "visibility": "admin_internal",
            "status": "active",
        },
    )
    assert escalate_resp.status in {400, 403}

    bundle_resp = await test_client.get("/api/web/knowledge/metadata", headers=_admin_headers())
    assert bundle_resp.status == 200
    terms = (await bundle_resp.json())["metadata"]["taxonomy_terms"]
    persisted = next(row for row in terms if row["space_id"] == space["space_id"] and row["code"] == term_code)
    assert persisted["visibility"] == "support_internal"


@pytest.mark.asyncio
async def test_admin_can_create_admin_internal_taxonomy_in_support_visible_space(test_client) -> None:
    code = _unique_code("acl-admin")
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": code, "title": "ACL Admin", "visibility": "support_internal", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    space = (await space_resp.json())["space"]

    term_resp = await test_client.post(
        "/api/web/knowledge/taxonomy",
        headers=_admin_headers(),
        json={
            "space_id": space["space_id"],
            "term_type": "tag",
            "code": _unique_code("admin-term"),
            "title": "Admin term",
            "visibility": "admin_internal",
            "status": "active",
        },
    )
    assert term_resp.status == 200
    assert (await term_resp.json())["term"]["visibility"] == "admin_internal"


@pytest.mark.asyncio
async def test_metadata_bundle_summary_counts_only_active_taxonomy_and_properties(test_client) -> None:
    code = _unique_code("counts-space")
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": code, "title": "Counts Space", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    space = (await space_resp.json())["space"]

    for term_code, status in (("active-term", "active"), ("draft-term", "draft"), ("archived-term", "archived")):
        term_resp = await test_client.post(
            "/api/web/knowledge/taxonomy",
            headers=_admin_headers(),
            json={
                "space_id": space["space_id"],
                "term_type": "tag",
                "code": f"{term_code}-{uuid.uuid4().hex[:6]}",
                "title": term_code,
                "visibility": "requester",
                "status": status,
            },
        )
        assert term_resp.status == 200

    for property_code, status in (("active-property", "active"), ("draft-property", "draft"), ("archived-property", "archived")):
        property_resp = await test_client.post(
            "/api/web/knowledge/properties",
            headers=_admin_headers(),
            json={
                "space_id": space["space_id"],
                "code": f"{property_code}-{uuid.uuid4().hex[:6]}",
                "title": property_code,
                "value_type": "text",
                "status": status,
            },
        )
        assert property_resp.status == 200

    bundle_resp = await test_client.get("/api/web/knowledge/metadata", headers=_admin_headers())
    assert bundle_resp.status == 200
    metadata = (await bundle_resp.json())["metadata"]
    scoped_terms = [row for row in metadata["taxonomy_terms"] if row["space_id"] == space["space_id"]]
    scoped_properties = [row for row in metadata["property_definitions"] if row["space_id"] == space["space_id"]]
    assert len(scoped_terms) == 3
    assert len(scoped_properties) == 3
    assert metadata["summary"]["taxonomy_terms_active"] == sum(1 for row in metadata["taxonomy_terms"] if row["status"] == "active")
    assert metadata["summary"]["property_definitions_active"] == sum(1 for row in metadata["property_definitions"] if row["status"] == "active")
    assert metadata["summary"]["taxonomy_terms_active"] < metadata["summary"]["taxonomy_terms_total"]
    assert metadata["summary"]["property_definitions_active"] < metadata["summary"]["property_definitions_total"]


@pytest.mark.asyncio
async def test_quality_model_global_code_uniqueness_is_db_enforced(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    code = _unique_code("global-quality")
    async with session_maker() as session:
        session.add_all(
            [
                KnowledgeQualityModel(model_id=str(uuid.uuid4()), space_id=None, code=code, title="Global quality one", weights_json={}, thresholds_json={}, status="active"),
                KnowledgeQualityModel(model_id=str(uuid.uuid4()), space_id=None, code=code, title="Global quality two", weights_json={}, thresholds_json={}, status="active"),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_quality_model_global_default_uniqueness_is_db_enforced(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                KnowledgeQualityModel(model_id=str(uuid.uuid4()), space_id=None, code=_unique_code("global-default-a"), title="Global default one", weights_json={}, thresholds_json={}, status="active", is_default=True),
                KnowledgeQualityModel(model_id=str(uuid.uuid4()), space_id=None, code=_unique_code("global-default-b"), title="Global default two", weights_json={}, thresholds_json={}, status="active", is_default=True),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_quality_model_space_default_uniqueness_is_db_enforced(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    space_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            KnowledgeSpace(
                space_id=space_id,
                code=_unique_code("default-space"),
                title="Default Space",
                visibility="requester",
                lifecycle_status="active",
            )
        )
        await session.flush()
        session.add_all(
            [
                KnowledgeQualityModel(model_id=str(uuid.uuid4()), space_id=space_id, code=_unique_code("space-default-a"), title="Space default one", weights_json={}, thresholds_json={}, status="active", is_default=True),
                KnowledgeQualityModel(model_id=str(uuid.uuid4()), space_id=space_id, code=_unique_code("space-default-b"), title="Space default two", weights_json={}, thresholds_json={}, status="active", is_default=True),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()
