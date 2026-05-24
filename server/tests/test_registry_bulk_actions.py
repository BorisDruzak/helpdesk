from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceInventoryBinding,
    RegistryAsset,
)
from registry.admin_operations_service import BULK_LIMIT, RegistryAdminOperationsService


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


@pytest.mark.asyncio
async def test_bulk_revoke_account_sessions_and_batch_limit(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        session.add(_device(device_id))
        account_session = DeviceAccountSession(
            session_id=str(uuid.uuid4()),
            device_id=device_id,
            account_mode="confirmed_binding",
            verification_status="verified",
            declared_account={},
            metadata_json={},
        )
        session.add(account_session)
        await session.flush()

        result = await service.bulk_revoke_sessions(
            {"ids": [account_session.session_id], "reason": "incident response"},
            actor_id="admin",
        )
        with pytest.raises(ValueError):
            service._validate_bulk_ids({"ids": [str(uuid.uuid4()) for _ in range(BULK_LIMIT + 1)]})
        await session.commit()

    async with session_maker() as session:
        row = await session.get(DeviceAccountSession, account_session.session_id)

    assert result["results"] == [{"id": account_session.session_id, "success": True}]
    assert result["summary"] == {"selected": 1, "success": 1, "failed": 0}
    assert result["items"] == [{"id": account_session.session_id, "status": "success"}]
    assert row.verification_status == "revoked"


@pytest.mark.asyncio
async def test_bulk_revoke_device_sessions_reports_each_selected_device(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    missing_device_id = str(uuid.uuid4())
    async with session_maker() as session:
        service = RegistryAdminOperationsService(session)
        session.add(_device(device_id))
        account_session = DeviceAccountSession(
            session_id=str(uuid.uuid4()),
            device_id=device_id,
            account_mode="confirmed_binding",
            verification_status="verified",
            declared_account={},
            metadata_json={},
        )
        session.add(account_session)
        await session.flush()

        result = await service.bulk_revoke_sessions(
            {"ids": [device_id, missing_device_id], "reason": "device incident"},
            actor_id="admin",
            by_device=True,
        )
        await session.commit()

    assert result["summary"] == {"selected": 2, "success": 1, "failed": 1}
    assert result["items"] == [
        {"id": device_id, "status": "success", "affected_sessions": 1},
        {"id": missing_device_id, "status": "error", "error_code": "NOT_FOUND"},
    ]
