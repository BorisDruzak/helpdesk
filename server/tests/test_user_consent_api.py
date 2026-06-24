from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ConsentDecision, Device, DeviceOutbox, Operation, RegistryPerson, RegistryPersonIdentity, Ticket, TicketEvent, UserConsentRequest
from app.repos.operations_repo import OperationsRepo
from app.repos.user_consent_repo import UserConsentRepo
from consent.service import UserConsentService
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService
from remote_assist.service import RemoteAssistService
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_USER_PREFIX
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects

pytestmark = pytest.mark.db_cleanup("full")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


REMOTE_ASSIST_REQUESTER_FORBIDDEN_KEYS = {
    "ice_servers",
    "urls",
    "username",
    "credential",
    "agent_token",
    "viewer_token",
    "signaling_token",
    "sdp",
    "offer",
    "answer",
    "candidate",
    "session_token",
    "authorization",
    "cookie",
}


def _assert_no_forbidden_remote_assist_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert str(key).lower() not in REMOTE_ASSIST_REQUESTER_FORBIDDEN_KEYS
            _assert_no_forbidden_remote_assist_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_remote_assist_keys(item)


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
async def test_create_request_returns_existing_pending(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id="person-duplicate",
                display_name="Duplicate Consent Person",
                full_name="Duplicate Consent Person",
                email="duplicate-consent@example.test",
                source="test",
                status="active",
            )
        )
        await session.flush()
        service = UserConsentService(session)
        first = await service.create_request(
            subject_type="operation",
            subject_id="duplicate-subject",
            requester_person_id="person-duplicate",
            requested_by_actor_id="support-test",
            requested_by_role="support",
            risk_level="safe_read",
            title="First consent",
        )
        second = await service.create_request(
            subject_type="operation",
            subject_id="duplicate-subject",
            requester_person_id="person-duplicate",
            requested_by_actor_id="support-test",
            requested_by_role="support",
            risk_level="safe_read",
            title="Second consent",
        )
        await session.commit()

    assert second.consent_id == first.consent_id

    async with session_maker() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(UserConsentRequest)
            .where(UserConsentRequest.subject_type == "operation")
            .where(UserConsentRequest.subject_id == "duplicate-subject")
            .where(UserConsentRequest.status == "pending")
        )
    assert count == 1


@pytest.mark.asyncio
async def test_create_request_handles_pending_subject_integrity_race(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    subject_id = "race-subject"
    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id="race-person",
                display_name="Race Consent Person",
                full_name="Race Consent Person",
                email="race-consent@example.test",
                source="test",
                status="active",
            )
        )
        await session.flush()
        existing = await UserConsentRepo(session).create(
            consent_id=str(uuid.uuid4()),
            subject_type="operation",
            subject_id=subject_id,
            requester_person_id="race-person",
            requested_by_actor_id="support-test",
            requested_by_role="support",
            risk_level="safe_read",
            title="Existing raced consent",
            status="pending",
        )
        await session.commit()
        existing_id = existing.consent_id

    real_get_pending = UserConsentRepo.get_pending_by_subject
    calls = {"get": 0}

    async def racing_get_pending(self, subject_type, subject_id_arg):
        calls["get"] += 1
        if calls["get"] == 1:
            return None
        return await real_get_pending(self, subject_type, subject_id_arg)

    async def raise_unique_violation(self, **_kwargs):
        raise IntegrityError(
            "insert into user_consent_requests",
            {},
            Exception("duplicate key value violates unique constraint ux_user_consent_requests_pending_subject"),
        )

    monkeypatch.setattr(UserConsentRepo, "get_pending_by_subject", racing_get_pending)
    monkeypatch.setattr(UserConsentRepo, "create", raise_unique_violation)

    async with session_maker() as session:
        consent = await UserConsentService(session).create_request(
            subject_type="operation",
            subject_id=subject_id,
            requester_person_id="race-person",
            requested_by_actor_id="support-test",
            requested_by_role="support",
            risk_level="safe_read",
            title="Raced consent",
        )

    assert consent.consent_id == existing_id


@pytest.mark.asyncio
async def test_create_request_reraises_unrelated_integrity_error(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    subject_id = "race-subject-other-constraint"
    async with session_maker() as session:
        session.add(
            RegistryPerson(
                person_id="race-person-other-constraint",
                display_name="Race Consent Other Constraint",
                full_name="Race Consent Other Constraint",
                email="race-consent-other@example.test",
                source="test",
                status="active",
            )
        )
        await session.flush()
        await UserConsentRepo(session).create(
            consent_id=str(uuid.uuid4()),
            subject_type="operation",
            subject_id=subject_id,
            requester_person_id="race-person-other-constraint",
            requested_by_actor_id="support-test",
            requested_by_role="support",
            risk_level="safe_read",
            title="Existing raced consent",
            status="pending",
        )
        await session.commit()

    real_get_pending = UserConsentRepo.get_pending_by_subject
    calls = {"get": 0}

    async def racing_get_pending(self, subject_type, subject_id_arg):
        calls["get"] += 1
        if calls["get"] == 1:
            return None
        return await real_get_pending(self, subject_type, subject_id_arg)

    async def raise_other_unique_violation(self, **_kwargs):
        raise IntegrityError(
            "insert into user_consent_requests",
            {},
            Exception("duplicate key value violates unique constraint some_other_constraint"),
        )

    monkeypatch.setattr(UserConsentRepo, "get_pending_by_subject", racing_get_pending)
    monkeypatch.setattr(UserConsentRepo, "create", raise_other_unique_violation)

    async with session_maker() as session:
        with pytest.raises(IntegrityError, match="some_other_constraint"):
            await UserConsentService(session).create_request(
                subject_type="operation",
                subject_id=subject_id,
                requester_person_id="race-person-other-constraint",
                requested_by_actor_id="support-test",
                requested_by_role="support",
                risk_level="safe_read",
                title="Raced consent",
            )


@pytest.mark.asyncio
async def test_pending_subject_partial_unique_index_is_present(test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        rows = (
            await session.execute(
                text(
                    """
                    select indexname, indexdef
                    from pg_indexes
                    where tablename = 'user_consent_requests'
                      and indexname = 'ux_user_consent_requests_pending_subject'
                    """
                )
            )
        ).mappings().all()

    assert rows
    assert "WHERE ((status)::text = 'pending'::text)" in rows[0]["indexdef"]


@pytest.mark.asyncio
async def test_requester_remote_assist_consent_payloads_hide_technical_secrets(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    login = "remote-assist-secret-owner@example.test"
    async with session_maker() as session:
        seeded = await _seed_operation_consent(session, login=login)
        ticket = await session.get(Ticket, seeded["ticket_id"])
        ticket.requester_id = login
        ticket.requester_person_id = seeded["person_id"]
        ticket.requester_binding_id = seeded["binding_id"]
        ticket.requester_account_session_id = seeded["session_id"]
        await session.flush()
        state = type("RemoteAssistTestState", (), {"is_agent_online": lambda self, _device_id: True})()
        remote_session = await RemoteAssistService(session).request_session(
            state=state,
            ticket_id=seeded["ticket_id"],
            device_id=seeded["device_id"],
            operator_id="support-test",
            requester_id=login,
            mode="view_only",
            reason="Requester-safe Remote Assist consent",
            duration_minutes=5,
        )
        await session.commit()
        remote_session_id = remote_session.id

    test_client.app["state"].connected_agents[seeded["device_id"]] = {"ws": None, "metadata": {}}
    headers = _headers(f"{TEST_UI_USER_PREFIX}{login}")
    listing = await test_client.get("/api/web/requester/consents", headers=headers)
    listing_payload = await listing.json()
    assert listing.status == 200, listing_payload
    remote_items = [
        item for item in listing_payload["data"]["consents"]
        if item["subject_type"] == "remote_assist" and item["subject_id"] == remote_session_id
    ]
    assert len(remote_items) == 1
    _assert_no_forbidden_remote_assist_keys(remote_items[0])
    assert remote_items[0]["requested_action_payload_redacted"]["mode"] == "view_only"
    assert remote_items[0]["requested_action_payload_redacted"]["duration_minutes"] == 5

    detail = await test_client.get(f"/api/web/requester/consents/{remote_items[0]['consent_id']}", headers=headers)
    detail_payload = await detail.json()
    assert detail.status == 200, detail_payload
    _assert_no_forbidden_remote_assist_keys(detail_payload)

    approved = await test_client.post(
        f"/api/web/requester/consents/{remote_items[0]['consent_id']}/approve",
        headers=headers,
        json={"reason": "ok"},
    )
    approved_payload = await approved.json()
    assert approved.status == 200, approved_payload
    _assert_no_forbidden_remote_assist_keys(approved_payload)


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
        started_events = await session.scalar(
            select(func.count())
            .select_from(TicketEvent)
            .where(
                TicketEvent.ticket_id == seeded["ticket_id"],
                TicketEvent.event_type == "tool_call_started",
                TicketEvent.operation_id == seeded["operation_id"],
            )
        )
        decided_events = await session.scalar(
            select(func.count())
            .select_from(TicketEvent)
            .where(TicketEvent.ticket_id == seeded["ticket_id"], TicketEvent.event_type == "user_consent_decided")
        )
    assert old_decisions == 1
    assert outbox_count == 1
    assert started_events == 1
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


@pytest.mark.asyncio
async def test_requester_decision_after_operation_no_longer_actionable_cancels_consent_without_side_effects(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    scenarios = [
        {
            "decision": "approve",
            "login": "consent-cancel-race@example.test",
            "operation_status": "cancel_requested",
        },
        {
            "decision": "deny",
            "login": "consent-timeout-race@example.test",
            "operation_status": "timed_out",
        },
    ]

    for scenario in scenarios:
        async with session_maker() as session:
            seeded = await _seed_operation_consent(session, login=scenario["login"])
            cancel_operation_id = str(uuid.uuid4()) if scenario["operation_status"] == "cancel_requested" else None
            update_kwargs = {
                "operation_id": seeded["operation_id"],
                "new_status": scenario["operation_status"],
                "expected_statuses": ["waiting_consent"],
            }
            if scenario["operation_status"] == "cancel_requested":
                update_kwargs.update(
                    status_before_cancel="waiting_consent",
                    active_cancel_operation_id=cancel_operation_id,
                    cancel_reason="cancel won before requester consent",
                )
            else:
                update_kwargs.update(
                    timestamp_field="finished_at",
                    error_code="TIMEOUT",
                    error_message="consent wait timed out",
                    clear_deadline=True,
                )
            changed = await OperationsRepo(session).update_status(**update_kwargs)
            assert changed is True
            await session.commit()

        response = await test_client.post(
            f"/api/web/requester/consents/{seeded['consent_id']}/{scenario['decision']}",
            headers=_headers(f"{TEST_UI_USER_PREFIX}{scenario['login']}"),
            json={"reason": "too late"},
        )
        payload = await response.json()
        assert response.status == 200, payload
        assert payload["data"]["consent"]["status"] == "canceled"

        async with session_maker() as session:
            operation = await session.get(Operation, seeded["operation_id"])
            decision_count = await session.scalar(
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
            canceled_events = await session.scalar(
                select(func.count())
                .select_from(TicketEvent)
                .where(TicketEvent.ticket_id == seeded["ticket_id"], TicketEvent.event_type == "user_consent_canceled")
            )
        assert operation.status == scenario["operation_status"]
        if cancel_operation_id is not None:
            assert operation.active_cancel_operation_id == cancel_operation_id
        else:
            assert operation.error_code == "TIMEOUT"
        assert decision_count == 0
        assert outbox_count == 0
        assert decided_events == 0
        assert canceled_events == 1
