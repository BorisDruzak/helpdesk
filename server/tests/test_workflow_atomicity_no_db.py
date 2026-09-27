from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from auth.context import AuthContext, AuthType
from tests.test_web_support_api import web_support_client
from tickets import handlers as tickets
from tickets.assignment_service import TicketAssignmentError
from web_api import support_handlers as support
from web_api.dto.support import SupportTicketMutationActionResult

pytestmark = pytest.mark.no_db


@pytest.fixture
def mutations(monkeypatch):
    ticket = SimpleNamespace(ticket_id="atomic-workflow-test", ticket_code="T-TEST", device_id=None,
                             status="new", queue_id=1, assignee_id=None, custom_fields={})
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket), update_ticket=AsyncMock(), add_event=AsyncMock())
    auth = AuthContext(actor_id="support1", actor_role="support", auth_type=AuthType.UI_TOKEN, token="synthetic")

    @asynccontextmanager
    async def transaction():
        yield session

    async def transition(**_kwargs):
        ticket.status = "in_progress"
        return {"event_payload": {}, "event_result": None}

    async def reroute(*_args, **_kwargs):
        ticket.queue_id = 2

    pushed = AsyncMock()
    close = AsyncMock()
    start = AsyncMock()
    for module in (tickets, support):
        monkeypatch.setattr(module, "get_session", transaction)
        monkeypatch.setattr(module, "_get_ticket_or_response", AsyncMock(return_value=(ticket, None, repo, auth)))
        monkeypatch.setattr(module, "_push_ticket_event", pushed)
        monkeypatch.setattr(module, "_reconcile_queue_scope_state", AsyncMock(return_value=(ticket, [])))
        monkeypatch.setattr(module, "close_ola_processing", close)
        monkeypatch.setattr(module, "start_ola_for_ticket", start)
        monkeypatch.setattr(module, "TicketRoutingService", lambda *_args: SimpleNamespace(apply_routing=reroute))
    monkeypatch.setattr(tickets, "_ticket_payload", AsyncMock(return_value={"ticket_id": ticket.ticket_id}))
    monkeypatch.setattr(support, "_require_permission", AsyncMock(return_value=None))
    monkeypatch.setattr(support, "validate_transition_for_ticket", AsyncMock(return_value=True))
    monkeypatch.setattr(support, "TicketWorkflowService", lambda *_: SimpleNamespace(apply_status_transition=transition))
    monkeypatch.setattr(support, "_write_support_web_observer_event", AsyncMock())
    monkeypatch.setattr(support, "_support_mutation_result", AsyncMock(return_value=SupportTicketMutationActionResult(
        ticket_id=ticket.ticket_id, action="queue", status="new", status_label="Новый",
        queue={"id": 1, "code": "test", "name": "Test"})))
    monkeypatch.setattr(support, "TicketEventsRepo", lambda *_: repo)
    monkeypatch.setattr(support, "_load_support_queue_state", AsyncMock(return_value=SimpleNamespace(
        accessible_entries=[({"ticket_id": ticket.ticket_id}, object())])))
    return SimpleNamespace(ticket=ticket, session=session, repo=repo, pushed=pushed, close=close, start=start)


@pytest.mark.asyncio
async def test_take_in_work_assignment_rejection_rolls_back(web_support_client, mutations, monkeypatch):
    failure = AsyncMock(side_effect=TicketAssignmentError("private assignment details"))
    monkeypatch.setattr(support.TicketAssignmentService, "assign_ticket", failure)
    response = await web_support_client.post(f"/api/web/support/tickets/{mutations.ticket.ticket_id}/status",
                                             json={"to_status": "in_progress"})
    failure.assert_awaited_once()
    assert response.status == 409
    assert (await response.json())["error_code"] == "ASSIGNMENT_CONFLICT"
    assert "private assignment details" not in await response.text()
    mutations.session.rollback.assert_awaited_once()
    mutations.session.commit.assert_not_awaited()
    mutations.pushed.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/api/tickets/{id}/queue", "/api/tickets/{id}/reroute",
                                  "/api/web/support/tickets/{id}/queue", "/api/web/support/tickets/{id}/reroute"])
@pytest.mark.parametrize("stage", ["close", "start"])
async def test_queue_ola_failure_rolls_back_before_broadcast(web_support_client, mutations, route, stage):
    failure = getattr(mutations, stage)
    failure.side_effect = RuntimeError("private OLA details")
    response = await web_support_client.post(route.format(id=mutations.ticket.ticket_id), json={"queue_id": 2})
    failure.assert_awaited_once()
    assert response.status == 503
    expected_code = "REROUTE_ACTION_FAILED" if route.endswith("/reroute") else "QUEUE_ACTION_FAILED"
    assert (await response.json())["error_code"] == expected_code
    assert "private OLA details" not in await response.text()
    mutations.session.rollback.assert_awaited_once()
    mutations.session.commit.assert_not_awaited()
    mutations.pushed.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["close", "start"])
async def test_mass_queue_ola_failure_is_an_error_item_without_commit(web_support_client, mutations, stage):
    failure = getattr(mutations, stage)
    failure.side_effect = RuntimeError("private OLA details")
    response = await web_support_client.post("/api/web/support/queue/mass-action", json={
        "action": "change_queue", "ticket_ids": [mutations.ticket.ticket_id], "queue_id": 2,
    })
    failure.assert_awaited_once()
    assert response.status == 200
    body = await response.json()
    assert body["data"]["error_count"] == 1 and body["data"]["success_count"] == 0
    assert "private OLA details" not in str(body)
    mutations.session.rollback.assert_awaited_once()
    mutations.session.commit.assert_not_awaited()
    mutations.pushed.assert_not_awaited()
