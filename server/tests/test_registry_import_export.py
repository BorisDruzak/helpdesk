from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RegistryAsset, RegistryPerson
from registry.admin_operations_service import RegistryAdminOperationsService


@pytest.mark.asyncio
async def test_registry_export_devices_and_people_csv(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        person = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Export User", full_name="Export User", source="manual", status="active")
        session.add(person)
        await session.flush()

        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="export-pc",
            hostname="export-pc",
            device_id=device_id,
            assigned_person_id=person.person_id,
            source="manual",
            status="active",
            discovery_payload={"agent_version": "3.1.59"},
        )
        session.add(asset)
        await session.flush()
        devices_csv = await RegistryAdminOperationsService(session).export_csv("devices")
        people_csv = await RegistryAdminOperationsService(session).export_csv("people")
        await session.commit()

    assert "device_id,hostname,active_person_name" in devices_csv
    assert device_id in devices_csv
    assert "person_id,full_name,display_name" in people_csv
    assert "Export User" in people_csv
