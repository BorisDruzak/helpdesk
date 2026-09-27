from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from requester import identity_service as identity

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", ["older-ticket-id", "T-000001"])
async def test_ticket_lookup_does_not_enumerate_recent_tickets(monkeypatch, reference):
    ticket = SimpleNamespace(ticket_id="older-ticket-id", ticket_code="T-000001")
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalar_one_or_none=lambda: ticket)))
    resolver = identity.RequesterIdentityResolver(session)
    resolver.resolve_person_for_web_user = AsyncMock(return_value=None)
    resolver.list_active_bindings = AsyncMock(return_value=[])
    resolver.list_tickets = AsyncMock(side_effect=AssertionError("bounded recent list used for authorization"))
    annotate = AsyncMock()
    monkeypatch.setattr(identity, "annotate_requester_ticket_policy_state", annotate)

    assert await resolver.get_ticket(actor_id="test-requester", ticket_id=reference) is ticket
    resolver.list_tickets.assert_not_awaited()
    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert reference in compiled.params.values()
    assert "test-requester" in compiled.params.values()
    assert "requester_id" in str(compiled)
    assert "requester_external_ref IS NULL" in str(compiled)
    assert "LIMIT" not in str(compiled)
    annotate.assert_awaited_once_with(session, [ticket])


@pytest.mark.asyncio
async def test_blank_reference_does_not_query_or_annotate(monkeypatch):
    session = SimpleNamespace(execute=AsyncMock())
    resolver = identity.RequesterIdentityResolver(session)
    resolver.resolve_person_for_web_user = AsyncMock()
    annotate = AsyncMock()
    monkeypatch.setattr(identity, "annotate_requester_ticket_policy_state", annotate)
    assert await resolver.get_ticket(actor_id="test-requester", ticket_id="  ") is None
    session.execute.assert_not_awaited()
    resolver.resolve_person_for_web_user.assert_not_awaited()
    annotate.assert_not_awaited()
