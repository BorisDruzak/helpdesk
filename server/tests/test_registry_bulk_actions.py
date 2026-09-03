from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceInventoryBinding,
    RegistryAsset,
)
from registry.admin_operations_service import BULK_LIMIT, RegistryAdminOperationsService


pytestmark = pytest.mark.db_cleanup("registry_access")

def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="bulk-pc",
        os="Windows 11",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


@pytest.mark.asyncio
async def test_bulk_assign_location_to_devices_and_partial_failure(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        location = (await service.create_location({"building": "HQ", "room": "701", "reason": "seed"}, actor_id="admin"))["location"]
        session.add(_device(device_id))
        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="bulk-pc",
            hostname="bulk-pc",
            device_id=device_id,
            source="manual",
            status="active",
            discovery_payload={},
        )
        binding = DeviceInventoryBinding(device_id=device_id)
        session.add_all([asset, binding])
        await session.flush()
        result = await service.bulk_assign_location(
            {"ids": [device_id, str(uuid.uuid4())], "payload": {"location_id": location["location_id"]}, "reason": "floor move"},
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        asset_row = await session.get(RegistryAsset, asset.asset_id)
        inventory = await session.get(DeviceInventoryBinding, device_id)

    assert result["results"][0]["success"] is True
    assert result["results"][1]["success"] is False
    assert result["bulk_operation_id"]
    assert result["summary"] == {"selected": 2, "success": 1, "failed": 1}
    assert result["items"] == [
        {"id": device_id, "status": "success"},
        {"id": result["results"][1]["id"], "status": "error", "error_code": "NOT_FOUND"},
    ]
    assert asset_row.location_id == location["location_id"]
    assert inventory.room == "701"
