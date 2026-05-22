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
        await service.approve_claim(first["registration"]["claim_id"], reviewed_by="admin")
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="second-ticket",
            title="Need help",
            description="Need help",
            user_display_name="Second Ticket",
            requester_profile={"full_name": "Second Ticket", "email": "second-ticket@example.test", "user_confirmed": True},
        )
        await session.commit()

    async with session_maker() as session:
        ticket = await session.get(Ticket, created["ticket_id"])

    assert ticket.requester_person_id is None
    assert ticket.requester_binding_id is None
    assert ticket.requester_registration_status == "conflict"
    assert ticket.custom_fields["requester_registration"]["status"] == "conflict"
