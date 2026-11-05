"""PostgreSQL acceptance for atomic support completion and owned confirmation."""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent, UiUser
from app.repos.ticket_events_repo import TicketEventsRepo
from tests.conftest import TEST_UI_SUPPORT_TOKEN, TEST_UI_ADMIN_TOKEN, TEST_UI_USER_PREFIX
from tests.test_ticket_queue_routing_contracts import _seed_queue
from tests.pg_lock_probe import wait_for_backend_blocker
from tickets.workflow_profiles import save_workflow_profiles
from tickets.workflow_service import TicketWorkflowService, WorkflowTransitionConflict

pytestmark = pytest.mark.db_cleanup("web_support")


@pytest.fixture
def test_client(test_client_light):
    return test_client_light


async def seed(test_engine, *, confirmation=False, assignee="support-test", requester="completion-user"):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="!", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="completion_" + uuid.uuid4().hex,
                                  name="Completion", members=["support-test"])
        session.add(Ticket(ticket_id=ticket_id, device_id=None, title="Completion acceptance",
                           description="Scoped synthetic ticket", status="in_progress", queue_id=queue.id,
                           assignee_id=assignee, requester_id=requester, ticket_type="incident",
                           custom_fields={"request_template": {"closure_policy": {
                               "before_resolved": {"require_public_summary": True, "require_resolution_code": True},
                               "allowed_resolution_codes": ["fixed_remote"],
                               "requester_confirmation": {"required": confirmation},
                           }}}))
        await session.commit()
    return maker, ticket_id


def command():
    return {"to_status": "resolved", "close_after_resolve": True,
            "requester_resolution_summary": "Доступ восстановлен", "resolution_summary": "Internal diagnosis"}


def headers_for(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("choice", ["close", "reopen"])
async def test_resolution_waits_for_owner_acceptance_and_rejects_staff_close(test_client, test_engine, choice):
    from tests.test_requester_workspace_api import _person_for_login
    owner = "confirm-owner-" + uuid.uuid4().hex[:8]
    foreign = "confirm-other-" + uuid.uuid4().hex[:8]
    maker, ticket_id = await seed(test_engine, confirmation=True, requester=owner)
    async with maker() as session:
        person = await _person_for_login(session, login=owner)
        await _person_for_login(session, login=foreign)
        ticket = await session.get(Ticket, ticket_id)
        ticket.requester_person_id = person.person_id
        ticket.requester_external_ref = person.person_id
        ticket.requester_snapshot_json = {"person": {"external_id": person.person_id}, "display_name": "Synthetic owner"}
        await session.commit()
    resolved = await test_client.post(f"/api/web/support/tickets/{ticket_id}/status", headers=headers_for(TEST_UI_SUPPORT_TOKEN),
        json={"to_status": "resolved", "requester_resolution_summary": "Проверьте, пожалуйста, работу принтера"})
    assert resolved.status == 200, await resolved.text()
    assert (await resolved.json())["data"]["status"] == "resolved"
    for token in (TEST_UI_SUPPORT_TOKEN, TEST_UI_ADMIN_TOKEN):
        denied = await test_client.post(f"/api/web/support/tickets/{ticket_id}/status", headers=headers_for(token), json={"to_status": "closed"})
        assert denied.status == 409, await denied.text()
        assert (await denied.json())["error_code"] == "REQUESTER_CONFIRMATION_REQUIRED"
    detail = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=headers_for(TEST_UI_SUPPORT_TOKEN))
    assert not any(option["value"] == "closed" for option in (await detail.json())["data"]["actions"]["status_options"])
    own_headers = headers_for(TEST_UI_USER_PREFIX + owner)
    public = await test_client.get(f"/api/web/requester/tickets/{ticket_id}", headers=own_headers)
    data = (await public.json())["data"]
    assert data["ticket"]["status"] == "resolved" and data["ticket"]["actions"]["can_confirm_solution"]
    assert data["handling"]["next_action_owner"] == "requester"
    not_owner = await test_client.post(f"/api/web/requester/tickets/{ticket_id}/close", headers=headers_for(TEST_UI_USER_PREFIX + foreign), json={})
    assert not_owner.status == 404
    chosen = await test_client.post(f"/api/web/requester/tickets/{ticket_id}/{choice}", headers=own_headers,
        json={} if choice == "close" else {"reason_code": "not_resolved", "reason_comment": "Принтер всё ещё не печатает"})
    assert chosen.status == 200, await chosen.text()
    async with maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "closed" if choice == "close" else ticket.status not in {"resolved", "closed"}


async def test_atomic_completion_api_persists_both_audits_and_public_result(test_client, test_engine):
    maker, ticket_id = await seed(test_engine)
    headers = headers_for(TEST_UI_SUPPORT_TOKEN)
    detail = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=headers)
    assert detail.status == 200, await detail.text()
    assert (await detail.json())["data"]["actions"]["can_resolve_and_close"] is True
    response = await test_client.post(f"/api/web/support/tickets/{ticket_id}/status", headers=headers, json=command())
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["status"] == "closed"
    async with maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "closed" and ticket.resolved_at and ticket.closed_at
        assert ticket.resolution_code is None
        events = (await session.execute(select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "status_changed").order_by(TicketEvent.id))).scalars().all()
        assert [(event.payload["to_status"], event.payload["actor_id"]) for event in events] == [
            ("resolved", "support-test"), ("closed", "support-test")]
    requester = await test_client.get(f"/api/web/requester/tickets/{ticket_id}",
                                      headers=headers_for(TEST_UI_USER_PREFIX + "completion-user"))
    assert requester.status == 200, await requester.text()
    public = (await requester.json())["data"]["ticket"]
    assert public["requester_resolution_summary"] == "Доступ восстановлен"
    assert "Internal diagnosis" not in str(public)
    assert public["actions"]["can_confirm_solution"] is False


@pytest.mark.parametrize("denial", ["confirmation", "owner", "close_gate"])
async def test_failed_completion_has_no_partial_resolution(test_client, test_engine, denial):
    maker, ticket_id = await seed(test_engine, confirmation=denial == "confirmation",
                                 assignee="other-operator" if denial == "owner" else "support-test")
    if denial == "close_gate":
        async with maker() as session:
            await save_workflow_profiles(session, {"workflow_profiles": [{
                "ticket_type": "incident", "label": "Completion gated", "purpose": "restore_service",
                "suggested_path": ["new", "in_progress", "resolved", "closed"],
                "allowed_statuses": ["new", "in_progress", "resolved", "closed"],
                "transitions": {"new": ["in_progress"], "in_progress": ["resolved"],
                                "resolved": [{"to": "closed", "allowed_roles": ["admin"]}], "closed": []},
            }]})
            await session.commit()
    response = await test_client.post(f"/api/web/support/tickets/{ticket_id}/status",
                                      headers=headers_for(TEST_UI_SUPPORT_TOKEN), json=command())
    assert response.status == (403 if denial == "owner" else 400), await response.text()
    async with maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "in_progress"
        assert ticket.resolved_at is None and ticket.closed_at is None
        assert ticket.requester_resolution_summary is None
        assert not (await session.execute(select(TicketEvent.id).where(TicketEvent.ticket_id == ticket_id))).all()


async def test_concurrent_completion_has_one_winner(test_engine):
    maker, ticket_id = await seed(test_engine)
    async with maker() as first, maker() as second:
        first_pid = await first.scalar(text("SELECT pg_backend_pid()"))
        second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
        await TicketEventsRepo(second).get_ticket(ticket_id)
        await TicketWorkflowService(first, TicketEventsRepo(first)).apply_status_transition(
            ticket_id, "in_progress", "resolved", "support-test", "support",
            requester_resolution_summary="Выполнено", close_after_resolve=True)

        async def losing_completion():
            try:
                await TicketWorkflowService(second, TicketEventsRepo(second)).apply_status_transition(
                    ticket_id, "in_progress", "resolved", "support-test", "support",
                    requester_resolution_summary="Выполнено", close_after_resolve=True)
            finally:
                await second.rollback()

        task = asyncio.create_task(losing_completion())
        try:
            await wait_for_backend_blocker(test_engine, blocked_pid=second_pid, blocker_pid=first_pid, task=task)
            await first.commit()
            with pytest.raises(WorkflowTransitionConflict):
                await asyncio.wait_for(task, 10)
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    async with maker() as session:
        assert (await session.get(Ticket, ticket_id)).status == "closed"
        events = (await session.execute(select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "status_changed"))).scalars().all()
        assert len(events) == 2


async def test_admin_requester_confirmation_keeps_own_ticket_scope(test_client, test_engine):
    maker, ticket_id = await seed(test_engine, confirmation=True, requester="admin-test")
    async with maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.status = "resolved"
        ticket.requester_resolution_summary = "Выполнено"
        ticket.custom_fields = {**ticket.custom_fields, "resolution_confirmation": {"pending": True}}
        await session.commit()
    headers = headers_for(TEST_UI_ADMIN_TOKEN)
    detail = await test_client.get(f"/api/web/requester/tickets/{ticket_id}", headers=headers)
    assert detail.status == 200, await detail.text()
    assert (await detail.json())["data"]["ticket"]["actions"]["can_confirm_solution"] is True
    response = await test_client.post(f"/api/web/requester/tickets/{ticket_id}/close", headers=headers, json={})
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["ticket"]["status"] == "closed"
    async with maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.requester_id = "someone-else"
        ticket.status = "resolved"
        ticket.custom_fields = {"resolution_confirmation": {"pending": True}}
        await session.commit()
    denied = await test_client.post(f"/api/web/requester/tickets/{ticket_id}/close", headers=headers, json={})
    assert denied.status == 404


@pytest.mark.parametrize("action", ["message", "feedback", "reopen"])
async def test_admin_requester_mutations_preserve_owned_ticket_scope(test_client, test_engine, action):
    maker, ticket_id = await seed(test_engine, requester="admin-test")
    payload = {"message": {"message_id": str(uuid.uuid4()), "text": "Requester update"},
               "feedback": {"rating": 5, "problem_resolved": True},
               "reopen": {"reason_code": "problem_returned"}}[action]
    if action != "message":
        async with maker() as session:
            ticket = await session.get(Ticket, ticket_id)
            ticket.status = "resolved"
            ticket.resolved_at = datetime.now(timezone.utc)
            await session.commit()
    headers = headers_for(TEST_UI_ADMIN_TOKEN)
    response = await test_client.post(f"/api/web/requester/tickets/{ticket_id}/{action}", headers=headers, json=payload)
    assert response.status == 200, await response.text()
    async with maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.requester_id = "someone-else"
        await session.commit()
    denied = await test_client.post(f"/api/web/requester/tickets/{ticket_id}/{action}", headers=headers, json=payload)
    assert denied.status == 404, await denied.text()


async def test_confirmation_rechecks_requester_ownership_after_lock_wait(test_client, test_engine, monkeypatch):
    maker, ticket_id = await seed(test_engine, confirmation=True, requester="admin-test")
    async with maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.status = "resolved"
        ticket.custom_fields = {"resolution_confirmation": {"pending": True}}
        await session.commit()
    reached_lock = asyncio.Event()
    blocked_pid = None
    original_get = TicketEventsRepo.get_ticket

    async def observe_lock(repo, requested_id, **kwargs):
        nonlocal blocked_pid
        if requested_id == ticket_id and kwargs.get("for_update"):
            blocked_pid = await repo.session.scalar(text("SELECT pg_backend_pid()"))
            reached_lock.set()
        return await original_get(repo, requested_id, **kwargs)

    monkeypatch.setattr(TicketEventsRepo, "get_ticket", observe_lock)
    async with maker() as owner_change:
        blocker_pid = await owner_change.scalar(text("SELECT pg_backend_pid()"))
        ticket = await owner_change.get(Ticket, ticket_id, with_for_update=True)
        ticket.requester_id = "someone-else"
        request = asyncio.create_task(test_client.post(f"/api/web/requester/tickets/{ticket_id}/close",
            headers=headers_for(TEST_UI_ADMIN_TOKEN), json={}))
        try:
            await asyncio.wait_for(reached_lock.wait(), 10)
            await wait_for_backend_blocker(test_engine, blocked_pid=blocked_pid, blocker_pid=blocker_pid, task=request)
            await owner_change.commit()
            response = await asyncio.wait_for(request, 10)
            assert response.status == 404, await response.text()
        finally:
            if not request.done():
                request.cancel()
            await asyncio.gather(request, return_exceptions=True)
    async with maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "resolved" and ticket.requester_id == "someone-else"
        assert not (await session.execute(select(TicketEvent.id).where(TicketEvent.ticket_id == ticket_id))).all()
