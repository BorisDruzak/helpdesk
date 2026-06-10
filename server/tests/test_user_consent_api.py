from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ConsentDecision, Device, DeviceOutbox, Operation, RegistryPerson, RegistryPersonIdentity, TicketEvent
from app.repos.operations_repo import OperationsRepo
from consent.service import UserConsentService
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_USER_PREFIX
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.61",
        hostname="consent-device",
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


async def _seed_operation_consent(session, *, login: str, expires_delta: timedelta = timedelta(minutes=30)) -> dict:
    device_id = str(uuid.uuid4())
    session.add(_device(device_id))
    registration = RegistrationService(session)
    claim = await registration.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=login,
        display_name=f"Requester {login}",
        profile={"full_name": f"Requester {login}", "email": login, "login": login, "user_confirmed": True},
    )
    approved = await registration.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
    account = await AccountSessionService(session).create_confirmed_binding_session(
        device_id=device_id,
        binding_id=approved["binding"]["binding_id"],
    )
    ticket_payload = await create_ticket_with_side_effects(
        session,
        device_id=device_id,
        requester_id=login,
        title="Consent API ticket",
        description="Consent API ticket",
        user_display_name=f"Requester {login}",
        requester_profile={"full_name": f"Requester {login}", "email": login},
        normalized_priority=build_default_priority_payload({}),
        requester_account={
            "account_mode": "confirmed_binding",
            "person_id": approved["person"]["person_id"],
            "binding_id": approved["binding"]["binding_id"],
            "session_id": account["session"]["session_id"],
            "validation": "test",
        },
        include_public_access=True,
    )
    operation_id = str(uuid.uuid4())
    await OperationsRepo(session).create_operation(
        operation_id=operation_id,
        device_id=device_id,
        ticket_id=ticket_payload["ticket_id"],
        kind="tool_call",
        tool_name="observer_canary.consent_probe",
        actor_role="support",
        trace_id=str(uuid.uuid4()),
        status="waiting_consent",
    )
    consent = await UserConsentService(session).create_request(
        subject_type="operation",
        subject_id=operation_id,
        ticket_id=ticket_payload["ticket_id"],
        device_id=device_id,
        requester_person_id=approved["person"]["person_id"],
        requester_binding_id=approved["binding"]["binding_id"],
        requester_account_session_id=account["session"]["session_id"],
        requested_by_actor_id="support-test",
        requested_by_role="support",
        risk_level="sensitive_read",
        title="Run diagnostic",
        description="Run a diagnostic that requires user consent.",
        requested_action_payload_redacted={"tool_name": "observer_canary.consent_probe"},
        expires_at=datetime.now(timezone.utc) + expires_delta,
    )
    await session.commit()
    return {
        "device_id": device_id,
        "login": login,
        "person_id": approved["person"]["person_id"],
        "binding_id": approved["binding"]["binding_id"],
        "session_id": account["session"]["session_id"],
        "session_token": account["session_token"],
        "ticket_id": ticket_payload["ticket_id"],
        "operation_id": operation_id,
        "consent_id": consent.consent_id,
    }


@pytest.mark.asyncio
async def test_requester_approve_consent_queues_operation_idempotently(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "consent-owner@example.test"
    async with session_maker() as session:
        seeded = await _seed_operation_consent(session, login=login)

    owner_headers = _headers(f"{TEST_UI_USER_PREFIX}{login}")
    listing = await test_client.get("/api/web/requester/consents", headers=owner_headers)
    listing_payload = await listing.json()
    assert listing.status == 200, listing_payload
    assert seeded["consent_id"] in {item["consent_id"] for item in listing_payload["data"]["consents"]}

    approved = await test_client.post(
        f"/api/web/requester/consents/{seeded['consent_id']}/approve",
        headers=owner_headers,
        json={"reason": "ok"},
    )
    approved_payload = await approved.json()
    assert approved.status == 200, approved_payload
    assert approved_payload["data"]["consent"]["status"] == "approved"
    assert approved_payload["data"]["consent"]["decided_from_surface"] == "browser"

    repeated = await test_client.post(
        f"/api/web/requester/consents/{seeded['consent_id']}/deny",
        headers=owner_headers,
        json={"reason": "too late"},
    )
    repeated_payload = await repeated.json()
    assert repeated.status == 200, repeated_payload
    assert repeated_payload["data"]["consent"]["status"] == "approved"

    async with session_maker() as session:
        operation = await session.get(Operation, seeded["operation_id"])
        assert operation.status == "queued"
        old_decisions = await session.scalar(
            select(func.count()).select_from(ConsentDecision).where(ConsentDecision.operation_id == seeded["operation_id"])
        )
        outbox_count = await session.scalar(
            select(func.count()).select_from(DeviceOutbox).where(DeviceOutbox.operation_id == seeded["operation_id"])
        )
        decided_events = await session.scalar(
            select(func.count())
            .select_from(TicketEvent)
            .where(TicketEvent.ticket_id == seeded["ticket_id"], TicketEvent.event_type == "user_consent_decided")
        )
    assert old_decisions == 1
    assert outbox_count == 1
    assert decided_events == 1


@pytest.mark.asyncio
async def test_foreign_requester_cannot_approve_user_consent(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owner_login = "consent-owner-foreign@example.test"
    foreign_login = "consent-foreign@example.test"
    async with session_maker() as session:
        seeded = await _seed_operation_consent(session, login=owner_login)
        person = RegistryPerson(
            person_id=str(uuid.uuid4()),
            display_name="Foreign Consent User",
            full_name="Foreign Consent User",
            email=foreign_login,
            source="test",
            status="active",
        )
        session.add(person)
        session.add(
            RegistryPersonIdentity(
                person_id=person.person_id,
                provider="ui_login",
                identifier=foreign_login,
                normalized_identifier=foreign_login,
                verified=True,
                source="test",
            )
        )
        await session.commit()

    response = await test_client.post(
        f"/api/web/requester/consents/{seeded['consent_id']}/approve",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{foreign_login}"),
        json={"reason": "not mine"},
    )
    payload = await response.json()
    assert response.status == 404, payload

    async with session_maker() as session:
        operation = await session.get(Operation, seeded["operation_id"])
        assert operation.status == "waiting_consent"


@pytest.mark.asyncio
async def test_agent_consent_decision_requires_valid_requester_account_session(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "consent-agent-owner@example.test"
    async with session_maker() as session:
        seeded = await _seed_operation_consent(session, login=login)

    agent_headers = _headers(f"{TEST_AGENT_PREFIX}{seeded['device_id']}")
    missing = await test_client.get("/api/registry/agent/consents", headers=agent_headers)
    missing_payload = await missing.json()
    assert missing.status == 403, missing_payload
    assert missing_payload["error_code"] == "ACCOUNT_SESSION_REQUIRED"

    session_headers = {
        **agent_headers,
        "X-Account-Session-Id": seeded["session_id"],
        "X-Account-Session-Token": seeded["session_token"],
    }
    listing = await test_client.get("/api/registry/agent/consents", headers=session_headers)
    listing_payload = await listing.json()
    assert listing.status == 200, listing_payload
    assert seeded["consent_id"] in {item["consent_id"] for item in listing_payload["data"]["consents"]}

    approved = await test_client.post(
        f"/api/registry/agent/consents/{seeded['consent_id']}/approve",
        headers=session_headers,
        json={"reason": "local user approved"},
    )
    approved_payload = await approved.json()
    assert approved.status == 200, approved_payload
    assert approved_payload["data"]["consent"]["status"] == "approved"
    assert approved_payload["data"]["consent"]["decided_from_surface"] == "agent_gui"

    browser_detail = await test_client.get(
        f"/api/web/requester/consents/{seeded['consent_id']}",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    browser_payload = await browser_detail.json()
    assert browser_detail.status == 200, browser_payload
    assert browser_payload["data"]["consent"]["status"] == "approved"


@pytest.mark.asyncio
async def test_expired_consent_does_not_start_operation(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "consent-expired@example.test"
    async with session_maker() as session:
        seeded = await _seed_operation_consent(session, login=login, expires_delta=timedelta(seconds=-1))

    response = await test_client.post(
        f"/api/web/requester/consents/{seeded['consent_id']}/approve",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={"reason": "late"},
    )
    payload = await response.json()
    assert response.status == 200, payload
    assert payload["data"]["consent"]["status"] == "expired"

    async with session_maker() as session:
        operation = await session.get(Operation, seeded["operation_id"])
        outbox_count = await session.scalar(
            select(func.count()).select_from(DeviceOutbox).where(DeviceOutbox.operation_id == seeded["operation_id"])
        )
    assert operation.status == "waiting_consent"
    assert outbox_count == 0
