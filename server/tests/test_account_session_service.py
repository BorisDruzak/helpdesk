from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceAccountLoginRequest, DeviceAccountSession, DeviceUserBinding
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


async def _approved_binding(
    session,
    device_id: str,
    email: str = "owner@example.test",
    *,
    relationship_type: str = "primary_user",
) -> dict:
    service = RegistrationService(session)
    claim = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=email,
        display_name="Registered Owner",
        profile={
            "full_name": "Registered Owner",
            "email": email,
            "phone": "+10000000001",
            "relationship_type": relationship_type,
            "user_confirmed": True,
        },
    )
    return await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")


async def _person_from_claim(session, *, device_id: str, email: str, display_name: str) -> str:
    result = await RegistrationService(session).submit_agent_profile_claim(
        device_id=device_id,
        requester_id=email,
        display_name=display_name,
        profile={
            "full_name": display_name,
            "email": email,
            "login": email.split("@", 1)[0],
            "user_confirmed": True,
        },
    )
    return result["person"]["person_id"]


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
async def test_shared_binding_can_create_confirmed_binding_session(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(
            session,
            device_id,
            email="shared@example.test",
            relationship_type="shared_user",
        )
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

    assert approved["binding"]["relationship_type"] == "shared_user"
    assert created["session"]["account_mode"] == "confirmed_binding"
    assert created["session"]["binding_id"] == approved["binding"]["binding_id"]
    assert validated["valid"] is True


def test_serialize_event_formats_event_at_without_route_500():
    row = SimpleNamespace(
        event_id="evt-1",
        device_id="device-1",
        session_id="session-1",
        request_id=None,
        ticket_id=None,
        event_type="p1_account_events_route_regression",
        actor_id="test-admin",
        actor_role="admin",
        event_at=datetime(2026, 5, 27, 19, 11, tzinfo=timezone.utc),
        payload={"marker": "account-events-route"},
    )

    item = AccountSessionService.serialize_event(row)

    assert item["event_type"] == "p1_account_events_route_regression"
    assert item["event_at"] == "2026-05-27T19:11:00+00:00"
    assert item["payload"] == {"marker": "account-events-route"}


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
    assert approved_request.get("session_token")
    assert approved_request["session"]["declared_account"]["phone"] == "+15551234567"
    assert approved_request["session"]["reason"] == "Temporary replacement"
    assert validated["valid"] is True


@pytest.mark.asyncio
async def test_verified_other_account_session_requires_valid_token(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        await _approved_binding(session, device_id)
        service = AccountSessionService(session)
        request = await service.create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other", "reason": "Temporary replacement"},
        )
        approved_request = await service.approve_login_request(request["request_id"], reviewed_by="admin")
        missing = await service.validate_session(
            device_id=device_id,
            session_id=approved_request["session"]["session_id"],
        )
        wrong = await service.validate_session(
            device_id=device_id,
            session_id=approved_request["session"]["session_id"],
            session_token="wrong-token",
        )
        valid = await service.validate_session(
            device_id=device_id,
            session_id=approved_request["session"]["session_id"],
            session_token=approved_request["session_token"],
        )
        await session.commit()

    assert missing["valid"] is False
    assert missing["error_code"] == "ACCOUNT_SESSION_TOKEN_REQUIRED"
    assert wrong["valid"] is False
    assert wrong["error_code"] == "ACCOUNT_SESSION_TOKEN_INVALID"
    assert valid["valid"] is True


@pytest.mark.asyncio
async def test_revoked_confirmed_binding_invalidates_session(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        account_service = AccountSessionService(session)
        created = await account_service.create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        await RegistrationService(session).revoke_binding(approved["binding"]["binding_id"], revoked_by="admin")

        invalid = await account_service.validate_session(
            device_id=device_id,
            session_id=created["session"]["session_id"],
            session_token=created.get("session_token"),
        )
        session_row = await session.get(DeviceAccountSession, created["session"]["session_id"])
        await session.commit()

    assert invalid["valid"] is False
    assert invalid["error_code"] == "ACCOUNT_SESSION_REVOKED"
    assert session_row.verification_status == "revoked"
    assert session_row.revoked_by == "admin"


@pytest.mark.asyncio
async def test_revoked_base_binding_invalidates_verified_other_account_session(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        account_service = AccountSessionService(session)
        request = await account_service.create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other", "reason": "Temporary replacement"},
        )
        approved_request = await account_service.approve_login_request(request["request_id"], reviewed_by="admin")
        await RegistrationService(session).revoke_binding(approved["binding"]["binding_id"], revoked_by="admin")

        invalid = await account_service.validate_session(
            device_id=device_id,
            session_id=approved_request["session"]["session_id"],
            session_token=approved_request["session_token"],
        )
        session_row = await session.get(DeviceAccountSession, approved_request["session"]["session_id"])
        await session.commit()

    assert invalid["valid"] is False
    assert invalid["error_code"] == "ACCOUNT_SESSION_REVOKED"
    assert session_row.verification_status == "revoked"
    assert session_row.revoked_by == "admin"


@pytest.mark.asyncio
async def test_transfer_owner_cancels_pending_other_account_login_requests(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        new_person_id = await _person_from_claim(
            session,
            device_id=device_id,
            email="new-owner@example.test",
            display_name="New Owner",
        )
        account_service = AccountSessionService(session)
        request = await account_service.create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other", "reason": "Temporary replacement"},
        )

        await RegistrationService(session).transfer_owner(
            device_id=device_id,
            new_person_id=new_person_id,
            old_binding_action="transferred",
            reviewed_by="admin",
            reason="device handed over",
        )
        request_row = await session.get(DeviceAccountLoginRequest, request["request_id"])
        pending = await account_service.list_pending_login_requests_for_device(device_id)
        await session.commit()

    assert request["base_binding_id"] == approved["binding"]["binding_id"]
    assert request_row.status == "canceled"
    assert request_row.reviewed_by == "admin"
    assert request_row.rejection_reason == "base binding changed: device handed over"
    assert pending == []


@pytest.mark.asyncio
async def test_approve_login_request_cancels_stale_base_binding_request(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        account_service = AccountSessionService(session)
        request = await account_service.create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other", "reason": "Temporary replacement"},
        )
        binding = await session.get(DeviceUserBinding, approved["binding"]["binding_id"])
        binding.status = "transferred"

        with pytest.raises(ValueError, match="base binding is no longer active"):
            await account_service.approve_login_request(request["request_id"], reviewed_by="admin")

        request_row = await session.get(DeviceAccountLoginRequest, request["request_id"])
        await session.commit()

    assert request_row.status == "canceled"
    assert request_row.reviewed_by == "admin"
    assert request_row.rejection_reason == "base binding is no longer active"


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


@pytest.mark.asyncio
async def test_other_account_login_request_allows_shared_only_registered_device(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(
            session,
            device_id,
            email="shared-owner@example.test",
            relationship_type="shared_user",
        )
        service = AccountSessionService(session)

        request = await service.create_other_account_login_request(
            device_id=device_id,
            requested_account={
                "full_name": "Other User",
                "login": "other",
                "reason": "Temporary replacement",
            },
        )
        await session.commit()

    assert approved["binding"]["relationship_type"] == "shared_user"
    assert request["status"] == "pending_verification"
    assert request["base_binding_id"] == approved["binding"]["binding_id"]
    assert request["base_person_id"] == approved["binding"]["person_id"]


@pytest.mark.asyncio
async def test_registration_pending_session_creation_validation_and_claim_invalidation(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        registration = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending@example.test",
            display_name="Pending User",
            profile={"full_name": "Pending User", "email": "pending@example.test"},
        )
        claim_id = registration["registration"]["claim_id"]
        service = AccountSessionService(session)

        created = await service.create_registration_pending_session(device_id=device_id, claim_id=claim_id)
        valid = await service.validate_session(
            device_id=device_id,
            session_id=created["session"]["session_id"],
            session_token=created["session_token"],
        )
        await RegistrationService(session).reject_claim(claim_id, reviewed_by="admin", reason="test")
        invalid = await service.validate_session(
            device_id=device_id,
            session_id=created["session"]["session_id"],
            session_token=created["session_token"],
        )
        await session.commit()

    assert created["session"]["account_mode"] == "registration_pending"
    assert created["session"]["verification_status"] == "pending_verification"
    assert created.get("session_token")
    assert valid["valid"] is True
    assert invalid["valid"] is False
    assert invalid["error_code"] == "ACCOUNT_SESSION_CLAIM_INACTIVE"


@pytest.mark.asyncio
async def test_registration_pending_session_is_revoked_when_claim_is_approved(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        registration = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending-approved@example.test",
            display_name="Pending Approved",
            profile={"full_name": "Pending Approved", "email": "pending-approved@example.test"},
        )
        claim_id = registration["registration"]["claim_id"]
        service = AccountSessionService(session)
        pending = await service.create_registration_pending_session(device_id=device_id, claim_id=claim_id)

        await RegistrationService(session).approve_claim(
            claim_id,
            reviewed_by="admin",
            admin_override_user_confirmation=True,
            override_reason="verified by admin",
        )
        row = await service.repo.get_session(pending["session"]["session_id"])
        await session.commit()

    assert row is not None
    assert row.account_mode == "registration_pending"
    assert row.verification_status == "revoked"
    assert row.revoked_at is not None


@pytest.mark.asyncio
async def test_account_session_ttl_defaults(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        service = AccountSessionService(session)
        confirmed = await service.create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        registration = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending-ttl@example.test",
            display_name="Pending TTL",
            profile={"full_name": "Pending TTL", "email": "pending-ttl@example.test"},
        )
        pending = await service.create_registration_pending_session(
            device_id=device_id,
            claim_id=registration["registration"]["claim_id"],
        )
        request = await service.create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other", "reason": "Temporary replacement"},
        )
        other = await service.approve_login_request(request["request_id"], reviewed_by="admin")
        await session.commit()

    assert confirmed["session"]["expires_at"] is None
    assert pending["session"]["expires_at"]
    assert other["session"]["expires_at"]


@pytest.mark.asyncio
async def test_logout_and_admin_revoke_invalidate_account_sessions(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        service = AccountSessionService(session)
        first = await service.create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        logged_out = await service.logout_session(
            device_id=device_id,
            session_id=first["session"]["session_id"],
            session_token=first["session_token"],
        )
        after_logout = await service.validate_session(
            device_id=device_id,
            session_id=first["session"]["session_id"],
            session_token=first["session_token"],
        )

        second = await service.create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        revoked = await service.revoke_session(
            session_id=second["session"]["session_id"],
            revoked_by="admin",
            reason="manual revoke",
        )
        after_revoke = await service.validate_session(
            device_id=device_id,
            session_id=second["session"]["session_id"],
            session_token=second["session_token"],
        )
        await session.commit()

    assert logged_out["verification_status"] == "revoked"
    assert after_logout["valid"] is False
    assert after_logout["error_code"] == "ACCOUNT_SESSION_REVOKED"
    assert revoked["verification_status"] == "revoked"
    assert revoked["revoked_by"] == "admin"
    assert after_revoke["valid"] is False
    assert after_revoke["error_code"] == "ACCOUNT_SESSION_REVOKED"
