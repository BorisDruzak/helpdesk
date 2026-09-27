"""ACCOUNT-033: client account claims must not assign another person's history."""
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent
from customer_history.projection_service import CustomerHistoryProjectionService, ticket_history_requester_refs
from requester.identity_service import RequesterIdentityResolver
from tests.conftest import TEST_UI_USER_PREFIX
from tests.test_requester_workspace_api import _headers, _person_for_login

pytestmark = pytest.mark.db_cleanup("web_support")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["unverified_other_account", "browser_no_device"])
async def test_client_declared_account_cannot_assign_foreign_requester(test_client, test_engine, mode):
    marker = "declared-account-" + uuid.uuid4().hex
    attacker_login = marker + "@example.test"
    victim_login = "victim-" + marker + "@example.test"
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        await _person_for_login(session, login=attacker_login)
        victim = await _person_for_login(session, login=victim_login)
        victim_id = victim.person_id
        await session.commit()
        before_events = (await session.execute(select(func.count()).select_from(TicketEvent))).scalar_one()

    response = await test_client.post(
        "/api/tickets/create", headers=_headers(TEST_UI_USER_PREFIX + attacker_login),
        json={"device_id": str(uuid.uuid4()), "title": marker,
              "description": "Unverified client claim must not assign foreign history",
              "requester_account": {"account_mode": mode, "person_id": victim_id,
                                    "login": victim_login, "email": victim_login}},
    )
    assert response.status == {"unverified_other_account": 200, "browser_no_device": 403}[mode]
    if mode == "browser_no_device":
        assert (await response.json())["error_code"] == "REQUESTER_IDENTITY_FORBIDDEN"
    async with maker() as session:
        if response.status != 200:
            assert (await session.execute(select(func.count()).select_from(Ticket).where(Ticket.title == marker))).scalar_one() == 0
            assert (await session.execute(select(func.count()).select_from(TicketEvent))).scalar_one() == before_events
            return
        ticket = (await session.execute(select(Ticket).where(Ticket.title == marker))).scalar_one()
        assert ticket.requester_person_id != victim_id
        assert ticket.requester_external_ref != victim_id
        assert victim_id not in ticket_history_requester_refs(ticket)
        rows = await CustomerHistoryProjectionService(session)._tickets_for_person(victim_id)
        assert ticket.ticket_id not in {row.ticket_id for row in rows}


@pytest.mark.asyncio
async def test_browser_identity_unavailable_rolls_back_and_verified_retry_succeeds(test_client, test_engine, monkeypatch):
    marker = "identity-unavailable-" + uuid.uuid4().hex
    login = marker + "@example.test"
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        person = await _person_for_login(session, login=login)
        person_id = person.person_id
        await session.commit()
        before_events = (await session.execute(select(func.count()).select_from(TicketEvent))).scalar_one()
    body = {"device_id": str(uuid.uuid4()), "title": marker, "description": "Verified retry",
            "requester_account": {"account_mode": "browser_no_device", "person_id": person_id}}
    with monkeypatch.context() as failure:
        failure.setattr(RequesterIdentityResolver, "resolve_person_for_web_user", AsyncMock(side_effect=RuntimeError("private resolver details")))
        response = await test_client.post("/api/tickets/create", headers=_headers(TEST_UI_USER_PREFIX + login), json=body)
        assert response.status == 503
        error = await response.json()
        assert error["error_code"] == "TICKET_INITIALIZATION_UNAVAILABLE"
        assert "private resolver details" not in str(error)
    async with maker() as session:
        assert (await session.execute(select(func.count()).select_from(Ticket).where(Ticket.title == marker))).scalar_one() == 0
        assert (await session.execute(select(func.count()).select_from(TicketEvent))).scalar_one() == before_events
    retried = await test_client.post("/api/tickets/create", headers=_headers(TEST_UI_USER_PREFIX + login), json=body)
    assert retried.status == 200
    async with maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.title == marker))).scalar_one()
        assert ticket.requester_person_id == ticket.requester_external_ref == person_id
        rows = await CustomerHistoryProjectionService(session)._tickets_for_person(person_id)
        assert ticket.ticket_id in {row.ticket_id for row in rows}
