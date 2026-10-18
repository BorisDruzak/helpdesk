"""The admin requester workspace uses the authenticated owner's boundaries."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from auth.context import AuthContext, AuthType
from app.repos.request_scenario_session_repo import RequestScenarioSessionRepo, SessionAccessError
import web_api.requester_handlers as handlers

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [("user", 200), ("admin", 200), ("support", 403), ("auditor", 403)])
async def test_bootstrap_keeps_owner_identity_and_rejects_other_roles(monkeypatch, role, expected):
    @asynccontextmanager
    async def session():
        yield object()

    resolver = MagicMock()
    resolver.build_bootstrap = AsyncMock(return_value={"devices": [], "profile": None})
    monkeypatch.setattr(handlers, "get_session", session)
    monkeypatch.setattr(handlers, "RequesterIdentityResolver", MagicMock(return_value=resolver))
    monkeypatch.setattr("auth.middleware._write_web_auth_audit", AsyncMock())

    @web.middleware
    async def auth(request, handler):
        request["auth_context"] = AuthContext("own-login", role, AuthType.SESSION)
        return await handler(request)

    app = web.Application(middlewares=[auth])
    app.router.add_get("/api/web/requester/bootstrap", handlers.handle_web_requester_bootstrap)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/web/requester/bootstrap?actor_id=other-login")
        assert response.status == expected
    if expected == 200:
        resolver.build_bootstrap.assert_awaited_once_with(actor_id="own-login", state=None)
    else:
        resolver.build_bootstrap.assert_not_awaited()


@pytest.mark.parametrize("role", ["user", "admin"])
def test_scenario_repository_accepts_workspace_roles_without_changing_owner(role):
    repo = RequestScenarioSessionRepo(None, AuthContext("own-login", role, AuthType.SESSION))
    assert repo.owner == "own-login"


@pytest.mark.asyncio
async def test_admin_scenario_audit_preserves_authenticated_role(monkeypatch):
    from types import SimpleNamespace
    audit = AsyncMock()
    monkeypatch.setattr("app.repos.request_scenario_session_repo.ServiceCatalogRepo",
                        MagicMock(return_value=SimpleNamespace(append_audit=audit)))
    repo = RequestScenarioSessionRepo(None, AuthContext("own-login", "admin", AuthType.SESSION))
    row = SimpleNamespace(id="own-session", version_id="v1", current_block_id="q", revision=1, state="active")
    await repo._audit(row, "start")
    assert audit.await_args.kwargs["actor_role"] == "admin"
    assert audit.await_args.kwargs["actor_id"] == "own-login"


@pytest.mark.parametrize("role", ["support", "auditor", "agent", "system"])
def test_scenario_repository_still_rejects_non_requester_roles(role):
    with pytest.raises(SessionAccessError):
        RequestScenarioSessionRepo(None, AuthContext("own-login", role, AuthType.SESSION))


@pytest.mark.asyncio
@pytest.mark.parametrize("detail", [False, True])
async def test_admin_ticket_consent_reads_stay_owner_scoped(monkeypatch, detail):
    from types import SimpleNamespace
    database = MagicMock(commit=AsyncMock())

    @asynccontextmanager
    async def session():
        yield database

    resolver = MagicMock()
    resolver.resolve_person_for_web_user = AsyncMock(return_value=SimpleNamespace(person_id="own-person"))
    resolver.requester_external_ref.return_value = "own-person"
    service = MagicMock(list_for_requester=AsyncMock(return_value=[]), get_for_requester=AsyncMock(return_value=None))
    monkeypatch.setattr(handlers, "get_session", session)
    monkeypatch.setattr(handlers, "RequesterIdentityResolver", MagicMock(return_value=resolver))
    monkeypatch.setattr(handlers, "UserConsentService", MagicMock(return_value=service))
    monkeypatch.setattr("auth.middleware._write_web_auth_audit", AsyncMock())

    @web.middleware
    async def auth(request, handler):
        request["auth_context"] = AuthContext("own-login", "admin", AuthType.SESSION)
        return await handler(request)

    app = web.Application(middlewares=[auth])
    app.router.add_get("/api/web/requester/consents", handlers.handle_web_requester_consents)
    app.router.add_get("/api/web/requester/consents/{consent_id}", handlers.handle_web_requester_consent_detail)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/web/requester/consents" + ("/foreign-consent" if detail else "") + "?actor_id=other")
        assert response.status == (404 if detail else 200)
    resolver.resolve_person_for_web_user.assert_awaited_once_with("own-login")
    called = service.get_for_requester if detail else service.list_for_requester
    assert called.await_args.kwargs["requester_external_ref"] == "own-person"
    assert called.await_args.kwargs["requester_person_id"] == "own-person"


@pytest.mark.asyncio
@pytest.mark.parametrize("role,owned,status,policy_allowed,expected", [
    (None, True, "queued", True, 401),
    ("user", True, "queued", True, 200),
    ("admin", True, "queued", True, 200),
    ("admin", True, "waiting_on_user", True, 200),
    ("user", False, "queued", True, 404),
    ("admin", False, "queued", True, 404),
    ("support", True, "queued", True, 403),
    ("auditor", True, "queued", True, 403),
    ("user", True, "closed", True, 409),
    ("admin", True, "closed", True, 409),
    ("admin", True, "queued", False, 409),
])
async def test_requester_reply_keeps_workspace_owner_role_and_state_boundaries(
    monkeypatch, role, owned, status, policy_allowed, expected,
):
    database = SimpleNamespace(commit=AsyncMock())

    @asynccontextmanager
    async def session():
        yield database

    ticket = SimpleNamespace(ticket_id="own-ticket", device_id=None, status=status,
        requester_person_id="own-person", requester_binding_id=None, requester_account_mode="declared_profile",
        custom_fields={"requester_action_policy": {"can_send_message": policy_allowed}})
    resolver = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket if owned else None))
    repo = SimpleNamespace(add_event=AsyncMock(return_value=(101, 1)))
    workflow = SimpleNamespace(apply_triggered_transition=AsyncMock(return_value={
        "event_result": (102, 2), "event_payload": {"status": "assigned"}}))
    observer, push = AsyncMock(), AsyncMock()
    monkeypatch.setattr(handlers, "get_session", session)
    monkeypatch.setattr(handlers, "RequesterIdentityResolver", MagicMock(return_value=resolver))
    monkeypatch.setattr(handlers, "TicketEventsRepo", MagicMock(return_value=repo))
    monkeypatch.setattr(handlers, "TicketWorkflowService", MagicMock(return_value=workflow))
    monkeypatch.setattr(handlers, "_write_requester_web_observer_event", observer)
    monkeypatch.setattr(handlers, "_push_ticket_event", push)
    monkeypatch.setattr("auth.middleware._write_web_auth_audit", AsyncMock())

    @web.middleware
    async def auth(request, handler):
        if role is not None:
            request["auth_context"] = AuthContext("own-login", role, AuthType.SESSION)
        return await handler(request)

    app = web.Application(middlewares=[auth])
    app.router.add_post("/api/web/requester/tickets/{ticket_id}/message", handlers.handle_web_requester_ticket_message)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/web/requester/tickets/own-ticket/message?actor_id=other-login", json={
            "text": "Привет", "message_id": "owned-message", "actor_id": "other-login",
            "sender_role": "support", "visibility": "internal"})
        result = await response.json()
        assert response.status == expected, result

    if role in {"user", "admin"}:
        resolver.get_ticket.assert_awaited_once_with(actor_id="own-login", ticket_id="own-ticket")
    else:
        resolver.get_ticket.assert_not_awaited()
    if expected != 200:
        repo.add_event.assert_not_awaited()
        observer.assert_not_awaited()
        push.assert_not_awaited()
        workflow.apply_triggered_transition.assert_not_awaited()
        return

    payload = repo.add_event.await_args.kwargs["payload"]
    assert payload["sender_role"] == "user" and payload["from"] == "user"
    assert payload["sender_display_name"] == "own-login" and payload["visibility"] == "public"
    assert payload["text"] == "Привет" and payload["requester_person_id"] == "own-person"
    assert observer.await_args.kwargs["auth_context"].actor_id == "own-login"
    assert observer.await_args.kwargs["auth_context"].actor_role == role
    database.commit.assert_awaited_once()
    if status == "waiting_on_user":
        assert workflow.apply_triggered_transition.await_args.kwargs["trigger_actor_id"] == "own-login"
        assert workflow.apply_triggered_transition.await_args.kwargs["trigger_actor_role"] == role
    else:
        workflow.apply_triggered_transition.assert_not_awaited()
