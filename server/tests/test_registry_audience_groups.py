from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AccessGroup,
    AccessGroupMember,
    AccessGroupPermission,
    RegistryAdminEvent,
    RegistryDepartment,
    RegistryPerson,
    RegistryPersonIdentity,
    UiUser,
)
from app.repos.access_control_repo import AccessControlRepo


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


async def _seed_audience_people(session) -> dict[str, str]:
    finance = RegistryDepartment(
        department_id=str(uuid.uuid4()),
        code="finance",
        name="Finance",
        status="active",
        source="manual",
    )
    payroll = RegistryDepartment(
        department_id=str(uuid.uuid4()),
        code="payroll",
        name="Payroll",
        parent_department_id=finance.department_id,
        status="active",
        source="manual",
    )
    archived = RegistryDepartment(
        department_id=str(uuid.uuid4()),
        code="archived",
        name="Archived",
        status="archived",
        source="manual",
    )
    finance_person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name="Finance Person",
        department_id=finance.department_id,
        source="manual",
        status="active",
    )
    payroll_person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name="Payroll Person",
        department_id=payroll.department_id,
        source="manual",
        status="active",
    )
    support_person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name="Support Person",
        email="support-audience@example.test",
        source="manual",
        status="active",
    )
    session.add_all([finance, payroll, archived, finance_person, payroll_person, support_person])
    session.add_all(
        [
            UiUser(user_login="support-audience@example.test", password_hash="test", actor_role="support", is_active=True),
            RegistryPersonIdentity(
                person_id=support_person.person_id,
                provider="ui_login",
                identifier="support-audience@example.test",
                normalized_identifier="support-audience@example.test",
                verified=True,
                source="admin_manual",
            ),
        ]
    )
    access_group = AccessGroup(code="support_audience", name="Support Audience", is_active=True)
    session.add(access_group)
    await session.flush()
    session.add(AccessGroupMember(group_id=access_group.id, actor_id="support-audience@example.test"))
    session.add(AccessGroupPermission(group_id=access_group.id, permission_code="settings.manage_queues"))
    await session.commit()
    return {
        "finance_department_id": finance.department_id,
        "payroll_department_id": payroll.department_id,
        "archived_department_id": archived.department_id,
        "finance_person_id": finance_person.person_id,
        "payroll_person_id": payroll_person.person_id,
        "support_person_id": support_person.person_id,
    }


@pytest.mark.asyncio
async def test_admin_audience_group_crud_members_preview_and_audit(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        seeded = await _seed_audience_people(session)

    create_response = await test_client.post(
        "/api/web/admin/registry/audience-groups",
        headers=ADMIN_HEADERS,
        json={"code": "finance_staff", "name": "Finance Staff", "description": "Finance visibility"},
    )
    assert create_response.status == 200
    group = (await create_response.json())["data"]["group"]
    assert group["code"] == "finance_staff"
    assert group["status"] == "active"

    members_response = await test_client.put(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/members",
        headers=ADMIN_HEADERS,
        json={
            "members": [
                {"member_type": "department_tree", "member_id": seeded["finance_department_id"], "include_children": True},
                {"member_type": "person", "member_id": seeded["support_person_id"]},
                {"member_type": "access_group", "member_id": "support_audience"},
            ],
            "reason": "seed finance audience",
        },
    )
    assert members_response.status == 200
    members = (await members_response.json())["data"]["members"]
    assert [item["member_type"] for item in members] == ["access_group", "department_tree", "person"]

    preview_response = await test_client.post(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/preview-members",
        headers=ADMIN_HEADERS,
        json={},
    )
    assert preview_response.status == 200
    preview = (await preview_response.json())["data"]["preview"]
    assert preview["person_count"] == 3
    assert {item["person_id"] for item in preview["people"]} == {
        seeded["finance_person_id"],
        seeded["payroll_person_id"],
        seeded["support_person_id"],
    }
    assert preview["warnings"] == []

    async with session_maker() as session:
        events = (
            await session.execute(
                select(RegistryAdminEvent)
                .where(RegistryAdminEvent.object_type == "audience_group")
                .where(RegistryAdminEvent.object_id == group["audience_group_id"])
                .order_by(RegistryAdminEvent.event_at.asc())
            )
        ).scalars().all()

    assert [event.event_type for event in events] == ["audience_group_created", "audience_group_members_updated"]


@pytest.mark.asyncio
async def test_audience_group_preview_reports_empty_unknown_archived_and_broad_role_warnings(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        seeded = await _seed_audience_people(session)

    create_response = await test_client.post(
        "/api/web/admin/registry/audience-groups",
        headers=ADMIN_HEADERS,
        json={"code": "warning_group", "name": "Warning Group"},
    )
    group = (await create_response.json())["data"]["group"]

    empty_preview_response = await test_client.post(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/preview-members",
        headers=ADMIN_HEADERS,
        json={},
    )
    empty_preview = (await empty_preview_response.json())["data"]["preview"]
    assert empty_preview["person_count"] == 0
    assert "empty_group" in {item["code"] for item in empty_preview["warnings"]}

    members_response = await test_client.put(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/members",
        headers=ADMIN_HEADERS,
        json={
            "members": [
                {"member_type": "department", "member_id": seeded["archived_department_id"]},
                {"member_type": "person", "member_id": str(uuid.uuid4())},
                {"member_type": "role", "member_id": "user"},
            ]
        },
    )
    assert members_response.status == 200

    preview_response = await test_client.post(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/preview-members",
        headers=ADMIN_HEADERS,
        json={},
    )
    preview = (await preview_response.json())["data"]["preview"]
    warning_codes = {item["code"] for item in preview["warnings"]}
    assert "archived_department" in warning_codes
    assert "unknown_person" in warning_codes
    assert "broad_role" in warning_codes


@pytest.mark.asyncio
async def test_audience_group_department_include_children_preview_matches_department_tree_contract(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        seeded = await _seed_audience_people(session)

    create_response = await test_client.post(
        "/api/web/admin/registry/audience-groups",
        headers=ADMIN_HEADERS,
        json={"code": "department_alias_preview", "name": "Department Alias Preview"},
    )
    assert create_response.status == 200
    group = (await create_response.json())["data"]["group"]

    members_response = await test_client.put(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/members",
        headers=ADMIN_HEADERS,
        json={
            "members": [
                {
                    "member_type": "department",
                    "member_id": seeded["finance_department_id"],
                    "include_children": True,
                }
            ],
        },
    )
    assert members_response.status == 200
    members = (await members_response.json())["data"]["members"]
    assert [(item["member_type"], item["include_children"]) for item in members] == [("department", True)]

    preview_response = await test_client.post(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/preview-members",
        headers=ADMIN_HEADERS,
        json={},
    )
    assert preview_response.status == 200
    preview = (await preview_response.json())["data"]["preview"]
    assert preview["person_count"] == 2
    assert {item["person_id"] for item in preview["people"]} == {
        seeded["finance_person_id"],
        seeded["payroll_person_id"],
    }
    assert preview["warnings"] == []


@pytest.mark.asyncio
async def test_audience_group_archive_excludes_default_list_and_does_not_grant_rbac(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_id = "audience-only@example.test"
    async with session_maker() as session:
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Audience Only",
            email=actor_id,
            source="manual",
            status="active",
        )
        session.add_all(
            [
                person,
                UiUser(user_login=actor_id, password_hash="test", actor_role="user", is_active=True),
                RegistryPersonIdentity(
                    person_id=person.person_id,
                    provider="ui_login",
                    identifier=actor_id,
                    normalized_identifier=actor_id,
                    verified=True,
                    source="admin_manual",
                ),
            ]
        )
        await session.commit()

    create_response = await test_client.post(
        "/api/web/admin/registry/audience-groups",
        headers=ADMIN_HEADERS,
        json={"code": "temporary_audience", "name": "Temporary Audience"},
    )
    group = (await create_response.json())["data"]["group"]
    await test_client.put(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/members",
        headers=ADMIN_HEADERS,
        json={"members": [{"member_type": "person", "member_id": person.person_id}]},
    )

    async with session_maker() as session:
        assert await AccessControlRepo(session).get_actor_group_permissions(actor_id) == []

    archive_response = await test_client.post(
        f"/api/web/admin/registry/audience-groups/{group['audience_group_id']}/archive",
        headers=ADMIN_HEADERS,
        json={"reason": "test cleanup"},
    )
    assert archive_response.status == 200
    assert (await archive_response.json())["data"]["group"]["status"] == "archived"

    list_response = await test_client.get("/api/web/admin/registry/audience-groups", headers=ADMIN_HEADERS)
    groups = (await list_response.json())["data"]["groups"]
    assert all(item["audience_group_id"] != group["audience_group_id"] for item in groups)

    archived_response = await test_client.get(
        "/api/web/admin/registry/audience-groups?include_archived=true",
        headers=ADMIN_HEADERS,
    )
    archived_groups = (await archived_response.json())["data"]["groups"]
    assert any(item["audience_group_id"] == group["audience_group_id"] for item in archived_groups)
