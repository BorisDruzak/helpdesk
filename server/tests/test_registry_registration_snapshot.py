from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DevicePresenceSnapshot, DeviceUserBinding, RegistryPersonIdentity
from registry.registration_service import RegistrationService
from registry.service import RegistrySnapshotService


def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="snapshot-reg",
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


@pytest.mark.asyncio
async def test_registry_snapshot_counts_stale_bindings_and_uses_badge_severity_vocabulary(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    stale_device_id = str(uuid.uuid4())
    conflict_device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add_all([_device(stale_device_id), _device(conflict_device_id)])
        service = RegistrationService(session)
        stale_claim = await service.submit_agent_profile_claim(
            device_id=stale_device_id,
            requester_id="stale-user",
            display_name="Stale User",
            profile={"full_name": "Stale User", "email": "stale@example.test", "user_confirmed": True},
        )
        stale_approved = await service.approve_claim(stale_claim["registration"]["claim_id"], reviewed_by="admin")
        stale_binding = await session.get(DeviceUserBinding, stale_approved["binding"]["binding_id"])
        stale_binding.status = "stale"

        first = await service.submit_agent_profile_claim(
            device_id=conflict_device_id,
            requester_id="conflict-a",
            display_name="Conflict A",
            profile={"full_name": "Conflict A", "email": "conflict-a@example.test", "user_confirmed": True},
        )
        await service.approve_claim(first["registration"]["claim_id"], reviewed_by="admin")
        await service.submit_agent_profile_claim(
            device_id=conflict_device_id,
            requester_id="conflict-b",
            display_name="Conflict B",
            profile={"full_name": "Conflict B", "email": "conflict-b@example.test", "user_confirmed": True},
        )
        snapshot = await RegistrySnapshotService(session).build_snapshot()
        await session.commit()

    assert snapshot["summary"]["stale_bindings"] == 1
    assert any(issue["kind"] == "binding_stale" for issue in snapshot["data_quality"])
    conflict_issues = [issue for issue in snapshot["data_quality"] if issue["kind"] == "registration_conflict"]
    assert conflict_issues
    assert {issue["severity"] for issue in conflict_issues} == {"danger"}


@pytest.mark.asyncio
async def test_registry_snapshot_uses_shared_device_status_for_shared_only_binding(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        claim = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="shared-user",
            display_name="Shared User",
            profile={"full_name": "Shared User", "email": "shared@example.test", "is_shared_device": True, "user_confirmed": True},
        )
        await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        snapshot = await RegistrySnapshotService(session).build_snapshot()
        await session.commit()

    asset = next(item for item in snapshot["assets"] if item["device_id"] == device_id)
    assert asset["registration_status"] == "shared_device"


@pytest.mark.asyncio
async def test_registry_snapshot_presence_mismatch_uses_identities_not_display_name(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    matched_device_id = str(uuid.uuid4())
    mismatched_device_id = str(uuid.uuid4())
    no_identity_device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add_all([_device(matched_device_id), _device(mismatched_device_id), _device(no_identity_device_id)])
        service = RegistrationService(session)
        matched = await service.submit_agent_profile_claim(
            device_id=matched_device_id,
            requester_id="matched",
            display_name="Not Login Display",
            profile={"full_name": "Not Login Display", "login": "DOMAIN\\Matched", "user_confirmed": True},
        )
        mismatched = await service.submit_agent_profile_claim(
            device_id=mismatched_device_id,
            requester_id="mismatch",
            display_name="Mismatch Display",
            profile={"full_name": "Mismatch Display", "login": "DOMAIN\\Expected", "user_confirmed": True},
        )
        no_identity = await service.submit_agent_profile_claim(
            device_id=no_identity_device_id,
            requester_id="no-identity",
            display_name="No Identity Display",
            profile={"full_name": "No Identity Display", "user_confirmed": True},
        )
        await service.approve_claim(matched["registration"]["claim_id"], reviewed_by="admin")
        await service.approve_claim(mismatched["registration"]["claim_id"], reviewed_by="admin")
        await service.approve_claim(no_identity["registration"]["claim_id"], reviewed_by="admin")
        no_identity_person_id = no_identity["person"]["person_id"]
        identities = (
            await session.execute(
                select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == no_identity_person_id)
            )
        ).scalars().all()
        for identity in identities:
            await session.delete(identity)
        now = datetime.now(timezone.utc)
        session.add_all(
            [
                DevicePresenceSnapshot(device_id=matched_device_id, snapshot={}, collected_at=now, current_user="domain\\matched"),
                DevicePresenceSnapshot(device_id=mismatched_device_id, snapshot={}, collected_at=now, current_user="domain\\other"),
                DevicePresenceSnapshot(device_id=no_identity_device_id, snapshot={}, collected_at=now, current_user="domain\\someone"),
            ]
        )
        await session.flush()
        snapshot = await RegistrySnapshotService(session).build_snapshot()
        await session.commit()

    mismatches = [issue for issue in snapshot["data_quality"] if issue["kind"] == "presence_user_mismatch"]
    assert [issue["object_id"] for issue in mismatches] == [
        next(asset["asset_id"] for asset in snapshot["assets"] if asset["device_id"] == mismatched_device_id)
    ]
