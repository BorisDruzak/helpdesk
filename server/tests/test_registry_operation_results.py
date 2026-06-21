from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceInventoryBinding, RegistryAsset, RegistryPerson, RegistryPersonIdentity
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.registration_service import RegistrationService


pytestmark = pytest.mark.db_cleanup("registry_access")

def _device(device_id: str, *, hostname: str = "operation-result-pc") -> Device:
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


def _assert_operation_result(result: dict[str, object], *, operation: str) -> None:
    assert result["operation_id"]
    assert result["operation"] == operation
    assert result["status"] in {"success", "partial_success", "error"}
    assert isinstance(result["summary"], dict)
    assert "success" in result["summary"]
    assert "failed" in result["summary"]
    assert isinstance(result["items"], list)
    assert result["events"]


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
            "department": "Operations",
            "building": "HQ",
            "room": "901",
            "user_confirmed": True,
        },
    )
    return result["person"]["person_id"]


@pytest.mark.asyncio
async def test_transfer_owner_apply_returns_operation_result(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        registration = RegistrationService(session)
        old_person_id = await _person_from_claim(registration, device_id=device_id, requester_id="result-old", display_name="Result Old")
        new_person_id = await _person_from_claim(registration, device_id=device_id, requester_id="result-new", display_name="Result New")
        first = await registration.bind_person_to_device(
            device_id=device_id,
            person_id=old_person_id,
            relationship_type="primary_user",
            replace_existing=False,
            reviewed_by="admin",
            reason="initial owner",
        )

        result = await registration.transfer_owner(
            device_id=device_id,
            new_person_id=new_person_id,
            old_binding_action="transferred",
            reviewed_by="admin",
            reason="operation result transfer",
        )
        await session.commit()

    _assert_operation_result(result, operation="transfer_owner")
    assert {"binding", "registry_asset", "inventory_binding"} <= {item["entity_type"] for item in result["items"]}
    assert any(item["id"] == first["binding"]["binding_id"] for item in result["items"])
    assert result["summary"]["success"] >= 3
    assert result["events"] == ["binding_transferred"]


@pytest.mark.asyncio
async def test_merge_people_apply_returns_operation_result(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        master = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Merge Master", source="manual", status="active")
        duplicate = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Merge Duplicate", phone="+70000009999", source="manual", status="active")
        identity = RegistryPersonIdentity(
            identity_id=str(uuid.uuid4()),
            person_id=duplicate.person_id,
            provider="email",
            identifier="merge-result@example.test",
            normalized_identifier="merge-result@example.test",
            verified=True,
            source="manual",
            metadata_json={},
        )
        session.add_all([master, duplicate, identity])
        await session.flush()

        result = await RegistryAdminOperationsService(session).merge_people(
            {
                "master_person_id": master.person_id,
                "duplicate_person_id": duplicate.person_id,
                "field_strategy": {"phone": "duplicate"},
                "reason": "operation result merge people",
            },
            actor_id="admin",
        )
        await session.commit()

    _assert_operation_result(result, operation="people_merge")
    assert result["summary"]["success"] >= 2
    assert any(item["entity_type"] == "identity" and item["id"] == identity.identity_id for item in result["items"])
    assert any(item["entity_type"] == "person" and item["id"] == duplicate.person_id for item in result["items"])
    assert result["events"] == ["person_merged"]


@pytest.mark.asyncio
async def test_merge_location_department_and_bulk_apply_return_operation_results(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        master_location = (await service.create_location({"building": "HQ", "room": "1001", "reason": "seed"}, actor_id="admin"))["location"]
        duplicate_location = (await service.create_location({"building": "HQ", "room": "1002", "reason": "seed"}, actor_id="admin"))["location"]
        master_department = (await service.create_department({"code": "OPSRESULT", "name": "Ops Result", "reason": "seed"}, actor_id="admin"))["department"]
        duplicate_department = (await service.create_department({"code": "OPSOLDRESULT", "name": "Ops Old Result", "reason": "seed"}, actor_id="admin"))["department"]
        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="operation-result-pc",
            hostname="operation-result-pc",
            device_id=device_id,
            location_id=duplicate_location["location_id"],
            department_id=duplicate_department["department_id"],
            source="manual",
            status="active",
            discovery_payload={},
        )
        inventory = DeviceInventoryBinding(device_id=device_id, building="HQ", room="1002", department="Ops Old Result")
        session.add_all([_device(device_id), asset, inventory])
        await session.flush()

        location_result = await service.merge_locations(
            {
                "master_location_id": master_location["location_id"],
                "duplicate_location_id": duplicate_location["location_id"],
                "reason": "operation result merge location",
            },
            actor_id="admin",
        )
        department_result = await service.merge_departments(
            {
                "master_department_id": master_department["department_id"],
                "duplicate_department_id": duplicate_department["department_id"],
                "reason": "operation result merge department",
            },
            actor_id="admin",
        )
        bulk_result = await service.bulk_assign_location(
            {
                "ids": [device_id, str(uuid.uuid4())],
                "payload": {"location_id": master_location["location_id"]},
                "reason": "operation result bulk",
            },
            actor_id="admin",
        )
        await session.commit()

    _assert_operation_result(location_result, operation="location_merge")
    _assert_operation_result(department_result, operation="department_merge")
    _assert_operation_result(bulk_result, operation="devices.assign_location")
    assert location_result["events"] == ["location_merged"]
    assert department_result["events"] == ["department_merged"]
    assert bulk_result["status"] == "partial_success"
    assert bulk_result["summary"]["success"] == 1
    assert bulk_result["summary"]["failed"] == 1
