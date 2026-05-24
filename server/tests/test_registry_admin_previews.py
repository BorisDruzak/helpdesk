from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceInventoryBinding,
    DeviceRegistrationClaim,
    DeviceUserBinding,
    RegistryAsset,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
)
from registry.account_session_service import AccountSessionService
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.registration_service import RegistrationService


def _device(device_id: str, *, hostname: str = "preview-pc") -> Device:
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
async def test_transfer_owner_preview_lists_effects_without_mutation(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        registration = RegistrationService(session)
        old_person_id = await _person_from_claim(
            registration,
            device_id=device_id,
            requester_id="preview-old",
            display_name="Preview Old",
        )
        new_person_id = await _person_from_claim(
            registration,
            device_id=device_id,
            requester_id="preview-new",
            display_name="Preview New",
        )
        first = await registration.bind_person_to_device(
            device_id=device_id,
            person_id=old_person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin",
            reason="initial owner",
        )
        account = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=first["binding"]["binding_id"],
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=device_id,
            title="Historical request",
            description="ticket",
            status="new",
            requester_id="preview-old",
            requester_person_id=old_person_id,
            requester_binding_id=first["binding"]["binding_id"],
            requester_account_session_id=account["session"]["session_id"],
        )
        session.add(ticket)
        await session.flush()

        preview = await registration.preview_transfer_owner(
            device_id=device_id,
            new_person_id=new_person_id,
            old_binding_action="transferred",
        )
        await session.commit()

    async with session_maker() as session:
        old_binding = await session.get(DeviceUserBinding, first["binding"]["binding_id"])
        account_row = await session.get(DeviceAccountSession, account["session"]["session_id"])
        inventory = await session.get(DeviceInventoryBinding, device_id)
        asset = await session.get(RegistryAsset, first["asset"]["asset_id"])

    assert preview["operation"] == "transfer_owner"
    assert preview["dry_run"] is True
    assert preview["counts"]["sessions_to_revoke"] == 1
    assert preview["counts"]["tickets_preserved"] == 1
    assert any(change["kind"] == "binding" and change["action"] == "update" for change in preview["changes"])
    assert any(change["kind"] == "account_session" and change["action"] == "revoke" for change in preview["changes"])
    assert old_binding.status == "active"
    assert old_binding.person_id == old_person_id
    assert account_row.verification_status == "verified"
    assert asset.assigned_person_id == old_person_id
    assert inventory.person_id == old_person_id


@pytest.mark.asyncio
async def test_people_merge_preview_counts_related_records_without_mutation(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        master = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Master User", source="manual", status="active")
        duplicate = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Duplicate User", phone="+70000000000", source="manual", status="active")
        session.add_all([master, duplicate])
        await session.flush()

        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="preview-pc",
            hostname="preview-pc",
            device_id=device_id,
            assigned_person_id=duplicate.person_id,
            source="manual",
            status="active",
            discovery_payload={},
        )
        identity = RegistryPersonIdentity(
            identity_id=str(uuid.uuid4()),
            person_id=duplicate.person_id,
            provider="email",
            identifier="dup@example.test",
            normalized_identifier="dup@example.test",
            verified=True,
            source="manual",
            metadata_json={},
        )
        binding = DeviceUserBinding(
            binding_id=str(uuid.uuid4()),
            device_id=device_id,
            asset_id=asset.asset_id,
            person_id=duplicate.person_id,
            relationship_type="primary_user",
            status="active",
            source="admin_manual",
            valid_from=datetime.now(timezone.utc),
        )
        account_session = DeviceAccountSession(
            session_id=str(uuid.uuid4()),
            device_id=device_id,
            account_mode="confirmed_binding",
            verification_status="verified",
            person_id=duplicate.person_id,
            binding_id=binding.binding_id,
            declared_account={},
            metadata_json={},
        )
        inventory_binding = DeviceInventoryBinding(
            device_id=device_id,
            person_id=duplicate.person_id,
            asset_id=asset.asset_id,
            source_binding_id=binding.binding_id,
            registration_status="admin_confirmed",
        )
        claim = DeviceRegistrationClaim(
            claim_id=str(uuid.uuid4()),
            device_id=device_id,
            asset_id=asset.asset_id,
            person_id=duplicate.person_id,
            claim_type="admin_created",
            status="approved",
            relationship_type="primary_user",
            profile_snapshot={},
            device_snapshot={},
            source="admin_manual",
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=device_id,
            title="Merge preview requester",
            description="ticket",
            status="new",
            requester_id="duplicate-user",
            requester_person_id=duplicate.person_id,
        )
        session.add_all([asset, identity, binding, account_session, inventory_binding, claim, ticket])
        await session.flush()

        preview = await RegistryAdminOperationsService(session).preview_merge_people(
            {
                "master_person_id": master.person_id,
                "duplicate_person_id": duplicate.person_id,
                "field_strategy": {"phone": "duplicate"},
            },
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        duplicate_row = await session.get(RegistryPerson, duplicate.person_id)
        identity_row = await session.get(RegistryPersonIdentity, identity.identity_id)
        binding_row = await session.get(DeviceUserBinding, binding.binding_id)
        session_row = await session.get(DeviceAccountSession, account_session.session_id)

    assert preview["operation"] == "people_merge"
    assert preview["dry_run"] is True
    assert preview["counts"] == {
        "identities_to_move": 1,
        "identity_conflicts": 0,
        "bindings_to_move": 1,
        "sessions_to_move": 1,
        "claims_to_move": 1,
        "tickets_to_move": 1,
        "assets_to_move": 1,
        "inventory_bindings_to_move": 1,
    }
    assert any(change["kind"] == "person" and change["action"] == "mark_merged" for change in preview["changes"])
    assert duplicate_row.status == "active"
    assert identity_row.person_id == duplicate.person_id
    assert binding_row.person_id == duplicate.person_id
    assert session_row.person_id == duplicate.person_id


@pytest.mark.asyncio
async def test_location_department_and_bulk_previews_are_read_only(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        master_location = (await service.create_location({"building": "HQ", "room": "500", "reason": "master"}, actor_id="admin"))["location"]
        duplicate_location = (await service.create_location({"building": "HQ", "room": "501", "reason": "duplicate"}, actor_id="admin"))["location"]
        master_department = (await service.create_department({"code": "OPS", "name": "Operations", "reason": "master"}, actor_id="admin"))["department"]
        duplicate_department = (await service.create_department({"code": "OLDOPS", "name": "Operations Old", "reason": "duplicate"}, actor_id="admin"))["department"]
        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="bulk-preview-pc",
            hostname="bulk-preview-pc",
            device_id=device_id,
            location_id=duplicate_location["location_id"],
            department_id=duplicate_department["department_id"],
            source="manual",
            status="active",
            discovery_payload={},
        )
        inventory = DeviceInventoryBinding(device_id=device_id, building="HQ", room="501", department="Operations Old")
        session.add_all([asset, inventory])
        await session.flush()

        location_preview = await service.preview_merge_locations(
            {
                "master_location_id": master_location["location_id"],
                "duplicate_location_id": duplicate_location["location_id"],
            },
            actor_id="admin",
        )
        department_preview = await service.preview_merge_departments(
            {
                "master_department_id": master_department["department_id"],
                "duplicate_department_id": duplicate_department["department_id"],
            },
            actor_id="admin",
        )
        bulk_preview = await service.preview_bulk(
            {
                "operation": "devices.assign_location",
                "ids": [device_id, str(uuid.uuid4())],
                "payload": {"location_id": master_location["location_id"]},
            },
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        asset_row = await session.get(RegistryAsset, asset.asset_id)
        inventory_row = await session.get(DeviceInventoryBinding, device_id)

    assert location_preview["counts"] == {"people_to_move": 0, "assets_to_move": 1, "inventory_bindings_to_update": 1}
    assert department_preview["counts"] == {"people_to_move": 0, "assets_to_move": 1, "inventory_bindings_to_update": 1}
    assert bulk_preview["operation"] == "devices.assign_location"
    assert bulk_preview["results"][0]["success"] is True
    assert bulk_preview["results"][1]["success"] is False
    assert asset_row.location_id == duplicate_location["location_id"]
    assert asset_row.department_id == duplicate_department["department_id"]
    assert inventory_row.room == "501"
    assert inventory_row.department == "Operations Old"
