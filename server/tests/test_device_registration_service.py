from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceRegistrationClaim,
    DeviceRegistrationEvent,
    DeviceInventoryBinding,
    DeviceUserBinding,
    RegistryAsset,
)
from registry.registration_service import RegistrationConflictError, RegistrationService
from registry.service import RegistryIngestionService


def _device(device_id: str, *, hostname: str = "reg-pc") -> Device:
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
async def test_submit_profile_creates_claim_not_active_binding(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        await session.commit()

    async with session_maker() as session:
        result = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="DOMAIN\\Ivanov",
            display_name="Ivan Ivanov",
            profile={
                "full_name": "Ivan Ivanov",
                "email": " Ivanov@Example.COM ",
                "department": "Accounting",
                "building": "HQ",
                "room": "214",
            },
        )
        await session.commit()

    async with session_maker() as session:
        claim = await session.get(DeviceRegistrationClaim, result["registration"]["claim_id"])
        bindings = (await session.execute(select(DeviceUserBinding))).scalars().all()
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()

    assert claim is not None
    assert claim.status == "pending_user_confirmation"
    assert claim.claim_type == "self_reported"
    assert claim.person_id == result["person"]["person_id"]
    assert bindings == []
    assert asset.assigned_person_id is None


@pytest.mark.asyncio
async def test_confirm_claim_moves_to_pending_admin_review(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="petrova",
            display_name="Anna Petrova",
            profile={"full_name": "Anna Petrova", "email": "petrova@example.test"},
        )
        confirmed = await service.confirm_claim_by_user(result["registration"]["claim_id"], actor_id="petrova")
        await session.commit()

    async with session_maker() as session:
        claim = await session.get(DeviceRegistrationClaim, result["registration"]["claim_id"])
        event_types = [
            row.event_type
            for row in (
                await session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.claim_id == claim.claim_id)
                )
            ).scalars()
        ]

    assert confirmed["registration"]["status"] == "pending_admin_review"
    assert claim.status == "pending_admin_review"
    assert "user_confirmed" in event_types


@pytest.mark.asyncio
async def test_admin_approve_claim_creates_active_binding_and_updates_asset_inventory(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="sidorov",
            display_name="Sergey Sidorov",
            profile={
                "full_name": "Sergey Sidorov",
                "login": "sidorov",
                "department": "IT",
                "building": "HQ",
                "floor": "2",
                "room": "201",
            },
        )
        await service.confirm_claim_by_user(result["registration"]["claim_id"], actor_id="sidorov")
        approved = await service.approve_claim(result["registration"]["claim_id"], reviewed_by="admin")
        await session.commit()

    async with session_maker() as session:
        binding = await session.get(DeviceUserBinding, approved["binding"]["binding_id"])
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
    assert asset.assigned_person_id == binding.person_id
    assert inventory.person_id == binding.person_id
    assert inventory.asset_id == asset.asset_id
    assert inventory.source_binding_id == binding.binding_id
    assert inventory.registration_status == "admin_confirmed"
    assert "admin_approved" in event_types
    assert "binding_activated" in event_types


@pytest.mark.asyncio
async def test_reject_claim_does_not_update_asset(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="reject-user",
            display_name="Reject User",
            profile={"full_name": "Reject User"},
        )
        rejected = await service.reject_claim(
            result["registration"]["claim_id"],
            reviewed_by="admin",
            reason="wrong user",
        )
        await session.commit()

    async with session_maker() as session:
        claim = await session.get(DeviceRegistrationClaim, result["registration"]["claim_id"])
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()
        bindings = (await session.execute(select(DeviceUserBinding))).scalars().all()

    assert rejected["registration"]["status"] == "rejected"
    assert claim.rejection_reason == "wrong user"
    assert asset.assigned_person_id is None
    assert bindings == []


@pytest.mark.asyncio
async def test_conflict_existing_primary_binding_requires_replace_existing(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="first",
            display_name="First User",
            profile={"full_name": "First User", "email": "first@example.test"},
        )
        await service.confirm_claim_by_user(first["registration"]["claim_id"], actor_id="first")
        first_approved = await service.approve_claim(first["registration"]["claim_id"], reviewed_by="admin")

        second = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="second",
            display_name="Second User",
            profile={"full_name": "Second User", "email": "second@example.test"},
        )
        await service.confirm_claim_by_user(second["registration"]["claim_id"], actor_id="second")

        with pytest.raises(RegistrationConflictError):
            await service.approve_claim(second["registration"]["claim_id"], reviewed_by="admin")

        second_approved = await service.approve_claim(
            second["registration"]["claim_id"],
            reviewed_by="admin",
            replace_existing=True,
        )
        await session.commit()

    async with session_maker() as session:
        old_binding = await session.get(DeviceUserBinding, first_approved["binding"]["binding_id"])
        new_binding = await session.get(DeviceUserBinding, second_approved["binding"]["binding_id"])
        active_primary = (
            await session.execute(
                select(DeviceUserBinding).where(
                    DeviceUserBinding.device_id == device_id,
                    DeviceUserBinding.status == "active",
                    DeviceUserBinding.relationship_type == "primary_user",
                )
            )
        ).scalars().all()

    assert old_binding.status in {"transferred", "revoked", "stale"}
    assert new_binding.status == "active"
    assert len(active_primary) == 1
    assert active_primary[0].binding_id == new_binding.binding_id


@pytest.mark.asyncio
async def test_registry_ingestion_profile_creates_registration_claim_without_asset_assignment(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistryIngestionService(session)
        result = await service.ingest_requester_profile(
            device_id=device_id,
            requester_id="legacy-profile",
            display_name="Legacy Profile",
            profile={"full_name": "Legacy Profile", "building": "HQ", "room": "1"},
        )
        await session.commit()

    async with session_maker() as session:
        claim = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalar_one()
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()

    assert result.person_id == claim.person_id
    assert result.asset_id == asset.asset_id
    assert result.registration["claim_id"] == claim.claim_id
    assert asset.assigned_person_id is None
