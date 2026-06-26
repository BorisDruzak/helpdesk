from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceBrowserPairing
from registry.browser_pairing_service import BrowserPairingService
from registry.registration_service import RegistrationService

pytestmark = pytest.mark.db_cleanup("full")


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


@pytest.mark.asyncio
async def test_web_user_login_confirmation_requires_active_binding(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id, email="owner@example.test")
        service = BrowserPairingService(session)

        created = await service.create_pairing(device_id=device_id, purpose="login", actor_id=device_id)
        confirmed = await service.confirm_login_pairing_for_web_user(
            pairing_id=created["pairing_id"],
            actor_id="owner@example.test",
        )
        pickup = await service.pickup_agent_result(device_id=device_id, pairing_id=created["pairing_id"])

        foreign = await service.create_pairing(device_id=device_id, purpose="login", actor_id=device_id)
        with pytest.raises(ValueError, match="active binding"):
            await service.confirm_login_pairing_for_web_user(
                pairing_id=foreign["pairing_id"],
                actor_id="foreign@example.test",
            )
        await session.commit()

    assert confirmed["status"] == "confirmed"
    assert confirmed["binding_id"] == approved["binding"]["binding_id"]
    assert pickup["status"] == "consumed"
    assert pickup["session"]["account_mode"] == "confirmed_binding"
    assert pickup["session_token"]


@pytest.mark.asyncio
async def test_web_user_registration_confirmation_creates_claim_for_pairing_device(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = BrowserPairingService(session)

        created = await service.create_pairing(device_id=device_id, purpose="registration", actor_id=device_id)
        confirmed = await service.confirm_registration_pairing_for_web_user(
            pairing_id=created["pairing_id"],
            actor_id="new-user@example.test",
        )
        row = await session.get(DeviceBrowserPairing, created["pairing_id"])
        await session.commit()

    assert confirmed["status"] == "confirmed"
    assert confirmed["claim_id"]
    assert confirmed["registration"]["device_id"] == device_id
    assert confirmed["registration"]["status"] in {"pending_admin_review", "user_confirmed", "approved", "conflict"}
    assert row.claim_id == confirmed["claim_id"]
    assert row.device_id == device_id


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_registration_pairing_pickup_waits_for_deliverable_session_before_consuming(monkeypatch):
    pairing_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    binding_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    row = SimpleNamespace(
        pairing_id=pairing_id,
        device_id=device_id,
        purpose="registration",
        status="confirmed",
        resulting_account_session_id=None,
        confirmed_person_id=person_id,
        binding_id=None,
        claim_id=claim_id,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        confirmed_at=datetime.now(timezone.utc),
        consumed_at=None,
        completed_at=None,
    )
    claim = SimpleNamespace(claim_id=claim_id, status="pending_admin_review", person_id=person_id)
    events: list[dict] = []

    class FakeSession:
        async def flush(self):
            return None

    class FakeRepo:
        async def get_pairing(self, requested_pairing_id):
            assert requested_pairing_id == pairing_id
            return row

    class FakeRegistrationRepo:
        async def get_claim(self, requested_claim_id):
            assert requested_claim_id == claim_id
            return claim

        async def list_active_bindings_for_device(self, requested_device_id):
            assert requested_device_id == device_id
            return [
                SimpleNamespace(
                    binding_id=binding_id,
                    person_id=person_id,
                    relationship_type="primary_user",
                )
            ]

    class FakeAccountSessionRepo:
        async def append_event(self, **payload):
            events.append(payload)

    class FakeAccountSessionService:
        def __init__(self, session):
            self.session = session

        async def create_confirmed_binding_session(self, *, device_id, binding_id):
            return {
                "session": {
                    "session_id": "session-1",
                    "device_id": device_id,
                    "binding_id": binding_id,
                    "account_mode": "confirmed_binding",
                },
                "session_token": "session-token-1",
            }

    monkeypatch.setattr(
        "registry.browser_pairing_service.AccountSessionService",
        FakeAccountSessionService,
    )
    service = BrowserPairingService.__new__(BrowserPairingService)
    service.session = FakeSession()
    service.repo = FakeRepo()
    service.registration_repo = FakeRegistrationRepo()
    service.account_session_repo = FakeAccountSessionRepo()

    pending_pickup = await service.pickup_agent_result(device_id=device_id, pairing_id=pairing_id)

    assert pending_pickup["status"] == "confirmed"
    assert pending_pickup["claim_id"] == claim_id
    assert "session_token" not in pending_pickup
    assert row.status == "confirmed"
    assert row.consumed_at is None
    assert row.completed_at is None
    assert events == []

    claim.status = "approved"
    delivered_pickup = await service.pickup_agent_result(device_id=device_id, pairing_id=pairing_id)

    assert delivered_pickup["status"] == "consumed"
    assert delivered_pickup["session"]["account_mode"] == "confirmed_binding"
    assert delivered_pickup["session"]["binding_id"] == binding_id
    assert delivered_pickup["session_token"]
    assert row.status == "consumed"
    assert row.consumed_at is not None
    assert row.resulting_account_session_id == delivered_pickup["session"]["session_id"]
    assert events == [
        {
            "device_id": device_id,
            "session_id": delivered_pickup["session"]["session_id"],
            "event_type": "browser_pairing_consumed",
            "actor_id": device_id,
            "actor_role": "agent",
            "payload": {"pairing_id": pairing_id, "purpose": "registration", "claim_id": claim_id},
        }
    ]


@pytest.mark.asyncio
async def test_create_registration_pairing_returns_register_browser_url(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = BrowserPairingService(session)

        created = await service.create_pairing(device_id=device_id, purpose="registration", actor_id=device_id)
        await session.commit()

    assert created["browser_url"].startswith("/app/device/register?pairing_id=")
