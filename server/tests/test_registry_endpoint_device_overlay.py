"""Populated PostgreSQL exact mapping and bounded business overlay."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import Device, RegistryEndpointDeviceMapping, RegistryAsset, RegistryPerson, RegistryDepartment, RegistryLocation, DeviceUserBinding
from registry.endpoint_device_overlay import read_registry_device_overlays

pytestmark = pytest.mark.db_cleanup("registration")


@pytest.mark.asyncio
async def test_exact_mapping_populated_overlay_two_reads_and_binding_cutoff(test_engine):
    now = datetime.now(timezone.utc)
    endpoint_id, unmapped_id = uuid4(), uuid4()
    local_id, asset_id = str(uuid4()), str(uuid4())
    asset_department, person_department, location = str(uuid4()), str(uuid4()), str(uuid4())
    people = [str(uuid4()) for _ in range(11)]
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    # Rollback retains no fixture data, including mapping rows and old telemetry.
    async with maker() as session:
        session.add_all([RegistryDepartment(department_id=asset_department, name="Asset department"),
            RegistryDepartment(department_id=person_department, name="Person department"),
            RegistryLocation(location_id=location, building="Test", display_name="Test location"),
            Device(device_id=local_id, protocol_version="registry", agent_version="not-technical-authority", hostname="Same host"),
            Device(device_id=str(unmapped_id), protocol_version="registry", agent_version="not-technical-authority", hostname="Same host")])
        await session.flush()
        session.add_all([RegistryPerson(person_id=value, display_name=f"Person-{i}", department_id=person_department,
            location_id=location) for i, value in enumerate(people)])
        session.add(RegistryAsset(asset_id=asset_id, device_id=local_id, asset_type="pc", name="Canonical asset",
            inventory_number="INV-123", department_id=asset_department, location_id=location))
        session.add(RegistryEndpointDeviceMapping(endpoint_device_ref=str(endpoint_id), device_id=local_id, verified_at=now))
        await session.flush()
        for i, person_id in enumerate(people):
            session.add(DeviceUserBinding(binding_id=str(uuid4()), device_id=local_id, asset_id=asset_id, person_id=person_id,
                relationship_type="primary_user" if i == 0 else "shared_user", status="revoked" if i == 8 else "active",
                valid_from=now + timedelta(days=1) if i == 10 else now - timedelta(days=1),
                valid_to=now - timedelta(hours=1) if i == 9 else None))
        await session.flush()
        statements = []
        def capture(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)
        event.listen(test_engine.sync_engine, "before_cursor_execute", capture)
        try:
            overlay = await read_registry_device_overlays(session, (endpoint_id, unmapped_id))
        finally:
            event.remove(test_engine.sync_engine, "before_cursor_execute", capture)
        mapped = overlay[endpoint_id]
        assert mapped.local_device_id == local_id and mapped.local_device_id != str(endpoint_id)
        assert mapped.asset_id == asset_id and mapped.inventory_number == "INV-123"
        assert mapped.department == "Asset department" and mapped.location == "Test location"
        assert len(mapped.bindings) == 6 and mapped.bindings_truncated
        assert mapped.bindings[0].person_id == people[0]
        assert mapped.bindings[0].department == "Person department"
        assert not {binding.person_id for binding in mapped.bindings} & set(people[8:])
        assert overlay[unmapped_id].status == "unmapped"  # UUID equality and hostname cannot create a link.
        assert len(statements) == 2
        assert not any("device_inventory" in sql or "presence_snapshot" in sql for sql in statements)
        await session.rollback()
