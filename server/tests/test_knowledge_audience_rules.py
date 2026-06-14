from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    RegistryAudienceGroup,
    RegistryAudienceGroupMember,
    RegistryDepartment,
    RegistryPerson,
    RegistryPersonIdentity,
    UiUser,
)
from app.repos.knowledge_repo import KnowledgeRepo


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


async def _seed_actor(session, *, login: str, department_code: str) -> dict[str, str]:
    department = RegistryDepartment(
        department_id=str(uuid.uuid4()),
        code=department_code,
        name=department_code.upper(),
        status="active",
        source="manual",
    )
    person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name=f"{department_code.upper()} Person",
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


async def _seed_published_item(session) -> dict[str, str]:
    repo = KnowledgeRepo(session)
    space = await repo.upsert_space(
        {
            "code": "audience-api",
            "title": "Audience API",
            "visibility": "requester",
            "lifecycle_status": "active",
        },
        actor_id="admin",
    )
    item = await repo.create_item_draft(
        {
            "space_code": "audience-api",
            "slug": "audience-api-visible",
            "item_type": "article",
            "title": "Audience API visible",
            "summary": "Audience API visible",
            "visibility": "requester",
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
        },
        actor_id="support",
    )
    version = await repo.create_version(
        item["item_id"],
        {"title": "Audience API visible", "body_format": "markdown", "body": "Audience body"},
        actor_id="support",
    )
    await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
    return {"item_id": item["item_id"], "space_id": space["space_id"]}


@pytest.mark.asyncio
async def test_admin_can_replace_list_preview_and_explain_knowledge_audience_rules(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        it_actor = await _seed_actor(session, login="knowledge-it@example.test", department_code="it")
        await _seed_actor(session, login="knowledge-finance@example.test", department_code="finance")
        item = await _seed_published_item(session)
        await session.commit()

    put_response = await test_client.put(
        "/api/web/admin/knowledge/audience-rules",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "item",
            "subject_id": item["item_id"],
            "rules": [
                {
                    "target_type": "department",
                    "target_id": it_actor["department_id"],
                    "include_children": True,
                    "priority": 10,
                    "reason": "IT-only requester article",
                }
            ],
            "reason": "scope item to IT",
        },
    )
    assert put_response.status == 200
    rules = (await put_response.json())["data"]["rules"]
    assert len(rules) == 1
    assert rules[0]["subject_type"] == "item"
    assert rules[0]["subject_id"] == item["item_id"]
    assert rules[0]["target_type"] == "department"
    assert rules[0]["target_id"] == it_actor["department_id"]
    assert rules[0]["include_children"] is True

    list_response = await test_client.get(
        f"/api/web/admin/knowledge/audience-rules?subject_type=item&subject_id={item['item_id']}",
        headers=ADMIN_HEADERS,
    )
    assert list_response.status == 200
    listed = (await list_response.json())["data"]["rules"]
    assert [rule["rule_id"] for rule in listed] == [rules[0]["rule_id"]]

    allowed_preview_response = await test_client.post(
        "/api/web/admin/knowledge/audience-rules/preview",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "item",
            "subject_id": item["item_id"],
            "actor_id": "knowledge-it@example.test",
            "actor_role": "user",
        },
    )
    assert allowed_preview_response.status == 200
    allowed_preview = (await allowed_preview_response.json())["data"]["preview"]
    assert allowed_preview["audience"]["person_id"] == it_actor["person_id"]
    assert allowed_preview["decision"]["allowed"] is True
    assert allowed_preview["decision"]["reason_code"] == "audience_rule_matched"
    assert allowed_preview["decision"]["matched_rule_ids"] == [rules[0]["rule_id"]]

    denied_preview_response = await test_client.post(
        "/api/web/admin/knowledge/audience-rules/preview",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "item",
            "subject_id": item["item_id"],
            "actor_id": "knowledge-finance@example.test",
            "actor_role": "user",
        },
    )
    assert denied_preview_response.status == 200
    denied_preview = (await denied_preview_response.json())["data"]["preview"]
    assert denied_preview["decision"]["allowed"] is False
    assert denied_preview["decision"]["reason_code"] == "audience_rule_not_matched"
    assert denied_preview["decision"]["matched_rule_ids"] == []
    assert rules[0]["rule_id"] not in str(denied_preview["safe_payload"])

    explain_response = await test_client.get(
        f"/api/web/admin/knowledge/access/explain?item_id={item['item_id']}&actor_id=knowledge-it@example.test&actor_role=user",
        headers=ADMIN_HEADERS,
    )
    assert explain_response.status == 200
    explain = (await explain_response.json())["data"]["explain"]
    assert explain["decision"]["allowed"] is True
    assert explain["decision"]["matched_rule_ids"] == [rules[0]["rule_id"]]
    assert explain["item"]["item_id"] == item["item_id"]


@pytest.mark.asyncio
async def test_admin_preview_matches_registry_audience_group_rule(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        member_actor = await _seed_actor(session, login="knowledge-group-member@example.test", department_code="it")
        await _seed_actor(session, login="knowledge-group-outsider@example.test", department_code="finance")
        item = await _seed_published_item(session)
        group = RegistryAudienceGroup(
            audience_group_id=str(uuid.uuid4()),
            code="knowledge_it_members",
            name="Knowledge IT Members",
            status="active",
            source="manual",
        )
        session.add(group)
        await session.flush()
        session.add(
            RegistryAudienceGroupMember(
                audience_group_id=group.audience_group_id,
                member_type="person",
                member_id=member_actor["person_id"],
                source="manual",
            )
        )
        await session.commit()

    put_response = await test_client.put(
        "/api/web/admin/knowledge/audience-rules",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "item",
            "subject_id": item["item_id"],
            "rules": [
                {
                    "target_type": "audience_group",
                    "target_id": group.audience_group_id,
                    "priority": 10,
                    "reason": "IT audience group only",
                }
            ],
            "reason": "scope item to registry audience group",
        },
    )
    assert put_response.status == 200
    rules = (await put_response.json())["data"]["rules"]

    allowed_preview_response = await test_client.post(
        "/api/web/admin/knowledge/audience-rules/preview",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "item",
            "subject_id": item["item_id"],
            "actor_id": "knowledge-group-member@example.test",
            "actor_role": "user",
        },
    )
    assert allowed_preview_response.status == 200
    allowed_preview = (await allowed_preview_response.json())["data"]["preview"]
    assert allowed_preview["audience"]["audience_groups"] == [
        {"audience_group_id": group.audience_group_id, "code": "knowledge_it_members"}
    ]
    assert allowed_preview["decision"]["allowed"] is True
    assert allowed_preview["decision"]["matched_rule_ids"] == [rules[0]["rule_id"]]

    denied_preview_response = await test_client.post(
        "/api/web/admin/knowledge/audience-rules/preview",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "item",
            "subject_id": item["item_id"],
            "actor_id": "knowledge-group-outsider@example.test",
            "actor_role": "user",
        },
    )
    assert denied_preview_response.status == 200
    denied_preview = (await denied_preview_response.json())["data"]["preview"]
    assert denied_preview["audience"]["audience_groups"] == []
    assert denied_preview["decision"]["allowed"] is False
    assert denied_preview["decision"]["reason_code"] == "audience_rule_not_matched"
    assert rules[0]["rule_id"] not in str(denied_preview["safe_payload"])


@pytest.mark.asyncio
async def test_admin_can_preview_space_audience_rules(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        it_actor = await _seed_actor(session, login="knowledge-space-it@example.test", department_code="it-space")
        await _seed_actor(session, login="knowledge-space-finance@example.test", department_code="finance-space")
        repo = KnowledgeRepo(session)
        space = await repo.upsert_space(
            {
                "code": "audience-space-preview",
                "title": "Audience Space Preview",
                "visibility": "requester",
                "lifecycle_status": "active",
            },
            actor_id="admin",
        )
        await session.commit()

    put_response = await test_client.put(
        "/api/web/admin/knowledge/audience-rules",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "space",
            "subject_id": space["space_id"],
            "rules": [
                {
                    "target_type": "department",
                    "target_id": it_actor["department_id"],
                    "priority": 10,
                    "reason": "IT space audience",
                }
            ],
            "reason": "scope space to IT",
        },
    )
    assert put_response.status == 200
    rules = (await put_response.json())["data"]["rules"]

    allowed_preview_response = await test_client.post(
        "/api/web/admin/knowledge/audience-rules/preview",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "space",
            "subject_id": space["space_id"],
            "actor_id": "knowledge-space-it@example.test",
            "actor_role": "user",
        },
    )
    assert allowed_preview_response.status == 200
    allowed_preview = (await allowed_preview_response.json())["data"]["preview"]
    assert allowed_preview["subject"] == {"subject_type": "space", "subject_id": space["space_id"]}
    assert allowed_preview["item"] is None
    assert allowed_preview["space"]["space_id"] == space["space_id"]
    assert allowed_preview["decision"]["allowed"] is True
    assert allowed_preview["decision"]["matched_rule_ids"] == [rules[0]["rule_id"]]

    denied_preview_response = await test_client.post(
        "/api/web/admin/knowledge/audience-rules/preview",
        headers=ADMIN_HEADERS,
        json={
            "subject_type": "space",
            "subject_id": space["space_id"],
            "actor_id": "knowledge-space-finance@example.test",
            "actor_role": "user",
        },
    )
    assert denied_preview_response.status == 200
    denied_preview = (await denied_preview_response.json())["data"]["preview"]
    assert denied_preview["decision"]["allowed"] is False
    assert denied_preview["decision"]["reason_code"] == "audience_rule_not_matched"
    assert rules[0]["rule_id"] not in str(denied_preview["safe_payload"])


@pytest.mark.asyncio
async def test_support_cannot_manage_or_explain_knowledge_audience_rules(test_client) -> None:
    support_headers = {"Authorization": "Bearer test-ui-support-token"}

    put_response = await test_client.put(
        "/api/web/admin/knowledge/audience-rules",
        headers=support_headers,
        json={"subject_type": "item", "subject_id": str(uuid.uuid4()), "rules": []},
    )
    assert put_response.status == 403

    explain_response = await test_client.get(
        f"/api/web/admin/knowledge/access/explain?item_id={uuid.uuid4()}&actor_id=support@example.test&actor_role=user",
        headers=support_headers,
    )
    assert explain_response.status == 403
