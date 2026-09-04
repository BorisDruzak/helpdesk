from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceInventoryBinding,
    DeviceUserBinding,
    RegistryAsset,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
)
from registry.policy_service import RegistryPolicyService
from registry.registration_service import RegistrationService, RegistrationValidationError


pytestmark = pytest.mark.db_cleanup("registry_access")

def _device(device_id: str, *, hostname: str = "policy-reg-pc") -> Device:
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
async def test_required_existing_policy_rejects_free_text_and_invalid_registry_ids(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        department = await service.registry_repo.get_or_create_department(
            name="Strict Registry Department",
            source="manual",
            status="active",
        )
        location = await service.registry_repo.get_or_create_location(
            building="HQ",
            floor="4",
            room="401",
            source="manual",
            status="active",
        )
        await RegistryPolicyService(session).update_policies(
            {
                "registration": {
                    "department_mode": "required_existing",
                    "location_mode": "required_existing",
                }
            },
            actor_id="admin",
        )

        with pytest.raises(RegistrationValidationError, match="department_id is required"):
            await service.submit_agent_profile_claim(
                device_id=device_id,
                requester_id="free-text@example.test",
                display_name="Free Text User",
                profile={
                    "full_name": "Free Text User",
                    "email": "free-text@example.test",
                    "department": "Shadow Department",
                    "building": "Shadow HQ",
                    "room": "404",
                },
            )

        pending_departments = (
            await session.execute(
                select(RegistryDepartment).where(
                    RegistryDepartment.source == "agent_profile",
                    RegistryDepartment.status == "pending",
                    RegistryDepartment.name == "Shadow Department",
                )
            )
        ).scalars().all()
        pending_locations = (
            await session.execute(
                select(RegistryLocation).where(
                    RegistryLocation.source == "agent_profile",
                    RegistryLocation.status == "pending",
                    RegistryLocation.building == "Shadow HQ",
                )
            )
        ).scalars().all()

        with pytest.raises(RegistrationValidationError, match="department_id not found"):
            await service.submit_agent_profile_claim(
                device_id=device_id,
                requester_id="bad-dept@example.test",
                display_name="Bad Department User",
                profile={
                    "full_name": "Bad Department User",
                    "email": "bad-dept@example.test",
                    "department_id": str(uuid.uuid4()),
                    "location_id": location.location_id,
                },
            )

        with pytest.raises(RegistrationValidationError, match="location_id not found"):
            await service.submit_agent_profile_claim(
                device_id=device_id,
                requester_id="bad-location@example.test",
                display_name="Bad Location User",
                profile={
                    "full_name": "Bad Location User",
                    "email": "bad-location@example.test",
                    "department_id": department.department_id,
                    "location_id": str(uuid.uuid4()),
                },
            )

        accepted = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="strict-ok@example.test",
            display_name="Strict OK User",
            profile={
                "full_name": "Strict OK User",
                "email": "strict-ok@example.test",
                "department_id": department.department_id,
                "location_id": location.location_id,
                "user_confirmed": True,
            },
        )
        await session.commit()

    assert pending_departments == []
    assert pending_locations == []
    assert accepted["registration"]["status"] == "approved"
    assert accepted["person"]["department_id"] == department.department_id
    assert accepted["person"]["location_id"] == location.location_id


@pytest.mark.asyncio
async def test_approval_applies_strict_department_location_to_verified_person_and_derived_state(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        department = await service.registry_repo.get_or_create_department(
            name="Approved Department",
            source="manual",
            status="active",
        )
        location = await service.registry_repo.get_or_create_location(
            building="HQ",
            floor="5",
            room="501",
            source="manual",
            status="active",
        )
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Verified Existing User",
                full_name="Verified Existing User",
                email="verified-existing@example.test",
                source="manual",
                status="active",
                profile_key="verified-existing",
                metadata_json={},
            )
        )
        await session.flush()
        await service.repo.create_or_update_person_identity(
            person_id=person_id,
            provider="ui_login",
            identifier="verified-existing@example.test",
            verified=True,
            source="admin_link",
        )
        await RegistryPolicyService(session).update_policies(
            {
                "registration": {
                    "require_admin_confirmation": True,
                    "department_mode": "required_existing",
                    "location_mode": "required_existing",
                }
            },
            actor_id="admin",
        )

        claim_payload = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="verified-existing@example.test",
            display_name="Verified Existing User",
            profile={
                "full_name": "Verified Existing User",
                "email": "verified-existing@example.test",
                "department_id": department.department_id,
                "location_id": location.location_id,
                "user_confirmed": True,
            },
        )
        person_after_submit = await session.get(RegistryPerson, person_id)
        person_department_after_submit = person_after_submit.department_id
        person_location_after_submit = person_after_submit.location_id
        approved = await service.approve_claim(claim_payload["registration"]["claim_id"], reviewed_by="admin")
        await session.commit()

    async with session_maker() as session:
        person = await session.get(RegistryPerson, person_id)
        binding = await session.get(DeviceUserBinding, approved["binding"]["binding_id"])
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()
        inventory = await session.get(DeviceInventoryBinding, device_id)

    assert person_department_after_submit is None
    assert person_location_after_submit is None
    assert approved["person"]["person_id"] == person_id
    assert approved["person"]["department_id"] == department.department_id
    assert approved["person"]["location_id"] == location.location_id
    assert person.department_id == department.department_id
    assert person.location_id == location.location_id
    assert binding.status == "active"
    assert binding.person_id == person_id
    assert asset.assigned_person_id == person_id
    assert asset.department_id == department.department_id
    assert asset.location_id == location.location_id
    assert inventory.person_id == person_id
    assert inventory.source_binding_id == binding.binding_id
    assert inventory.registration_status == "admin_confirmed"
