from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
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
from registry.admin_operations_service import RegistryAdminOperationsService


pytestmark = pytest.mark.db_cleanup("registry_access")

def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="merge-pc",
        os="Windows 11",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


@pytest.mark.asyncio
async def test_people_merge_moves_related_records_and_marks_duplicate(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        master = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Master User", email="master@example.test", source="manual", status="active")
        duplicate = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Duplicate User", phone="+70000000000", source="manual", status="active")
        session.add_all([master, duplicate])
        await session.flush()

        asset = RegistryAsset(
            asset_id=str(uuid.uuid4()),
            asset_type="pc",
            name="merge-pc",
            hostname="merge-pc",
            device_id=device_id,
            assigned_person_id=duplicate.person_id,
            source="manual",
            status="active",
            discovery_payload={},
        )
        session.add(asset)
        await session.flush()

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
            title="Merge requester",
            description="ticket",
            status="new",
            requester_id="duplicate-user",
            requester_person_id=duplicate.person_id,
        )
        session.add_all([identity, binding, inventory_binding, claim, ticket])
        await session.flush()

        session.add(account_session)
        await session.flush()

        result = await RegistryAdminOperationsService(session).merge_people(
            {
                "master_person_id": master.person_id,
                "duplicate_person_id": duplicate.person_id,
                "field_strategy": {"phone": "duplicate"},
                "reason": "same employee",
            },
            actor_id="admin",
        )
        await session.commit()

    async with session_maker() as session:
        master_row = await session.get(RegistryPerson, master.person_id)
        duplicate_row = await session.get(RegistryPerson, duplicate.person_id)
        identity_row = await session.get(RegistryPersonIdentity, identity.identity_id)
        binding_row = await session.get(DeviceUserBinding, binding.binding_id)
        session_row = await session.get(DeviceAccountSession, account_session.session_id)
        claim_row = await session.get(DeviceRegistrationClaim, claim.claim_id)
        ticket_row = await session.get(Ticket, ticket.ticket_id)
        asset_row = await session.get(RegistryAsset, asset.asset_id)
        inventory_row = await session.get(DeviceInventoryBinding, device_id)
        event = (await session.execute(select(RegistryAdminEvent).where(RegistryAdminEvent.event_type == "person_merged"))).scalar_one()

    assert result["moved"]["identities"] == 1
    assert master_row.phone == "+70000000000"
    assert duplicate_row.status == "merged"
    assert identity_row.person_id == master.person_id
    assert binding_row.person_id == master.person_id
    assert session_row.person_id == master.person_id
    assert claim_row.person_id == master.person_id
    assert ticket_row.requester_person_id == master.person_id
    assert asset_row.assigned_person_id == master.person_id
    assert inventory_row.person_id == master.person_id
    assert inventory_row.source_binding_id == binding.binding_id
    assert event.reason == "same employee"
