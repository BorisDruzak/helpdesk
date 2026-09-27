from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from requester import identity_service
from tickets import create_flow, handlers

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("resolved", ["claimed", "foreign", None])
async def test_browser_claim_requires_matching_server_identity(monkeypatch, resolved):
    resolve = AsyncMock(return_value=SimpleNamespace(person_id=resolved) if resolved else None)
    monkeypatch.setattr(identity_service, "RequesterIdentityResolver", lambda *args, **kwargs: SimpleNamespace(resolve_person_for_web_user=resolve))
    if resolved == "claimed":
        assert await create_flow._verify_browser_requester_identity(object(), actor_id="actor", claimed_person_id="claimed", state=None) == "claimed"
    else:
        with pytest.raises(create_flow.RequesterIdentityMismatch):
            await create_flow._verify_browser_requester_identity(object(), actor_id="actor", claimed_person_id="claimed", state=None)
    resolve.assert_awaited_once_with("actor")


@pytest.mark.asyncio
@pytest.mark.parametrize("actor,claimed", [("", "claimed"), ("actor", "")])
async def test_missing_browser_claim_is_rejected_before_identity_lookup(monkeypatch, actor, claimed):
    resolve = AsyncMock()
    monkeypatch.setattr(identity_service, "RequesterIdentityResolver", lambda *args, **kwargs: SimpleNamespace(resolve_person_for_web_user=resolve))
    with pytest.raises(create_flow.RequesterIdentityMismatch):
        await create_flow._verify_browser_requester_identity(object(), actor_id=actor, claimed_person_id=claimed, state=None)
    resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_browser_identity_failure_is_typed_unavailable(monkeypatch):
    resolve = AsyncMock(side_effect=RuntimeError("private resolver details"))
    monkeypatch.setattr(identity_service, "RequesterIdentityResolver", lambda *args, **kwargs: SimpleNamespace(resolve_person_for_web_user=resolve))
    with pytest.raises(create_flow.TicketInitializationError) as caught:
        await create_flow._verify_browser_requester_identity(object(), actor_id="actor", claimed_person_id="claimed", state=None)
    assert caught.value.stage == "requester_identity"
    assert "private resolver details" not in str(caught.value)


@pytest.mark.asyncio
async def test_legacy_http_identity_mismatch_rolls_back_before_reply(monkeypatch):
    session = SimpleNamespace(rollback=AsyncMock(), commit=AsyncMock())

    @asynccontextmanager
    async def get_session():
        yield session

    @web.middleware
    async def actor(request, handler):
        request["auth_context"] = AuthContext(actor_id="test-actor", actor_role="user", auth_type=AuthType.UI_TOKEN, token="synthetic")
        return await handler(request)

    monkeypatch.setattr(handlers, "get_session", get_session)
    monkeypatch.setattr(handlers, "create_ticket_with_side_effects", AsyncMock(side_effect=create_flow.RequesterIdentityMismatch()))
    app = web.Application(middlewares=[actor])
    app.router.add_post("/create", handlers.handle_tickets_create)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/create", json={"device_id": "test-device", "description": "Test"})
        assert response.status == 403
        assert (await response.json())["error_code"] == "REQUESTER_IDENTITY_FORBIDDEN"
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
