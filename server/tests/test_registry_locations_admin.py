from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import DeviceInventoryBinding, RegistryAdminEvent, RegistryAsset, RegistryPerson
from registry.admin_operations_service import RegistryAdminOperationsService


@pytest.mark.asyncio
async def test_location_create_update_duplicate_and_archive(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        created = await service.create_location(
            {"building": "HQ", "floor": "4", "room": "401", "reason": "cmdb seed"},
            actor_id="admin",
        )
        location_id = created["location"]["location_id"]

        with pytest.raises(ValueError):
            await service.create_location(
                {"building": "HQ", "floor": "4", "room": "401", "reason": "duplicate"},
                actor_id="admin",
            )

        updated = await service.update_location(
            location_id,
            {"display_name": "HQ 4 / 401", "notes": "support room", "reason": "normalize name"},
            actor_id="admin",
        )
        archived = await service.archive_location(location_id, {"reason": "empty location"}, actor_id="admin")
        await session.commit()

    assert updated["location"]["display_name"] == "HQ 4 / 401"
    assert updated["location"]["notes"] == "support room"
    assert archived["location"]["status"] == "archived"


@pytest.mark.asyncio
async def test_location_merge_moves_people_assets_inventory_and_writes_event(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        master = (await service.create_location({"building": "HQ", "room": "500", "reason": "master"}, actor_id="admin"))["location"]
        duplicate = (await service.create_location({"building": "HQ", "room": "501", "reason": "duplicate"}, actor_id="admin"))["location"]
        person = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Location User", location_id=duplicate["location_id"], source="manual", status="active")
        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="merge-pc",
            hostname="merge-pc",
            device_id=device_id,
            location_id=duplicate["location_id"],
            source="manual",
            status="active",
            discovery_payload={},
        )
        binding = DeviceInventoryBinding(device_id=device_id, building="HQ", room="501")
        session.add_all([person, asset, binding])
        await session.flush()

        result = await service.merge_locations(
            {
                "master_location_id": master["location_id"],
                "duplicate_location_id": duplicate["location_id"],
                "reason": "same room renamed",
            },
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        person_row = await session.get(RegistryPerson, person.person_id)
        asset_row = await session.get(RegistryAsset, asset.asset_id)
        inventory = await session.get(DeviceInventoryBinding, device_id)
        event = (
            await session.execute(select(RegistryAdminEvent).where(RegistryAdminEvent.event_type == "location_merged"))
        ).scalar_one()

    assert result["moved"] == {"people": 1, "assets": 1}
    assert person_row.location_id == master["location_id"]
    assert asset_row.location_id == master["location_id"]
    assert inventory.room == "500"
    assert event.reason == "same room renamed"
