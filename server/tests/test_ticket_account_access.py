from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, Ticket
from app.repos.ticket_events_repo import TicketEventsRepo
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService
from tickets.account_access_service import TicketAccountAccessService
from tickets.create_flow import create_ticket_with_side_effects


def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="ticket-account-access",
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


async def _approved_binding(session, device_id: str) -> dict:
    service = RegistrationService(session)
    claim = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id="owner@example.test",
        display_name="Registered Owner",
        profile={"full_name": "Registered Owner", "email": "owner@example.test", "user_confirmed": True},
    )
    return await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")


@pytest.mark.asyncio
async def test_verified_other_account_can_only_view_own_session_ticket(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        account_service = AccountSessionService(session)
        owner_session = await account_service.create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        owner_ticket = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=device_id,
            title="Owner ticket",
            description="Owner ticket",
            user_display_name="Registered Owner",
            requester_account={
                "session_id": owner_session["session"]["session_id"],
                "session_token": owner_session["session_token"],
            },
        )
        request = await account_service.create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other", "reason": "temporary"},
        )
        other_session = await account_service.approve_login_request(request["request_id"], reviewed_by="admin")
        other_ticket = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=device_id,
            title="Other ticket",
            description="Other ticket",
            user_display_name="Other User",
            requester_account={
                "session_id": other_session["session"]["session_id"],
                "session_token": other_session["session_token"],
            },
        )
        validation = await account_service.validate_session(
            device_id=device_id,
            session_id=other_session["session"]["session_id"],
            session_token=other_session["session_token"],
        )
        access = TicketAccountAccessService(session)
        owner_row = await session.get(Ticket, owner_ticket["ticket_id"])
        other_row = await session.get(Ticket, other_ticket["ticket_id"])
        can_owner = await access.can_view_ticket(ticket=owner_row, account_session=validation["session"])
        can_other = await access.can_view_ticket(ticket=other_row, account_session=validation["session"])
        listed = await TicketEventsRepo(session).list_tickets(
            filters={"device_id": device_id, "account_session_access": validation["session"]}
        )
        await session.commit()

    assert can_owner is False
    assert can_other is True
    assert [ticket.ticket_id for ticket in listed] == [other_ticket["ticket_id"]]


@pytest.mark.asyncio
async def test_revoked_session_cannot_validate_for_ticket_access(test_engine):
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
        await account_service.revoke_session(session_id=created["session"]["session_id"], revoked_by="admin")
        validation = await TicketAccountAccessService(session).validate_agent_account_session(
            device_id=device_id,
            requester_account={"session_id": created["session"]["session_id"], "session_token": created["session_token"]},
        )
        await session.commit()

    assert validation["valid"] is False
    assert validation["error_code"] == "ACCOUNT_SESSION_REVOKED"
