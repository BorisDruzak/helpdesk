from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy.dialects import postgresql

from app.repos.ticket_events_repo import TicketEventsRepo
from tickets import workflow_service as workflow
from tickets.workflow_profiles import get_workflow_profile
from tests.test_web_support_api import web_support_client
from tests.test_workflow_atomicity_no_db import mutations
from tickets import handlers as tickets
from web_api import support_handlers as support
from web_api import requester_handlers as requester
from web_api import quality_handlers as quality
from auth.context import AuthContext, AuthType

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_stale_transition_stops_before_policy_or_side_effects(monkeypatch):
    ticket = SimpleNamespace(status="queued")
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket))
    policy = AsyncMock(side_effect=AssertionError("stale transition reached policy execution"))
    monkeypatch.setattr(workflow, "load_ticket_workflow_profile", policy)
    with pytest.raises(ValueError, match="Состояние обращения изменилось"):
        await workflow.TicketWorkflowService(SimpleNamespace(), repo).apply_status_transition(
            ticket_id="test", from_status="new", to_status="canceled", actor_id="test", actor_role="support")
    policy.assert_not_awaited()
    repo.get_ticket.assert_awaited_once_with("test", for_update=True)


@pytest.mark.asyncio
async def test_locked_ticket_read_refreshes_identity_map():
    result = SimpleNamespace(scalar_one_or_none=lambda: None)
    session = SimpleNamespace(execute=AsyncMock(return_value=result), flush=AsyncMock())
    await TicketEventsRepo(session).get_ticket("test", for_update=True)
    session.flush.assert_awaited_once()
    statement = session.execute.await_args.args[0]
    assert "FOR UPDATE" in str(statement.compile(dialect=postgresql.dialect()))
    assert statement.get_execution_options()["populate_existing"] is True


@pytest.mark.asyncio
async def test_ordinary_ticket_read_does_not_flush_or_lock():
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
                              flush=AsyncMock())
    await TicketEventsRepo(session).get_ticket("test")
    session.flush.assert_not_awaited()
    statement = session.execute.await_args.args[0]
    assert "FOR UPDATE" not in str(statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["closed", "assigned"])
async def test_automatic_reply_does_not_apply_stale_or_duplicate_fallback(monkeypatch, status):
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=SimpleNamespace(status=status)))
    profile = get_workflow_profile("service_request")
    monkeypatch.setattr(workflow, "load_ticket_workflow_profile", AsyncMock(return_value=profile))
    service = workflow.TicketWorkflowService(SimpleNamespace(), repo)
    service.apply_status_transition = AsyncMock(side_effect=AssertionError("stale automatic transition"))
    result = await service.apply_triggered_transition("test", trigger="requester_replied", actor_id="system",
                                                     actor_role="system", fallback_status="assigned")
    assert result["no_op"] is True
    service.apply_status_transition.assert_not_awaited()
    repo.get_ticket.assert_awaited_once_with("test", for_update=True)


@pytest.mark.asyncio
async def test_available_reply_fallback_keeps_normal_workflow_target(monkeypatch):
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=SimpleNamespace(status="waiting_on_user")))
    monkeypatch.setattr(workflow, "load_ticket_workflow_profile", AsyncMock(return_value=get_workflow_profile("service_request")))
    service = workflow.TicketWorkflowService(SimpleNamespace(), repo)
    service.apply_status_transition = AsyncMock(return_value={"applied": True})
    result = await service.apply_triggered_transition("test", trigger="requester_replied", actor_id="system",
                                                     actor_role="system", fallback_status="assigned")
    assert result["applied"] is True
    assert service.apply_status_transition.await_args.kwargs["from_status"] == "waiting_on_user"
    assert service.apply_status_transition.await_args.kwargs["to_status"] == "assigned"
    repo.get_ticket.assert_awaited_once_with("test", for_update=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/api/tickets/{id}/status", "/api/web/support/tickets/{id}/status"])
async def test_status_conflict_returns_409_without_commit_or_broadcast(web_support_client, mutations, monkeypatch, route):
    failure = AsyncMock(side_effect=workflow.WorkflowTransitionConflict())
    for module in (tickets, support):
        monkeypatch.setattr(module, "TicketWorkflowService", lambda *_: SimpleNamespace(apply_status_transition=failure))
        monkeypatch.setattr(module, "validate_transition_for_ticket", AsyncMock(return_value=True))
    response = await web_support_client.post(route.format(id=mutations.ticket.ticket_id), json={"to_status": "canceled"})
    failure.assert_awaited_once()
    assert response.status == 409
    assert (await response.json())["error_code"] == "WORKFLOW_CONFLICT"
    mutations.session.rollback.assert_awaited_once()
    mutations.session.commit.assert_not_awaited()
    mutations.pushed.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/api/tickets/test/reopen", "/public_api/tickets/test/reopen"])
async def test_reopen_conflict_returns_409_without_commit(web_support_client, mutations, monkeypatch, route):
    failure = AsyncMock(side_effect=workflow.WorkflowTransitionConflict())
    monkeypatch.setattr(quality, "get_session", tickets.get_session)
    monkeypatch.setattr(quality, "TicketReopenService", lambda *_: SimpleNamespace(reopen_ticket=failure))
    monkeypatch.setattr(quality, "_public_auth_context", AsyncMock(return_value=AuthContext(
        actor_id="test", actor_role="requester", auth_type=AuthType.UI_TOKEN, token="synthetic")))
    response = await web_support_client.post(route, json={"reason_code": "not_fixed"})
    failure.assert_awaited_once()
    assert response.status == 409
    assert (await response.json())["error_code"] == "WORKFLOW_CONFLICT"
    mutations.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_requester_confirmation_conflict_rolls_back(monkeypatch, mutations):
    failure = AsyncMock(side_effect=workflow.WorkflowTransitionConflict())
    ticket = SimpleNamespace(ticket_id="test", status="resolved")
    monkeypatch.setattr(requester, "get_session", tickets.get_session)
    monkeypatch.setattr(requester, "RequesterIdentityResolver", lambda *args, **kwargs: SimpleNamespace(
        get_ticket=AsyncMock(return_value=ticket)))
    monkeypatch.setattr(requester, "TicketEventsRepo", lambda *_: mutations.repo)
    monkeypatch.setattr(requester, "requester_ticket_actions", lambda *_: {"can_confirm_solution": True})
    monkeypatch.setattr(requester, "TicketWorkflowService", lambda *_: SimpleNamespace(apply_status_transition=failure))

    @web.middleware
    async def authenticated_requester(request, handler):
        request["auth_context"] = AuthContext(actor_id="test", actor_role="user", auth_type=AuthType.UI_TOKEN,
                                              token="synthetic")
        return await handler(request)

    app = web.Application(middlewares=[authenticated_requester])
    app.router.add_post("/tickets/{ticket_id}/close", requester.handle_web_requester_ticket_close)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/tickets/test/close", json={})
        failure.assert_awaited_once()
        assert response.status == 409
        assert (await response.json())["error_code"] == "WORKFLOW_CONFLICT"
    mutations.session.rollback.assert_awaited_once()
    mutations.session.commit.assert_not_awaited()
