from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceRegistrationClaim, Ticket
from registry.registration_service import RegistrationService
from tickets.create_flow import create_ticket_with_side_effects


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
    assert ticket.requester_registration_status == "admin_confirmed"
    assert ticket.asset_id == approved["binding"]["asset_id"]


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
    assert ticket.requester_registration_status == "admin_confirmed"
    assert ticket.asset_id == approved["binding"]["asset_id"]
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
    assert ticket.requester_registration_status == "pending_user_confirmation"
    assert ticket.custom_fields["requester_registration"]["pending_claim"]["claim_id"] == claim.claim_id


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
    assert ticket.custom_fields["requester_registration"]["pending_claim"]["claim_id"] == conflict["registration"]["claim_id"]


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
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="confirmed-account",
            title="Need help",
            description="Need help",
            user_display_name="Confirmed Account",
            requester_profile={"full_name": "Conflicting Form", "email": "conflicting-form@example.test"},
            requester_account={
                "account_mode": "confirmed_binding",
                "binding_id": approved["binding"]["binding_id"],
                "person_id": approved["binding"]["person_id"],
                "display_name": "Confirmed Account",
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
    assert ticket.requester_registration_status == "admin_confirmed"
    assert ticket.custom_fields["requester_account_context"]["account_mode"] == "confirmed_binding"
    assert len(claims) == 1


@pytest.mark.asyncio
async def test_other_account_context_marks_ticket_without_registration_claim(test_engine):
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
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="other-account",
            title="Need help",
            description="Need help",
            user_display_name="Other Account",
            requester_profile={"full_name": "Other Account", "email": "other-account@example.test"},
            requester_account={
                "account_session_id": "session-other",
                "account_mode": "other_account",
                "display_name": "Other Account",
                "full_name": "Other Account",
                "login": "other-account",
                "email": "other-account@example.test",
                "created_from_other_account": True,
                "base_binding_id": approved["binding"]["binding_id"],
                "base_person_id": approved["binding"]["person_id"],
                "base_display_name": "Registered Owner",
            },
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])
        claims = (
            await session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id))
        ).scalars().all()

    assert ticket.requester_registration_status == "other_account"
    assert ticket.requester_binding_id is None
    assert ticket.asset_id == approved["binding"]["asset_id"]
    assert ticket.custom_fields["requester_account_context"]["created_from_other_account"] is True
    assert ticket.custom_fields["requester_account_context"]["active_device_binding_id"] == approved["binding"]["binding_id"]
    assert ticket.custom_fields["requester_account_context"]["warning"] == "ticket_created_from_other_account_on_registered_device"
    assert len(claims) == 1
    assert claims[0].status == "approved"


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
    assert ticket.asset_id == pending["asset"]["asset_id"]
    assert ticket.requester_registration_status in {"pending_user_confirmation", "registration_pending"}
    assert ticket.custom_fields["requester_account_context"]["account_mode"] == "registration_pending"
