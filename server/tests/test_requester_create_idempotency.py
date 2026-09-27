import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RequesterTicketCreateRequest, RegistryPerson, Ticket, TicketEvent
from requester.create_idempotency import CreateRequestKey, RequesterCreateLedger
from tickets.public_access import set_public_access_code
from web_api import requester_handlers
from tests.conftest import TEST_UI_USER_PREFIX
from tests.test_requester_workspace_api import _headers, _person_for_login
from tickets import create_flow

pytestmark = pytest.mark.db_cleanup("web_support")


async def _actor(test_engine):
    login = "idempotency-" + uuid.uuid4().hex + "@example.test"
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        person = await _person_for_login(session, login=login)
        await session.commit()
        return login, person.person_id


def _request(login, key):
    return {**_headers(f"{TEST_UI_USER_PREFIX}{login}"), "Idempotency-Key": key}


@pytest.mark.asyncio
async def test_http_replay_reuses_ticket_code_and_events_and_is_actor_scoped(test_client, test_engine):
    login, _ = await _actor(test_engine)
    key = uuid.uuid4().hex
    body = {"title": "Idempotency " + key, "description": "Retry after lost response"}
    first = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=body)
    assert first.status == 200
    initial = (await first.json())["data"]
    ticket_id = initial["ticket_id"]
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        events_before = (await session.execute(select(func.count()).select_from(TicketEvent).where(TicketEvent.ticket_id == ticket_id))).scalar_one()
    again = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=dict(reversed(list(body.items()))))
    assert again.status == 200
    replay = (await again.json())["data"]
    assert replay["ticket_id"] == ticket_id
    assert replay["ticket_code"] == initial["ticket_code"]
    assert bool(replay["public_access_code"] == initial["public_access_code"])
    mismatch = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json={**body, "description": "Changed intent"})
    assert mismatch.status == 409
    assert (await mismatch.json())["error_code"] == "CREATE_REQUEST_CONFLICT"
    async with maker() as session:
        count = (await session.execute(select(func.count()).select_from(Ticket).where(Ticket.title == body["title"]))).scalar_one()
        events_after = (await session.execute(select(func.count()).select_from(TicketEvent).where(TicketEvent.ticket_id == ticket_id))).scalar_one()
        assert count == 1 and events_after == events_before
    other_login, _ = await _actor(test_engine)
    other = await test_client.post("/api/web/requester/tickets", headers=_request(other_login, key), json=body)
    assert other.status == 200
    assert (await other.json())["data"]["ticket_id"] != ticket_id


@pytest.mark.asyncio
async def test_failed_initialization_rolls_back_key_and_retry_can_succeed(test_client, test_engine, monkeypatch):
    login, _ = await _actor(test_engine)
    key = uuid.uuid4().hex
    body = {"title": "Rollback " + key, "description": "Retry failed initialization"}
    with monkeypatch.context() as failure:
        failure.setattr(create_flow.TicketSlaService, "start_sla", AsyncMock(side_effect=RuntimeError("test SLA unavailable")))
        response = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=body)
        assert response.status == 503
    request_key = CreateRequestKey.parse(login, key, body)
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        assert await RequesterCreateLedger(session).lookup(request_key) is None
        assert (await session.execute(select(func.count()).select_from(Ticket).where(Ticket.title == body["title"]))).scalar_one() == 0
    retry = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=body)
    assert retry.status == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke", ["person", "ticket", "code"])
async def test_replay_rechecks_access_and_retains_deleted_ticket_tombstone(test_client, test_engine, revoke):
    login, person_id = await _actor(test_engine)
    key = uuid.uuid4().hex
    body = {"title": "Revoke " + key, "description": "Current authorization required"}
    response = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=body)
    assert response.status == 200
    ticket_id = (await response.json())["data"]["ticket_id"]
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        if revoke == "person":
            person = await session.get(RegistryPerson, person_id)
            person.status = "inactive"
        elif revoke == "ticket":
            ticket = await session.get(Ticket, ticket_id)
            await session.delete(ticket)
        else:
            ticket = await session.get(Ticket, ticket_id)
            ticket.custom_fields = set_public_access_code(ticket.custom_fields, "SYNTHETICNEWCODE")
        await session.commit()
    repeated = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=body)
    assert repeated.status == {"person": 404, "ticket": 409, "code": 200}[revoke]
    if revoke == "code":
        assert (await repeated.json())["data"]["public_access_code"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["description", "form"])
async def test_preflight_rejection_does_not_consume_request_key(test_client, test_engine, invalid):
    login, _ = await _actor(test_engine)
    key = uuid.uuid4().hex
    valid = {"title": "Preflight " + key, "description": "Valid retry after rejection"}
    body = {**valid, "description": ""} if invalid == "description" else {**valid, "form_key": "missing-" + key}
    response = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=body)
    assert response.status == {"description": 400, "form": 403}[invalid]
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        assert await RequesterCreateLedger(session).lookup(CreateRequestKey.parse(login, key, body)) is None
    retry = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=valid)
    assert retry.status == 200


@pytest.mark.asyncio
async def test_response_construction_failure_rolls_back_ticket_and_key(test_client, test_engine, monkeypatch):
    login, _ = await _actor(test_engine)
    key = uuid.uuid4().hex
    body = {"title": "Projection " + key, "description": "Retry after response construction failure"}
    with monkeypatch.context() as failure:
        failure.setattr(requester_handlers, "created_ticket_response", lambda *_: (_ for _ in ()).throw(RuntimeError("test projection failure")))
        response = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=body)
        assert response.status == 500
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        assert await RequesterCreateLedger(session).lookup(CreateRequestKey.parse(login, key, body)) is None
        assert (await session.execute(select(func.count()).select_from(Ticket).where(Ticket.title == body["title"]))).scalar_one() == 0
    retry = await test_client.post("/api/web/requester/tickets", headers=_request(login, key), json=body)
    assert retry.status == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_winner", [True, False])
async def test_concurrent_reservation_waits_for_commit_or_rollback(test_engine, commit_winner):
    maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    key = CreateRequestKey.parse("test-actor", uuid.uuid4().hex, {"description": "Concurrent retry"})
    ticket_id = str(uuid.uuid4())
    async with maker() as first, maker() as second:
        assert await RequesterCreateLedger(first).reserve(key) is None
        first.add(Ticket(ticket_id=ticket_id, title="Concurrent create", description="Test", status="new", requester_id="test-actor", custom_fields={}))
        await RequesterCreateLedger(first).complete(key, ticket_id)
        task = asyncio.create_task(RequesterCreateLedger(second).reserve(key))
        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), 0.2)
            if commit_winner:
                await first.commit()
            else:
                await first.rollback()
            result = await asyncio.wait_for(task, 10)
            if commit_winner:
                assert result.ticket_id == ticket_id
            else:
                assert result is None
            await second.rollback()
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    async with maker() as session:
        row = await session.get(RequesterTicketCreateRequest, (key.actor_hash, key.key_hash))
        assert (row is not None) == commit_winner
