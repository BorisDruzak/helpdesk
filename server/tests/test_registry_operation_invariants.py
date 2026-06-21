from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    Device,
    DeviceAccountLoginRequest,
    DeviceAccountSession,
    DeviceInventoryBinding,
    DeviceRegistrationClaim,
    DeviceUserBinding,
    RegistryAdminEvent,
    RegistryAsset,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
)
from registry.account_session_service import AccountSessionService
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.registration_service import RegistrationService


pytestmark = pytest.mark.db_cleanup("registry_access")

def _new_id() -> str:
    return str(uuid.uuid4())


def _device(device_id: str, *, hostname: str = "registry-invariant") -> Device:
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


def _person(name: str, **extra: object) -> RegistryPerson:
    return RegistryPerson(
        person_id=_new_id(),
        display_name=name,
        full_name=name,
        source="manual",
        status="active",
        **extra,
    )


async def _count(session: AsyncSession, statement) -> int:
    return int((await session.execute(statement)).scalar_one())


async def _active_primary_count(session: AsyncSession, device_id: str) -> int:
    return await _count(
        session,
        select(func.count())
        .select_from(DeviceUserBinding)
        .where(
            DeviceUserBinding.device_id == device_id,
            DeviceUserBinding.status == "active",
            DeviceUserBinding.relationship_type == "primary_user",
        ),
    )


@pytest.mark.asyncio
async def test_bind_primary_leaves_only_one_active_primary(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id))
        first = _person("Primary One")
        second = _person("Primary Two")
        session.add_all([first, second])
        await session.flush()

        service = RegistrationService(session)
        first_binding = await service.bind_person_to_device(
            device_id=device_id,
            person_id=first.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="initial owner",
        )
        second_binding = await service.bind_person_to_device(
            device_id=device_id,
            person_id=second.person_id,
            relationship_type="primary_user",
            replace_existing=True,
            reviewed_by="admin",
            reason="replace owner",
        )
        await session.commit()

    async with session_maker() as session:
        old_row = await session.get(DeviceUserBinding, first_binding["binding"]["binding_id"])
        new_row = await session.get(DeviceUserBinding, second_binding["binding"]["binding_id"])
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()
        inventory = await session.get(DeviceInventoryBinding, device_id)

        assert await _active_primary_count(session, device_id) == 1
        assert old_row.status == "transferred"
        assert new_row.status == "active"
        assert new_row.person_id == second.person_id
        assert asset.assigned_person_id == second.person_id
        assert inventory.person_id == second.person_id
        assert inventory.source_binding_id == new_row.binding_id


@pytest.mark.asyncio
async def test_transfer_owner_leaves_no_duplicate_active_primary(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id))
        old_owner = _person("Transfer Old")
        new_owner = _person("Transfer New")
        session.add_all([old_owner, new_owner])
        await session.flush()

        registration = RegistrationService(session)
        old_binding = await registration.bind_person_to_device(
            device_id=device_id,
            person_id=old_owner.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="initial owner",
        )
        session_payload = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=old_binding["binding"]["binding_id"],
        )
        new_binding = await registration.transfer_owner(
            device_id=device_id,
            new_person_id=new_owner.person_id,
            old_binding_action="transferred",
            reviewed_by="admin",
            reason="handover",
        )
        await session.commit()

    async with session_maker() as session:
        old_row = await session.get(DeviceUserBinding, old_binding["binding"]["binding_id"])
        new_row = await session.get(DeviceUserBinding, new_binding["binding"]["binding_id"])
        account_session = await session.get(DeviceAccountSession, session_payload["session"]["session_id"])

        assert await _active_primary_count(session, device_id) == 1
        assert old_row.status == "transferred"
        assert new_row.status == "active"
        assert new_row.person_id == new_owner.person_id
        assert account_session.verification_status == "revoked"


@pytest.mark.asyncio
async def test_revoke_primary_clears_asset_and_inventory_assignment(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id))
        person = _person("Revoked Owner")
        session.add(person)
        await session.flush()

        registration = RegistrationService(session)
        binding = await registration.bind_person_to_device(
            device_id=device_id,
            person_id=person.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="temporary owner",
        )
        await registration.revoke_binding(
            binding["binding"]["binding_id"],
            revoked_by="admin",
            reason="device returned to pool",
        )
        await session.commit()

    async with session_maker() as session:
        row = await session.get(DeviceUserBinding, binding["binding"]["binding_id"])
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()
        inventory = await session.get(DeviceInventoryBinding, device_id)

        assert row.status == "revoked"
        assert await _active_primary_count(session, device_id) == 0
        assert asset.assigned_person_id is None
        assert inventory.person_id is None
        assert inventory.source_binding_id is None
        assert inventory.registration_status == "revoked"


@pytest.mark.asyncio
async def test_shared_and_responsible_do_not_change_primary_owner(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id))
        primary = _person("Primary Owner")
        shared = _person("Shared User")
        responsible = _person("Responsible User")
        session.add_all([primary, shared, responsible])
        await session.flush()

        service = RegistrationService(session)
        primary_binding = await service.bind_person_to_device(
            device_id=device_id,
            person_id=primary.person_id,
            relationship_type="primary_user",
            reviewed_by="admin",
            reason="confirmed owner",
        )
        await service.add_shared_user(
            device_id=device_id,
            person_id=shared.person_id,
            reviewed_by="admin",
            reason="shared workstation",
        )
        await service.assign_responsible(
            device_id=device_id,
            person_id=responsible.person_id,
            reviewed_by="admin",
            reason="support responsible",
        )
        await session.commit()

    async with session_maker() as session:
        active_primary = (
            await session.execute(
                select(DeviceUserBinding).where(
                    DeviceUserBinding.device_id == device_id,
                    DeviceUserBinding.status == "active",
                    DeviceUserBinding.relationship_type == "primary_user",
                )
            )
        ).scalar_one()
        asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one()
        inventory = await session.get(DeviceInventoryBinding, device_id)

        assert active_primary.binding_id == primary_binding["binding"]["binding_id"]
        assert active_primary.person_id == primary.person_id
        assert asset.assigned_person_id == primary.person_id
        assert inventory.person_id == primary.person_id
        assert inventory.source_binding_id == primary_binding["binding"]["binding_id"]


@pytest.mark.asyncio
async def test_people_merge_leaves_no_live_duplicate_person_references(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        session.add(_device(device_id))
        master = _person("Merge Master")
        duplicate = _person("Merge Duplicate")
        session.add_all([master, duplicate])
        await session.flush()

        asset = RegistryAsset(
            asset_id=_new_id(),
            asset_type="pc",
            name="merge-pc",
            hostname="merge-pc",
            device_id=device_id,
            assigned_person_id=duplicate.person_id,
            source="manual",
            status="active",
            discovery_payload={},
        )
        binding = DeviceUserBinding(
            binding_id=_new_id(),
            device_id=device_id,
            asset_id=asset.asset_id,
            person_id=duplicate.person_id,
            relationship_type="primary_user",
            status="active",
            source="admin_manual",
            valid_from=datetime.now(timezone.utc),
        )
        session.add(asset)
        await session.flush()
        session.add(binding)
        await session.flush()

        session.add_all(
            [
                RegistryPersonIdentity(
                    identity_id=_new_id(),
                    person_id=duplicate.person_id,
                    provider="email",
                    identifier="dup@example.test",
                    normalized_identifier="dup@example.test",
                    verified=True,
                    source="manual",
                    metadata_json={},
                ),
                DeviceAccountSession(
                    session_id=_new_id(),
                    device_id=device_id,
                    account_mode="confirmed_binding",
                    verification_status="verified",
                    person_id=duplicate.person_id,
                    base_person_id=duplicate.person_id,
                    binding_id=binding.binding_id,
                    base_binding_id=binding.binding_id,
                    declared_account={},
                    metadata_json={},
                ),
                DeviceAccountLoginRequest(
                    request_id=_new_id(),
                    device_id=device_id,
                    requested_account={"email": "dup@example.test"},
                    matched_person_id=duplicate.person_id,
                    base_person_id=duplicate.person_id,
                    base_binding_id=binding.binding_id,
                    status="pending_verification",
                    verification_method="admin_approval",
                    metadata_json={},
                ),
                DeviceRegistrationClaim(
                    claim_id=_new_id(),
                    device_id=device_id,
                    asset_id=asset.asset_id,
                    person_id=duplicate.person_id,
                    claim_type="admin_created",
                    status="approved",
                    relationship_type="primary_user",
                    profile_snapshot={},
                    device_snapshot={},
                    source="admin_manual",
                ),
                DeviceInventoryBinding(
                    device_id=device_id,
                    person_id=duplicate.person_id,
                    asset_id=asset.asset_id,
                    source_binding_id=binding.binding_id,
                    registration_status="admin_confirmed",
                ),
                Ticket(
                    ticket_id=_new_id(),
                    device_id=device_id,
                    title="Merge requester",
                    description="ticket",
                    status="new",
                    requester_id="duplicate",
                    requester_person_id=duplicate.person_id,
                ),
            ]
        )
        await session.flush()

        result = await RegistryAdminOperationsService(session).merge_people(
            {
                "master_person_id": master.person_id,
                "duplicate_person_id": duplicate.person_id,
                "reason": "same employee",
            },
            actor_id="admin",
        )
        assert result["moved"]["login_requests"] == 1
        await session.commit()

    async with session_maker() as session:
        duplicate_row = await session.get(RegistryPerson, duplicate.person_id)
        assert duplicate_row.status == "merged"
        assert duplicate_row.metadata_json["merged_into"] == master.person_id
        assert await _count(session, select(func.count()).select_from(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == duplicate.person_id)) == 0
        assert await _count(session, select(func.count()).select_from(DeviceUserBinding).where(DeviceUserBinding.person_id == duplicate.person_id)) == 0
        assert await _count(session, select(func.count()).select_from(DeviceAccountSession).where(or_(DeviceAccountSession.person_id == duplicate.person_id, DeviceAccountSession.base_person_id == duplicate.person_id))) == 0
        assert await _count(session, select(func.count()).select_from(DeviceAccountLoginRequest).where(or_(DeviceAccountLoginRequest.matched_person_id == duplicate.person_id, DeviceAccountLoginRequest.base_person_id == duplicate.person_id))) == 0
        assert await _count(session, select(func.count()).select_from(DeviceRegistrationClaim).where(DeviceRegistrationClaim.person_id == duplicate.person_id)) == 0
        assert await _count(session, select(func.count()).select_from(Ticket).where(Ticket.requester_person_id == duplicate.person_id)) == 0
        assert await _count(session, select(func.count()).select_from(RegistryAsset).where(RegistryAsset.assigned_person_id == duplicate.person_id)) == 0
        assert await _count(session, select(func.count()).select_from(DeviceInventoryBinding).where(DeviceInventoryBinding.person_id == duplicate.person_id)) == 0


@pytest.mark.asyncio
async def test_location_merge_leaves_no_duplicate_location_references(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        master = (await service.create_location({"building": "HQ", "floor": "7", "room": "701", "reason": "master"}, actor_id="admin"))["location"]
        duplicate = (await service.create_location({"building": "HQ", "floor": "7", "room": "701A", "reason": "duplicate"}, actor_id="admin"))["location"]
        person = _person("Location Person", location_id=duplicate["location_id"])
        asset = RegistryAsset(
            asset_id=_new_id(),
            asset_type="pc",
            name="location-pc",
            hostname="location-pc",
            device_id=device_id,
            location_id=duplicate["location_id"],
            source="manual",
            status="active",
            discovery_payload={},
        )
        inventory = DeviceInventoryBinding(device_id=device_id, building="HQ", floor="7", room="701A")
        session.add_all([person, asset, inventory])
        await session.flush()

        await service.merge_locations(
            {
                "master_location_id": master["location_id"],
                "duplicate_location_id": duplicate["location_id"],
                "reason": "same room",
            },
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        assert await _count(session, select(func.count()).select_from(RegistryPerson).where(RegistryPerson.location_id == duplicate["location_id"])) == 0
        assert await _count(session, select(func.count()).select_from(RegistryAsset).where(RegistryAsset.location_id == duplicate["location_id"])) == 0
        assert (await session.get(DeviceInventoryBinding, device_id)).room == "701"


@pytest.mark.asyncio
async def test_department_merge_leaves_no_duplicate_department_references(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()

    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        master = (await service.create_department({"code": "OPS", "name": "Operations", "reason": "master"}, actor_id="admin"))["department"]
        duplicate = (await service.create_department({"code": "OPS-OLD", "name": "Operations Old", "reason": "duplicate"}, actor_id="admin"))["department"]
        person = _person("Department Person", department_id=duplicate["department_id"])
        asset = RegistryAsset(
            asset_id=_new_id(),
            asset_type="pc",
            name="department-pc",
            hostname="department-pc",
            device_id=device_id,
            department_id=duplicate["department_id"],
            source="manual",
            status="active",
            discovery_payload={},
        )
        inventory = DeviceInventoryBinding(device_id=device_id, department="Operations Old")
        session.add_all([person, asset, inventory])
        await session.flush()

        await service.merge_departments(
            {
                "master_department_id": master["department_id"],
                "duplicate_department_id": duplicate["department_id"],
                "reason": "same department",
            },
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        assert await _count(session, select(func.count()).select_from(RegistryPerson).where(RegistryPerson.department_id == duplicate["department_id"])) == 0
        assert await _count(session, select(func.count()).select_from(RegistryAsset).where(RegistryAsset.department_id == duplicate["department_id"])) == 0
        assert (await session.get(DeviceInventoryBinding, device_id)).department == "Operations"


@pytest.mark.asyncio
async def test_policy_change_writes_policy_changed_audit(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        await RegistryAdminOperationsService(session).update_policies(
            {
                "policies": {"registration": {"stale_after_days": 120}},
                "reason": "align stale policy",
            },
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        event = (
            await session.execute(select(RegistryAdminEvent).where(RegistryAdminEvent.event_type == "policy_changed"))
        ).scalar_one()
        assert event.object_type == "policy"
        assert event.object_id == "registry_management"
        assert event.actor_id == "admin"
        assert event.reason == "align stale policy"
        assert event.payload["changed_from_defaults"]["registration.stale_after_days"]["effective"] == 120


@pytest.mark.asyncio
async def test_bulk_partial_failure_keeps_successful_items_and_reports_failures(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = _new_id()
    missing_device_id = _new_id()

    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        location = (await service.create_location({"building": "HQ", "room": "801", "reason": "seed"}, actor_id="admin"))["location"]
        session.add(_device(device_id))
        asset = RegistryAsset(
            asset_id=_new_id(),
            asset_type="pc",
            name="bulk-invariant-pc",
            hostname="bulk-invariant-pc",
            device_id=device_id,
            source="manual",
            status="active",
            discovery_payload={},
        )
        inventory = DeviceInventoryBinding(device_id=device_id)
        session.add_all([asset, inventory])
        await session.flush()

        result = await service.bulk_assign_location(
            {
                "ids": [device_id, missing_device_id],
                "payload": {"location_id": location["location_id"]},
                "reason": "floor move",
            },
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        asset_row = await session.get(RegistryAsset, asset.asset_id)
        inventory_row = await session.get(DeviceInventoryBinding, device_id)
        event_count = await _count(
            session,
            select(func.count())
            .select_from(RegistryAdminEvent)
            .where(
                RegistryAdminEvent.event_type == "bulk_device_location_assigned",
                RegistryAdminEvent.related_device_id == device_id,
            ),
        )

        assert result["summary"] == {"selected": 2, "success": 1, "failed": 1}
        assert result["items"] == [
            {"id": device_id, "status": "success"},
            {"id": missing_device_id, "status": "error", "error_code": "NOT_FOUND"},
        ]
        assert asset_row.location_id == location["location_id"]
        assert inventory_row.room == "801"
        assert event_count == 1
