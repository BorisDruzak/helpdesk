from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import DeviceInventoryBinding, RegistryAdminEvent, RegistryAsset, RegistryPerson
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.service import RegistrySnapshotService


pytestmark = pytest.mark.db_cleanup("registry_access")

@pytest.mark.asyncio
async def test_department_create_update_duplicate_and_archive(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        created = await service.create_department(
            {"code": "it", "name": "IT", "support_queue": "L2", "reason": "cmdb seed"},
            actor_id="admin",
        )
        department_id = created["department"]["department_id"]

        with pytest.raises(ValueError):
            await service.create_department({"code": "IT", "name": "IT duplicate", "reason": "duplicate"}, actor_id="admin")

        updated = await service.update_department(
            department_id,
            {"name": "IT Operations", "manager_person_id": "manager-1", "reason": "rename"},
            actor_id="admin",
        )
        archived = await service.archive_department(department_id, {"reason": "empty department"}, actor_id="admin")
        await session.commit()

    assert updated["department"]["name"] == "IT Operations"
    assert updated["department"]["manager_person_id"] == "manager-1"
    assert archived["department"]["status"] == "archived"


@pytest.mark.asyncio
async def test_department_merge_moves_people_assets_inventory_and_counts_in_snapshot(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        master = (await service.create_department({"code": "OPS", "name": "Operations", "reason": "master"}, actor_id="admin"))["department"]
        duplicate = (await service.create_department({"code": "OPS2", "name": "Operations Old", "reason": "duplicate"}, actor_id="admin"))["department"]
        person = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Department User", department_id=duplicate["department_id"], source="manual", status="active")
        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="dept-pc",
            hostname="dept-pc",
            device_id=device_id,
            department_id=duplicate["department_id"],
            source="manual",
            status="active",
            discovery_payload={},
        )
        binding = DeviceInventoryBinding(device_id=device_id, department="Operations Old")
        session.add_all([person, asset, binding])
        await session.flush()

        result = await service.merge_departments(
            {
                "master_department_id": master["department_id"],
                "duplicate_department_id": duplicate["department_id"],
                "reason": "duplicate department",
            },
            actor_id="admin",
        )
        snapshot = await RegistrySnapshotService(session).build_snapshot()
        await session.commit()

    async with session_maker() as session:
        person_row = await session.get(RegistryPerson, person.person_id)
        asset_row = await session.get(RegistryAsset, asset.asset_id)
        inventory = await session.get(DeviceInventoryBinding, device_id)
        event = (
            await session.execute(select(RegistryAdminEvent).where(RegistryAdminEvent.event_type == "department_merged"))
        ).scalar_one()

    master_payload = next(row for row in snapshot["departments"] if row["department_id"] == master["department_id"])
    assert result["moved"] == {"people": 1, "assets": 1}
    assert person_row.department_id == master["department_id"]
    assert asset_row.department_id == master["department_id"]
    assert inventory.department == "Operations"
    assert master_payload["users_count"] == 1
    assert master_payload["devices_count"] == 1
    assert event.reason == "duplicate department"
