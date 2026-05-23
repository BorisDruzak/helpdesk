from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, Ticket
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.context import AuthContext, AuthType
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService
from tickets.account_access_service import TicketAccountAccessService
from tickets.create_flow import create_ticket_with_side_effects
from tests.conftest import TEST_AGENT_PREFIX
from tests.test_ticket_form_packs import _ensure_default_sla_policy, _ensure_fallback_queue
from uploads.handlers import _require_agent_ticket_account_access


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


def _agent_headers(device_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_AGENT_PREFIX}{device_id}"}


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
async def test_agent_create_preview_requires_account_session(test_client):
    device_id = str(uuid.uuid4())
    response = await test_client.post(
        "/api/tickets/create/preview",
        headers=_agent_headers(device_id),
        json={"form_key": "agent_test_form"},
    )
    payload = await response.json()

    assert response.status == 403
    assert payload["error_code"] == "ACCOUNT_SESSION_REQUIRED"


@pytest.mark.asyncio
async def test_agent_create_preview_accepts_valid_account_session(test_client, test_engine):
    await _ensure_fallback_queue(test_engine)
    await _ensure_default_sla_policy(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        account = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create/preview",
        headers=_agent_headers(device_id),
        json={
            "request_template_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {"room": "214"},
            "requester_account": {
                "session_id": account["session"]["session_id"],
                "session_token": account["session_token"],
            },
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["preview"]["request_template_key"] == "printer"


@pytest.mark.asyncio
async def test_confirmed_owner_policy_sees_historical_owner_ticket_not_other_account_ticket(test_engine):
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
        owner_validation = await account_service.validate_session(
            device_id=device_id,
            session_id=owner_session["session"]["session_id"],
            session_token=owner_session["session_token"],
        )
        historical_ticket = await TicketEventsRepo(session).create_ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=device_id,
            title="Historical owner ticket",
            description="Historical owner ticket",
            requester_id=device_id,
            requester_person_id=approved["binding"]["person_id"],
            requester_binding_id=approved["binding"]["binding_id"],
            requester_registration_status="admin_confirmed",
        )
        request = await account_service.create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other.user", "reason": "temporary"},
        )
        other_session = await account_service.approve_login_request(request["request_id"], reviewed_by="admin")
        other_ticket = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=device_id,
            title="Other account ticket",
            description="Other account ticket",
            user_display_name="Other User",
            requester_account={
                "session_id": other_session["session"]["session_id"],
                "session_token": other_session["session_token"],
            },
        )
        access = TicketAccountAccessService(session)
        other_row = await session.get(Ticket, other_ticket["ticket_id"])
        can_view_historical = await access.can_view_ticket(ticket=historical_ticket, account_session=owner_validation["session"])
        can_view_other = await access.can_view_ticket(ticket=other_row, account_session=owner_validation["session"])
        listed = await TicketEventsRepo(session).list_tickets(
            filters={"device_id": device_id, "account_session_access": owner_validation["session"]}
        )
        await session.commit()

    listed_ids = {ticket.ticket_id for ticket in listed}
    assert can_view_historical is True
    assert can_view_other is False
    assert historical_ticket.ticket_id in listed_ids
    assert other_ticket["ticket_id"] not in listed_ids


@pytest.mark.asyncio
async def test_registration_pending_session_visibility_is_scoped(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        claim = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending@example.test",
            display_name="Pending User",
            profile={"full_name": "Pending User", "email": "pending@example.test"},
        )
        account_service = AccountSessionService(session)
        pending_session = await account_service.create_registration_pending_session(
            device_id=device_id,
            claim_id=claim["registration"]["claim_id"],
        )
        pending_ticket = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=device_id,
            title="Pending registration ticket",
            description="Pending registration ticket",
            user_display_name="Pending User",
            requester_account={
                "session_id": pending_session["session"]["session_id"],
                "session_token": pending_session["session_token"],
            },
        )
        unrelated_ticket = await TicketEventsRepo(session).create_ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=device_id,
            title="Unrelated ticket",
            description="Unrelated ticket",
            requester_id=device_id,
            requester_registration_status="admin_confirmed",
        )
        validation = await account_service.validate_session(
            device_id=device_id,
            session_id=pending_session["session"]["session_id"],
            session_token=pending_session["session_token"],
        )
        access = TicketAccountAccessService(session)
        pending_row = await session.get(Ticket, pending_ticket["ticket_id"])
        can_view_pending = await access.can_view_ticket(ticket=pending_row, account_session=validation["session"])
        can_view_unrelated = await access.can_view_ticket(ticket=unrelated_ticket, account_session=validation["session"])
        listed = await TicketEventsRepo(session).list_tickets(
            filters={"device_id": device_id, "account_session_access": validation["session"]}
        )
        await session.commit()

    assert can_view_pending is True
    assert can_view_unrelated is False
    assert [ticket.ticket_id for ticket in listed] == [pending_ticket["ticket_id"]]


@pytest.mark.asyncio
async def test_agent_artifact_download_access_requires_valid_account_session(test_engine):
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
            requested_account={"full_name": "Other User", "login": "other.user", "reason": "temporary"},
        )
        other_session = await account_service.approve_login_request(request["request_id"], reviewed_by="admin")
        auth_context = AuthContext(actor_id=device_id, actor_role="agent", auth_type=AuthType.AGENT_TOKEN, token="test")
        valid_request = SimpleNamespace(
            query={},
            headers={
                "X-Account-Session-Id": owner_session["session"]["session_id"],
                "X-Account-Session-Token": owner_session["session_token"],
            },
        )
        other_request = SimpleNamespace(
            query={},
            headers={
                "X-Account-Session-Id": other_session["session"]["session_id"],
                "X-Account-Session-Token": other_session["session_token"],
            },
        )
        missing_request = SimpleNamespace(query={}, headers={})
        valid = await _require_agent_ticket_account_access(
            session=session,
            request=valid_request,
            auth_context=auth_context,
            ticket_id=owner_ticket["ticket_id"],
            write=False,
        )
        missing = await _require_agent_ticket_account_access(
            session=session,
            request=missing_request,
            auth_context=auth_context,
            ticket_id=owner_ticket["ticket_id"],
            write=False,
        )
        wrong = await _require_agent_ticket_account_access(
            session=session,
            request=other_request,
            auth_context=auth_context,
            ticket_id=owner_ticket["ticket_id"],
            write=False,
        )
        await account_service.revoke_session(session_id=owner_session["session"]["session_id"], revoked_by="admin")
        revoked = await _require_agent_ticket_account_access(
            session=session,
            request=valid_request,
            auth_context=auth_context,
            ticket_id=owner_ticket["ticket_id"],
            write=False,
        )
        await session.commit()

    assert valid is None
    assert missing is not None and missing.status == 403
    assert wrong is not None and wrong.status == 403
    assert revoked is not None and revoked.status == 403


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
