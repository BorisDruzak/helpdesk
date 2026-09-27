from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tickets import public_ticket_handlers as handlers

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_stage", ["routing", "sla", "ola", "session_token"])
async def test_public_create_required_failure_does_not_commit(monkeypatch, failed_stage):
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())

    @asynccontextmanager
    async def transaction():
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    ticket = SimpleNamespace(ticket_id="test-public-create", device_id="test-public-create",
                             custom_fields={}, assignee_id="existing", status="assigned")
    repo = SimpleNamespace(create_ticket=AsyncMock(return_value=ticket), update_ticket=AsyncMock(),
                           get_ticket=AsyncMock(return_value=ticket), add_event=AsyncMock())
    stages = {stage: AsyncMock(side_effect=RuntimeError("private dependency details")
                              if stage == failed_stage else None)
              for stage in ("routing", "sla", "ola", "session_token")}
    stages["session_token"].return_value = "synthetic-session-value"
    monkeypatch.setattr(handlers, "get_session", transaction)
    monkeypatch.setattr(handlers, "TicketEventsRepo", lambda *_: repo)
    monkeypatch.setattr(handlers, "DevicesRepo", lambda *_: object())
    monkeypatch.setattr(handlers, "TicketRoutingService", lambda *_: SimpleNamespace(apply_routing=stages["routing"]))
    monkeypatch.setattr(handlers, "TicketSlaService", lambda *_: SimpleNamespace(start_sla=stages["sla"]))
    monkeypatch.setattr(handlers, "start_ola_for_ticket", stages["ola"])
    monkeypatch.setattr(handlers, "start_ticket_created_playbooks", AsyncMock())
    monkeypatch.setattr(handlers, "AuthService", lambda *_: SimpleNamespace(generate_ticket_public_session_token=stages["session_token"]))
    monkeypatch.setattr(handlers, "ticket_to_dict", lambda *_args, **_kwargs: {"ticket_id": ticket.ticket_id})
    request = SimpleNamespace(app={"state": object()}, json=AsyncMock(return_value={
        "description": "Atomic public create", "user_display_name": "Test requester",
        "urgency": False, "importance": False,
    }))

    response = await handlers.handle_public_ticket_create(request)

    assert response.status == 503
    assert "private dependency details" not in response.text
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    stages[failed_stage].assert_awaited_once()
    order = list(stages)
    for stage in order[order.index(failed_stage) + 1:]:
        stages[stage].assert_not_awaited()


@pytest.mark.asyncio
async def test_public_session_issuance_uses_supplied_transaction(monkeypatch):
    from auth import service as auth_service

    session = object()
    create = AsyncMock(return_value=("synthetic-session-value", object()))
    repo = SimpleNamespace(create_ticket_public_session=create)
    monkeypatch.setattr(auth_service, "AuthTokensRepo", lambda supplied: repo if supplied is session else None)
    own_transaction = AsyncMock(side_effect=AssertionError("must use supplied transaction"))
    monkeypatch.setattr(auth_service, "get_session", own_transaction)

    result = await auth_service.AuthService(object()).generate_ticket_public_session_token(
        ticket_id="test-ticket", actor_id="test-requester", expires_minutes=5, session=session,
    )

    assert result == "synthetic-session-value"
    assert create.await_args.kwargs["commit"] is False
    own_transaction.assert_not_called()
