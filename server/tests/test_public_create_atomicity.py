from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent, TicketPublicSession
from app.repos.auth_tokens_repo import AuthTokensRepo
from tickets import public_ticket_handlers as handlers

pytestmark = pytest.mark.db_cleanup("web_support")


def _body(title):
    return {"title": title, "description": "Atomic public create test", "user_display_name": "Test requester",
            "urgency": False, "importance": False,
            "requester_profile": {"phone": "+70001234567"}}


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["routing", "sla", "ola", "session_token", "serialization"])
async def test_public_create_failure_rolls_back_ticket_events_and_session(test_client_light, test_engine, monkeypatch, stage):
    title = "public-atomic-" + uuid.uuid4().hex
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        before_events = (await session.execute(select(func.count()).select_from(TicketEvent))).scalar_one()
        before_sessions = (await session.execute(select(func.count()).select_from(TicketPublicSession))).scalar_one()

    failure = AsyncMock(side_effect=RuntimeError("private dependency details"))
    if stage == "routing":
        monkeypatch.setattr(handlers.TicketRoutingService, "apply_routing", failure)
    elif stage == "sla":
        monkeypatch.setattr(handlers.TicketSlaService, "start_sla", failure)
    elif stage == "ola":
        monkeypatch.setattr(handlers, "start_ola_for_ticket", failure)
    elif stage == "session_token":
        original = AuthTokensRepo.create_ticket_public_session

        async def fail_after_session_write(self, **kwargs):
            await original(self, **kwargs)
            await failure()

        monkeypatch.setattr(AuthTokensRepo, "create_ticket_public_session", fail_after_session_write)
    else:
        def fail_response(*_args, **_kwargs):
            raise RuntimeError("private dependency details")

        monkeypatch.setattr(handlers, "ticket_to_dict", fail_response)

    response = await test_client_light.post("/public_api/tickets/create", json=_body(title))
    assert response.status == 503, await response.text()
    assert "private dependency details" not in await response.text()
    if stage != "serialization":
        failure.assert_awaited_once()
    async with maker() as session:
        assert (await session.execute(select(func.count()).select_from(Ticket).where(Ticket.title == title))).scalar_one() == 0
        assert (await session.execute(select(func.count()).select_from(TicketEvent))).scalar_one() == before_events
        assert (await session.execute(select(func.count()).select_from(TicketPublicSession))).scalar_one() == before_sessions


@pytest.mark.asyncio
async def test_public_create_commits_access_and_authorize_keeps_default_transaction(test_client_light, test_engine):
    response = await test_client_light.post("/public_api/tickets/create", json=_body("public-success-" + uuid.uuid4().hex))
    assert response.status == 200, await response.text()
    body = await response.json()
    ticket_id = body["ticket"]["ticket_id"]
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        assert await session.get(Ticket, ticket_id) is not None
        token = await AuthTokensRepo(session).verify_ticket_public_session(body["public_token"])
        assert token is not None and token.ticket_id == ticket_id

    authorized = await test_client_light.post(f"/public_api/tickets/{ticket_id}/authorize", json={"code": body["public_access_code"]})
    assert authorized.status == 200, await authorized.text()
    authorized_body = await authorized.json()
    async with maker() as session:
        token = await AuthTokensRepo(session).verify_ticket_public_session(authorized_body["public_token"])
        assert token is not None and token.ticket_id == ticket_id
