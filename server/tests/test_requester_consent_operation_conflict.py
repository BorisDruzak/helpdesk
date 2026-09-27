"""A real operation CAS conflict must roll back the browser consent decision."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Operation, Ticket, TicketEvent, UserConsentRequest
from app.repos.operations_repo import OperationsRepo
from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo
from tests.conftest import TEST_UI_USER_PREFIX
from tests.test_requester_workspace_api import _headers, _person_for_login

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
@pytest.mark.parametrize("decision,action", [("approved", "approve"), ("denied", "deny")])
async def test_browser_consent_conflict_rolls_back_decision_and_allows_retry(test_client, test_engine, monkeypatch, decision, action):
    marker = uuid.uuid4().hex
    login = f"consent-race-{marker}@example.test"
    ticket_id, operation_id, consent_id = (str(uuid.uuid4()) for _ in range(3))
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        person = await _person_for_login(session, login=login)
        session.add(Ticket(ticket_id=ticket_id, device_id=device_id, title="Consent race", description="Synthetic regression", status="in_progress", requester_person_id=person.person_id))
        await session.flush()
        session.add(Operation(operation_id=operation_id, ticket_id=ticket_id, device_id=device_id, kind="endpoint_operation", actor_role="support", trace_id=str(uuid.uuid4()), status="waiting_consent", queued_at=now, started_at=now))
        await session.flush()
        await EndpointOperationLinksRepo(session).create_pending(operation_id=operation_id,
            endpoint_device_ref=device_id, create_idempotency_key=f"consent-race-{marker}", next_attempt_at=now)
        session.add(UserConsentRequest(consent_id=consent_id, subject_type="operation", subject_id=operation_id, ticket_id=ticket_id, requester_person_id=person.person_id, title="Synthetic consent", status="pending", expires_at=now + timedelta(hours=1)))
        await session.commit()

    original_update = OperationsRepo.update_status
    raced = False

    async def change_before_cas(self, **kwargs):
        nonlocal raced
        if kwargs.get("operation_id") == operation_id and not raced:
            raced = True
            async with maker() as concurrent:
                await concurrent.execute(update(Operation).where(Operation.operation_id == operation_id).values(status="failed"))
                await concurrent.commit()
        return await original_update(self, **kwargs)

    monkeypatch.setattr(OperationsRepo, "update_status", change_before_cas)
    route = f"/api/web/requester/consents/{consent_id}/{action}"
    response = await test_client.post(route, headers=_headers(TEST_UI_USER_PREFIX + login), json={})
    assert raced
    assert response.status == 409
    assert (await response.json())["error_code"] == "OPERATION_STATE_CONFLICT"
    async with maker() as session:
        consent = await session.get(UserConsentRequest, consent_id)
        operation = await session.get(Operation, operation_id)
        assert consent.status == "pending" and consent.decided_at is None
        assert operation.status == "failed"
        assert (await session.execute(select(func.count()).select_from(TicketEvent).where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "user_consent_decided"))).scalar_one() == 0
        operation.status = "waiting_consent"
        await session.commit()

    response = await test_client.post(route, headers=_headers(TEST_UI_USER_PREFIX + login), json={})
    assert response.status == 200
    async with maker() as session:
        consent = await session.get(UserConsentRequest, consent_id)
        operation = await session.get(Operation, operation_id)
        assert consent.status == decision and consent.decided_at is not None
        assert operation.status == ("queued" if decision == "approved" else "denied")
        assert (await session.execute(select(func.count()).select_from(TicketEvent).where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "user_consent_decided"))).scalar_one() == 1
