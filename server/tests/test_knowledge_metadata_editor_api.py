from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import AccessGroup, AccessGroupMember, AccessGroupPermission, UiUser


pytestmark = pytest.mark.db_cleanup("knowledge")

def _unique_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-support-token"}


async def _grant_support_knowledge_manager(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        group = AccessGroup(
            code=f"knowledge_manager_{uuid.uuid4().hex[:8]}",
            name="Knowledge managers",
            description=None,
            is_active=True,
        )
        session.add(group)
        await session.flush()
        session.add(AccessGroupMember(group_id=group.id, actor_id="support-test"))
        for permission in ("workspace.admin.view", "knowledge.metadata.manage"):
            session.add(AccessGroupPermission(group_id=group.id, permission_code=permission))
        await session.commit()


@pytest.mark.asyncio
async def test_support_without_knowledge_manager_permission_cannot_mutate_metadata(test_client) -> None:
    space_code = _unique_code("editor-rbac")
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": space_code, "title": "Editor RBAC", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    space = (await space_resp.json())["space"]

    denied_resp = await test_client.post(
        "/api/web/knowledge/taxonomy",
        headers=_support_headers(),
        json={
            "space_id": space["space_id"],
            "term_type": "tag",
            "code": "support-denied",
            "title": "Support denied",
            "visibility": "requester",
            "status": "active",
        },
    )
    assert denied_resp.status == 403
    denied_payload = await denied_resp.json()
    assert denied_payload["error_code"] == "FORBIDDEN"
    assert denied_payload["required_permission"] == "knowledge.metadata.manage"


@pytest.mark.asyncio
async def test_metadata_editor_requires_required_property_values(test_client, test_engine) -> None:
    await _grant_support_knowledge_manager(test_engine)
    space_code = _unique_code("editor-required")
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": space_code, "title": "Editor Required", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    space = (await space_resp.json())["space"]

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_admin_headers(),
        json={
            "space_code": space_code,
            "slug": _unique_code("required-article"),
            "item_type": "article",
            "title": "Required metadata article",
            "summary": "Required metadata validation target",
            "visibility": "requester",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    property_resp = await test_client.post(
        "/api/web/knowledge/properties",
        headers=_admin_headers(),
        json={
            "space_id": space["space_id"],
            "code": "audience",
            "title": "Аудитория",
            "value_type": "select",
            "required": True,
            "allowed_values": ["requester", "support"],
            "applies_to_item_types": ["article"],
            "status": "active",
        },
    )
    assert property_resp.status == 200

    missing_resp = await test_client.put(
        f"/api/web/knowledge/items/{item['item_id']}/metadata",
        headers=_support_headers(),
        json={"properties": {}, "taxonomy_term_ids": []},
    )
    assert missing_resp.status == 400
    missing_payload = await missing_resp.json()
    assert missing_payload["error"] == "validation_error"
    assert "required property is missing: audience" in missing_payload["details"]

    invalid_resp = await test_client.put(
        f"/api/web/knowledge/items/{item['item_id']}/metadata",
        headers=_support_headers(),
        json={"properties": {"audience": "manager"}, "taxonomy_term_ids": []},
    )
    assert invalid_resp.status == 400

    valid_resp = await test_client.put(
        f"/api/web/knowledge/items/{item['item_id']}/metadata",
        headers=_support_headers(),
        json={"properties": {"audience": "requester"}, "taxonomy_term_ids": []},
    )
    assert valid_resp.status == 200
    metadata = (await valid_resp.json())["item_metadata"]
    assert metadata["properties"]["audience"] == "requester"


@pytest.mark.asyncio
async def test_metadata_editor_applicability_replacement_roundtrip(test_client, test_engine) -> None:
    await _grant_support_knowledge_manager(test_engine)
    space_code = _unique_code("editor-app")
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=_admin_headers(),
        json={"code": space_code, "title": "Editor Applicability", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200

    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=_admin_headers(),
        json={
            "space_code": space_code,
            "slug": _unique_code("applicability-article"),
            "item_type": "article",
            "title": "Applicability article",
            "summary": "Applicability editor target",
            "visibility": "requester",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]

    replace_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/applicability",
        headers=_support_headers(),
        json={
            "rules": [
                {"scope_type": "service", "scope_ref": "network/vpn", "include_mode": "include", "priority": 10},
                {"scope_type": "role", "scope_ref": "contractor", "include_mode": "exclude", "priority": 20},
            ]
        },
    )
    assert replace_resp.status == 200
    assert [row["scope_type"] for row in (await replace_resp.json())["rules"]] == ["service", "role"]

    get_resp = await test_client.get(
        f"/api/web/knowledge/items/{item['item_id']}/applicability",
        headers=_support_headers(),
    )
    assert get_resp.status == 200
    rules = (await get_resp.json())["rules"]
    assert [(row["scope_type"], row["scope_ref"], row["include_mode"]) for row in rules] == [
        ("service", "network/vpn", "include"),
        ("role", "contractor", "exclude"),
    ]


@pytest.mark.asyncio
async def test_metadata_editor_read_bundle_for_auditor_and_mutation_denied(test_client) -> None:
    bundle_resp = await test_client.get("/api/web/knowledge/metadata", headers={"Authorization": "Bearer test-ui-auditor-token"})
    assert bundle_resp.status == 200
    assert (await bundle_resp.json())["status"] == "ok"

    mutate_resp = await test_client.post(
        "/api/web/knowledge/properties",
        headers={"Authorization": "Bearer test-ui-auditor-token"},
        json={"space_id": "missing", "code": "auditor", "title": "Auditor", "value_type": "text"},
    )
    assert mutate_resp.status == 403

    requester_bundle_resp = await test_client.get(
        "/api/web/knowledge/metadata",
        headers={"Authorization": "Bearer test-ui-user:metadata-editor"},
    )
    assert requester_bundle_resp.status in {401, 403}
