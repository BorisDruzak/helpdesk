"""Consent decisions must retain a deliverable operation after transport failure."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import EndpointOperationLink, Operation, Ticket, UserConsentRequest
from domain_ports.endpoint import EndpointUnavailable
from tests.conftest import TEST_UI_USER_PREFIX
from tests.test_endpoint_operation_persistence import _IdempotentProvider, _setup, _worker
from tests.test_requester_workspace_api import _headers, _person_for_login

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_waiting_consent_is_not_dispatched_then_approval_survives_transport_failure(test_client, test_engine):
    login = f"consent-delivery-{uuid.uuid4().hex}@example.test"
    maker, ticket_id, operation_id, actor, facade, request, now = await _setup(test_engine)
    await facade.create(actor=actor, request=request)
    consent_id = str(uuid.uuid4())
    async with maker() as session:
        person = await _person_for_login(session, login=login)
        ticket = await session.get(Ticket, ticket_id)
        ticket.requester_person_id = person.person_id
        operation = await session.get(Operation, operation_id)
        operation.status = "waiting_consent"
        session.add(UserConsentRequest(consent_id=consent_id, subject_type="operation",
            subject_id=operation_id, ticket_id=ticket_id, requester_person_id=person.person_id,
            title="Synthetic pending Endpoint consent", status="pending",
            expires_at=now + timedelta(hours=1)))
        await session.commit()

    class Provider(_IdempotentProvider):
        unavailable = True

        async def create_operation(self, device, request, *, idempotency_key):
            if self.unavailable:
                self.calls.append((device, request, idempotency_key))
                return EndpointUnavailable()
            return await super().create_operation(device, request, idempotency_key=idempotency_key)

    provider = Provider(now)
    for held_status in ("waiting_consent", "denied", "unknown_future_state"):
        async with maker() as session:
            (await session.get(Operation, operation_id)).status = held_status
            await session.commit()
        assert await _worker(maker, provider, now, "before-consent").reconcile_once(limit=1) == 0
    assert provider.calls == []
    async with maker() as session:
        (await session.get(Operation, operation_id)).status = "waiting_consent"
        await session.commit()

    response = await test_client.post(f"/api/web/requester/consents/{consent_id}/approve",
        headers=_headers(TEST_UI_USER_PREFIX + login), json={})
    assert response.status == 200
    assert await _worker(maker, provider, now, "failed-transport").reconcile_once(limit=1) == 1
    async with maker() as session:
        consent = await session.get(UserConsentRequest, consent_id)
        operation = await session.get(Operation, operation_id)
        link = (await session.execute(select(EndpointOperationLink).where(
            EndpointOperationLink.operation_id == operation_id))).scalar_one()
        assert consent.status == "approved" and operation.status == "queued"
        assert link.endpoint_operation_ref is None and link.remote_status == "create_pending"
        assert link.lease_owner is None and link.next_attempt_at > now
        next_attempt = link.next_attempt_at
        persisted_key = link.create_idempotency_key

    provider.unavailable = False
    assert await _worker(maker, provider, next_attempt, "restarted-after-outage").reconcile_once(limit=1) == 1
    assert [call[2] for call in provider.calls] == [persisted_key, persisted_key]
    assert len(provider.operations) == 1
    async with maker() as session:
        assert (await session.get(UserConsentRequest, consent_id)).status == "approved"
        link = (await session.execute(select(EndpointOperationLink).where(
            EndpointOperationLink.operation_id == operation_id))).scalar_one()
        assert link.endpoint_operation_ref == provider.operations[persisted_key].operation.external_id


@pytest.mark.asyncio
async def test_legacy_operation_without_delivery_link_cannot_be_approved(test_client, test_engine):
    login = f"orphan-consent-{uuid.uuid4().hex}@example.test"
    ticket_id, operation_id, consent_id = (str(uuid.uuid4()) for _ in range(3))
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        person = await _person_for_login(session, login=login)
        session.add(Ticket(ticket_id=ticket_id, device_id=device_id, title="Historical orphan consent", description="Synthetic historical regression", status="in_progress",
            requester_person_id=person.person_id))
        await session.flush()
        session.add(Operation(operation_id=operation_id, ticket_id=ticket_id, device_id=device_id, kind="tool_call",
            actor_role="support", trace_id=str(uuid.uuid4()), status="waiting_consent", queued_at=now))
        session.add(UserConsentRequest(consent_id=consent_id, subject_type="operation", subject_id=operation_id,
            ticket_id=ticket_id, requester_person_id=person.person_id, title="Legacy consent without delivery",
            status="pending", expires_at=now + timedelta(hours=1)))
        await session.commit()
    response = await test_client.post(f"/api/web/requester/consents/{consent_id}/approve",
        headers=_headers(TEST_UI_USER_PREFIX + login), json={})
    assert response.status == 409
    assert (await response.json())["error_code"] == "OPERATION_DELIVERY_UNAVAILABLE"
    async with maker() as session:
        assert (await session.get(UserConsentRequest, consent_id)).status == "pending"
        assert (await session.get(Operation, operation_id)).status == "waiting_consent"
