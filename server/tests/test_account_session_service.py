from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService


def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="account-session",
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
        profile={"full_name": "Registered Owner", "email": email, "phone": "+10000000001", "user_confirmed": True},
    )
    return await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")


@pytest.mark.asyncio
async def test_confirmed_binding_session_creation_and_validation(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        service = AccountSessionService(session)

        created = await service.create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        validated = await service.validate_session(
            device_id=device_id,
            session_id=created["session"]["session_id"],
            session_token=created.get("session_token"),
        )
        await session.commit()

    assert created["session"]["account_mode"] == "confirmed_binding"
    assert created["session"]["verification_status"] == "verified"
    assert created["session"]["binding_id"] == approved["binding"]["binding_id"]
    assert created["session"]["display_name"] == "Registered Owner"
    assert created["session"]["full_name"] == "Registered Owner"
    assert created["session"]["email"] == "owner@example.test"
    assert created["session"]["phone"] == "+10000000001"
    assert created["session"]["person"]["display_name"] == "Registered Owner"
    assert validated["valid"] is True
    assert validated["session"]["person_id"] == approved["binding"]["person_id"]


@pytest.mark.asyncio
async def test_other_account_login_request_approval_creates_verified_session(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        service = AccountSessionService(session)

        request = await service.create_other_account_login_request(
            device_id=device_id,
            requested_account={
                "full_name": "Other User",
                "display_name": "Other",
                "login": "other",
                "email": "other@example.test",
                "phone": "+15551234567",
                "reason": "Temporary replacement",
            },
        )
        approved_request = await service.approve_login_request(request["request_id"], reviewed_by="admin")
        validated = await service.validate_session(
            device_id=device_id,
            session_id=approved_request["session"]["session_id"],
            session_token=approved_request.get("session_token"),
        )
        await session.commit()

    assert request["status"] == "pending_verification"
    assert approved_request["session"]["account_mode"] == "verified_other_account"
    assert approved_request["session"]["verification_method"] == "admin_approval"
    assert approved_request["session"]["base_binding_id"] == approved["binding"]["binding_id"]
    assert approved_request.get("session_token") is None
    assert approved_request["session"]["declared_account"]["phone"] == "+15551234567"
    assert approved_request["session"]["reason"] == "Temporary replacement"
    assert validated["valid"] is True


@pytest.mark.asyncio
async def test_other_account_login_request_requires_active_binding(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = AccountSessionService(session)

        with pytest.raises(ValueError, match="active binding"):
            await service.create_other_account_login_request(
                device_id=device_id,
                requested_account={"full_name": "Other User", "login": "other", "reason": "test"},
            )


@pytest.mark.asyncio
async def test_reject_and_expired_session_are_invalid(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        service = AccountSessionService(session)
        request = await service.create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other", "reason": "test"},
        )
        rejected = await service.reject_login_request(request["request_id"], reviewed_by="admin", reason="no")
        created = await service.create_confirmed_binding_session(device_id=device_id, binding_id=approved["binding"]["binding_id"])
        row = await service.repo.get_session(created["session"]["session_id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        invalid = await service.validate_session(device_id=device_id, session_id=row.session_id)
        await session.commit()

    assert rejected["status"] == "rejected"
    assert invalid["valid"] is False
    assert invalid["error_code"] == "ACCOUNT_SESSION_EXPIRED"
