from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from requester.create_idempotency import CreateRequestKey, CreateRequestConflict, RequesterCreateLedger
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from auth.context import AuthContext, AuthType
from web_api import requester_handlers
from requester import create_idempotency
from tickets.public_access import set_public_access_code

pytestmark = pytest.mark.no_db


def test_key_hashes_are_actor_scoped_and_payload_order_independent():
    first = CreateRequestKey.parse("actor-a", "request-key-123", {"title": "Test", "form": {"a": 1, "b": 2}})
    reordered = CreateRequestKey.parse("actor-a", "request-key-123", {"form": {"b": 2, "a": 1}, "title": "Test"})
    assert first == reordered
    assert len(first.key_hash) == len(first.payload_hash) == 64
    assert first != CreateRequestKey.parse("actor-b", "request-key-123", {"title": "Test"})


@pytest.mark.parametrize("key", [None, "", "short", "x" * 129, "invalid key", "x\n123456789"])
def test_invalid_keys_are_rejected_without_silent_truncation(key):
    with pytest.raises(ValueError):
        CreateRequestKey.parse("actor", key, {"description": "Test"})


@pytest.mark.asyncio
async def test_reservation_conflict_rechecks_payload_after_wait():
    key = CreateRequestKey.parse("actor", "request-key-123", {"description": "Test"})
    row = SimpleNamespace(payload_hash="different", ticket_id="existing")
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
                              get=AsyncMock(return_value=row))
    ledger = RequesterCreateLedger(session)
    with pytest.raises(CreateRequestConflict):
        await ledger.reserve(key)
    session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_deleted_ticket_reservation_is_not_recreated():
    key = CreateRequestKey.parse("actor", "request-key-123", {"description": "Test"})
    row = SimpleNamespace(payload_hash=key.payload_hash, ticket_id=None)
    ledger = RequesterCreateLedger(SimpleNamespace(get=AsyncMock(return_value=row)))
    with pytest.raises(CreateRequestConflict):
        await ledger.lookup(key)


@pytest.mark.asyncio
@pytest.mark.parametrize("key", [None, "short", "invalid key"])
async def test_http_create_requires_valid_key_before_database_access(monkeypatch, key):
    database = Mock(side_effect=AssertionError("invalid key reached database"))
    monkeypatch.setattr(requester_handlers, "get_session", database)

    @web.middleware
    async def actor(request, handler):
        request["auth_context"] = AuthContext(actor_id="test-actor", actor_role="user", auth_type=AuthType.UI_TOKEN, token="synthetic")
        return await handler(request)

    app = web.Application(middlewares=[actor])
    app.router.add_post("/create", requester_handlers.handle_web_requester_ticket_create)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/create", headers={"Idempotency-Key": key} if key is not None else {}, json={"description": "Test"})
        assert response.status == 400
        assert (await response.json())["error_code"] == "VALIDATION_ERROR"
    database.assert_not_called()


@pytest.mark.asyncio
async def test_replay_does_not_read_access_code_before_current_authorization():
    session = SimpleNamespace(execute=AsyncMock())
    resolver = SimpleNamespace(get_ticket=AsyncMock(return_value=None))
    with pytest.raises(PermissionError):
        await create_idempotency.replay_created_ticket(session, SimpleNamespace(ticket_id="test-ticket"), resolver, actor_id="actor")
    resolver.get_ticket.assert_awaited_once_with(actor_id="actor", ticket_id="test-ticket")
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_code", [None, "STALECODE"])
async def test_replay_does_not_reissue_or_return_invalid_access_code(monkeypatch, stored_code):
    ticket = SimpleNamespace(ticket_id="test-ticket", custom_fields=set_public_access_code({}, "CURRENTCODE"))
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: stored_code)))
    resolver = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket))
    monkeypatch.setattr(create_idempotency, "created_ticket_response", lambda row, code: {"ticket_id": row.ticket_id, "public_access_code": code})
    result = await create_idempotency.replay_created_ticket(session, SimpleNamespace(ticket_id="test-ticket"), resolver, actor_id="actor")
    assert result == {"ticket_id": "test-ticket", "public_access_code": None}
