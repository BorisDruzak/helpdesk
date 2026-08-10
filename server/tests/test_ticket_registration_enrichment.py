from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceRegistrationClaim, RegistryPerson, Ticket
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService
from tests.conftest import TEST_AGENT_PREFIX
from tickets.create_flow import create_ticket_with_side_effects
from tickets.ticket_context import TicketContextBuilder


pytestmark = pytest.mark.db_cleanup("tickets")

def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="ticket-reg",
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


@pytest.mark.asyncio
async def test_ticket_with_active_binding_gets_requester_context_and_asset(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="ticket-active",
            display_name="Ticket Active",
            profile={"full_name": "Ticket Active", "email": "ticket-active@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(result["registration"]["claim_id"], reviewed_by="admin")
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="ticket-active",
            title="Need help",
            description="Need help",
            user_display_name="Ticket Active",
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])

    assert ticket.requester_person_id == approved["binding"]["person_id"]
    assert ticket.requester_binding_id == approved["binding"]["binding_id"]
    assert ticket.requester_external_ref == approved["binding"]["person_id"]
    assert ticket.requester_snapshot_json == {
        "person": {"external_id": approved["binding"]["person_id"]},
        "display_name": "Ticket Active",
    }
    assert ticket.requester_registration_status == "admin_confirmed"
    assert ticket.asset_id is None
    assert ticket.requester_account_mode == "agent_legacy_or_device_only"
    assert ticket.custom_fields["requester_account_context"]["account_mode"] == "agent_legacy_or_device_only"
    assert ticket.custom_fields["requester_account_context"]["context_scope"] == "limited"
    assert ticket.custom_fields["requester_account_context"]["profile_completion_evidence"] is False
    assert ticket.custom_fields["ticket_context"]["requester_context"]["account_mode"] == "agent_legacy_or_device_only"
    assert ticket.custom_fields["ticket_context"]["requester_context"]["context_scope"] == "limited"
    assert "profile_completion" not in ticket.custom_fields["ticket_context"]["requester_context"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_display_name",
    ["   ", "X" * 257],
    ids=["blank", "overlong"],
)
async def test_verified_requester_with_invalid_snapshot_does_not_create_legacy_only_ticket(
    test_engine,
    invalid_display_name: str,
):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    title = f"Invalid requester snapshot {len(invalid_display_name)}"

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="ticket-invalid-snapshot",
            display_name="Valid Before Approval",
            profile={
                "full_name": "Valid Before Approval",
                "email": "ticket-invalid-snapshot@example.test",
                "user_confirmed": True,
            },
        )
        approved = await service.approve_claim(
            result["registration"]["claim_id"],
            reviewed_by="admin",
        )
        person = await session.get(RegistryPerson, approved["person"]["person_id"])
        assert person is not None
        person.display_name = invalid_display_name
        person.full_name = invalid_display_name
        await session.flush()

        with pytest.raises(ValueError):
            await create_ticket_with_side_effects(
                session,
                device_id=device_id,
                requester_id="ticket-invalid-snapshot",
                title=title,
                description="Must fail instead of writing legacy-only requester scope",
                user_display_name="Payload display must not be used",
            )

        stored = await session.scalar(select(Ticket).where(Ticket.title == title))
        assert stored is None


@pytest.mark.asyncio
async def test_stale_verified_requester_does_not_create_legacy_only_ticket(
    test_engine,
    monkeypatch,
):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    title = "Stale verified requester"

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="ticket-stale-verified-person",
            display_name="Stale Verified Person",
            profile={
                "full_name": "Stale Verified Person",
                "email": "ticket-stale-verified-person@example.test",
                "user_confirmed": True,
            },
        )
        await service.approve_claim(
            result["registration"]["claim_id"],
            reviewed_by="admin",
        )

        async def _missing_verified_person(_builder, _person_id):
            return None, None

        monkeypatch.setattr(
            TicketContextBuilder,
            "requester_reference_snapshot",
            _missing_verified_person,
        )

        with pytest.raises(ValueError, match="complete requester reference snapshot"):
            await create_ticket_with_side_effects(
                session,
                device_id=device_id,
                requester_id="ticket-stale-verified-person",
                title=title,
                description="Must fail when the verified person disappears",
                user_display_name="Payload display must not be used",
            )

        stored = await session.scalar(select(Ticket).where(Ticket.title == title))
        assert stored is None


@pytest.mark.asyncio
async def test_ticket_with_active_binding_ignores_conflicting_requester_profile(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="ticket-active-profile",
            display_name="Ticket Active Profile",
            profile={"full_name": "Ticket Active Profile", "email": "ticket-active-profile@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(result["registration"]["claim_id"], reviewed_by="admin")
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="different-requester",
            title="Need help",
            description="Need help",
            user_display_name="Different Requester",
            requester_profile={"full_name": "Different Requester", "email": "different-requester@example.test"},
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])
        claims = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalars().all()

    assert ticket.requester_person_id == approved["binding"]["person_id"]
    assert ticket.requester_binding_id == approved["binding"]["binding_id"]
    assert ticket.requester_external_ref == approved["binding"]["person_id"]
    assert ticket.requester_snapshot_json == {
        "person": {"external_id": approved["binding"]["person_id"]},
        "display_name": "Ticket Active Profile",
    }
    assert ticket.requester_registration_status == "admin_confirmed"
    assert ticket.asset_id is None
    assert len(claims) == 1
    assert claims[0].status == "approved"


@pytest.mark.asyncio
async def test_ticket_with_requester_profile_creates_claim_and_pending_status(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="ticket-pending",
            title="Need help",
            description="Need help",
            user_display_name="Ticket Pending",
            requester_profile={"full_name": "Ticket Pending", "email": "ticket-pending@example.test"},
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])
        claim = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalar_one()

    assert claim.status == "pending_user_confirmation"
    assert ticket.requester_person_id is None
    assert ticket.requester_binding_id is None
    assert ticket.requester_registration_status == "self_reported"
    assert ticket.requester_account_mode == "agent_legacy_or_device_only"
    assert ticket.custom_fields["requester_account_context"]["account_mode"] == "agent_legacy_or_device_only"
    assert ticket.custom_fields["requester_account_context"]["context_scope"] == "limited"
    assert ticket.custom_fields["requester_account_context"]["profile_completion_evidence"] is False
    assert "ticket_context" not in ticket.custom_fields
    assert "pending_claim" not in ticket.custom_fields["requester_registration"]
    assert ticket.custom_fields["requester_registration"]["requires_user_action"] is True


@pytest.mark.asyncio
async def test_ticket_with_conflict_claim_does_not_assign_requester_person(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="first-ticket",
            display_name="First Ticket",
            profile={"full_name": "First Ticket", "email": "first-ticket@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(first["registration"]["claim_id"], reviewed_by="admin")
        conflict = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="second-ticket",
            display_name="Second Ticket",
            profile={"full_name": "Second Ticket", "email": "second-ticket@example.test", "user_confirmed": True},
        )
        await service.revoke_binding(approved["binding"]["binding_id"], revoked_by="admin", reason="test conflict without active")
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="second-ticket",
            title="Need help",
            description="Need help",
            user_display_name="Second Ticket",
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])

    assert ticket.requester_person_id is None
    assert ticket.requester_binding_id is None
    assert ticket.requester_registration_status == "conflict"
    assert ticket.custom_fields["requester_registration"]["status"] == "conflict"
    assert "pending_claim" not in ticket.custom_fields["requester_registration"]
    assert ticket.custom_fields["requester_registration"]["requires_admin_action"] is True


@pytest.mark.asyncio
async def test_confirmed_binding_account_context_uses_active_binding(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        claim = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="confirmed-account",
            display_name="Confirmed Account",
            profile={"full_name": "Confirmed Account", "email": "confirmed-account@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        account_session = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="confirmed-account",
            title="Need help",
            description="Need help",
            user_display_name="Confirmed Account",
            requester_profile={"full_name": "Conflicting Form", "email": "conflicting-form@example.test"},
            requester_account={
                "session_id": account_session["session"]["session_id"],
                "session_token": account_session.get("session_token"),
            },
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])
        claims = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalars().all()

    assert ticket.requester_person_id == approved["binding"]["person_id"]
    assert ticket.requester_binding_id == approved["binding"]["binding_id"]
    assert ticket.requester_external_ref == approved["binding"]["person_id"]
    assert ticket.requester_snapshot_json == {
        "person": {"external_id": approved["binding"]["person_id"]},
        "display_name": "Confirmed Account",
    }
    assert ticket.requester_registration_status == "admin_confirmed"
    assert ticket.requester_account_session_id == account_session["session"]["session_id"]
    assert ticket.requester_account_mode == "confirmed_binding"
    assert ticket.requester_account_warning is None
    assert ticket.custom_fields["requester_account_context"]["account_mode"] == "confirmed_binding"
    assert ticket.custom_fields["requester_account_context"]["validation"] == "server_session_verified"
    assert len(claims) == 1


@pytest.mark.asyncio
async def test_verified_other_account_session_marks_ticket_without_registration_claim(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        claim = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="registered-owner",
            display_name="Registered Owner",
            profile={"full_name": "Registered Owner", "email": "registered-owner@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        account_service = AccountSessionService(session)
        request = await account_service.create_other_account_login_request(
            device_id=device_id,
            requested_account={
                "full_name": "Other Account",
                "display_name": "Other Account",
                "login": "other-account",
                "email": "other-account@example.test",
                "phone": "+15551234567",
                "reason": "Temporary replacement",
            },
        )
        session_payload = await account_service.approve_login_request(request["request_id"], reviewed_by="admin")
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="other-account",
            title="Need help",
            description="Need help",
            user_display_name="Other Account",
            requester_profile={"full_name": "Other Account", "email": "other-account@example.test"},
            requester_account={
                "session_id": session_payload["session"]["session_id"],
                "session_token": session_payload.get("session_token"),
            },
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])
        claims = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalars().all()

    assert ticket.requester_registration_status == "other_account"
    assert ticket.requester_account_session_id == session_payload["session"]["session_id"]
    assert ticket.requester_account_mode == "verified_other_account"
    assert ticket.requester_account_warning == "ticket_created_from_other_account_on_registered_device"
    assert ticket.requester_binding_id is None
    assert ticket.requester_person_id is None
    assert ticket.requester_external_ref is None
    assert ticket.requester_snapshot_json is None
    assert ticket.asset_id is None
    assert ticket.custom_fields["requester_account_context"]["created_from_other_account"] is True
    assert ticket.custom_fields["requester_account_context"]["verification_status"] == "verified"
    assert ticket.custom_fields["requester_account_context"]["verification_method"] == "admin_approval"
    assert ticket.custom_fields["requester_account_context"]["declared_account"]["phone"] == "+15551234567"
    assert ticket.custom_fields["requester_account_context"]["declared_account"]["reason"] == "Temporary replacement"
    assert ticket.custom_fields["requester_account_context"]["active_device_binding_id"] == approved["binding"]["binding_id"]
    assert ticket.custom_fields["requester_account_context"]["warning"] == "ticket_created_from_other_account_on_registered_device"
    assert len(claims) == 1
    assert claims[0].status == "approved"


@pytest.mark.asyncio
async def test_unapproved_other_account_request_cannot_create_verified_ticket(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        claim = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="registered-owner",
            display_name="Registered Owner",
            profile={"full_name": "Registered Owner", "email": "registered-owner2@example.test", "user_confirmed": True},
        )
        await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        request = await AccountSessionService(session).create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other Account", "login": "other-account", "reason": "Temporary replacement"},
        )
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="other-account",
            title="Need help",
            description="Need help",
            user_display_name="Other Account",
            requester_account={"session_id": request["request_id"]},
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])

    assert ticket.requester_registration_status == "account_session_invalid"
    assert ticket.requester_external_ref is None
    assert ticket.requester_snapshot_json is None
    assert ticket.custom_fields["requester_account_context"]["validation"] == "server_session_invalid"


@pytest.mark.asyncio
async def test_registration_pending_account_after_revoke_marks_pending_without_blocking(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        first = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="registered-first",
            display_name="Registered First",
            profile={"full_name": "Registered First", "email": "registered-first@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(first["registration"]["claim_id"], reviewed_by="admin")
        await service.revoke_binding(approved["binding"]["binding_id"], revoked_by="admin", reason="test pending")
        pending = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending-after-revoke",
            display_name="Pending After Revoke",
            profile={"full_name": "Pending After Revoke", "email": "pending-after-revoke@example.test"},
        )
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="pending-after-revoke",
            title="Need help",
            description="Need help",
            user_display_name="Pending After Revoke",
            requester_account={
                "account_mode": "registration_pending",
                "display_name": "Pending After Revoke",
                "metadata": {"claim_id": pending["registration"]["claim_id"]},
            },
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])

    assert ticket.requester_binding_id is None
    assert ticket.asset_id is None
    assert ticket.requester_registration_status in {"pending_user_confirmation", "registration_pending"}
    assert ticket.custom_fields["requester_account_context"]["account_mode"] == "registration_pending"


@pytest.mark.asyncio
async def test_agent_create_with_required_invalid_session_returns_403_before_ticket_create(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        headers={"Authorization": f"Bearer {TEST_AGENT_PREFIX}{device_id}"},
        json={
            "device_id": device_id,
            "title": "Need help",
            "description": "Need help",
            "requester_account": {"session_id": str(uuid.uuid4())},
            "require_account_session": True,
        },
    )

    assert response.status == 403, await response.text()
    payload = await response.json()
    assert payload["error_code"] == "ACCOUNT_SESSION_NOT_FOUND"
    async with session_maker() as session:
        tickets = (await session.execute(select(Ticket).where(Ticket.device_id == device_id))).scalars().all()
    assert tickets == []


@pytest.mark.asyncio
async def test_agent_create_without_account_session_returns_403_before_ticket_create(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        headers={"Authorization": f"Bearer {TEST_AGENT_PREFIX}{device_id}"},
        json={
            "device_id": device_id,
            "title": "Need help",
            "description": "Need help",
        },
    )

    assert response.status == 403, await response.text()
    payload = await response.json()
    assert payload["error_code"] == "ACCOUNT_SESSION_REQUIRED"
    async with session_maker() as session:
        tickets = (await session.execute(select(Ticket).where(Ticket.device_id == device_id))).scalars().all()
    assert tickets == []
