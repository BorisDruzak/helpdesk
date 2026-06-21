from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceRegistrationEvent,
    DeviceInventoryBinding,
    DeviceUserBinding,
    RegistryAsset,
)
from registry.account_session_service import AccountSessionService
from registry.policy_service import RegistryPolicyService
from registry.registration_service import RegistrationConflictError, RegistrationService


pytestmark = pytest.mark.db_cleanup("registry_access")

def _device(device_id: str, *, hostname: str = "registry-admin") -> Device:
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


async def _person_from_claim(
    service: RegistrationService,
    *,
    device_id: str,
    requester_id: str,
    display_name: str,
) -> str:
    await RegistryPolicyService(service.session).update_policies(
        {"registration": {"require_admin_confirmation": True}},
        actor_id="admin-test",
    )
    result = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=requester_id,
        display_name=display_name,
        profile={
            "full_name": display_name,
            "email": f"{requester_id}@example.test",
            "login": requester_id,
            "department": "IT",
            "building": "HQ",
            "room": "401",
            "user_confirmed": True,
        },
    )
    return result["person"]["person_id"]


@pytest.mark.asyncio
async def test_admin_binds_person_to_unregistered_device_and_syncs_derived_state(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        person_id = await _person_from_claim(
            service,
            device_id=device_id,
            requester_id="manual-owner",
            display_name="Manual Owner",
        )

        result = await service.bind_person_to_device(
            device_id=device_id,
            person_id=person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin",
            reason="verified by phone",
        )
        await session.commit()

    async with session_maker() as session:
        binding = await session.get(DeviceUserBinding, result["binding"]["binding_id"])
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()
        inventory = await session.get(DeviceInventoryBinding, device_id)
        event_types = [
            row.event_type
            for row in (
                await session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.binding_id == binding.binding_id)
                )
            ).scalars()
        ]

    assert binding.status == "active"
    assert binding.relationship_type == "primary_user"
    assert binding.source == "admin_manual"
    assert asset.assigned_person_id == person_id
    assert inventory.person_id == person_id
    assert inventory.source_binding_id == binding.binding_id
    assert inventory.registration_status == "admin_confirmed"
    assert "admin_binding_created" in event_types
    assert "binding_activated" in event_types


@pytest.mark.asyncio
async def test_admin_bind_primary_conflict_requires_replace_existing(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        first_person_id = await _person_from_claim(
            service,
            device_id=device_id,
            requester_id="first-owner",
            display_name="First Owner",
        )
        second_person_id = await _person_from_claim(
            service,
            device_id=device_id,
            requester_id="second-owner",
            display_name="Second Owner",
        )
        first = await service.bind_person_to_device(
            device_id=device_id,
            person_id=first_person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin",
            reason="initial owner",
        )

        with pytest.raises(RegistrationConflictError):
            await service.bind_person_to_device(
                device_id=device_id,
                person_id=second_person_id,
                relationship_type="primary_user",
                replace_existing=False,
                reviewed_by="admin",
                reason="conflicting owner",
            )

        replaced = await service.bind_person_to_device(
            device_id=device_id,
            person_id=second_person_id,
            relationship_type="primary_user",
            replace_existing=True,
            reviewed_by="admin",
            reason="ownership transfer",
        )
        await session.commit()

    async with session_maker() as session:
        old_binding = await session.get(DeviceUserBinding, first["binding"]["binding_id"])
        new_binding = await session.get(DeviceUserBinding, replaced["binding"]["binding_id"])

    assert old_binding.status == "transferred"
    assert new_binding.status == "active"
    assert new_binding.person_id == second_person_id


@pytest.mark.asyncio
async def test_admin_transfer_owner_revokes_dependent_account_sessions(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        registration = RegistrationService(session)
        first_person_id = await _person_from_claim(
            registration,
            device_id=device_id,
            requester_id="transfer-old",
            display_name="Transfer Old",
        )
        second_person_id = await _person_from_claim(
            registration,
            device_id=device_id,
            requester_id="transfer-new",
            display_name="Transfer New",
        )
        first = await registration.bind_person_to_device(
            device_id=device_id,
            person_id=first_person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin",
            reason="initial owner",
        )
        account = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=first["binding"]["binding_id"],
        )

        transferred = await registration.transfer_owner(
            device_id=device_id,
            new_person_id=second_person_id,
            old_binding_action="transferred",
            reviewed_by="admin",
            reason="device handed over",
        )
        await session.commit()

    async with session_maker() as session:
        old_binding = await session.get(DeviceUserBinding, first["binding"]["binding_id"])
        new_binding = await session.get(DeviceUserBinding, transferred["binding"]["binding_id"])
        account_session = await session.get(DeviceAccountSession, account["session"]["session_id"])
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()

    assert old_binding.status == "transferred"
    assert new_binding.status == "active"
    assert new_binding.person_id == second_person_id
    assert account_session.verification_status == "revoked"
    assert account_session.revoked_by == "admin"
    assert asset.assigned_person_id == second_person_id


@pytest.mark.asyncio
async def test_admin_shared_and_responsible_bindings_follow_policy(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        shared_one = await _person_from_claim(service, device_id=device_id, requester_id="shared-one", display_name="Shared One")
        shared_two = await _person_from_claim(service, device_id=device_id, requester_id="shared-two", display_name="Shared Two")
        responsible_one = await _person_from_claim(service, device_id=device_id, requester_id="resp-one", display_name="Responsible One")
        responsible_two = await _person_from_claim(service, device_id=device_id, requester_id="resp-two", display_name="Responsible Two")

        first_shared = await service.add_shared_user(
            device_id=device_id,
            person_id=shared_one,
            reviewed_by="admin",
            reason="shared workplace",
        )
        second_shared = await service.add_shared_user(
            device_id=device_id,
            person_id=shared_two,
            reviewed_by="admin",
            reason="shared workplace",
        )
        first_responsible = await service.assign_responsible(
            device_id=device_id,
            person_id=responsible_one,
            replace_existing=True,
            reviewed_by="admin",
            reason="responsible person",
        )
        second_responsible = await service.assign_responsible(
            device_id=device_id,
            person_id=responsible_two,
            replace_existing=True,
            reviewed_by="admin",
            reason="responsible replacement",
        )
        await session.commit()

    async with session_maker() as session:
        rows = (
            await session.execute(select(DeviceUserBinding).where(DeviceUserBinding.device_id == device_id))
        ).scalars().all()
        active_shared = [row for row in rows if row.status == "active" and row.relationship_type == "shared_user"]
        active_responsible = [row for row in rows if row.status == "active" and row.relationship_type == "responsible"]
        old_responsible = await session.get(DeviceUserBinding, first_responsible["binding"]["binding_id"])

    assert {row.binding_id for row in active_shared} == {
        first_shared["binding"]["binding_id"],
        second_shared["binding"]["binding_id"],
    }
    assert len(active_responsible) == 1
    assert active_responsible[0].binding_id == second_responsible["binding"]["binding_id"]
    assert old_responsible.status == "transferred"
