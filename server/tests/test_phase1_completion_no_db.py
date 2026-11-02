from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tickets import workflow_service as workflow
from tickets.workflow_profiles import get_workflow_profile
from tickets.workflow_profiles import WorkflowTransitionGate
from dataclasses import replace
from tests.test_web_support_api import web_support_client
from tests.test_workflow_atomicity_no_db import mutations
from web_api import support_handlers as support
from web_api import requester_handlers as requester
from auth.context import AuthContext, AuthType
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from contextlib import asynccontextmanager
from app.api.serializers import ticket_to_dict

pytestmark = pytest.mark.no_db


@pytest.fixture
def completion(monkeypatch):
    ticket = SimpleNamespace(ticket_id="completion", device_id=None, status="in_progress",
                             assignee_id="support1", evidence_required=False, resolved_at=None,
                             resolution_at=None, custom_fields={"request_template": {"closure_policy": {
                                 "before_resolved": {"require_public_summary": True},
                                 "requester_confirmation": {"required": False},
                             }}})
    events = []

    async def event(**kwargs):
        events.append(kwargs["payload"])
        return SimpleNamespace()

    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket), add_event=event)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = workflow.TicketWorkflowService(session, repo)

    async def persist(**kwargs):
        ticket.status = kwargs["to_status"]
        for key, value in kwargs["updates"].items():
            setattr(ticket, key, value)

    monkeypatch.setattr(workflow, "load_ticket_workflow_profile", AsyncMock(return_value=get_workflow_profile("incident")))
    monkeypatch.setattr(service, "_apply_waiting_effects", AsyncMock())
    monkeypatch.setattr(service, "_apply_gate_actions", AsyncMock())
    monkeypatch.setattr(service, "_persist_transition_and_finalize", persist)
    return SimpleNamespace(service=service, ticket=ticket, session=session, events=events)


async def resolve(completion, **kwargs):
    return await completion.service.apply_status_transition(
        ticket_id="completion", from_status="in_progress", to_status="resolved",
        actor_id=kwargs.pop("actor_id", "support1"), actor_role="support",
        requester_resolution_summary=kwargs.pop("summary", "Проблема устранена"),
        close_after_resolve=True, **kwargs)


async def test_completion_records_both_canonical_transitions_without_committing(completion):
    result = await resolve(completion)
    assert completion.ticket.status == "closed"
    assert completion.ticket.requester_resolution_summary == "Проблема устранена"
    assert [(e["from_status"], e["to_status"], e["actor_id"]) for e in completion.events] == [
        ("in_progress", "resolved", "support1"), ("resolved", "closed", "support1")]
    assert result["updates"]["status"] == "closed"
    completion.session.commit.assert_not_awaited()


@pytest.mark.parametrize("failure", ["confirmation", "owner", "summary", "stale"])
async def test_completion_rejects_before_mutating(completion, failure):
    kwargs = {}
    if failure == "confirmation":
        completion.ticket.custom_fields["request_template"]["closure_policy"]["requester_confirmation"]["required"] = True
    elif failure == "owner":
        kwargs["actor_id"] = "different-support"
    elif failure == "summary":
        kwargs["summary"] = "  "
    else:
        completion.ticket.status = "closed"
    with pytest.raises(ValueError):
        await resolve(completion, **kwargs)
    assert completion.events == []
    completion.session.commit.assert_not_awaited()


@pytest.mark.parametrize("bad", ["true", 1, None])
async def test_status_rejects_non_boolean_completion_flag(web_support_client, mutations, bad):
    response = await web_support_client.post(f"/api/web/support/tickets/{mutations.ticket.ticket_id}/status",
                                            json={"to_status": "resolved", "close_after_resolve": bad})
    assert response.status == 400
    assert (await response.json())["error_code"] == "VALIDATION_ERROR"
    mutations.session.commit.assert_not_awaited()


async def test_failed_second_transition_rolls_back_before_response(web_support_client, mutations, monkeypatch):
    mutations.ticket.status = "in_progress"
    mutations.ticket.assignee_id = "support1"
    monkeypatch.setattr(support, "TicketWorkflowService", lambda *_: SimpleNamespace(
        apply_status_transition=AsyncMock(side_effect=ValueError("workflow_profile closure denied"))))
    response = await web_support_client.post(f"/api/web/support/tickets/{mutations.ticket.ticket_id}/status",
                                            json={"to_status": "resolved", "close_after_resolve": True,
                                                  "requester_resolution_summary": "Готово"})
    assert response.status == 400
    mutations.session.rollback.assert_awaited_once()
    mutations.session.commit.assert_not_awaited()
    mutations.pushed.assert_not_awaited()


@pytest.mark.parametrize("owned", [True, False])
async def test_admin_confirms_only_own_requester_ticket_under_lock(monkeypatch, owned):
    ticket = SimpleNamespace(ticket_id="owned", status="resolved", device_id=None,
                             requester_resolution_summary="Публичный результат", resolution_summary="internal secret",
                             custom_fields={"resolution_confirmation": {"pending": True}})
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    locks = []

    async def locked(ticket_id, **kwargs):
        locks.append(kwargs.get("for_update", False))
        return ticket

    async def get_owned(**kwargs):
        assert kwargs["actor_id"] == "admin-own-requester"
        return ticket if owned else None

    repo = SimpleNamespace(get_ticket=locked, update_ticket=AsyncMock(return_value=ticket))

    async def transition(**kwargs):
        assert kwargs["actor_id"] == "admin-own-requester"
        assert kwargs["actor_role"] == "requester"
        ticket.status = "closed"
        return {}

    @asynccontextmanager
    async def transaction():
        yield session

    monkeypatch.setattr(requester, "get_session", transaction)
    monkeypatch.setattr(requester, "RequesterIdentityResolver", lambda *a, **kw: SimpleNamespace(get_ticket=get_owned))
    monkeypatch.setattr(requester, "TicketEventsRepo", lambda *_: repo)
    monkeypatch.setattr(requester, "TicketWorkflowService", lambda *_: SimpleNamespace(apply_status_transition=transition))
    monkeypatch.setattr(requester, "_write_requester_web_observer_event", AsyncMock())
    monkeypatch.setattr(requester, "_push_ticket_event", AsyncMock())

    @web.middleware
    async def authenticated(request, handler):
        request["auth_context"] = AuthContext(actor_id="admin-own-requester", actor_role="admin",
                                              auth_type=AuthType.UI_TOKEN, token="synthetic")
        return await handler(request)

    app = web.Application(middlewares=[authenticated])
    app.router.add_post("/tickets/{ticket_id}/close", requester.handle_web_requester_ticket_close)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/tickets/owned/close", json={})
        assert response.status == (200 if owned else 404)
        if owned:
            payload = await response.json()
            assert payload["data"]["ticket"]["requester_resolution_summary"] == "Публичный результат"
            assert "internal secret" not in str(payload)
            assert True in locks
        else:
            session.commit.assert_not_awaited()


async def test_public_result_serialization_excludes_internal_summary(completion):
    await resolve(completion, resolution_summary="internal secret")
    payload = ticket_to_dict(completion.ticket, visibility="requester")
    assert payload["requester_resolution_summary"] == "Проблема устранена"
    assert "resolution_summary" not in payload


@pytest.mark.parametrize("special", [None, "confirmation", "code", "closing_gate", "resolution_gate", "owner"])
async def test_completion_capability_reflects_policy_and_ownership(completion, monkeypatch, special):
    profile = get_workflow_profile("incident")
    policy = completion.ticket.custom_fields["request_template"]["closure_policy"]
    if special == "confirmation":
        policy["requester_confirmation"]["required"] = True
    elif special == "code":
        policy["before_resolved"]["require_resolution_code"] = True
    elif special in {"closing_gate", "resolution_gate"}:
        source, target = ("resolved", "closed") if special == "closing_gate" else ("in_progress", "resolved")
        profile = replace(profile, transition_gates={source: {target: WorkflowTransitionGate(
            to_status=target, allowed_roles=("admin",))}})
    elif special == "owner":
        completion.ticket.assignee_id = "other"
    monkeypatch.setattr(support, "validate_transition_for_ticket", AsyncMock(return_value=True))
    monkeypatch.setattr(support, "load_ticket_workflow_profile", AsyncMock(return_value=profile))
    monkeypatch.setattr(support, "build_approval_summary", AsyncMock(return_value=None))
    actions = await support._build_support_status_actions(completion.session, completion.ticket, is_staff=True, actor_id="support1")
    assert actions.can_resolve_and_close is (special in {None, "code"})


@pytest.mark.parametrize("guard,met", [("approval", False), ("approval", True), ("legacy_evidence", False), ("legacy_evidence", True)])
async def test_completion_projection_matches_canonical_approval_and_legacy_evidence(completion, monkeypatch, guard, met):
    from copy import deepcopy

    if guard == "approval":
        completion.ticket.custom_fields["request_template"]["approval_policy"] = {"required": True}
        statuses = ["approved"] if met else ["requested"]
        completion.session.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: statuses)))
        error = "approval_policy requires approved approval"
    else:
        completion.ticket.evidence_required = True
        completion.session.scalar = AsyncMock(return_value=1 if met else None)
        error = "добавьте доказательство"
    before = deepcopy(completion.ticket.custom_fields)
    monkeypatch.setattr(support, "validate_transition_for_ticket", AsyncMock(return_value=True))
    monkeypatch.setattr(support, "load_ticket_workflow_profile", AsyncMock(return_value=get_workflow_profile("incident")))
    monkeypatch.setattr(support, "build_approval_summary", AsyncMock(return_value=None))
    actions = await support._build_support_status_actions(completion.session, completion.ticket, is_staff=True, actor_id="support1")
    assert actions.can_resolve_and_close is met
    assert completion.ticket.custom_fields == before
    assert completion.events == []
    completion.session.commit.assert_not_awaited()
    if met:
        await resolve(completion)
        assert completion.ticket.status == "closed"
    else:
        with pytest.raises(ValueError, match=error):
            await resolve(completion)
        assert completion.ticket.status == "in_progress"
        assert completion.events == []


@pytest.mark.parametrize("required", ["omitted", None, 0, False])
@pytest.mark.parametrize("surface", ["projection", "command"])
async def test_atomic_completion_requires_explicit_boolean_confirmation_opt_out(completion, monkeypatch, required, surface):
    confirmation = {"auto_close_after_days": 3}
    if required != "omitted":
        confirmation["required"] = required
    completion.ticket.custom_fields["request_template"]["closure_policy"]["requester_confirmation"] = confirmation
    monkeypatch.setattr(support, "validate_transition_for_ticket", AsyncMock(return_value=True))
    monkeypatch.setattr(support, "load_ticket_workflow_profile", AsyncMock(return_value=get_workflow_profile("incident")))
    monkeypatch.setattr(support, "build_approval_summary", AsyncMock(return_value=None))
    if surface == "projection":
        actions = await support._build_support_status_actions(completion.session, completion.ticket, is_staff=True, actor_id="support1")
        assert actions.can_resolve_and_close is (required is False)
        return
    if required is False:
        await resolve(completion)
        assert completion.ticket.status == "closed"
    else:
        with pytest.raises(ValueError, match="requester confirmation"):
            await resolve(completion)
        assert completion.ticket.status == "in_progress" and completion.events == []
