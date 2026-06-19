from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceUserBinding,
    RegistryAdminEvent,
    RegistryAsset,
    RegistryPerson,
    RegistryPersonIdentity,
    UiToken,
    UiUser,
)
from app.repos.auth_tokens_repo import AuthTokensRepo
from requester.identity_service import RequesterIdentityResolver
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService

ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


def _device(device_id: str, *, hostname: str = "people-admin") -> Device:
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


@pytest.mark.asyncio
async def test_admin_creates_updates_and_manages_person_identity(test_client):
    create_response = await test_client.post(
        "/api/web/admin/registry/people",
        json={
            "display_name": "Manual User",
            "full_name": "Manual User Full",
            "email": "manual@example.test",
            "phone": "+70000000000",
            "reason": "created by admin",
        },
        headers=ADMIN_HEADERS,
    )
    assert create_response.status == 200
    created = await create_response.json()
    person_id = created["data"]["person"]["person_id"]

    update_response = await test_client.patch(
        f"/api/web/admin/registry/people/{person_id}",
        json={"display_name": "Manual User Updated", "status": "active"},
        headers=ADMIN_HEADERS,
    )
    assert update_response.status == 200
    updated = await update_response.json()
    assert updated["data"]["person"]["display_name"] == "Manual User Updated"

    identity_response = await test_client.post(
        f"/api/web/admin/registry/people/{person_id}/identities",
        json={"provider": "email", "identifier": "Manual@Example.Test", "verified": False, "reason": "mail checked"},
        headers=ADMIN_HEADERS,
    )
    assert identity_response.status == 200
    identity = (await identity_response.json())["data"]["identity"]
    assert identity["normalized_identifier"] == "manual@example.test"
    assert identity["verified"] is False

    verify_response = await test_client.patch(
        f"/api/web/admin/registry/identities/{identity['identity_id']}",
        json={"verified": True, "source": "admin_manual"},
        headers=ADMIN_HEADERS,
    )
    assert verify_response.status == 200
    verified = (await verify_response.json())["data"]["identity"]
    assert verified["verified"] is True


@pytest.mark.asyncio
async def test_admin_identity_collision_does_not_steal_verified_identity(test_client):
    first_response = await test_client.post(
        "/api/web/admin/registry/people",
        json={"display_name": "Identity Owner"},
        headers=ADMIN_HEADERS,
    )
    second_response = await test_client.post(
        "/api/web/admin/registry/people",
        json={"display_name": "Identity Collision"},
        headers=ADMIN_HEADERS,
    )
    first_id = (await first_response.json())["data"]["person"]["person_id"]
    second_id = (await second_response.json())["data"]["person"]["person_id"]

    first_identity = await test_client.post(
        f"/api/web/admin/registry/people/{first_id}/identities",
        json={"provider": "email", "identifier": "collision@example.test", "verified": True},
        headers=ADMIN_HEADERS,
    )
    assert first_identity.status == 200

    collision = await test_client.post(
        f"/api/web/admin/registry/people/{second_id}/identities",
        json={"provider": "email", "identifier": "collision@example.test", "verified": True},
        headers=ADMIN_HEADERS,
    )
    assert collision.status == 409
    payload = await collision.json()
    assert payload["error_code"] == "IDENTITY_COLLISION"
    assert payload["collision_person_id"] == first_id


@pytest.mark.asyncio
async def test_admin_links_ui_user_to_registry_person(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    user_login = "Requester.Link@Example.Test"

    async with session_maker() as session:
        session.add(UiUser(user_login=user_login, password_hash="test", actor_role="user", is_active=True))
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Requester Link",
            email="requester.link@example.test",
            source="manual",
            status="active",
        )
        session.add(person)
        await session.commit()
        person_id = person.person_id

    response = await test_client.post(
        f"/api/web/admin/registry/ui-users/{user_login}/link-person",
        json={"person_id": person_id, "reason": "verified requester account"},
        headers=ADMIN_HEADERS,
    )
    assert response.status == 200
    payload = await response.json()
    assert payload["data"]["ui_user"]["user_login"] == user_login
    assert payload["data"]["ui_user"]["linked_person_id"] == person_id
    identity = payload["data"]["identity"]
    assert identity["provider"] == "ui_login"
    assert identity["identifier"] == user_login
    assert identity["normalized_identifier"] == user_login.lower()
    assert identity["verified"] is True

    async with session_maker() as session:
        stored_identity = (
            await session.execute(
                select(RegistryPersonIdentity).where(
                    RegistryPersonIdentity.provider == "ui_login",
                    RegistryPersonIdentity.normalized_identifier == user_login.lower(),
                )
            )
        ).scalar_one()
        event = (
            await session.execute(
                select(RegistryAdminEvent)
                .where(RegistryAdminEvent.event_type == "identity_added")
                .where(RegistryAdminEvent.related_person_id == person_id)
            )
        ).scalar_one()
        resolved_person = await RequesterIdentityResolver(session).resolve_person_for_web_user(user_login.lower())

    assert stored_identity.person_id == person_id
    assert stored_identity.verified is True
    assert event.payload["ui_user_login"] == user_login
    assert resolved_person is not None
    assert resolved_person.person_id == person_id


@pytest.mark.asyncio
async def test_admin_ui_user_link_collision_does_not_steal_login(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    user_login = "collision-ui@example.test"

    async with session_maker() as session:
        session.add(UiUser(user_login=user_login, password_hash="test", actor_role="user", is_active=True))
        first = RegistryPerson(person_id=str(uuid.uuid4()), display_name="UI Owner", source="manual", status="active")
        second = RegistryPerson(person_id=str(uuid.uuid4()), display_name="UI Collision", source="manual", status="active")
        session.add_all([first, second])
        await session.flush()
        await RegistrationService(session).repo.create_or_update_person_identity(
            person_id=first.person_id,
            provider="ui_login",
            identifier=user_login,
            verified=True,
            source="admin_manual",
        )
        await session.commit()
        first_id = first.person_id
        second_id = second.person_id

    response = await test_client.post(
        f"/api/web/admin/registry/ui-users/{user_login}/link-person",
        json={"person_id": second_id, "reason": "wrong target"},
        headers=ADMIN_HEADERS,
    )
    assert response.status == 409
    payload = await response.json()
    assert payload["error_code"] == "IDENTITY_COLLISION"
    assert payload["collision_person_id"] == first_id

    async with session_maker() as session:
        identity = (
            await session.execute(
                select(RegistryPersonIdentity).where(
                    RegistryPersonIdentity.provider == "ui_login",
                    RegistryPersonIdentity.normalized_identifier == user_login,
                )
            )
        ).scalar_one()
    assert identity.person_id == first_id


@pytest.mark.asyncio
@pytest.mark.parametrize("target_status", ["inactive", "archived"])
async def test_admin_deactivates_person_and_revokes_bindings_and_sessions(test_client, test_engine, target_status):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    user_login = f"status-user-{uuid.uuid4().hex[:8]}"
    token = f"ui-token-{uuid.uuid4().hex}"
    token_hash = AuthTokensRepo.hash_token(token)

    async with session_maker() as session:
        session.add(_device(device_id))
        session.add(UiUser(user_login=user_login, password_hash="test", actor_role="user", is_active=True))
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Deactivated Owner",
            source="manual",
            status="active",
        )
        session.add(person)
        await session.flush()
        session.add(
            RegistryPersonIdentity(
                person_id=person.person_id,
                provider="ui_login",
                identifier=user_login,
                normalized_identifier=user_login.lower(),
                verified=True,
                source="admin_manual",
            )
        )
        session.add(
            UiToken(
                token_hash=token_hash,
                token_prefix=token[:8],
                user_login=user_login,
                actor_role="user",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        result = await RegistrationService(session).bind_person_to_device(
            device_id=device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin-test",
            reason="initial owner",
        )
        account = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=result["binding"]["binding_id"],
        )
        await session.commit()
        person_id = person.person_id
        binding_id = result["binding"]["binding_id"]
        session_id = account["session"]["session_id"]

    response = await test_client.patch(
        f"/api/web/admin/registry/people/{person_id}",
        json={"status": target_status, "reason": "employee left"},
        headers=ADMIN_HEADERS,
    )
    assert response.status == 200
    payload = await response.json()
    assert payload["data"]["revoked_bindings"][0]["binding_id"] == binding_id
    assert payload["data"]["disabled_ui_users"][0]["user_login"] == user_login

    async with session_maker() as session:
        binding = await session.get(DeviceUserBinding, binding_id)
        account_session = await session.get(DeviceAccountSession, session_id)
        asset = await session.get(RegistryAsset, result["asset"]["asset_id"])
        ui_user = await session.get(UiUser, user_login)
        ui_token = await session.get(UiToken, token_hash)

    assert binding.status == "revoked"
    assert account_session.verification_status == "revoked"
    assert account_session.revoked_by == "admin-test"
    assert asset.assigned_person_id is None
    assert ui_user.is_active is False
    assert ui_token.revoked_at is not None
