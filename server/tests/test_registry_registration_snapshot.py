from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceUserBinding
from registry.registration_service import RegistrationService
from registry.service import RegistrySnapshotService


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
