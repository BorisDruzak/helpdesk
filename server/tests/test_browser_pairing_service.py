from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceBrowserPairing
from registry.browser_pairing_service import BrowserPairingService
from registry.registration_service import RegistrationService


def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.62",
        hostname="browser-pairing",
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


async def _approved_binding(session, device_id: str, email: str = "owner@example.test") -> dict:
    service = RegistrationService(session)
    claim = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=email,
        display_name="Registered Owner",
        profile={
            "full_name": "Registered Owner",
            "email": email,
            "phone": "+10000000001",
            "relationship_type": "primary_user",
            "user_confirmed": True,
        },
    )
    return await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")


@pytest.mark.asyncio
async def test_create_pairing_hashes_secrets_and_supersedes_pending(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = BrowserPairingService(session)

        first = await service.create_pairing(
            device_id=device_id,
            purpose="login",
            actor_id=device_id,
            agent_version="3.1.62",
            user_agent="pytest-agent",
        )
        first_row = await session.get(DeviceBrowserPairing, first["pairing_id"])
        second = await service.create_pairing(device_id=device_id, purpose="login", actor_id=device_id)
        superseded_row = await session.get(DeviceBrowserPairing, first["pairing_id"])
        active_row = await session.get(DeviceBrowserPairing, second["pairing_id"])
        await session.commit()

    assert first["pairing_token"]
    assert first["pairing_code"]
    assert first_row.pairing_token_hash != first["pairing_token"]
    assert first_row.pairing_code_hash != first["pairing_code"]
    assert first["pairing_token"] not in str(first_row.metadata_json or {})
    assert first["pairing_code"] not in str(first_row.metadata_json or {})
    assert superseded_row.status == "superseded"
    assert superseded_row.completed_at is not None
    assert active_row.status == "pending"


@pytest.mark.asyncio
async def test_lookup_by_pairing_code_requires_pending_and_not_expired(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = BrowserPairingService(session)
        created = await service.create_pairing(device_id=device_id, purpose="login", actor_id=device_id)

        found = await service.lookup_by_pairing_code(created["pairing_code"])
        row = await session.get(DeviceBrowserPairing, created["pairing_id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        expired = await service.lookup_by_pairing_code(created["pairing_code"])
        await session.commit()

    assert found is not None
    assert found["pairing_id"] == created["pairing_id"]
    assert expired is None


@pytest.mark.asyncio
async def test_confirmed_login_pairing_pickup_returns_session_token_once(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        service = BrowserPairingService(session)

        created = await service.create_pairing(device_id=device_id, purpose="login", actor_id=device_id)
        confirmed = await service.confirm_login_pairing(
            pairing_id=created["pairing_id"],
            pairing_token=created["pairing_token"],
            binding_id=approved["binding"]["binding_id"],
            actor_id="browser-user",
        )
        first_pickup = await service.pickup_agent_result(device_id=device_id, pairing_id=created["pairing_id"])
        second_pickup = await service.pickup_agent_result(device_id=device_id, pairing_id=created["pairing_id"])
        session_row = await session.get(DeviceBrowserPairing, created["pairing_id"])
        await session.commit()

    assert confirmed["status"] == "confirmed"
    assert first_pickup["status"] == "consumed"
    assert first_pickup["session"]["account_mode"] == "confirmed_binding"
    assert first_pickup["session"]["binding_id"] == approved["binding"]["binding_id"]
    assert first_pickup["session_token"]
    assert second_pickup["status"] == "consumed"
    assert "session_token" not in second_pickup
    assert session_row.resulting_account_session_id == first_pickup["session"]["session_id"]
