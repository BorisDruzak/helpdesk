from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DevicePresenceSnapshot,
    DeviceUserBinding,
    RegistryAsset,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    RegistryService as RegistryServiceModel,
)
from registry.registration_service import RegistrationService
from registry.service import RegistrySnapshotService


pytestmark = pytest.mark.db_cleanup("registry_access")

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
async def test_registry_snapshot_excludes_retired_account_session_runtime(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        snapshot = await RegistrySnapshotService(session).build_snapshot()

    assert "account_sessions" not in snapshot
    assert "account_login_requests" not in snapshot
    assert {"sessions_active", "sessions_other_account", "other_account_requests"}.isdisjoint(snapshot["summary"])


@pytest.mark.asyncio
async def test_registry_snapshot_projects_production_context_from_registry_metadata(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    manager_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    service_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        session.add(
            RegistryLocation(
                location_id=location_id,
                building="HQ",
                floor="4",
                room="401",
                display_name="HQ 401",
                source="manual",
                status="active",
            )
        )
        session.add(RegistryPerson(person_id=manager_id, display_name="Manager User", source="manual", status="active"))
        session.add(
            RegistryDepartment(
                department_id=department_id,
                code="ITPROD",
                name="IT Production",
                source="manual",
                status="active",
                metadata_json={"manager_person_id": manager_id, "support_queue": "it-l1"},
            )
        )
        session.add(
            RegistryServiceModel(
                service_id=service_id,
                code=f"svc_{uuid.uuid4().hex[:8]}",
                name="Production ERP",
                source="manual",
                status="active",
                metadata_json={"criticality": "critical", "audience": "office", "owner_person_id": manager_id},
            )
        )
        session.add(
            RegistryPerson(
                person_id=person_id,
                display_name="Production User",
                full_name="Production User",
                phone="+7 343 000-00-00",
                department_id=department_id,
                location_id=location_id,
                source="manual",
                status="active",
                metadata_json={
                    "position": "Engineer",
                    "internal_extension": "1234",
                    "workplace_label": "HQ-401-A",
                    "manager_person_id": manager_id,
                },
            )
        )
        await session.flush()
        session.add(
            RegistryAsset(
                asset_id=asset_id,
                asset_type="pc",
                name="prod-pc",
                hostname="prod-pc",
                device_id=device_id,
                assigned_person_id=person_id,
                department_id=department_id,
                location_id=location_id,
                service_id=service_id,
                source="manual",
                status="active",
                discovery_payload={},
            )
        )
        await session.flush()
        session.add(
            DeviceUserBinding(
                binding_id=str(uuid.uuid4()),
                device_id=device_id,
                asset_id=asset_id,
                person_id=person_id,
                relationship_type="responsible",
                status="active",
                source="manual",
                confidence=1,
            )
        )
        snapshot = await RegistrySnapshotService(session).build_snapshot()
        await session.commit()

    person = next(item for item in snapshot["people"] if item["person_id"] == person_id)
    assert person["position"] == "Engineer"
    assert person["internal_extension"] == "1234"
    assert person["workplace_label"] == "HQ-401-A"
    assert person["manager_person_id"] == manager_id
    assert person["manager_name"] == "Manager User"
    assert person["production_context"]["department_name"] == "IT Production"
    assert person["production_context"]["location_name"] == "HQ 401"
    assert person["production_context"]["manager_name"] == "Manager User"

    department = next(item for item in snapshot["departments"] if item["department_id"] == department_id)
    assert department["manager_name"] == "Manager User"

    asset = next(item for item in snapshot["assets"] if item["asset_id"] == asset_id)
    assert asset["responsible_person_id"] == person_id
    assert asset["responsible_person_name"] == "Production User"

    service = next(item for item in snapshot["services"] if item["service_id"] == service_id)
    assert service["criticality"] == "critical"
    assert service["audience"] == "office"
    assert service["owner_person_id"] == manager_id
    assert service["owner_person_name"] == "Manager User"


@pytest.mark.asyncio
async def test_registry_snapshot_projects_requester_profile_completion_status(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    complete_person_id = str(uuid.uuid4())
    incomplete_person_id = str(uuid.uuid4())
    department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            RegistryDepartment(
                department_id=department_id,
                code="support",
                name="Support",
                source="manual",
                status="active",
            )
        )
        session.add(
            RegistryLocation(
                location_id=location_id,
                building="HQ",
                floor="2",
                room="201",
                display_name="HQ 201",
                source="manual",
                status="active",
            )
        )
        session.add(
            RegistryPerson(
                person_id=complete_person_id,
                display_name="Complete User",
                full_name="Complete User",
                phone="+7 343 000-00-01",
                department_id=department_id,
                location_id=location_id,
                source="manual",
                status="active",
            )
        )
        session.add(
            RegistryPerson(
                person_id=incomplete_person_id,
                display_name="Incomplete User",
                full_name="Incomplete User",
                phone=None,
                department_id=None,
                location_id=location_id,
                source="manual",
                status="active",
            )
        )
        snapshot = await RegistrySnapshotService(session).build_snapshot()
        await session.commit()

    complete = next(item for item in snapshot["people"] if item["person_id"] == complete_person_id)
    incomplete = next(item for item in snapshot["people"] if item["person_id"] == incomplete_person_id)

    assert complete["profile_completion"]["complete"] is True
    assert complete["profile_completion"]["status"] == "complete"
    assert complete["profile_completion"]["missing_fields"] == []

    assert incomplete["profile_completion"]["complete"] is False
    assert incomplete["profile_completion"]["status"] == "required"
    assert {field["key"] for field in incomplete["profile_completion"]["missing_fields"]} == {"department_id", "phone"}


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
