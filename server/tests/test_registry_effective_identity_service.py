from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AccessGroup,
    AccessGroupMember,
    Device,
    RegistryDepartment,
    RegistryAudienceGroup,
    RegistryAudienceGroupMember,
    RegistryPerson,
    RegistryPersonIdentity,
    UiUser,
)
from registry.account_session_service import AccountSessionService
from registry.effective_identity_service import EffectiveIdentityService
from registry.registration_service import RegistrationService


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


def _device(device_id: str, *, hostname: str = "effective-identity") -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname=hostname,
        os="Windows 11",
        capabilities={},
        device_metadata={"machine_id": device_id},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


async def _approved_binding(
    session,
    device_id: str,
    email: str = "owner-effective@example.test",
    *,
    display_name: str = "Effective Owner",
) -> dict:
    service = RegistrationService(session)
    claim = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=email,
        display_name=display_name,
        profile={
            "full_name": display_name,
            "email": email,
            "phone": "+10000000001",
            "relationship_type": "primary_user",
            "user_confirmed": True,
        },
    )
    return await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")


def _warning_codes(payload: dict) -> set[str]:
    return {str(item.get("code")) for item in payload.get("warnings", [])}


@pytest.mark.asyncio
async def test_linked_ui_login_resolves_registry_person_department_path_and_access_groups(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_id = "requester.identity@example.test"

    async with session_maker() as session:
        root = RegistryDepartment(
            department_id=str(uuid.uuid4()),
            code="root",
            name="Root Department",
            status="active",
            source="manual",
        )
        finance = RegistryDepartment(
            department_id=str(uuid.uuid4()),
            code="finance",
            name="Finance",
            parent_department_id=root.department_id,
            status="active",
            source="manual",
        )
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Requester Identity",
            email=actor_id,
            department_id=finance.department_id,
            source="manual",
            status="active",
        )
        group = AccessGroup(code="requester_sensitive", name="Requester Sensitive", is_active=True)
        audience_group = RegistryAudienceGroup(
            audience_group_id=str(uuid.uuid4()),
            code="identity_readers",
            name="Identity Readers",
            status="active",
            source="manual",
        )
        archived_audience_group = RegistryAudienceGroup(
            audience_group_id=str(uuid.uuid4()),
            code="archived_identity_readers",
            name="Archived Identity Readers",
            status="archived",
            source="manual",
        )
        session.add_all(
            [
                root,
                finance,
                person,
                RegistryPersonIdentity(
                    person_id=person.person_id,
                    provider="ui_login",
                    identifier=actor_id,
                    normalized_identifier=actor_id.lower(),
                    verified=True,
                    source="admin_manual",
                ),
                UiUser(user_login=actor_id, password_hash="test", actor_role="user", is_active=True),
                group,
                audience_group,
                archived_audience_group,
            ]
        )
        await session.flush()
        session.add_all(
            [
                AccessGroupMember(group_id=group.id, actor_id=actor_id),
                RegistryAudienceGroupMember(
                    audience_group_id=audience_group.audience_group_id,
                    member_type="person",
                    member_id=person.person_id,
                    source="manual",
                ),
                RegistryAudienceGroupMember(
                    audience_group_id=archived_audience_group.audience_group_id,
                    member_type="person",
                    member_id=person.person_id,
                    source="manual",
                ),
            ]
        )

        service = EffectiveIdentityService(session)
        payload = (await service.resolve_actor_identity(actor_id, "user")).to_dict()
        audience_payload = (
            await service.resolve_person_audience(
                person_id=person.person_id,
                actor_id=actor_id,
                actor_role="user",
            )
        ).to_dict()

    assert payload["actor_id"] == actor_id
    assert payload["actor_role"] == "user"
    assert payload["person"]["person_id"] == person.person_id
    assert payload["person"]["display_name"] == "Requester Identity"
    assert [item["code"] for item in payload["department_path"]] == ["root", "finance"]
    assert payload["access_groups"] == ["requester_sensitive"]
    assert payload["audience_groups"] == [
        {"audience_group_id": audience_group.audience_group_id, "code": "identity_readers"}
    ]
    assert audience_payload["audience_groups"] == [
        {"audience_group_id": audience_group.audience_group_id, "code": "identity_readers"}
    ]
    assert payload["warnings"] == []


@pytest.mark.asyncio
async def test_verified_self_reported_ui_login_resolves_requester_audience(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_id = "self-reported.identity@example.test"

    async with session_maker() as session:
        department = RegistryDepartment(
            department_id=str(uuid.uuid4()),
            code="self-reported-dept",
            name="Self Reported Department",
            status="active",
            source="requester_profile",
        )
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Self Reported Requester",
            email=actor_id,
            department_id=department.department_id,
            source="requester_profile",
            status="self_reported",
        )
        session.add_all(
            [
                department,
                person,
                RegistryPersonIdentity(
                    person_id=person.person_id,
                    provider="ui_login",
                    identifier=actor_id,
                    normalized_identifier=actor_id.lower(),
                    verified=True,
                    source="requester_profile",
                ),
                UiUser(user_login=actor_id, password_hash="test", actor_role="user", is_active=True),
            ]
        )

        service = EffectiveIdentityService(session)
        identity_payload = (await service.resolve_actor_identity(actor_id, "user")).to_dict()
        audience_payload = (
            await service.resolve_person_audience(
                person_id=None,
                actor_id=actor_id,
                actor_role="user",
            )
        ).to_dict()

    assert identity_payload["person"]["person_id"] == person.person_id
    assert [item["department_id"] for item in identity_payload["department_path"]] == [department.department_id]
    assert "registry_person_not_linked" not in _warning_codes(identity_payload)
    assert audience_payload["person_id"] == person.person_id
    assert [item["department_id"] for item in audience_payload["department_path"]] == [department.department_id]


@pytest.mark.asyncio
async def test_audience_group_department_include_children_matches_department_tree_contract(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_id = "department-tree-alias@example.test"

    async with session_maker() as session:
        parent = RegistryDepartment(
            department_id=str(uuid.uuid4()),
            code="contract-parent",
            name="Contract Parent",
            status="active",
            source="manual",
        )
        child = RegistryDepartment(
            department_id=str(uuid.uuid4()),
            code="contract-child",
            name="Contract Child",
            parent_department_id=parent.department_id,
            status="active",
            source="manual",
        )
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Department Child Member",
            email=actor_id,
            department_id=child.department_id,
            source="manual",
            status="active",
        )
        department_alias_group = RegistryAudienceGroup(
            audience_group_id=str(uuid.uuid4()),
            code="department_include_children_alias",
            name="Department Include Children Alias",
            status="active",
            source="manual",
        )
        department_exact_group = RegistryAudienceGroup(
            audience_group_id=str(uuid.uuid4()),
            code="department_exact_parent",
            name="Department Exact Parent",
            status="active",
            source="manual",
        )
        department_tree_group = RegistryAudienceGroup(
            audience_group_id=str(uuid.uuid4()),
            code="department_tree_parent",
            name="Department Tree Parent",
            status="active",
            source="manual",
        )
        session.add_all(
            [
                parent,
                child,
                person,
                UiUser(user_login=actor_id, password_hash="test", actor_role="user", is_active=True),
                RegistryPersonIdentity(
                    person_id=person.person_id,
                    provider="ui_login",
                    identifier=actor_id,
                    normalized_identifier=actor_id.lower(),
                    verified=True,
                    source="admin_manual",
                ),
                department_alias_group,
                department_exact_group,
                department_tree_group,
            ]
        )
        await session.flush()
        session.add_all(
            [
                RegistryAudienceGroupMember(
                    audience_group_id=department_alias_group.audience_group_id,
                    member_type="department",
                    member_id=parent.department_id,
                    include_children=True,
                    source="manual",
                ),
                RegistryAudienceGroupMember(
                    audience_group_id=department_exact_group.audience_group_id,
                    member_type="department",
                    member_id=parent.department_id,
                    include_children=False,
                    source="manual",
                ),
                RegistryAudienceGroupMember(
                    audience_group_id=department_tree_group.audience_group_id,
                    member_type="department_tree",
                    member_id=parent.department_id,
                    source="manual",
                ),
            ]
        )

        payload = (await EffectiveIdentityService(session).resolve_actor_identity(actor_id, "user")).to_dict()

    assert [item["code"] for item in payload["department_path"]] == ["contract-parent", "contract-child"]
    assert [item["code"] for item in payload["audience_groups"]] == [
        "department_include_children_alias",
        "department_tree_parent",
    ]


@pytest.mark.asyncio
async def test_unlinked_ui_user_returns_quality_warning_without_person(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_id = "unlinked.identity@example.test"

    async with session_maker() as session:
        session.add(UiUser(user_login=actor_id, password_hash="test", actor_role="user", is_active=True))

        payload = (await EffectiveIdentityService(session).resolve_actor_identity(actor_id, "user")).to_dict()

    assert payload["actor_id"] == actor_id
    assert payload["person"] is None
    assert "registry_person_not_linked" in _warning_codes(payload)
    assert payload["access_groups"] == []


@pytest.mark.asyncio
async def test_agent_machine_token_does_not_resolve_requester_identity(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))

        payload = (await EffectiveIdentityService(session).resolve_actor_identity(device_id, "agent")).to_dict()

    assert payload["actor_id"] == device_id
    assert payload["actor_role"] == "agent"
    assert payload["person"] is None
    assert payload["identity_source"] == "machine_token"
    assert "agent_machine_identity_not_requester" in _warning_codes(payload)


@pytest.mark.asyncio
async def test_confirmed_account_session_resolves_binding_person_through_session_validation(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        created = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )

        payload = (
            await EffectiveIdentityService(session).resolve_account_session_identity(
                device_id=device_id,
                session_id=created["session"]["session_id"],
                session_token=created["session_token"],
            )
        ).to_dict()

    assert payload["person"]["person_id"] == approved["binding"]["person_id"]
    assert payload["account_session"]["valid"] is True
    assert payload["account_session"]["account_mode"] == "confirmed_binding"
    assert payload["account_session"]["binding_id"] == approved["binding"]["binding_id"]


@pytest.mark.asyncio
async def test_verified_other_account_does_not_use_registered_owner_as_requester_identity(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id, email="base-owner@example.test", display_name="Base Owner")
        account_service = AccountSessionService(session)
        request = await account_service.create_other_account_login_request(
            device_id=device_id,
            requested_account={
                "full_name": "Unlinked Other",
                "display_name": "Other",
                "login": "unlinked-other",
                "email": "unlinked-other@example.test",
                "reason": "Temporary replacement",
            },
        )
        approved_request = await account_service.approve_login_request(request["request_id"], reviewed_by="admin")

        payload = (
            await EffectiveIdentityService(session).resolve_account_session_identity(
                device_id=device_id,
                session_id=approved_request["session"]["session_id"],
                session_token=approved_request["session_token"],
            )
        ).to_dict()

    assert payload["account_session"]["valid"] is True
    assert payload["account_session"]["account_mode"] == "verified_other_account"
    assert payload["account_session"]["base_person_id"] == approved["binding"]["person_id"]
    assert payload["account_session"]["person_id"] is None
    assert payload["person"] is None
    assert "declared_account_unlinked_registry_person" in _warning_codes(payload)


@pytest.mark.asyncio
async def test_identity_explain_payload_never_exposes_account_session_token(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        created = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        payload = (
            await EffectiveIdentityService(session).resolve_account_session_identity(
                device_id=device_id,
                session_id=created["session"]["session_id"],
                session_token=created["session_token"],
            )
        ).to_dict()

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert created["session_token"] not in encoded
    assert "session_token" not in encoded
    assert "session_token_hash" not in encoded


@pytest.mark.asyncio
async def test_admin_effective_identity_route_returns_same_contract(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_id = "route.identity@example.test"

    async with session_maker() as session:
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Route Identity",
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
                    normalized_identifier=actor_id.lower(),
                    verified=True,
                    source="admin_manual",
                ),
            ]
        )
        await session.commit()

    response = await test_client.get(
        f"/api/web/admin/registry/identity/effective?actor_id={actor_id}&actor_role=user",
        headers=ADMIN_HEADERS,
    )
    assert response.status == 200
    payload = (await response.json())["data"]
    assert payload["identity"]["person"]["person_id"] == person.person_id
    assert payload["identity"]["warnings"] == []
