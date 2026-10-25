from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from auth.context import AuthContext, AuthType
from tests.test_workflow_atomicity_no_db import mutations
from tests.test_web_support_api import web_support_client
from web_api import support_handlers as support

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("member,load,code", [(False, 0, "ASSIGNEE_NOT_IN_QUEUE"), (True, 3, "ASSIGNEE_CAPACITY_REACHED"), (True, 0, None)])
async def test_take_projection_uses_membership_and_target_active_load(work, monkeypatch, member, load, code):
    work.repo.is_actor_in_queue.return_value = member
    work.repo.count_active_tickets_for_assignee.return_value = load
    monkeypatch.setattr(support, "can", AsyncMock(return_value=True))
    auth = AuthContext(actor_id="support1", actor_role="admin", auth_type=AuthType.UI_TOKEN, token="synthetic")
    projector = support._SupportTakeProjector(work.session, work.repo, auth)
    result = await projector.project(work.ticket, transition_allowed=True)
    assert result.allowed == (code is None)
    assert result.reason_code == code
    await projector.project(work.ticket, transition_allowed=True)
    assert work.repo.is_actor_in_queue.await_count == 1
    assert work.repo.count_active_tickets_for_assignee.await_count == (1 if member else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("member,load,code", [(False, 0, "ASSIGNEE_NOT_IN_QUEUE"), (True, 3, "ASSIGNEE_CAPACITY_REACHED")])
async def test_take_denial_is_specific_and_precedes_workflow(web_support_client, work, member, load, code):
    work.repo.is_actor_in_queue.return_value = member
    work.repo.count_active_tickets_for_assignee.return_value = load
    response = await web_support_client.post(f"/api/web/support/tickets/{work.ticket.ticket_id}/status", json={"to_status": "in_progress"})
    assert response.status == 409
    assert (await response.json())["error_code"] == code
    assert work.ticket.status == "new"
    work.repo.add_event.assert_not_awaited()
    work.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_retained_assignee_cannot_resume_when_active_capacity_is_full(web_support_client, work):
    work.ticket.status = "waiting_on_user"
    work.ticket.assignee_id = "support1"
    work.repo.count_active_tickets_for_assignee.return_value = 3
    response = await web_support_client.post(f"/api/web/support/tickets/{work.ticket.ticket_id}/status", json={"to_status": "in_progress"})
    assert response.status == 409
    assert (await response.json())["error_code"] == "ASSIGNEE_CAPACITY_REACHED"
    assert work.ticket.status == "waiting_on_user"
    work.repo.add_event.assert_not_awaited()
    work.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_retained_assignee_take_projection_reports_full_capacity(work):
    work.ticket.status = "waiting_on_user"
    work.ticket.assignee_id = "support1"
    work.repo.count_active_tickets_for_assignee.return_value = 3
    auth = AuthContext(actor_id="support1", actor_role="support", auth_type=AuthType.UI_TOKEN, token="synthetic")
    result = await support._SupportTakeProjector(work.session, work.repo, auth).project(work.ticket, transition_allowed=True)
    assert result.allowed is False
    assert result.reason_code == "ASSIGNEE_CAPACITY_REACHED"


@pytest.fixture
def work(mutations, monkeypatch):
    mutations.repo.add_event.return_value = (1, datetime.now(timezone.utc))
    monkeypatch.setattr(support, "TicketSlaService", lambda *_: SimpleNamespace(close_frt=close_frt))
    close_frt = AsyncMock()
    mutations.close_frt = close_frt
    return mutations


@pytest.mark.asyncio
@pytest.mark.parametrize("status,assignee", [("new", None), ("queued", None), ("assigned", "support1"),
    ("in_progress", None), ("in_progress", "other"), ("resolved", "support1"), ("closed", "support1")])
async def test_public_reply_requires_started_work_before_event_or_sla(web_support_client, work, status, assignee):
    work.ticket.status = status
    work.ticket.assignee_id = assignee
    response = await web_support_client.post(f"/api/web/support/tickets/{work.ticket.ticket_id}/messages", json={"text": "Ответ сотруднику"})
    assert response.status in {403, 409}
    assert (await response.json())["error_code"] in {"TICKET_NOT_IN_WORK", "ASSIGNEE_CONFLICT"}
    work.repo.add_event.assert_not_awaited()
    work.close_frt.assert_not_awaited()
    work.session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("role,assignee,visibility,status", [
    ("support", "support1", "public", "in_progress"),
    ("support", "support1", "public", "waiting_on_user"),
    ("admin", "other", "public", "in_progress"),
    ("support", None, "internal", "new"),
])
async def test_valid_reply_and_internal_notes_preserve_existing_semantics(web_support_client, work, monkeypatch, role, assignee, visibility, status):
    work.ticket.status = status
    work.ticket.assignee_id = assignee
    auth = AuthContext(actor_id="support1", actor_role=role, auth_type=AuthType.UI_TOKEN, token="synthetic")
    monkeypatch.setattr(support, "_get_ticket_or_response", AsyncMock(return_value=(work.ticket, None, work.repo, auth)))
    response = await web_support_client.post(f"/api/web/support/tickets/{work.ticket.ticket_id}/messages", json={"text": "Ответ", "visibility": visibility})
    assert response.status == 200, await response.text()
    assert work.ticket.status == status
    work.repo.get_ticket.assert_awaited_with(work.ticket.ticket_id, for_update=True)
    work.repo.add_event.assert_awaited_once()
    assert work.close_frt.await_count == (1 if visibility == "public" else 0)


@pytest.mark.asyncio
async def test_start_work_cannot_hijack_another_assignee(web_support_client, work):
    work.ticket.status = "assigned"
    work.ticket.assignee_id = "other"
    response = await web_support_client.post(f"/api/web/support/tickets/{work.ticket.ticket_id}/status", json={"to_status": "in_progress"})
    assert response.status == 403
    assert (await response.json())["error_code"] == "ASSIGNEE_CONFLICT"
    work.session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("action,body", [("messages", {"text": "Reply"}), ("status", {"to_status": "in_progress"})])
async def test_scope_is_rechecked_after_locked_refresh(web_support_client, work, monkeypatch, action, body):
    work.ticket.status = "in_progress"
    work.ticket.assignee_id = "support1"
    original = support._get_ticket_or_response.return_value
    forbidden = support._support_json_error("forbidden", status=403)
    monkeypatch.setattr(support, "_get_ticket_or_response", AsyncMock(side_effect=[original, (None, forbidden, work.repo, original[3])]))
    response = await web_support_client.post(f"/api/web/support/tickets/{work.ticket.ticket_id}/{action}", json=body)
    assert response.status == 403
    work.repo.add_event.assert_not_awaited()
    work.session.commit.assert_not_awaited()
