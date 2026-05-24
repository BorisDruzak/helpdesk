from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceAccountSession, DeviceUserBinding, RegistryAsset, RegistryPerson
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
async def test_admin_deactivates_person_and_revokes_bindings_and_sessions(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Deactivated Owner",
            source="manual",
            status="active",
        )
        session.add(person)
        await session.flush()
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
        json={"status": "inactive", "reason": "employee left"},
        headers=ADMIN_HEADERS,
    )
    assert response.status == 200
    payload = await response.json()
    assert payload["data"]["revoked_bindings"][0]["binding_id"] == binding_id

    async with session_maker() as session:
        binding = await session.get(DeviceUserBinding, binding_id)
        account_session = await session.get(DeviceAccountSession, session_id)
        asset = await session.get(RegistryAsset, result["asset"]["asset_id"])

    assert binding.status == "revoked"
    assert account_session.verification_status == "revoked"
    assert account_session.revoked_by == "admin-test"
    assert asset.assigned_person_id is None
