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
    DeviceInventoryBindingHistory,
    RegistryPersonIdentity,
    DeviceUserBinding,
    RegistryAsset,
)
from registry.registration_service import RegistrationConflictError, RegistrationService
from registry.policy_service import RegistryPolicyService
from registry.service import RegistryIngestionService

pytestmark = pytest.mark.db_cleanup("agent_runtime")


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
        await RegistryPolicyService(session).update_policies(
            {"registration": {"require_admin_confirmation": True}},
            actor_id="admin",
        )
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


@pytest.mark.asyncio
async def test_approve_unconfirmed_claim_requires_explicit_admin_override(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="unconfirmed",
            display_name="Unconfirmed User",
            profile={"full_name": "Unconfirmed User", "email": "unconfirmed@example.test"},
        )
        with pytest.raises(RegistrationConflictError):
            await service.approve_claim(result["registration"]["claim_id"], reviewed_by="admin")
        approved = await service.approve_claim(
            result["registration"]["claim_id"],
            reviewed_by="admin",
            admin_override_user_confirmation=True,
            override_reason="verified by phone",
        )
        await session.commit()

    async with session_maker() as session:
        binding = await session.get(DeviceUserBinding, approved["binding"]["binding_id"])
        event = (
            await session.execute(
                select(DeviceRegistrationEvent).where(
                    DeviceRegistrationEvent.claim_id == result["registration"]["claim_id"],
                    DeviceRegistrationEvent.event_type == "admin_approved",
                )
            )
        ).scalar_one()

    assert binding.status == "active"
    assert event.payload["admin_override_user_confirmation"] is True
    assert event.payload["override_reason"] == "verified by phone"


@pytest.mark.asyncio
async def test_approving_second_claim_same_person_device_reuses_active_binding(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="same-user",
            display_name="Same User",
            profile={"full_name": "Same User", "email": "same@example.test", "user_confirmed": True},
        )
        first_approved = await service.approve_claim(first["registration"]["claim_id"], reviewed_by="admin")
        second = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="same-user",
            display_name="Same User",
            profile={"full_name": "Same User", "email": "same@example.test", "user_confirmed": True},
        )
        second_approved = await service.approve_claim(second["registration"]["claim_id"], reviewed_by="admin")
        await session.commit()

    async with session_maker() as session:
        bindings = (
            await session.execute(
                select(DeviceUserBinding).where(
                    DeviceUserBinding.device_id == device_id,
                    DeviceUserBinding.status == "active",
                    DeviceUserBinding.relationship_type == "primary_user",
                )
            )
        ).scalars().all()
        claim = await session.get(DeviceRegistrationClaim, second["registration"]["claim_id"])

    assert second_approved["binding"]["binding_id"] == first_approved["binding"]["binding_id"]
    assert len(bindings) == 1
    assert claim.status in {"approved", "superseded"}


@pytest.mark.asyncio
async def test_resubmitting_open_agent_claim_for_device_reuses_existing_claim(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending-a",
            display_name="Pending A",
            profile={"full_name": "Pending A", "email": "pending-a@example.test"},
        )
        second = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending-b",
            display_name="Pending B",
            profile={"full_name": "Pending B", "email": "pending-b@example.test"},
        )
        await session.commit()

    async with session_maker() as session:
        open_claims = (
            await session.execute(
                select(DeviceRegistrationClaim).where(
                    DeviceRegistrationClaim.device_id == device_id,
                    DeviceRegistrationClaim.source == "agent_profile",
                    DeviceRegistrationClaim.status.in_(
                        [
                            "self_reported",
                            "pending_user_confirmation",
                            "user_confirmed",
                            "pending_admin_review",
                            "conflict",
                        ]
                    ),
                )
            )
        ).scalars().all()
        claim = await session.get(DeviceRegistrationClaim, first["registration"]["claim_id"])

    assert second["registration"]["claim_id"] == first["registration"]["claim_id"]
    assert len(open_claims) == 1
    assert claim.person_id == second["person"]["person_id"]
    assert claim.profile_snapshot["email"] == "pending-b@example.test"


@pytest.mark.asyncio
async def test_admin_bind_satisfies_matching_pending_agent_claim(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        submitted = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="manual-match",
            display_name="Manual Match",
            profile={"full_name": "Manual Match", "email": "manual-match@example.test"},
        )
        bound = await service.bind_person_to_device(
            device_id=device_id,
            person_id=submitted["person"]["person_id"],
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="admin verified pending registration",
        )
        await session.commit()

    async with session_maker() as session:
        claim = await session.get(DeviceRegistrationClaim, submitted["registration"]["claim_id"])
        binding = await session.get(DeviceUserBinding, bound["binding"]["binding_id"])
        open_claims = (
            await session.execute(
                select(DeviceRegistrationClaim).where(
                    DeviceRegistrationClaim.device_id == device_id,
                    DeviceRegistrationClaim.status.in_(
                        [
                            "self_reported",
                            "pending_user_confirmation",
                            "user_confirmed",
                            "pending_admin_review",
                            "conflict",
                        ]
                    ),
                )
            )
        ).scalars().all()

    assert claim.status == "approved"
    assert binding.source_claim_id == claim.claim_id
    assert open_claims == []


@pytest.mark.asyncio
async def test_revoke_active_primary_clears_asset_and_inventory_registration(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="revoke-user",
            display_name="Revoke User",
            profile={"full_name": "Revoke User", "email": "revoke@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(result["registration"]["claim_id"], reviewed_by="admin")
        await service.revoke_binding(approved["binding"]["binding_id"], revoked_by="admin", reason="test revoke")
        await session.commit()

    async with session_maker() as session:
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()
        inventory = await session.get(DeviceInventoryBinding, device_id)
        history = (
            await session.execute(
                select(DeviceInventoryBindingHistory).where(DeviceInventoryBindingHistory.device_id == device_id)
            )
        ).scalars().all()

    assert asset.assigned_person_id is None
    assert inventory.person_id is None
    assert inventory.source_binding_id is None
    assert inventory.registration_status == "revoked"
    assert any(row.reason == "registration_revoked" for row in history)


@pytest.mark.asyncio
async def test_verified_identity_collision_reuses_existing_person_without_stealing_identity(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    first_device_id = str(uuid.uuid4())
    second_device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add_all([_device(first_device_id), _device(second_device_id)])
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=first_device_id,
            requester_id="identity-a",
            display_name="Identity A",
            profile={"full_name": "Identity A", "email": "collision@example.test"},
        )
        identity = (
            await session.execute(
                select(RegistryPersonIdentity).where(
                    RegistryPersonIdentity.provider == "email",
                    RegistryPersonIdentity.normalized_identifier == "collision@example.test",
                )
            )
        ).scalar_one()
        identity.verified = True
        second = await service.submit_agent_profile_claim(
            device_id=second_device_id,
            requester_id="identity-b",
            display_name="Identity B",
            profile={"full_name": "Identity B", "email": "collision@example.test"},
        )
        await session.commit()

    assert second["person"]["person_id"] == first["person"]["person_id"]


@pytest.mark.asyncio
async def test_verified_identity_keeps_existing_person_fields_on_conflicting_self_report(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    first_device_id = str(uuid.uuid4())
    second_device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add_all([_device(first_device_id), _device(second_device_id)])
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=first_device_id,
            requester_id="verified-owner",
            display_name="Verified Owner",
            profile={
                "full_name": "Verified Owner",
                "email": "verified@example.test",
                "phone": "100",
                "department": "Original Department",
            },
        )
        identity = (
            await session.execute(
                select(RegistryPersonIdentity).where(
                    RegistryPersonIdentity.provider == "email",
                    RegistryPersonIdentity.normalized_identifier == "verified@example.test",
                )
            )
        ).scalar_one()
        identity.verified = True
        await service.submit_agent_profile_claim(
            device_id=second_device_id,
            requester_id="verified-conflict",
            display_name="Conflicting Self Report",
            profile={
                "full_name": "Conflicting Self Report",
                "email": "verified@example.test",
                "phone": "999",
                "department": "Wrong Department",
            },
        )
        await session.commit()

    async with session_maker() as session:
        person = await session.get(RegistryPersonIdentity, identity.identity_id)
        owner = await RegistrationService(session).registry_repo.get_person(first["person"]["person_id"])

    assert person.person_id == first["person"]["person_id"]
    assert owner.display_name == "Verified Owner"
    assert owner.full_name == "Verified Owner"
    assert owner.phone == "100"


@pytest.mark.asyncio
async def test_unverified_identity_can_refresh_self_reported_person_fields(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    first_device_id = str(uuid.uuid4())
    second_device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add_all([_device(first_device_id), _device(second_device_id)])
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=first_device_id,
            requester_id="unverified-owner",
            display_name="Old Self Report",
            profile={"full_name": "Old Self Report", "email": "unverified@example.test", "phone": "100"},
        )
        await service.submit_agent_profile_claim(
            device_id=second_device_id,
            requester_id="unverified-owner",
            display_name="Updated Self Report",
            profile={"full_name": "Updated Self Report", "email": "unverified@example.test", "phone": "200"},
        )
        await session.commit()

    async with session_maker() as session:
        owner = await RegistrationService(session).registry_repo.get_person(first["person"]["person_id"])

    assert owner.display_name == "Updated Self Report"
    assert owner.full_name == "Updated Self Report"
    assert owner.phone == "200"


@pytest.mark.asyncio
async def test_registration_service_rejects_invalid_or_missing_device_id_before_fk_error(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        service = RegistrationService(session)
        with pytest.raises(ValueError, match="valid UUID"):
            await service.submit_agent_profile_claim(
                device_id="not-a-device",
                requester_id="bad",
                display_name="Bad",
                profile={"full_name": "Bad"},
            )
        with pytest.raises(ValueError, match="device not found"):
            await service.submit_agent_profile_claim(
                device_id=str(uuid.uuid4()),
                requester_id="missing",
                display_name="Missing",
                profile={"full_name": "Missing"},
            )
