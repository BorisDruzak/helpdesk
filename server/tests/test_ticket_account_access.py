from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import null, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, Ticket
from app.repos.registration_repo import RegistrationRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.context import AuthContext, AuthType
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService
from tickets.account_access_service import TicketAccountAccessService
from tickets.create_flow import create_ticket_with_side_effects
from tests.conftest import TEST_AGENT_PREFIX
from tests.test_ticket_form_packs import _ensure_default_sla_policy, _ensure_fallback_queue
from uploads.handlers import _can_upload_to_ticket, _require_agent_ticket_account_access


pytestmark = pytest.mark.db_cleanup("tickets")

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
async def test_unverified_other_account_does_not_resolve_declared_person(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)

        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=device_id,
            title="Unverified other account ticket",
            description="Unverified account must not contaminate customer history.",
            user_display_name="Claimed Other User",
            requester_account={
                "account_mode": "unverified_other_account",
                "full_name": "Claimed Other User",
                "login": "owner@example.test",
                "email": "owner@example.test",
                "reason": "legacy unverified payload",
            },
        )

        ticket = await session.get(Ticket, created["ticket_id"])
        await session.commit()

    assert ticket is not None
    assert ticket.requester_person_id is None
    assert ticket.requester_binding_id is None
    assert ticket.requester_external_ref is None
    assert ticket.requester_snapshot_json is None
    assert ticket.requester_registration_status == "unverified_other_account"
    assert ticket.requester_account_mode == "unverified_other_account"
    assert ticket.requester_account_warning == "unverified_other_account_legacy_payload"
    assert ticket.custom_fields["requester_account_context"]["verification_status"] == "unverified"
    assert ticket.custom_fields["requester_account_context"]["declared_account"]["email"] == "owner@example.test"
    assert ticket.custom_fields["requester_account_context"]["active_device_person_id"] == approved["person"]["person_id"]
    assert "ticket_context" not in ticket.custom_fields


def test_confirmed_binding_access_prefers_neutral_ref_and_falls_back_for_historical_ticket():
    access = object.__new__(TicketAccountAccessService)
    neutral_ticket = SimpleNamespace(
        device_id="device-1",
        requester_external_ref="person-neutral",
        requester_person_id="person-legacy",
        requester_binding_id=None,
        requester_account_session_id=None,
    )
    historical_ticket = SimpleNamespace(
        device_id="device-1",
        requester_external_ref=None,
        requester_snapshot_json=None,
        requester_person_id="person-legacy",
        requester_binding_id=None,
        requester_account_session_id=None,
    )
    malformed_neutral_ticket = SimpleNamespace(
        device_id="device-1",
        requester_external_ref=None,
        requester_snapshot_json={
            "person": {"external_id": "person-neutral"},
            "display_name": "Neutral owner",
        },
        requester_person_id="person-legacy",
        requester_binding_id=None,
        requester_account_session_id=None,
    )

    conflicting_legacy_session = {
        "device_id": "device-1",
        "account_mode": "confirmed_binding",
        "person_id": "person-legacy",
    }
    neutral_owner_session = {
        "device_id": "device-1",
        "account_mode": "confirmed_binding",
        "person_id": "person-neutral",
    }

    assert access._ticket_allowed(neutral_ticket, conflicting_legacy_session) is False
    assert access._ticket_allowed(neutral_ticket, neutral_owner_session) is True
    assert access._ticket_allowed(historical_ticket, conflicting_legacy_session) is True
    assert access._ticket_allowed(malformed_neutral_ticket, conflicting_legacy_session) is False

    verified_other_ticket = SimpleNamespace(
        device_id="device-1",
        requester_external_ref="person-neutral",
        requester_snapshot_json={
            "person": {"external_id": "person-neutral"},
            "display_name": "Neutral owner",
        },
        requester_person_id="person-neutral",
        requester_binding_id=None,
        requester_account_session_id="verified-other-session-1",
    )
    assert access._ticket_allowed(
        verified_other_ticket,
        {
            "device_id": "device-1",
            "account_mode": "verified_other_account",
            "person_id": "person-neutral",
            "session_id": "verified-other-session-2",
        },
    ) is False
    assert access._ticket_allowed(
        verified_other_ticket,
        {
            "device_id": "device-1",
            "account_mode": "verified_other_account",
            "person_id": "person-neutral",
            "session_id": "verified-other-session-1",
        },
    ) is True


@pytest.mark.asyncio
async def test_confirmed_binding_list_filter_uses_neutral_first_and_sql_null_fallback(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        rows = [
            Ticket(
                ticket_id=str(uuid.uuid4()),
                title="Matching neutral",
                description="matching neutral",
                status="new",
                requester_id="requester",
                requester_external_ref="person-owner",
                requester_snapshot_json={
                    "person": {"external_id": "person-owner"},
                    "display_name": "Owner",
                },
                requester_person_id="legacy-other",
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                title="Pre-migration historical",
                description="sql null fallback",
                status="new",
                requester_id="requester",
                requester_external_ref=None,
                requester_snapshot_json=null(),
                requester_person_id="person-owner",
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                title="Malformed neutral",
                description="must not use legacy fallback",
                status="new",
                requester_id="requester",
                requester_external_ref=None,
                requester_snapshot_json={
                    "person": {"external_id": "other-owner"},
                    "display_name": "Other owner",
                },
                requester_person_id="person-owner",
            ),
        ]
        session.add_all(rows)
        await session.flush()

        stmt = TicketAccountAccessService(session).apply_ticket_list_filter(
            select(Ticket),
            account_session={
                "account_mode": "confirmed_binding",
                "person_id": "person-owner",
            },
        )
        visible_ids = set((await session.execute(stmt)).scalars().all())

    assert rows[0] in visible_ids
    assert rows[1] in visible_ids
    assert rows[2] not in visible_ids


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
            "form_payload": {
                "room": "214",
                "impact_scope": "department",
                "work_continuity": "partial_work",
            },
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
async def test_agent_create_rejects_registration_pending_session(test_client, test_engine):
    await _ensure_fallback_queue(test_engine)
    await _ensure_default_sla_policy(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        claim = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending-create@example.test",
            display_name="Pending Create",
            profile={"full_name": "Pending Create", "email": "pending-create@example.test"},
        )
        account = await AccountSessionService(session).create_registration_pending_session(
            device_id=device_id,
            claim_id=claim["registration"]["claim_id"],
        )
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        headers=_agent_headers(device_id),
        json={
            "title": "Pending registration create attempt",
            "description": "Pending registration cannot open the normal ticket workspace.",
            "user_display_name": "Pending Create",
            "requester_account": {
                "session_id": account["session"]["session_id"],
                "session_token": account["session_token"],
            },
        },
    )

    assert response.status == 403, await response.text()
    payload = await response.json()
    assert payload["error_code"] == "ACCOUNT_ACCESS_DENIED"


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
async def test_web_user_upload_access_uses_requester_person_ownership(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id)
        await RegistrationRepo(session).create_or_update_person_identity(
            person_id=approved["person"]["person_id"],
            provider="ui_login",
            identifier="owner@example.test",
            verified=True,
            source="test",
        )
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id="legacy-requester-id",
            title="Person-owned upload ticket",
            description="Upload access must follow requester ownership, not only requester_id",
            user_display_name="Registered Owner",
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
        )
        ticket = await session.get(Ticket, created["ticket_id"])
        assert ticket is not None
        owner_context = AuthContext(
            actor_id="owner@example.test",
            actor_role="user",
            auth_type=AuthType.UI_TOKEN,
            token="owner-ui-token",
        )
        other_context = AuthContext(
            actor_id="other@example.test",
            actor_role="user",
            auth_type=AuthType.UI_TOKEN,
            token="other-ui-token",
        )
        owner_allowed = await _can_upload_to_ticket(session, owner_context, ticket)
        other_allowed = await _can_upload_to_ticket(session, other_context, ticket)
        await session.commit()

    assert owner_allowed is True
    assert other_allowed is False


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
