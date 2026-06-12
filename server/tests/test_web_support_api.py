import uuid
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AccessGroup,
    AccessGroupMember,
    AccessGroupPermission,
    Artifact,
    Device,
    DeviceOutbox,
    Operation,
    Playbook,
    PlaybookStep,
    PlaybookVersion,
    HelpdeskPolicyAudit,
    RegistryAsset,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryService,
    ReportingPolicy,
    SupportQueueSavedView,
    Ticket,
    TicketApproval,
    TicketEvent,
    TicketNotification,
    UiUser,
    UserConsentRequest,
)
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.context import AuthContext, AuthType
from registry.registration_service import RegistrationService
from registry.service import RegistryIngestionService
from routes import setup_routes
from tickets.workflow_profiles import save_workflow_profiles
import web_api.support_handlers as support_handlers_module
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_AUDITOR_TOKEN, TEST_UI_SUPPORT_TOKEN
from tests.test_ticket_queue_routing_contracts import _seed_queue


@pytest.fixture
async def web_support_client():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="support1",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_support_bootstrap_exposes_observer_capabilities(web_support_client):
    response = await web_support_client.get("/api/web/support/bootstrap")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["workspace"] == "support"
    assert "observer_trace" in payload["data"]["features"]
    assert payload["data"]["observer"]["ticket_summary_endpoint"] == "/api/tickets/{ticket_id}/observer"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_web_support_queue_returns_empty_payload_when_db_is_unavailable(web_support_client, monkeypatch):
    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(support_handlers_module, "get_session", failing_session)

    response = await web_support_client.get("/api/web/support/queue?scope=all")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["visible_count"] == 0
    assert payload["data"]["summary"]["selected_ticket_id"] is None
    assert payload["data"]["tickets"] == []
    assert payload["data"]["filters"]["status_options"] == [{"value": "all", "label": "Все статусы"}]


@pytest.mark.asyncio
async def test_web_support_queue_mass_action_adds_internal_notes(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code=f"mass_note_{uuid.uuid4().hex[:8]}", name="Mass note", members=["support-test"])
        tickets = [
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id=f"device-mass-note-{index}",
                title=f"Mass note target {index}",
                description="bulk note target",
                status="queued",
                requester_id=f"user-mass-note-{index}",
                queue_id=queue.id,
            )
            for index in range(2)
        ]
        session.add_all(tickets)
        ticket_ids = [ticket.ticket_id for ticket in tickets]
        await session.commit()

    response = await test_client.post(
        "/api/web/support/queue/mass-action",
        headers=_support_headers(),
        json={
            "action": "internal_note",
            "ticket_ids": ticket_ids,
            "internal_note": "Проверили очередь массовым действием",
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["success_count"] == 2
    assert payload["data"]["error_count"] == 0

    async with session_maker() as session:
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id.in_(ticket_ids))
                .where(TicketEvent.event_type == "chat_message")
            )
        ).scalars().all()

    assert len(events) == 2
    assert {event.payload["visibility"] for event in events} == {"internal"}
    assert {event.payload["bulk_action"] for event in events} == {True}


@pytest.mark.asyncio
async def test_web_support_queue_mass_action_skips_inaccessible_ticket(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        visible_queue = await _seed_queue(session, code=f"mass_visible_{uuid.uuid4().hex[:8]}", name="Mass visible", members=["support-test"])
        hidden_queue = await _seed_queue(session, code=f"mass_hidden_{uuid.uuid4().hex[:8]}", name="Mass hidden", members=["other-support"])
        visible_ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-mass-visible",
            title="Visible mass target",
            description="visible",
            status="queued",
            requester_id="user-visible",
            queue_id=visible_queue.id,
        )
        hidden_ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-mass-hidden",
            title="Hidden mass target",
            description="hidden",
            status="queued",
            requester_id="user-hidden",
            queue_id=hidden_queue.id,
        )
        session.add_all([visible_ticket, hidden_ticket])
        visible_ticket_id = visible_ticket.ticket_id
        hidden_ticket_id = hidden_ticket.ticket_id
        await session.commit()

    response = await test_client.post(
            "/api/web/support/queue/mass-action",
            headers=_support_headers(),
            json={
                "action": "assign_self",
                "ticket_ids": [visible_ticket_id, hidden_ticket_id],
                "reason": "triage",
            },
        )

    assert response.status == 200, await response.text()
    payload = (await response.json())["data"]
    assert payload["success_count"] == 1
    assert payload["skipped_count"] == 1
    statuses = {item["ticket_id"]: item["status"] for item in payload["results"]}
    assert statuses[visible_ticket_id] == "success"
    assert statuses[hidden_ticket_id] == "skipped"


@pytest.mark.asyncio
async def test_web_support_queue_mass_action_priority_requires_reason(test_client):
    response = await test_client.post(
        "/api/web/support/queue/mass-action",
        headers=_support_headers(),
        json={"action": "change_priority", "ticket_ids": [str(uuid.uuid4())], "priority": "P1", "reason": ""},
    )

    assert response.status == 400
    payload = await response.json()
    assert payload["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_web_support_queue_saved_views_persist_personal_columns(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        await session.commit()

    response = await test_client.post(
        "/api/web/support/queue/saved-views",
        headers=_support_headers(),
        json={
            "name": "Morning triage",
            "scope": "personal",
            "filters": {"scope": "mine", "smartViewId": "sla_risk", "search": "printer", "showArchive": False},
            "columns": ["subject", "sla", "assignee"],
            "is_default": True,
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    view = payload["data"]
    assert view["owner_actor_id"] == "support-test"
    assert view["scope"] == "personal"
    assert view["is_default"] is True
    assert view["filters"]["smartViewId"] == "sla_risk"
    assert view["columns"] == ["number", "subject", "sla", "assignee"]

    response = await test_client.get("/api/web/support/queue/saved-views", headers=_support_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["default_view_id"] == view["id"]
    assert payload["data"]["default_columns"] == ["number", "subject", "sla", "assignee"]
    assert [item["id"] for item in payload["data"]["views"]] == [view["id"]]


@pytest.mark.asyncio
async def test_web_support_queue_saved_views_follow_queue_membership(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        visible_queue = await _seed_queue(session, code=f"saved_visible_{uuid.uuid4().hex[:8]}", name="Saved visible", members=["support-test"])
        hidden_queue = await _seed_queue(session, code=f"saved_hidden_{uuid.uuid4().hex[:8]}", name="Saved hidden", members=["other-support"])
        session.add_all(
            [
                SupportQueueSavedView(
                    id=str(uuid.uuid4()),
                    name="Visible queue view",
                    scope="queue",
                    queue_id=visible_queue.id,
                    filters_json={"scope": "all"},
                    columns_json=["number", "subject", "sla"],
                    sort_json=[],
                    is_favorite=False,
                    is_default=False,
                    created_by="lead",
                    updated_by="lead",
                ),
                SupportQueueSavedView(
                    id=str(uuid.uuid4()),
                    name="Hidden queue view",
                    scope="queue",
                    queue_id=hidden_queue.id,
                    filters_json={"scope": "all"},
                    columns_json=["number", "subject", "sla"],
                    sort_json=[],
                    is_favorite=False,
                    is_default=False,
                    created_by="lead",
                    updated_by="lead",
                ),
            ]
        )
        await session.commit()

    response = await test_client.get("/api/web/support/queue/saved-views", headers=_support_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()
    names = {item["name"] for item in payload["data"]["views"]}
    assert "Visible queue view" in names
    assert "Hidden queue view" not in names


@pytest.mark.asyncio
async def test_web_support_queue_saved_view_global_scope_requires_admin(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        await session.commit()

    response = await test_client.post(
        "/api/web/support/queue/saved-views",
        headers=_support_headers(),
        json={"name": "Global triage", "scope": "global", "columns": ["number", "subject"]},
    )

    assert response.status == 403
    payload = await response.json()
    assert payload["error_code"] == "FORBIDDEN"


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_AUDITOR_TOKEN}"}


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


async def _seed_support_ticket(
    test_engine,
    *,
    device_id: str = "device-rbac",
    status: str = "in_progress",
) -> str:
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="auditor-test", password_hash="test", actor_role="auditor", is_active=True),
        ])
        queue = await _seed_queue(session, code=f"rbac_{uuid.uuid4().hex[:8]}", name="RBAC queue", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=device_id,
            title="RBAC protected ticket action",
            description="Ticket write endpoint must check effective permissions.",
            status=status,
            requester_id="user-rbac",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()
        return ticket_id


async def _grant_auditor_permissions(test_engine, permissions: list[str]) -> None:
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        group = AccessGroup(
            code=f"rbac_grant_{uuid.uuid4().hex[:8]}",
            name="RBAC test grant",
            description=None,
            is_active=True,
        )
        session.add(group)
        await session.flush()
        session.add(AccessGroupMember(group_id=group.id, actor_id="auditor-test"))
        for permission in permissions:
            session.add(AccessGroupPermission(group_id=group.id, permission_code=permission))
        await session.commit()


async def _assert_forbidden_permission(response, permission: str) -> dict:
    assert response.status == 403, await response.text()
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "FORBIDDEN"
    assert payload["required_permission"] == permission
    assert permission in payload["error"]
    return payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("visibility", "permission"),
    [
        ("public", "ticket.comment.public"),
        ("internal", "ticket.comment.internal"),
    ],
)
async def test_web_support_message_action_requires_comment_permission(
    test_client,
    test_engine,
    visibility,
    permission,
):
    ticket_id = await _seed_support_ticket(test_engine)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/messages",
        headers=_auditor_headers(),
        json={"text": "permission probe", "visibility": visibility},
    )

    await _assert_forbidden_permission(response, permission)


@pytest.mark.asyncio
async def test_web_support_status_action_requires_status_permission(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine, status="new")

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/status",
        headers=_auditor_headers(),
        json={"to_status": "in_progress", "reason": "permission probe"},
    )

    await _assert_forbidden_permission(response, "ticket.status.change")


@pytest.mark.asyncio
async def test_web_support_worklog_action_uses_web_support_boundary(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/worklogs",
        headers=_support_headers(),
        json={"spent_minutes": 7, "note": "Typed support worklog"},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["worklog"]["ticket_id"] == ticket_id
    assert payload["worklog"]["actor_id"] == "support-test"
    assert payload["worklog"]["spent_minutes"] == 7
    assert payload["worklog"]["note"] == "Typed support worklog"

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        rows = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "worklog_added")
            )
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].payload["spent_minutes"] == 7


@pytest.mark.asyncio
async def test_web_support_lifecycle_event_uses_existing_ticket_root_trace(test_client, test_engine):
    root_trace_id = str(uuid.uuid4())
    ticket_id = await _seed_support_ticket(test_engine)

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()
        ticket.observer_root_trace_id = root_trace_id
        await session.commit()

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/worklogs",
        headers=_support_headers(),
        json={"spent_minutes": 11, "note": "Observer trace continuity"},
    )

    assert response.status == 200, await response.text()

    async with session_maker() as session:
        event = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "worklog_added")
            )
        ).scalar_one()

    assert event.trace_id == root_trace_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "body", "permission"),
    [
        ("assign", {"assignee_id": "support-test"}, "ticket.assign"),
        ("queue", {"queue_id": 1, "reason": "permission_probe"}, "ticket.queue.change"),
        ("priority", {"priority": "P1", "reason": "permission_probe"}, "ticket.status.change"),
        ("reroute", {"reason": "manual_recalculate"}, "ticket.queue.change"),
    ],
)
async def test_web_support_ticket_mutation_aliases_require_permissions(
    test_client,
    test_engine,
    endpoint,
    body,
    permission,
):
    ticket_id = await _seed_support_ticket(test_engine, status="new")

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/{endpoint}",
        headers=_auditor_headers(),
        json=body,
    )

    await _assert_forbidden_permission(response, permission)


@pytest.mark.asyncio
async def test_web_support_passport_mutations_require_manage_permission(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/generate",
        headers=_auditor_headers(),
        json={"mode": "create"},
    )

    await _assert_forbidden_permission(response, "ticket.passport.manage")


@pytest.mark.asyncio
async def test_web_support_passport_payload_exposes_reporting_requirements(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine, status="in_progress")
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        from sqlalchemy import delete

        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "reporting_policies"))
        await session.execute(delete(ReportingPolicy))
        ticket = await session.get(Ticket, ticket_id)
        ticket.custom_fields = {
            "request_template": {
                "key": "website_unavailable",
                "ticket_type": "incident",
                "reporting_policy": {
                    "required_sections": ["problem", "evidence", "user_result"],
                    "export_visibility": {"hide_sections": ["internal_result"]},
                    "require_official_passport": True,
                },
            }
        }
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/passport",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    requirements = payload["data"]["requirements"]
    assert requirements["require_official_passport"] is True
    assert requirements["blocking_missing_count"] == 2
    assert requirements["export_preview"]["hidden_sections"] == ["internal_result"]
    missing_by_key = {item["required_fact"]: item for item in requirements["missing_facts"]}
    assert missing_by_key["evidence"]["requester_visible_label"] == "Доказательство решения"
    assert missing_by_key["user_result"]["source"] == "ticket.requester_resolution_summary"


@pytest.mark.asyncio
async def test_web_support_playbook_action_requires_run_permission(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        playbook = Playbook(key="rbac.playbook", name="RBAC playbook", domain="diagnostics")
        session.add(playbook)
        await session.flush()
        version = PlaybookVersion(
            playbook_id=playbook.id,
            version="1.0.0",
            status="published",
            manifest_json={},
            published_at=datetime.now(timezone.utc),
        )
        session.add(version)
        await session.flush()
        version_id = version.id
        await session.commit()
    ticket_id = await _seed_support_ticket(test_engine, device_id="device-rbac-playbook")

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/playbooks/run",
        headers=_auditor_headers(),
        json={"playbook_version_id": version_id},
    )

    await _assert_forbidden_permission(response, "ticket.playbook.run")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("risk_level", "permission"),
    [
        ("safe_read", "ticket.tool.run"),
        ("system_write", "ticket.tool.run"),
    ],
)
async def test_web_support_tool_action_requires_base_run_permission(
    test_client,
    test_engine,
    monkeypatch,
    risk_level,
    permission,
):
    ticket_id = await _seed_support_ticket(test_engine, device_id="device-rbac-tool")

    class FakeToolExecutionService:
        def __init__(self, _state):
            pass

        async def get_tools_list(self, device_id):
            return [{"tool": "rbac.probe", "spec": {"risk_level": risk_level}}]

        async def get_tools_from_server(self, device_id):
            return []

        async def run_tool(self, **_kwargs):
            raise AssertionError("run_tool must not be dispatched without permission")

    monkeypatch.setattr(support_handlers_module, "ToolExecutionService", FakeToolExecutionService)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/tools/run",
        headers=_auditor_headers(),
        json={"tool_name": "rbac.probe", "params": {}},
    )

    await _assert_forbidden_permission(response, permission)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("risk_level", "granted_permissions", "required_permission"),
    [
        ("safe_read", ["ticket.tool.run"], "module.tool.run.low_risk"),
        (
            "system_write",
            ["ticket.tool.run", "module.tool.run.low_risk"],
            "module.tool.run.high_risk",
        ),
    ],
)
async def test_web_support_tool_action_requires_risk_permission(
    test_client,
    test_engine,
    monkeypatch,
    risk_level,
    granted_permissions,
    required_permission,
):
    ticket_id = await _seed_support_ticket(test_engine, device_id="device-rbac-tool-risk")
    await _grant_auditor_permissions(test_engine, granted_permissions)

    class FakeToolExecutionService:
        def __init__(self, _state):
            pass

        async def get_tools_list(self, device_id):
            return [{"tool": "rbac.probe", "spec": {"risk_level": risk_level}}]

        async def get_tools_from_server(self, device_id):
            return []

        async def run_tool(self, **_kwargs):
            raise AssertionError("run_tool must not be dispatched without risk permission")

    monkeypatch.setattr(support_handlers_module, "ToolExecutionService", FakeToolExecutionService)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/tools/run",
        headers=_auditor_headers(),
        json={"tool_name": "rbac.probe", "params": {}},
    )

    await _assert_forbidden_permission(response, required_permission)


@pytest.mark.asyncio
async def test_web_support_queue_returns_typed_scope_and_filter_payload(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_a", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_b", password_hash="test", actor_role="support", is_active=True),
        ])
        queue_a = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test", "op_a"])
        queue_b = await _seed_queue(session, code="network", name="Network", members=["op_b"])
        session.add_all([
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-visible",
                title="Visible by queue",
                description="Queue member should see this",
                status="new",
                requester_id="user-a",
                queue_id=queue_a.id,
                priority="P2",
                custom_fields={"priority_class": "P2"},
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-assigned",
                title="Visible by assignee",
                description="Assigned ticket stays visible",
                status="in_progress",
                requester_id="user-b",
                queue_id=queue_b.id,
                assignee_id="support-test",
                priority="P1",
                custom_fields={"priority_class": "P1"},
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-hidden",
                title="Hidden by queue",
                description="Different queue should stay hidden",
                status="new",
                requester_id="user-c",
                queue_id=queue_b.id,
            ),
        ])
        await session.commit()

    response = await test_client.get("/api/web/support/queue?scope=all&query=visible", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["scope"] == "all"
    assert payload["data"]["summary"]["visible_count"] == 2
    assert payload["data"]["summary"]["selected_ticket_id"] is not None
    ticket_titles = [item["title"] for item in payload["data"]["tickets"]]
    assert ticket_titles == ["Visible by assignee", "Visible by queue"]
    tickets_by_title = {item["title"]: item for item in payload["data"]["tickets"]}
    assert tickets_by_title["Visible by assignee"]["priority"] == "P1"
    assert tickets_by_title["Visible by assignee"]["priority_class"] == "P1"
    assert tickets_by_title["Visible by assignee"]["assignee_display_name"] == "support-test"
    assert tickets_by_title["Visible by queue"]["priority"] == "P2"
    assert tickets_by_title["Visible by queue"]["priority_class"] == "P2"
    assert tickets_by_title["Visible by queue"]["assignee_display_name"] is None
    queue_counts = {item["code"]: item for item in payload["data"]["summary"]["queue_counts"]}
    assert queue_counts["servicedesk_l1"]["name"] == "ServiceDesk L1"
    assert queue_counts["servicedesk_l1"]["count"] == 1
    assert queue_counts["network"]["name"] == "Network"
    assert queue_counts["network"]["count"] == 1
    assert {item["value"] for item in payload["data"]["filters"]["status_options"]} >= {"all", "in_progress", "new"}

    mine_response = await test_client.get("/api/web/support/queue?scope=mine", headers=_support_headers())
    assert mine_response.status == 200, await mine_response.text()
    mine_payload = await mine_response.json()

    assert mine_payload["data"]["scope"] == "mine"
    assert [item["title"] for item in mine_payload["data"]["tickets"]] == ["Visible by assignee"]


@pytest.mark.asyncio
async def test_web_support_workspace_summary_returns_view_and_queue_counts_without_rows(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_b", password_hash="test", actor_role="support", is_active=True),
        ])
        queue_l1 = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        queue_network = await _seed_queue(session, code="networks", name="Сети", members=["support-test", "op_b"])
        queue_other = await _seed_queue(session, code="other_team", name="Other team", members=["op_b"])
        requester_reply_ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-summary-reply",
            title="Summary requester replied",
            description="Unread user reply should be counted",
            status="in_progress",
            requester_id="summary-user-reply",
            queue_id=queue_l1.id,
            assignee_id="support-test",
            first_response_due_at=now + timedelta(minutes=10),
        )
        session.add_all([
            requester_reply_ticket,
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-summary-unassigned",
                title="Summary unassigned",
                description="Unassigned queue row should be counted",
                status="queued",
                requester_id="summary-user-unassigned",
                queue_id=queue_network.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-summary-hidden",
                title="Summary hidden",
                description="Different queue member should stay hidden",
                status="new",
                requester_id="summary-user-hidden",
                queue_id=queue_other.id,
                assignee_id="op_b",
            ),
        ])
        await session.flush()
        await TicketEventsRepo(session).add_event(
            ticket_id=requester_reply_ticket.ticket_id,
            device_id=requester_reply_ticket.device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={
                "message_id": "msg-summary-user-1",
                "sender_role": "user",
                "from": "user",
                "text": "Пользователь ответил.",
                "visibility": "public",
            },
            trace_id=str(uuid.uuid4()),
            event_id="msg-summary-user-1",
        )
        await session.commit()

    response = await test_client.get("/api/web/support/workspace/summary", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    data = payload["data"]
    assert "tickets" not in data
    assert data["views"]["needs_action"] >= 1
    assert data["views"]["sla_risk"] == 1
    assert data["views"]["unassigned"] == 1
    assert data["views"]["requester_replied"] == 1
    queues = {item["id"]: item for item in data["queues"]}
    assert queues["servicedesk_l1"]["name"] == "ServiceDesk L1"
    assert queues["servicedesk_l1"]["count"] == 1
    assert queues["networks"]["name"] == "Сети"
    assert queues["networks"]["count"] == 1
    assert {item["value"] for item in data["smart_view_counts"]} >= {"my_action", "sla_risk", "unassigned", "requester_reply"}


@pytest.mark.asyncio
async def test_web_support_workspace_hides_internal_navigation_noise_without_hiding_tickets(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        visible_queue = await _seed_queue(
            session,
            code="servicedesk_l1",
            name="ServiceDesk L1",
            members=["support-test"],
        )
        noisy_queue = await _seed_queue(
            session,
            code="stage27_workspace_noise",
            name="Stage 27 workspace noise",
            members=["support-test"],
        )
        live_queue = await _seed_queue(
            session,
            code="live_network_1777437448",
            name="Live Network 1777437448",
            members=["support-test"],
        )
        test_queue = await _seed_queue(
            session,
            code="servicedesk_test",
            name="ServiceDesk Test",
            members=["support-test"],
        )
        session.add_all([
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-visible-workspace-nav",
                title="Normal workspace ticket",
                description="Normal queue should remain in navigation",
                status="new",
                requester_id="nav-normal-user",
                queue_id=visible_queue.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-stage27-workspace-nav",
                title="Stage 27 workspace ticket",
                description="Internal queue ticket should remain accessible by search",
                status="new",
                requester_id="nav-stage-user",
                queue_id=noisy_queue.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-live-workspace-nav",
                title="Live workspace ticket",
                description="Live smoke queue ticket should remain accessible by search",
                status="new",
                requester_id="nav-live-user",
                queue_id=live_queue.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-test-workspace-nav",
                title="ServiceDesk test workspace ticket",
                description="Test queue ticket should remain accessible by search",
                status="new",
                requester_id="nav-test-user",
                queue_id=test_queue.id,
            ),
        ])
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_smart_view(
            code="stage27_custom_deadline_noise",
            title="Stage27 custom deadline noise",
            filter_config={"status_not_in": ["closed", "canceled"]},
            sort=[{"field": "updated_at", "direction": "desc"}],
            columns=["ticket_id", "title"],
            actor_id="admin",
            actor_role="admin",
        )
        await session.commit()

    summary_response = await test_client.get("/api/web/support/workspace/summary", headers=_support_headers())
    assert summary_response.status == 200, await summary_response.text()
    summary_payload = await summary_response.json()
    summary_data = summary_payload["data"]

    assert "servicedesk_l1" in {item["id"] for item in summary_data["queues"]}
    queue_ids = {item["id"] for item in summary_data["queues"]}
    assert "stage27_workspace_noise" not in queue_ids
    assert "live_network_1777437448" not in queue_ids
    assert "servicedesk_test" not in queue_ids
    assert "stage27_custom_deadline_noise" not in {item["value"] for item in summary_data["smart_view_counts"]}
    assert "stage27_custom_deadline_noise" not in {item["value"] for item in summary_data["smart_view_options"]}

    queue_response = await test_client.get(
        "/api/web/support/queue?scope=all&query=Stage%2027",
        headers=_support_headers(),
    )
    assert queue_response.status == 200, await queue_response.text()
    queue_payload = await queue_response.json()
    queue_data = queue_payload["data"]

    assert [item["title"] for item in queue_data["tickets"]] == ["Stage 27 workspace ticket"]
    assert "stage27_workspace_noise" not in {
        item["code"] for item in queue_data["summary"]["queue_counts"]
    }
    assert "stage27_custom_deadline_noise" not in {
        item["value"] for item in queue_data["filters"]["smart_view_options"]
    }

    live_response = await test_client.get(
        "/api/web/support/queue?scope=all&query=Live%20workspace",
        headers=_support_headers(),
    )
    assert live_response.status == 200, await live_response.text()
    live_payload = await live_response.json()
    assert [item["title"] for item in live_payload["data"]["tickets"]] == ["Live workspace ticket"]
    assert "live_network_1777437448" not in {
        item["code"] for item in live_payload["data"]["summary"]["queue_counts"]
    }


@pytest.mark.asyncio
async def test_web_support_hide_removes_ticket_from_queue_but_direct_workspace_marks_hidden(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="hide_contract", name="Hide contract", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-hide-contract",
            title="Hide workspace contract",
            description="Hidden support ticket must leave active worklists.",
            status="new",
            requester_id="hide-contract-user",
            queue_id=queue.id,
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    before = await test_client.get(
        "/api/web/support/queue?scope=all&query=Hide%20workspace%20contract",
        headers=_support_headers(),
    )
    assert before.status == 200, await before.text()
    before_payload = await before.json()
    assert [item["ticket_id"] for item in before_payload["data"]["tickets"]] == [ticket_id]

    hide_response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/hide",
        headers=_support_headers(),
        json={"reason": "live workspace cleanup"},
    )
    assert hide_response.status == 200, await hide_response.text()
    hide_payload = await hide_response.json()
    assert hide_payload["status"] == "success"
    assert hide_payload["data"]["hidden_from_workspace"] is True
    assert hide_payload["data"]["hidden_reason"] == "live workspace cleanup"

    hidden_default = await test_client.get(
        "/api/web/support/queue?scope=all&query=Hide%20workspace%20contract",
        headers=_support_headers(),
    )
    assert hidden_default.status == 200, await hidden_default.text()
    hidden_default_payload = await hidden_default.json()
    assert hidden_default_payload["data"]["tickets"] == []

    hidden_included = await test_client.get(
        "/api/web/support/queue?scope=all&query=Hide%20workspace%20contract&include_hidden=1",
        headers=_support_headers(),
    )
    assert hidden_included.status == 200, await hidden_included.text()
    hidden_included_payload = await hidden_included.json()
    assert hidden_included_payload["data"]["tickets"][0]["ticket_id"] == ticket_id
    assert hidden_included_payload["data"]["tickets"][0]["hidden_from_workspace"] is True

    detail_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/workspace",
        headers=_support_headers(),
    )
    assert detail_response.status == 200, await detail_response.text()
    detail_payload = await detail_response.json()
    assert detail_payload["data"]["detail"]["ticket"]["hidden_from_workspace"] is True
    assert detail_payload["data"]["detail"]["ticket"]["hidden_reason"] == "live workspace cleanup"

    async with session_maker() as session:
        event = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "ticket_hidden_from_workspace")
            )
        ).scalar_one()
    assert event.payload["reason"] == "live workspace cleanup"


@pytest.mark.asyncio
async def test_web_support_archive_is_admin_only_and_requires_show_archive_toggle(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="archive_contract", name="Archive contract", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-archive-contract",
            title="Archive workspace contract",
            description="Archived tickets are excluded until explicitly requested.",
            status="closed",
            requester_id="archive-contract-user",
            queue_id=queue.id,
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    denied = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/archive",
        headers=_support_headers(),
        json={"reason": "archive requires admin"},
    )
    await _assert_forbidden_permission(denied, "ticket.archive.manage")

    archive_response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/archive",
        headers=_admin_headers(),
        json={"reason": "resolved and verified"},
    )
    assert archive_response.status == 200, await archive_response.text()
    archive_payload = await archive_response.json()
    assert archive_payload["data"]["archived_at"] is not None
    assert archive_payload["data"]["archive_reason"] == "resolved and verified"

    default_queue = await test_client.get(
        "/api/web/support/queue?scope=all&query=Archive%20workspace%20contract",
        headers=_support_headers(),
    )
    assert default_queue.status == 200, await default_queue.text()
    default_payload = await default_queue.json()
    assert default_payload["data"]["tickets"] == []

    archive_queue = await test_client.get(
        "/api/web/support/queue?scope=all&query=Archive%20workspace%20contract&include_archived=1",
        headers=_support_headers(),
    )
    assert archive_queue.status == 200, await archive_queue.text()
    archive_queue_payload = await archive_queue.json()
    assert archive_queue_payload["data"]["tickets"][0]["ticket_id"] == ticket_id
    assert archive_queue_payload["data"]["tickets"][0]["archived_at"] is not None

    detail_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/workspace",
        headers=_support_headers(),
    )
    assert detail_response.status == 200, await detail_response.text()
    detail_payload = await detail_response.json()
    assert detail_payload["data"]["detail"]["ticket"]["archived_at"] is not None

    unarchive_response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/unarchive",
        headers=_admin_headers(),
        json={"reason": "returned to active work"},
    )
    assert unarchive_response.status == 200, await unarchive_response.text()
    unarchive_payload = await unarchive_response.json()
    assert unarchive_payload["data"]["archived_at"] is None


@pytest.mark.asyncio
async def test_web_support_cleanup_noise_hides_obvious_live_stage_test_tickets(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        tickets = [
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-cleanup-normal",
                title="Normal user printer outage",
                description="Real ticket stays visible.",
                status="new",
                requester_id="cleanup-normal-user",
                queue_id=queue.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-cleanup-live",
                title="Live workspace ticket",
                description="Generated live check row.",
                status="new",
                requester_id="cleanup-live-user",
                queue_id=queue.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-cleanup-stage",
                title="Stage 27 workspace ticket",
                description="Generated stage check row.",
                status="new",
                requester_id="cleanup-stage-user",
                queue_id=queue.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-cleanup-test",
                title="ServiceDesk test workspace ticket",
                description="Generated test check row.",
                status="new",
                requester_id="cleanup-test-user",
                queue_id=queue.id,
            ),
        ]
        session.add_all(tickets)
        expected_hidden_ids = {tickets[1].ticket_id, tickets[2].ticket_id, tickets[3].ticket_id}
        await session.commit()

    cleanup_response = await test_client.post(
        "/api/web/support/workspace/cleanup-noise",
        headers=_support_headers(),
        json={"reason": "manual live/stage/test cleanup"},
    )
    assert cleanup_response.status == 200, await cleanup_response.text()
    cleanup_payload = await cleanup_response.json()
    assert cleanup_payload["data"]["hidden_count"] == 3
    assert set(cleanup_payload["data"]["hidden_ticket_ids"]) == expected_hidden_ids

    active_response = await test_client.get("/api/web/support/queue?scope=all&query=workspace", headers=_support_headers())
    assert active_response.status == 200, await active_response.text()
    active_payload = await active_response.json()
    assert active_payload["data"]["tickets"] == []

    all_response = await test_client.get(
        "/api/web/support/queue?scope=all&query=workspace&include_hidden=1",
        headers=_support_headers(),
    )
    assert all_response.status == 200, await all_response.text()
    all_payload = await all_response.json()
    assert {item["ticket_id"] for item in all_payload["data"]["tickets"]} == expected_hidden_ids


@pytest.mark.asyncio
async def test_web_support_queue_applies_smart_view_sla_risk(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="smart_sla", name="Smart SLA", members=["support-test"])
        session.add_all([
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-sla-risk",
                title="SLA risk visible",
                description="Due soon ticket should be in smart view",
                status="in_progress",
                requester_id="user-sla-risk",
                queue_id=queue.id,
                first_response_due_at=now + timedelta(minutes=30),
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-sla-later",
                title="SLA later hidden",
                description="Far deadline should stay outside smart view",
                status="in_progress",
                requester_id="user-sla-later",
                queue_id=queue.id,
                first_response_due_at=now + timedelta(days=2),
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-sla-closed",
                title="Closed SLA hidden",
                description="Terminal tickets should stay outside risk views",
                status="closed",
                requester_id="user-sla-closed",
                queue_id=queue.id,
                first_response_due_at=now + timedelta(minutes=10),
            ),
        ])
        await session.commit()

    response = await test_client.get("/api/web/support/queue?scope=all&smart_view=sla_risk", headers=_support_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["smart_view"] == "sla_risk"
    assert [item["title"] for item in payload["data"]["tickets"]] == ["SLA risk visible"]
    smart_view_options = payload["data"]["filters"]["smart_view_options"]
    assert {"value": "sla_risk", "label": "Риск по сроку ответа"} in smart_view_options


@pytest.mark.asyncio
async def test_web_support_queue_surfaces_ola_risk_smart_view_count(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="smart_ola", name="Smart OLA", members=["support-test"])
        session.add_all([
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-ola-risk",
                title="OLA risk visible",
                description="Queue deadline should be in smart view",
                status="in_progress",
                requester_id="user-ola-risk",
                queue_id=queue.id,
                ola_ack_due_at=now + timedelta(minutes=30),
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-ola-later",
                title="OLA later hidden",
                description="Far OLA deadline should stay outside risk view",
                status="in_progress",
                requester_id="user-ola-later",
                queue_id=queue.id,
                ola_ack_due_at=now + timedelta(days=2),
            ),
        ])
        await session.commit()

    response = await test_client.get("/api/web/support/queue?scope=all&smart_view=ola_risk", headers=_support_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["smart_view"] == "ola_risk"
    assert [item["title"] for item in payload["data"]["tickets"]] == ["OLA risk visible"]
    smart_view_options = payload["data"]["filters"]["smart_view_options"]
    assert {"value": "ola_risk", "label": "Риск внутренней очереди"} in smart_view_options
    smart_view_counts = {item["value"]: item["count"] for item in payload["data"]["summary"]["smart_view_counts"]}
    assert smart_view_counts["ola_risk"] == 1


@pytest.mark.asyncio
async def test_web_support_queue_applies_mass_incident_candidates_smart_view(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="smart_mass", name="Smart mass", members=["support-test"])
        session.add_all([
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-mass-candidate",
                title="Mass incident candidate visible",
                description="Tagged ticket should be in mass incident candidates",
                status="in_progress",
                requester_id="user-mass-candidate",
                queue_id=queue.id,
                tags=["mass_incident_candidate"],
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-mass-field",
                title="Mass incident field visible",
                description="Policy fact should be in mass incident candidates",
                status="queued",
                requester_id="user-mass-field",
                queue_id=queue.id,
                custom_fields={"mass_incident_detected": True},
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-mass-normal",
                title="Normal ticket hidden",
                description="Ticket without mass signal should stay outside smart view",
                status="in_progress",
                requester_id="user-mass-normal",
                queue_id=queue.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-mass-closed",
                title="Closed mass hidden",
                description="Terminal mass ticket should stay outside smart view",
                status="closed",
                requester_id="user-mass-closed",
                queue_id=queue.id,
                tags=["mass_incident_candidate"],
            ),
        ])
        await session.commit()

    response = await test_client.get(
        "/api/web/support/queue?scope=all&smart_view=mass_incident_candidates",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["smart_view"] == "mass_incident_candidates"
    assert {item["title"] for item in payload["data"]["tickets"]} == {
        "Mass incident candidate visible",
        "Mass incident field visible",
    }
    assert {
        "value": "mass_incident_candidates",
        "label": "Похожие массовые обращения",
    } in payload["data"]["filters"]["smart_view_options"]
    smart_view_counts = {item["value"]: item["count"] for item in payload["data"]["summary"]["smart_view_counts"]}
    assert smart_view_counts["mass_incident_candidates"] == 2


@pytest.mark.asyncio
async def test_web_support_queue_applies_published_custom_smart_view(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="custom_deadline", name="Custom deadline", members=["support-test"])
        session.add_all([
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-custom-risk",
                title="Custom deadline visible early",
                description="Published smart view should include this ticket",
                status="in_progress",
                requester_id="user-custom-risk",
                queue_id=queue.id,
                first_response_due_at=now + timedelta(minutes=45),
                updated_at=now - timedelta(minutes=5),
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-custom-risk-later",
                title="Custom deadline visible later",
                description="Published smart view should sort this after the earlier deadline",
                status="in_progress",
                requester_id="user-custom-risk-later",
                queue_id=queue.id,
                first_response_due_at=now + timedelta(minutes=90),
                updated_at=now,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-custom-later",
                title="Custom deadline hidden",
                description="Far deadline should stay outside custom smart view",
                status="in_progress",
                requester_id="user-custom-later",
                queue_id=queue.id,
                first_response_due_at=now + timedelta(days=1),
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-custom-closed",
                title="Custom closed hidden",
                description="Terminal ticket should stay outside custom smart view",
                status="closed",
                requester_id="user-custom-closed",
                queue_id=queue.id,
                first_response_due_at=now + timedelta(minutes=10),
            ),
        ])
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_smart_view(
            code="custom_answer_deadline",
            title="Проверка срока ответа",
            filter_config={
                "status_not_in": ["closed", "canceled"],
                "due_before_hours": 2,
                "due_fields": ["first_response_due_at"],
            },
            sort=[{"field": "first_response_due_at", "direction": "asc"}],
            columns=["ticket_id", "title", "first_response_due_at"],
            actor_id="admin",
            actor_role="admin",
        )
        await session.commit()

    response = await test_client.get(
        "/api/web/support/queue?scope=all&smart_view=custom_answer_deadline",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["smart_view"] == "custom_answer_deadline"
    assert [item["title"] for item in payload["data"]["tickets"]] == [
        "Custom deadline visible early",
        "Custom deadline visible later",
    ]
    assert {"value": "custom_answer_deadline", "label": "Проверка срока ответа"} in payload["data"]["filters"]["smart_view_options"]


@pytest.mark.asyncio
async def test_web_support_queue_counts_all_target_smart_views(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="smart_all", name="Smart all", members=["support-test"])
        tickets = [
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-sla",
                title="Count SLA risk",
                description="SLA deadline should be counted",
                status="in_progress",
                requester_id="user-count-sla",
                queue_id=queue.id,
                assignee_id="support-test",
                first_response_due_at=now + timedelta(minutes=20),
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-ola",
                title="Count OLA risk",
                description="OLA deadline should be counted",
                status="assigned",
                requester_id="user-count-ola",
                queue_id=queue.id,
                assignee_id="support-test",
                ola_processing_due_at=now + timedelta(minutes=40),
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-unassigned",
                title="Count unassigned",
                description="Open ticket without assignee should be counted",
                status="queued",
                requester_id="user-count-unassigned",
                queue_id=queue.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-approval",
                title="Count waiting approval",
                description="Approval wait should be counted",
                status="waiting_on_approval",
                requester_id="user-count-approval",
                queue_id=queue.id,
                assignee_id="support-test",
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-stale",
                title="Count stale waiting",
                description="Old waiting ticket should be counted",
                status="waiting_on_user",
                requester_id="user-count-stale",
                queue_id=queue.id,
                assignee_id="support-test",
                updated_at=now - timedelta(days=4),
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-diagnostics",
                title="Count diagnostics failed",
                description="Failed diagnostic status should be counted",
                status="in_progress",
                requester_id="user-count-diagnostics",
                queue_id=queue.id,
                assignee_id="support-test",
                custom_fields={"diagnostics": {"status": "failed"}},
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-requester-reply",
                title="Count requester reply",
                description="Unread requester message should be counted",
                status="in_progress",
                requester_id="user-count-requester-reply",
                queue_id=queue.id,
                assignee_id="support-test",
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-mass",
                title="Count mass candidate",
                description="Mass candidate signal should be counted",
                status="in_progress",
                requester_id="user-count-mass",
                queue_id=queue.id,
                assignee_id="support-test",
                custom_fields={"similar_tickets": ["T-000111"]},
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-count-closed",
                title="Closed signals hidden",
                description="Terminal ticket should not be counted by open-only smart views",
                status="closed",
                requester_id="user-count-closed",
                queue_id=queue.id,
                assignee_id="support-test",
                tags=["diagnostics_failed", "mass_incident_candidate"],
                first_response_due_at=now + timedelta(minutes=5),
                ola_ack_due_at=now + timedelta(minutes=5),
            ),
        ]
        session.add_all(tickets)
        await session.flush()

        requester_reply_ticket = next(ticket for ticket in tickets if ticket.title == "Count requester reply")
        await TicketEventsRepo(session).add_event(
            ticket_id=requester_reply_ticket.ticket_id,
            device_id=requester_reply_ticket.device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={
                "message_id": "msg-count-user-1",
                "sender_role": "user",
                "from": "user",
                "text": "Пользователь ответил.",
                "visibility": "public",
            },
            trace_id=str(uuid.uuid4()),
            event_id="msg-count-user-1",
        )
        await session.commit()

    response = await test_client.get("/api/web/support/queue?scope=all", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    counts = {item["value"]: item["count"] for item in payload["data"]["summary"]["smart_view_counts"]}
    assert counts["sla_risk"] == 1
    assert counts["ola_risk"] == 1
    assert counts["unassigned"] == 1
    assert counts["waiting_approval"] == 1
    assert counts["stale_waiting"] == 1
    assert counts["diagnostics_failed"] == 1
    assert counts["requester_reply"] == 1
    assert counts["mass_incident_candidates"] == 1

    expected_titles = {
        "sla_risk": ["Count SLA risk"],
        "ola_risk": ["Count OLA risk"],
        "unassigned": ["Count unassigned"],
        "waiting_approval": ["Count waiting approval"],
        "stale_waiting": ["Count stale waiting"],
        "diagnostics_failed": ["Count diagnostics failed"],
        "requester_reply": ["Count requester reply"],
        "mass_incident_candidates": ["Count mass candidate"],
    }
    for smart_view, titles in expected_titles.items():
        view_response = await test_client.get(
            f"/api/web/support/queue?scope=all&smart_view={smart_view}",
            headers=_support_headers(),
        )
        assert view_response.status == 200, await view_response.text()
        view_payload = await view_response.json()
        assert [item["title"] for item in view_payload["data"]["tickets"]] == titles


@pytest.mark.asyncio
async def test_web_support_ticket_detail_includes_observer_summary(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    detail_device_id = "00000000-0000-4000-8000-000000000101"

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_a", password_hash="test", actor_role="support", is_active=True),
        ])
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test", "op_a"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=detail_device_id,
            title="Нужно проверить приложение",
            description="После обновления пропала синхронизация.",
            status="new",
            requester_id="user-a",
            queue_id=queue.id,
            custom_fields={
                "request_kind": "printer",
                "request_form_key": "printer",
                "request_form_title": "Принтер",
                "request_form_summary": [
                    {"key": "room", "label": "Кабинет", "value": "214"},
                    {"key": "printer_model", "label": "Модель", "value": "HP LaserJet"},
                ],
            },
        )
        ticket_id = ticket.ticket_id
        session.add(
            Device(
                device_id=detail_device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.2.3",
                hostname="ws-detail-host",
                os="Windows 11",
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                capabilities={},
                device_metadata={"applied_update_version": "1.2.3"},
            )
        )
        session.add(ticket)
        await session.flush()

        registry_service = RegistryIngestionService(session)
        await registry_service.ingest_agent_handshake(
            device_id=detail_device_id,
            hostname="ws-detail-host",
            os_name="Windows 11",
            agent_version="1.2.3",
        )
        profile_result = await registry_service.ingest_requester_profile(
            device_id=detail_device_id,
            requester_id="user-a",
            display_name="Иванов Иван",
            profile={
                "full_name": "Иванов Иван",
                "department": "Бухгалтерия",
                "building": "Главное здание",
                "room": "214",
                "phone": "+7 343 000-00-00",
            },
        )
        registration_service = RegistrationService(session)
        claim_id = profile_result.registration["claim_id"]
        await registration_service.confirm_claim_by_user(claim_id, actor_id="user-a", actor_role="user")
        await registration_service.approve_claim(claim_id, reviewed_by="admin")

        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=detail_device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={
                "message_id": "msg-support-1",
                "sender_role": "support",
                "from": "support",
                "text": "Проверяю логи и канал связи.",
                "visibility": "public",
            },
            trace_id=str(uuid.uuid4()),
            event_id="msg-support-1",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=detail_device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={
                "message_id": "msg-user-2",
                "sender_role": "user",
                "from": "user",
                "text": "Спасибо, жду результат.",
                "visibility": "public",
            },
            trace_id=str(uuid.uuid4()),
            event_id="msg-user-2",
        )
        operation_started_at = datetime.now(timezone.utc).replace(microsecond=0)
        operation_finished_at = operation_started_at + timedelta(seconds=2)
        session.add(
            Operation(
                operation_id="op-detail-lifecycle",
                device_id=detail_device_id,
                ticket_id=ticket_id,
                kind="run_tool",
                tool_name="network.diagnostics",
                command_name=None,
                actor_role="support",
                trace_id="trace-detail-lifecycle",
                status="failed",
                queued_at=operation_started_at - timedelta(seconds=1),
                started_at=operation_started_at,
                finished_at=operation_finished_at,
                retry_count=1,
                max_retries=3,
                error_code="HTTP_502",
                error_message="HTTP 502",
                result_summary="Связность не подтверждена",
            )
        )
        await session.commit()

    response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["ticket"]["ticket_id"] == ticket_id
    assert payload["data"]["ticket"]["title"] == "Нужно проверить приложение"
    assert payload["data"]["ticket"]["queue"]["code"] == "servicedesk_l1"
    assert payload["data"]["observer"]["summary"]["ticket_id"] == ticket_id
    assert payload["data"]["observer"]["ticket_summary_endpoint"] == f"/api/tickets/{ticket_id}/observer"
    observer_summary = payload["data"]["observer"]["summary"]
    assert observer_summary["health_label"] in {"empty", "ok", "running", "error"}
    if observer_summary["root_trace_id"]:
        assert observer_summary["root_trace_url"] == f"/app/admin/observer?trace_id={observer_summary['root_trace_id']}"
        assert payload["data"]["observer"]["root_trace"]["trace_id"] == observer_summary["root_trace_id"]
    assert isinstance(payload["data"]["observer"]["related_traces"], list)
    assert all("trace_url" in item for item in payload["data"]["observer"]["related_traces"])
    assert payload["data"]["request_form"]["request_kind"] == "printer"
    assert payload["data"]["request_form"]["form_title"] == "Принтер"
    assert payload["data"]["request_form"]["rows"][0] == {"key": "room", "label": "Кабинет", "value": "214"}
    assert payload["data"]["timeline"][0]["message_id"] == "msg-support-1"
    assert payload["data"]["timeline"][0]["text"] == "Проверяю логи и канал связи."
    assert payload["data"]["timeline"][1]["message_id"] == "msg-user-2"
    assert payload["data"]["timeline"][1]["text"] == "Спасибо, жду результат."
    assert payload["data"]["snapshot"]["device"]["hostname"] == "ws-detail-host"
    assert payload["data"]["snapshot"]["device"]["agent_version"] == "1.2.3"
    assert payload["data"]["snapshot"]["registry"]["person_display_name"] == "Иванов Иван"
    assert payload["data"]["snapshot"]["registry"]["department_name"] == "Бухгалтерия"
    assert payload["data"]["snapshot"]["registry"]["room"] == "214"
    assert payload["data"]["snapshot"]["registry"]["asset_name"] == "ws-detail-host"
    operation_payload = payload["data"]["snapshot"]["latest_operations"][0]
    assert operation_payload["tool_name"] == "network.diagnostics"
    assert operation_payload["duration_ms"] == 2000
    assert operation_payload["trace_id"] == "trace-detail-lifecycle"
    assert operation_payload["trace_relation"] == "operation_child"
    assert operation_payload["trace_url"] == "/app/admin/observer?trace_id=trace-detail-lifecycle"
    assert operation_payload["root_trace_id"] == observer_summary["root_trace_id"]
    assert operation_payload["root_trace_url"] == observer_summary["root_trace_url"]
    assert operation_payload["retry_of_operation_id"] is None
    assert operation_payload["retry_source_trace_id"] is None
    assert operation_payload["retry_count"] == 1
    assert operation_payload["max_retries"] == 3
    assert operation_payload["retryable"] is True
    assert operation_payload["can_retry"] is True
    assert operation_payload["retry_url"] == "/api/operations/op-detail-lifecycle/retry"
    assert operation_payload["retry_disabled_reason"] is None
    assert operation_payload["can_cancel"] is False
    assert operation_payload["cancel_url"] is None
    assert operation_payload["cancel_disabled_reason"] == "already_finished"
    assert "retry:available" in operation_payload["policy_labels"]
    assert operation_payload["error_code"] == "HTTP_502"
    assert operation_payload["error_category"] == "execution"
    assert operation_payload["details_url"] == "/api/operations/op-detail-lifecycle"
    assert payload["data"]["snapshot"]["presence"]["agent_online"] is False
    assert {item["value"] for item in payload["data"]["actions"]["status_options"]} >= {"in_progress"}


@pytest.mark.asyncio
async def test_web_support_operation_cancel_uses_web_session_boundary(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine, device_id="device-web-cancel", status="in_progress")
    operation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(microsecond=0)

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(
            Operation(
                operation_id=operation_id,
                device_id="device-web-cancel",
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="screen.record",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="running",
                queued_at=now - timedelta(seconds=5),
                started_at=now,
            )
        )
        await session.commit()

    response = await test_client.post(
        f"/api/web/support/operations/{operation_id}/cancel",
        headers=_support_headers(),
        json={"reason": "operator_requested_from_support_workspace", "actor_role": "user"},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "ok"
    cancel_operation_id = payload["cancel_operation_id"]

    async with session_maker() as session:
        target = await session.get(Operation, operation_id)
        cancel_op = await session.get(Operation, cancel_operation_id)
        cancel_outbox = await session.scalar(
            select(DeviceOutbox).where(DeviceOutbox.operation_id == cancel_operation_id)
        )

        assert target.status == "cancel_requested"
        assert target.active_cancel_operation_id == cancel_operation_id
        assert cancel_op is not None
        assert cancel_op.kind == "cancel_operation"
        assert cancel_op.actor_role == "support"
        assert cancel_op.cancel_target_operation_id == operation_id
        assert cancel_outbox is not None
        assert cancel_outbox.command == "cancel_operation"


@pytest.mark.asyncio
async def test_web_support_operation_cancel_denies_auditor(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine, device_id="device-web-cancel-deny", status="in_progress")
    operation_id = str(uuid.uuid4())

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(
            Operation(
                operation_id=operation_id,
                device_id="device-web-cancel-deny",
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="screen.record",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="running",
                queued_at=datetime.now(timezone.utc).replace(microsecond=0),
            )
        )
        await session.commit()

    response = await test_client.post(
        f"/api/web/support/operations/{operation_id}/cancel",
        headers=_auditor_headers(),
        json={"reason": "auditor_attempt"},
    )

    assert response.status == 403, await response.text()
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_web_support_ticket_detail_marks_retry_operation_trace_relation(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine, device_id="device-retry-relation", status="in_progress")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    source_operation_id = str(uuid.uuid4())
    retry_operation_id = str(uuid.uuid4())
    source_trace_id = str(uuid.uuid4())
    retry_trace_id = str(uuid.uuid4())

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.observer_root_trace_id = str(uuid.uuid4())
        session.add_all(
            [
                Operation(
                    operation_id=source_operation_id,
                    device_id="device-retry-relation",
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="system.collect",
                    actor_role="support",
                    trace_id=source_trace_id,
                    status="failed",
                    queued_at=now - timedelta(minutes=5),
                    finished_at=now - timedelta(minutes=4),
                    retry_count=1,
                    max_retries=2,
                ),
                Operation(
                    operation_id=retry_operation_id,
                    device_id="device-retry-relation",
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="system.collect",
                    actor_role="support",
                    trace_id=retry_trace_id,
                    status="queued",
                    queued_at=now,
                    retry_count=0,
                    max_retries=2,
                    retry_of_operation_id=source_operation_id,
                ),
            ]
        )
        await session.commit()

    response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()
    retry_operation = payload["data"]["snapshot"]["latest_operations"][0]
    assert retry_operation["operation_id"] == retry_operation_id
    assert retry_operation["trace_relation"] == "retry_child"
    assert retry_operation["retry_of_operation_id"] == source_operation_id
    assert retry_operation["retry_source_trace_id"] == source_trace_id
    assert retry_operation["trace_url"] == f"/app/admin/observer?trace_id={retry_trace_id}"


@pytest.mark.asyncio
async def test_web_support_ticket_workspace_aggregates_detail_tools_passport_and_knowledge(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine, device_id="device-workspace-aggregate", status="in_progress")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    first_response_due_at = now + timedelta(minutes=20)
    resolution_due_at = now + timedelta(hours=3)
    ola_ack_due_at = now - timedelta(minutes=5)
    ola_processing_due_at = now + timedelta(minutes=45)
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.created_at = now - timedelta(minutes=10)
        ticket.first_response_due_at = first_response_due_at
        ticket.resolution_due_at = resolution_due_at
        ticket.ola_ack_due_at = ola_ack_due_at
        ticket.ola_ack_breached_at = now - timedelta(minutes=1)
        ticket.ola_processing_due_at = ola_processing_due_at
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/workspace",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    data = payload["data"]
    assert data["detail"]["ticket"]["ticket_id"] == ticket_id
    assert data["tools"]["ticket_id"] == ticket_id
    assert data["playbooks"]["ticket_id"] == ticket_id
    assert data["passport"]["ticket_id"] == ticket_id
    assert data["knowledge"]["ticket_id"] == ticket_id
    assert data["knowledge"]["similar_tickets"] == []
    assert data["knowledge"]["articles"] == []
    assert data["knowledge"]["ai_summary"]["text"] is None
    assert data["sla_ola"]["first_response"]["due_at"] == first_response_due_at.isoformat()
    assert data["sla_ola"]["first_response"]["status"] == "at_risk"
    assert data["sla_ola"]["first_response"]["remaining_seconds"] > 0
    assert data["sla_ola"]["resolution"]["status"] == "ok"
    assert data["sla_ola"]["ola_ack"]["status"] == "breached"
    assert data["sla_ola"]["ola_processing"]["status"] == "ok"
    assert data["sla_ola"]["ola_processing"]["target_seconds"] is not None
    assert data["passport_readiness"]["ticket_id"] == ticket_id
    assert data["passport_readiness"]["done"] <= data["passport_readiness"]["total"]
    assert {item["key"] for item in data["passport_readiness"]["items"]} == {
        "problem_identified",
        "cause_found",
        "solution_applied",
        "verified_and_closed",
    }


@pytest.mark.asyncio
async def test_web_support_ticket_workspace_stops_first_response_timer_after_reply(test_client, test_engine):
    ticket_id = await _seed_support_ticket(test_engine, device_id="device-workspace-first-response", status="in_progress")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.created_at = now - timedelta(minutes=10)
        ticket.first_response_at = now - timedelta(minutes=1)
        ticket.first_response_due_at = now + timedelta(minutes=20)
        ticket.resolution_due_at = now + timedelta(hours=3)
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/workspace",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    data = payload["data"]
    assert data["detail"]["ticket"]["first_response_at"] == (now - timedelta(minutes=1)).isoformat()
    assert data["sla_ola"]["first_response"]["due_at"] is None
    assert data["sla_ola"]["first_response"]["remaining_seconds"] is None
    assert data["sla_ola"]["first_response"]["status"] == "unknown"
    assert data["sla_ola"]["resolution"]["due_at"] == (now + timedelta(hours=3)).isoformat()


@pytest.mark.asyncio
async def test_web_support_ticket_workspace_exposes_actionable_closure_plan(test_client, test_engine):
    ticket_id = await _seed_support_ticket(
        test_engine,
        device_id=f"device-closure-plan-{uuid.uuid4().hex[:6]}",
        status="in_progress",
    )
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.priority = "P1"
        ticket.custom_fields = {
            "priority_class": "P0",
            "request_template": {
                "key": "website_unavailable",
                "ticket_type": "incident",
                "closure_policy": {
                    "before_resolved": {
                        "require_resolution_code": True,
                        "require_public_summary": True,
                    },
                    "evidence": {
                        "require_evidence_for_priorities": ["P0"],
                    },
                },
            },
        }
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/workspace",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    plan = payload["data"]["closure_plan"]
    blockers = {item["key"]: item for item in plan["blockers"]}

    assert plan["ticket_id"] == ticket_id
    assert plan["ready_for_resolution"] is False
    assert plan["missing_count"] >= 3
    assert plan["evidence_candidate_count"] == 0
    assert blockers["resolution_code"]["action_kind"] == "edit_resolution"
    assert blockers["priority_evidence"]["action_kind"] == "attach_evidence"
    assert blockers["priority_evidence"]["action_label"] == "Добавить evidence"


@pytest.mark.asyncio
async def test_web_support_ticket_knowledge_suggestions_returns_sources_and_workspace_payload(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code=f"knowledge_{uuid.uuid4().hex[:8]}", name="Knowledge queue", members=["support-test"])
        similar_ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-knowledge-related",
            title="Ошибка 502 Bad Gateway на портале",
            description="Resolved similar incident.",
            status="resolved",
            requester_id="requester-related",
            queue_id=queue.id,
            assignee_id="support-test",
            priority="P2",
            resolution_summary="Перезапуск nginx и очистка upstream cache.",
            requester_resolution_summary="Портал снова доступен.",
        )
        session.add(similar_ticket)
        await session.flush()
        await session.refresh(similar_ticket)
        similar_ticket_id = similar_ticket.ticket_id
        similar_ticket_code = similar_ticket.ticket_code
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-knowledge-selected",
            title="Пользователь видит 502 на портале",
            description="Нужна рекомендация по известной ошибке 502.",
            status="in_progress",
            requester_id="requester-selected",
            queue_id=queue.id,
            assignee_id="support-test",
            priority="P1",
            custom_fields={
                "similar_tickets": [similar_ticket.ticket_id],
                "knowledge_attempts": [
                    {
                        "item_id": "KB-502",
                        "version_id": "version-502",
                        "result": "viewed",
                        "surface": "requester_portal",
                        "occurred_at": "2026-06-12T08:15:00+00:00",
                        "metadata": {"debug": "secret-token"},
                    },
                    {
                        "item_id": "AGENT-KB",
                        "result": "viewed",
                        "surface": "agent_gui",
                        "occurred_at": "2026-06-12T08:16:00+00:00",
                    },
                ],
            },
        )
        session.add(ticket)
        await session.flush()
        await TicketEventsRepo(session).add_kb_link(
            ticket.ticket_id,
            "KB-502",
            title="Ошибка 502 Bad Gateway",
            source="manual",
            created_by="support-test",
        )
        ticket_id = ticket.ticket_id
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/knowledge-suggestions",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    data = payload["data"]
    assert data["ticket_id"] == ticket_id
    assert data["requester_attempts"] == [
        {
            "item_id": "KB-502",
            "version_id": "version-502",
            "result": "viewed",
            "surface": "requester_portal",
            "occurred_at": "2026-06-12T08:15:00+00:00",
        }
    ]
    assert "secret-token" not in repr(data["requester_attempts"])
    assert data["articles"] == [
        {
            "id": "KB-502",
            "title": "Ошибка 502 Bad Gateway",
            "url": "/app/knowledge/KB-502",
        }
    ]
    assert data["similar_tickets"][0]["id"] == similar_ticket_id
    assert data["similar_tickets"][0]["number"] == similar_ticket_code
    assert data["similar_tickets"][0]["subject"] == "Ошибка 502 Bad Gateway на портале"
    assert data["similar_tickets"][0]["resolution_summary"] == "Портал снова доступен."
    assert data["ai_summary"]["text"].startswith("AI-рекомендация / Бета:")
    assert "KB-502" in data["ai_summary"]["sources"]
    assert similar_ticket_code in data["ai_summary"]["sources"]
    assert data["ai_summary"]["confidence"] == "high"
    assert data["diagnostics"]["provider"] == "support_knowledge_provider"
    assert data["diagnostics"]["provider_status"] == "ok"
    assert data["diagnostics"]["external_provider_status"] == "not_configured"
    assert data["diagnostics"]["catalog_entry_count"] >= 1
    assert data["diagnostics"]["source_counts"]["manual_kb"] == 1
    assert data["diagnostics"]["source_counts"]["similar_ticket"] == 1
    assert data["diagnostics"]["article_matches"]["KB-502"]["source_type"] == "manual_kb"
    assert data["diagnostics"]["article_matches"]["KB-502"]["score"] == 100
    assert data["diagnostics"]["article_matches"]["KB-502"]["match_reasons"] == ["manual_link"]
    assert data["diagnostics"]["similar_ticket_matches"][similar_ticket_id]["source_type"] == "similar_ticket"
    assert data["diagnostics"]["similar_ticket_matches"][similar_ticket_id]["score"] >= 70
    assert "linked_ticket" in data["diagnostics"]["similar_ticket_matches"][similar_ticket_id]["match_reasons"]

    workspace_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/workspace",
        headers=_support_headers(),
    )
    assert workspace_response.status == 200, await workspace_response.text()
    workspace_payload = await workspace_response.json()
    assert workspace_payload["data"]["knowledge"] == data


@pytest.mark.asyncio
async def test_web_support_ticket_knowledge_suggestions_uses_catalog_search_without_manual_links(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(
            session,
            code=f"knowledge_catalog_{uuid.uuid4().hex[:8]}",
            name="Knowledge catalog queue",
            members=["support-test"],
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-knowledge-catalog",
            title="Portal returns HTTP 502 Bad Gateway",
            description="The website is unavailable after deploy; browser shows 502 and upstream gateway error.",
            status="in_progress",
            requester_id="requester-catalog",
            queue_id=queue.id,
            assignee_id="support-test",
            priority="P1",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/knowledge-suggestions",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    data = payload["data"]
    articles_by_id = {article["id"]: article for article in data["articles"]}
    assert articles_by_id["KB-HTTP-502"] == {
        "id": "KB-HTTP-502",
        "title": "Ошибка 502 Bad Gateway",
        "url": "/app/knowledge/KB-HTTP-502",
    }
    assert "KB-HTTP-502" in data["ai_summary"]["sources"]
    assert data["ai_summary"]["text"].startswith("AI-")
    assert data["diagnostics"]["source_counts"]["catalog"] >= 1
    assert data["diagnostics"]["provider_status"] == "ok"
    assert data["diagnostics"]["external_provider_status"] == "not_configured"
    assert data["diagnostics"]["catalog_entry_count"] >= 1
    assert "502" in data["diagnostics"]["query_tokens"]
    assert "502" in data["diagnostics"]["query_signals"]
    assert data["diagnostics"]["article_matches"]["KB-HTTP-502"]["source_type"] == "catalog"
    assert data["diagnostics"]["article_matches"]["KB-HTTP-502"]["score"] >= 80
    assert "502" in data["diagnostics"]["article_matches"]["KB-HTTP-502"]["match_reasons"]


@pytest.mark.asyncio
async def test_web_support_ticket_detail_timeline_includes_normalized_lifecycle_events(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-timeline-contract",
            title="Timeline contract ticket",
            description="System lifecycle events must be visible in support workspace timeline.",
            status="in_progress",
            requester_id="requester-timeline",
            queue_id=queue.id,
            assignee_id="support-test",
            priority="P1",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.flush()

        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="status_changed",
            payload={"from_status": "new", "to_status": "in_progress", "actor_id": "support-test", "actor_role": "support"},
            event_id="timeline-status-changed",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="assignee_changed",
            payload={"old_value": None, "new_value": "support-test", "actor_id": "lead-test", "actor_role": "support"},
            event_id="timeline-assignee-changed",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="queue_changed",
            payload={"from_queue_id": None, "to_queue_id": queue.id, "new_queue_code": "servicedesk_l1"},
            event_id="timeline-queue-changed",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="priority_changed",
            payload={"old_priority": "P3", "new_priority": "P1", "reason": "impact_update"},
            event_id="timeline-priority-changed",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="sla_breached",
            payload={"timer_type": "resolution", "status": "breached"},
            event_id="timeline-sla-breached",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="ola_breached",
            payload={"breached_fields": ["ola_ack"], "status": "breached"},
            event_id="timeline-ola-breached",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="passport_evidence_added",
            payload={"evidence_id": 42, "evidence_type": "diagnostic_result", "summary": "DNS check attached"},
            event_id="timeline-passport-evidence",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="tool_call_result",
            payload={
                "operation_id": "op-timeline-1",
                "trace_id": "trace-timeline-1",
                "tool_name": "diagnose.website",
                "status": "succeeded",
                "duration_ms": 1253,
                "retry_count": 0,
                "max_retries": 2,
                "summary": "HTTP 502 Bad Gateway",
                "steps": [
                    {"name": "DNS", "status": "ok", "value": "site.example -> 192.0.2.10"},
                    {"name": "HTTP", "status": "error", "value": "502 Bad Gateway"},
                ],
            },
            event_id="timeline-tool-result",
        )
        await session.commit()

    response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    timeline_by_type = {entry["event_type"]: entry for entry in payload["data"]["timeline"]}
    assert {
        "status_changed",
        "assignee_changed",
        "queue_changed",
        "priority_changed",
        "sla_breached",
        "ola_breached",
        "passport_evidence_added",
        "tool_call_result",
    } <= set(timeline_by_type)
    assert timeline_by_type["status_changed"]["event_category"] == "history"
    assert timeline_by_type["status_changed"]["event_details"]["to_status"] == "in_progress"
    assert timeline_by_type["sla_breached"]["event_category"] == "sla"
    assert timeline_by_type["ola_breached"]["event_category"] == "ola"
    assert timeline_by_type["passport_evidence_added"]["event_category"] == "passport"
    assert timeline_by_type["tool_call_result"]["event_category"] == "diagnostics"
    assert timeline_by_type["tool_call_result"]["operation_steps"] == [
        {"name": "DNS", "status": "ok", "value": "site.example -> 192.0.2.10", "details": None},
        {"name": "HTTP", "status": "error", "value": "502 Bad Gateway", "details": None},
    ]
    assert timeline_by_type["tool_call_result"]["operation_id"] == "op-timeline-1"
    assert timeline_by_type["tool_call_result"]["trace_id"] == "trace-timeline-1"
    assert timeline_by_type["tool_call_result"]["duration_ms"] == 1253
    assert timeline_by_type["tool_call_result"]["retry_count"] == 0
    assert timeline_by_type["tool_call_result"]["max_retries"] == 2
    assert timeline_by_type["tool_call_result"]["retryable"] is False
    assert timeline_by_type["tool_call_result"]["can_retry"] is False
    assert timeline_by_type["tool_call_result"]["can_cancel"] is False
    assert timeline_by_type["tool_call_result"]["cancel_disabled_reason"] == "already_finished"
    assert timeline_by_type["tool_call_result"]["details_url"] == "/api/operations/op-timeline-1"


@pytest.mark.asyncio
async def test_web_support_ticket_timeline_endpoint_filters_normalized_events(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="timeline_filter", name="Timeline filter", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-timeline-filter",
            title="Timeline filter contract ticket",
            description="Standalone timeline endpoint should filter normalized support events.",
            status="in_progress",
            requester_id="requester-timeline-filter",
            queue_id=queue.id,
            assignee_id="support-test",
            priority="P1",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.flush()

        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={"from": "user", "text": "Public requester message", "visibility": "public"},
            event_id="timeline-filter-public-message",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={"from": "support", "text": "Internal support note", "visibility": "internal"},
            event_id="timeline-filter-internal-note",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="tool_call_result",
            payload={
                "tool_name": "dns.resolve",
                "status": "succeeded",
                "summary": "DNS resolved",
                "steps": [{"name": "DNS", "status": "ok", "value": "example.test -> 192.0.2.10"}],
            },
            event_id="timeline-filter-tool-result",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="status_changed",
            payload={"from_status": "new", "to_status": "in_progress", "actor_id": "support-test"},
            event_id="timeline-filter-status-changed",
        )
        await session.commit()

    diagnostics_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/timeline?filter=diagnostics",
        headers=_support_headers(),
    )
    assert diagnostics_response.status == 200, await diagnostics_response.text()
    diagnostics_data = (await diagnostics_response.json())["data"]
    assert diagnostics_data["ticket_id"] == ticket_id
    assert diagnostics_data["filter"] == "diagnostics"
    assert diagnostics_data["total"] == 1
    assert [item["event_category"] for item in diagnostics_data["items"]] == ["diagnostics"]
    assert diagnostics_data["items"][0]["operation_steps"][0]["name"] == "DNS"

    internal_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/timeline?filter=internal",
        headers=_support_headers(),
    )
    assert internal_response.status == 200, await internal_response.text()
    internal_data = (await internal_response.json())["data"]
    assert internal_data["total"] == 1
    assert internal_data["items"][0]["visibility"] == "internal"

    history_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/timeline?filter=history",
        headers=_support_headers(),
    )
    assert history_response.status == 200, await history_response.text()
    history_data = (await history_response.json())["data"]
    assert history_data["total"] == 1
    assert history_data["items"][0]["event_type"] == "status_changed"

    all_response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/timeline?filter=all",
        headers=_support_headers(),
    )
    assert all_response.status == 200, await all_response.text()
    all_data = (await all_response.json())["data"]
    assert all_data["total"] == 4


@pytest.mark.asyncio
async def test_web_support_all_timeline_keeps_recent_server_events_after_agent_history(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="timeline_recent_all", name="Timeline recent all", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-timeline-recent-all",
            title="Timeline recent all contract ticket",
            description="All timeline must not hide fresh server-side operation events behind long agent history.",
            status="in_progress",
            requester_id="requester-timeline-recent-all",
            queue_id=queue.id,
            assignee_id="support-test",
            priority="P1",
        )
        session.add(ticket)
        await session.flush()

        repo = TicketEventsRepo(session)
        for seq in range(1, 91):
            await repo.add_event(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=seq,
                event_type="status_changed",
                payload={"from_status": "queued", "to_status": "in_progress", "actor_id": "support-test", "seq": seq},
                event_id=f"timeline-recent-agent-{seq}",
            )
        await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="tool_call_result",
            payload={
                "tool_name": "system.collect",
                "status": "succeeded",
                "summary": "Fresh diagnostic result after long history",
                "operation_id": "op-recent-all",
            },
            event_id="timeline-recent-server-result",
        )
        ticket_id = ticket.ticket_id
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/timeline?filter=all&limit=80",
        headers=_support_headers(),
    )
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    assert data["total"] == 80
    assert data["items"][-1]["event_type"] == "tool_call_result"
    assert data["items"][-1]["operation_id"] == "op-recent-all"
    assert data["items"][-1]["result_summary"] == "Fresh diagnostic result after long history"


@pytest.mark.asyncio
async def test_web_support_timeline_extracts_nested_diagnostic_steps(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        queue = await _seed_queue(session, code="timeline_nested_steps", name="Timeline nested steps", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-timeline-nested",
            title="Nested diagnostic payload",
            description="Diagnostic result cards should not require only top-level steps.",
            status="in_progress",
            requester_id="requester-timeline-nested",
            queue_id=queue.id,
            assignee_id="support-test",
            priority="P1",
        )
        session.add(ticket)
        await session.flush()
        await TicketEventsRepo(session).add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="tool_call_result",
            payload={
                "tool_name": "diagnose.website",
                "status": "partial",
                "summary": "Website diagnostics completed with HTTP error",
                "result": {
                    "checks": [
                        {"title": "DNS", "state": "ok", "summary": "site.example -> 192.0.2.10"},
                        {"title": "TCP", "state": "ok", "value": "192.0.2.10:443"},
                        {
                            "title": "HTTP",
                            "state": "error",
                            "summary": "502 Bad Gateway",
                            "details": "Upstream returned an invalid gateway response.",
                        },
                    ]
                },
            },
            event_id="timeline-nested-tool-result",
        )
        ticket_id = ticket.ticket_id
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/timeline?filter=diagnostics",
        headers=_support_headers(),
    )
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    steps = data["items"][0]["operation_steps"]
    assert steps == [
        {"name": "DNS", "status": "ok", "value": "site.example -> 192.0.2.10", "details": None},
        {"name": "TCP", "status": "ok", "value": "192.0.2.10:443", "details": None},
        {
            "name": "HTTP",
            "status": "error",
            "value": "502 Bad Gateway",
            "details": "Upstream returned an invalid gateway response.",
        },
    ]


@pytest.mark.asyncio
async def test_web_support_workspace_enriches_requester_contact_from_registry(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        queue = await _seed_queue(session, code="contact_registry", name="Contact registry", members=["support-test"])
        queue_id = queue.id
        queue_name = queue.name
        person_id = str(uuid.uuid4())
        department_id = str(uuid.uuid4())
        location_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        service_id = str(uuid.uuid4())
        session.add_all([
            RegistryDepartment(
                department_id=department_id,
                code="marketing",
                name="Отдел маркетинга",
            ),
            RegistryLocation(
                location_id=location_id,
                building="БЦ",
                floor="3",
                room="305",
                display_name="БЦ, 3 этаж, каб. 305",
            ),
            RegistryPerson(
                person_id=person_id,
                display_name="Александр Смирнов",
                full_name="Смирнов Александр Петрович",
                phone="+7 (495) 123-45-67",
                email="a.smirnov@example.test",
                department_id=department_id,
                location_id=location_id,
                source="manual",
            ),
            RegistryService(
                service_id=service_id,
                code="corp-site",
                name="Корпоративный сайт",
                owner_queue_id=queue_id,
                source="registry",
            ),
        ])
        await session.flush()
        session.add(
            RegistryAsset(
                asset_id=asset_id,
                asset_type="pc",
                name="PC-SMIRNOV",
                hostname="PC-SMIRNOV",
                device_id="device-contact-registry",
                location_id=location_id,
                assigned_person_id=person_id,
                department_id=department_id,
                service_id=service_id,
            )
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-contact-registry",
            title="Requester contact enrichment",
            description="Right sidebar should show contact fields from registry.",
            status="in_progress",
            requester_id="requester-contact",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        session.add(ticket)
        ticket_id = ticket.ticket_id
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/workspace",
        headers=_support_headers(),
    )
    assert response.status == 200, await response.text()
    registry = (await response.json())["data"]["detail"]["snapshot"]["registry"]
    assert registry["person_display_name"] == "Александр Смирнов"
    assert registry["person_phone"] == "+7 (495) 123-45-67"
    assert registry["person_email"] == "a.smirnov@example.test"
    assert registry["department_name"] == "Отдел маркетинга"
    assert registry["floor"] == "3"
    assert registry["service_id"] == service_id
    assert registry["service_name"] == "Корпоративный сайт"
    assert registry["service_owner_queue_id"] == queue_id
    assert registry["service_owner_queue_name"] == queue_name


@pytest.mark.asyncio
async def test_web_support_ticket_detail_exposes_template_visibility_policy(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-visibility-policy",
            title="Публичный статус по шаблону",
            description="Внутренний workflow не должен быть единственным статусом для пользователя.",
            status="waiting_on_internal_team",
            requester_id="user-visibility",
            queue_id=queue.id,
            custom_fields={
                "request_template": {
                    "key": "website_unavailable",
                    "ticket_type": "incident",
                    "visibility_policy": {
                        "public_status_mapping": {
                            "waiting_on_internal_team": "Заявка в работе"
                        },
                        "hide_from_requester": ["ola", "raw_diagnostics"],
                        "show_to_requester": ["public_messages", "public_status", "expected_due_at"],
                    },
                }
            },
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()
    ticket_payload = payload["data"]["ticket"]

    assert ticket_payload["status"] == "waiting_on_internal_team"
    assert ticket_payload["public_status"] == "in_work"
    assert ticket_payload["public_status_label"] == "Заявка в работе"
    assert ticket_payload["visibility"]["source"] == "request_template.visibility_policy"
    assert "ola" in ticket_payload["visibility"]["hidden_from_requester"]
    assert "raw_diagnostics" in ticket_payload["visibility"]["hidden_from_requester"]
    assert ticket_payload["requester_visible_fields"] == ["public_messages", "public_status", "expected_due_at"]


@pytest.mark.asyncio
async def test_web_support_detail_timeline_exposes_form_playbook_autostart(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-auto-playbook",
            title="Не печатает принтер",
            description="Заявка пришла из формы и должна показать автодиагностику.",
            status="new",
            requester_id="user-auto-playbook",
            queue_id=queue.id,
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.flush()

        await TicketEventsRepo(session).add_event(
            ticket_id=ticket_id,
            device_id="device-auto-playbook",
            agent_seq=None,
            event_type="playbook_started",
            payload={
                "playbook_key": "printer.quick_diag",
                "playbook_run_id": 77,
                "trigger": "ticket_created",
                "facts_package": {
                    "request_form_key": "printer",
                    "request_form_summary": [
                        {"key": "room", "label": "Кабинет", "value": "214"},
                        {"key": "symptom", "label": "Симптом", "value": "Не печатает"},
                    ],
                    "request_form_data": {"room": "214", "symptom": "Не печатает"},
                },
            },
            trace_id="trace-playbook-autostart",
            event_id="playbook-started-77",
        )
        await session.commit()

    response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    playbook_event = next(
        (entry for entry in payload["data"]["timeline"] if entry["event_type"] == "playbook_started"),
        None,
    )
    assert playbook_event is not None
    assert playbook_event["sender_display_name"] == "Автодиагностика"
    assert playbook_event["text"] == "Автодиагностика запущена: printer.quick_diag"
    assert playbook_event["tool_name"] == "printer.quick_diag"
    assert playbook_event["tool_status"] == "running"
    assert "Run #77" in playbook_event["result_summary"]
    assert "Кабинет: 214" in playbook_event["result_summary"]


@pytest.mark.asyncio
async def test_web_support_message_action_returns_typed_result_and_persists_event(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-message",
            title="Нужна обратная связь",
            description="Пользователь ждёт ответ по инциденту.",
            status="in_progress",
            requester_id="user-message",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/messages",
        headers=_support_headers(),
        json={
            "text": "Начал диагностику, скоро пришлю результат.",
            "visibility": "public",
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["ticket_id"] == ticket_id
    assert payload["data"]["message"]["text"] == "Начал диагностику, скоро пришлю результат."
    assert payload["data"]["message"]["visibility"] == "public"

    detail_response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())
    detail_payload = await detail_response.json()
    assert detail_response.status == 200, await detail_response.text()
    assert detail_payload["data"]["timeline"][0]["text"] == "Начал диагностику, скоро пришлю результат."


@pytest.mark.asyncio
async def test_web_support_message_action_accepts_attachment_refs(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-attachment",
            title="Нужно вложение",
            description="Оператор прикладывает файл.",
            status="in_progress",
            requester_id="user-attachment",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            storage_path="support-log.txt",
            original_name="support-log.txt",
            mime_type="text/plain",
            size_bytes=128,
            sha256="a" * 64,
            kind="file",
            device_id="device-attachment",
            ticket_id=ticket.ticket_id,
            operation_id=None,
            expires_at=None,
        )
        ticket_id = ticket.ticket_id
        artifact_id = artifact.artifact_id
        session.add_all([ticket, artifact])
        await session.commit()

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/messages",
        headers=_support_headers(),
        json={
            "text": "",
            "visibility": "public",
            "attachment_refs": [artifact_id],
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["message"]["attachments"][0]["artifact_id"] == artifact_id
    assert payload["data"]["message"]["attachments"][0]["name"] == "support-log.txt"

    detail_response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())
    detail_payload = await detail_response.json()
    assert detail_response.status == 200, await detail_response.text()
    assert detail_payload["data"]["timeline"][0]["attachments"][0]["artifact_id"] == artifact_id


@pytest.mark.asyncio
async def test_web_support_status_action_returns_typed_result_and_updates_ticket(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-status",
            title="Нужно взять тикет в работу",
            description="Статус должен обновиться через typed action.",
            status="new",
            requester_id="user-status",
            queue_id=queue.id,
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/status",
        headers=_support_headers(),
        json={
            "to_status": "in_progress",
            "reason": "operator_started_work",
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["ticket_id"] == ticket_id
    assert payload["data"]["status"] == "in_progress"
    assert payload["data"]["status_label"] == "В работе"

    detail_response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())
    detail_payload = await detail_response.json()
    assert detail_response.status == 200, await detail_response.text()
    assert detail_payload["data"]["ticket"]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_web_support_ticket_mutation_aliases_update_ticket_through_typed_boundary(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        source_queue = await _seed_queue(session, code="alias_l1", name="Alias L1", members=["support-test"])
        target_queue = await _seed_queue(session, code="alias_network", name="Alias Network", members=["support-test"])
        target_queue_id = target_queue.id
        target_queue_code = target_queue.code
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-alias-actions",
            title="Typed alias mutation ticket",
            description="Support workspace action menu must use typed mutation aliases.",
            status="new",
            requester_id="user-alias",
            queue_id=source_queue.id,
            priority="P4",
            custom_fields={"priority_class": "P3"},
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    assign_response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/assign",
        headers=_support_headers(),
        json={"assignee_id": "support-test", "reason": "manual_assign"},
    )
    assert assign_response.status == 200, await assign_response.text()
    assign_payload = await assign_response.json()
    assert assign_payload["status"] == "success"
    assert assign_payload["data"]["action"] == "assign"
    assert assign_payload["data"]["ticket_id"] == ticket_id
    assert assign_payload["data"]["assignee_id"] == "support-test"

    queue_response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/queue",
        headers=_support_headers(),
        json={"queue_id": target_queue_id, "reason": "manual_queue_change"},
    )
    assert queue_response.status == 200, await queue_response.text()
    queue_payload = await queue_response.json()
    assert queue_payload["data"]["action"] == "queue"
    assert queue_payload["data"]["queue"]["id"] == target_queue_id
    assert queue_payload["data"]["queue"]["code"] == target_queue_code
    assert queue_payload["data"]["assignee_id"] == "support-test"

    priority_response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/priority",
        headers=_support_headers(),
        json={"priority": "P0", "reason": "major_incident"},
    )
    assert priority_response.status == 200, await priority_response.text()
    priority_payload = await priority_response.json()
    assert priority_payload["data"]["action"] == "priority"
    assert priority_payload["data"]["priority"] == "P1"
    assert priority_payload["data"]["priority_class"] == "P0"

    reroute_response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/reroute",
        headers=_support_headers(),
        json={"reason": "manual_recalculate"},
    )
    assert reroute_response.status == 200, await reroute_response.text()
    reroute_payload = await reroute_response.json()
    assert reroute_payload["data"]["action"] == "reroute"
    assert reroute_payload["data"]["ticket_id"] == ticket_id
    assert "queue" in reroute_payload["data"]

    detail_response = await test_client.get(f"/api/web/support/tickets/{ticket_id}", headers=_support_headers())
    assert detail_response.status == 200, await detail_response.text()
    detail_payload = await detail_response.json()
    assert detail_payload["data"]["ticket"]["assignee_id"] == "support-test"
    assert detail_payload["data"]["ticket"]["priority_class"] == "P0"


@pytest.mark.asyncio
async def test_web_support_resolved_status_respects_confirmation_required_false(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-status-no-confirmation",
            title="Resolve without requester confirmation",
            description="Closure policy disables requester confirmation.",
            status="in_progress",
            requester_id="user-status",
            queue_id=queue.id,
            custom_fields={
                "request_template": {
                    "key": "no_confirmation_template",
                    "ticket_type": "incident",
                    "closure_policy": {
                        "requester_confirmation": {
                            "required": False,
                            "auto_close_after_days": 3,
                            "reopen_on_negative_feedback": False,
                        }
                    },
                }
            },
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/status",
        headers=_support_headers(),
        json={
            "to_status": "resolved",
            "resolution_code": "fixed_remote",
            "resolution_summary": "Resolved by operator.",
            "requester_resolution_summary": "Service restored.",
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["data"]["status"] == "resolved"

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ((ticket.custom_fields or {}).get("resolution_confirmation") or {}).get("pending") is not True
        events = await TicketEventsRepo(session).get_events(ticket_id, event_types=["chat_message"])
        assert not any((event.payload or {}).get("metadata", {}).get("confirmation_request") for event in events)


@pytest.mark.asyncio
async def test_web_support_status_action_reports_workflow_gate_block(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        await save_workflow_profiles(
            session,
            {
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Incident gated",
                        "purpose": "restore_service",
                        "suggested_path": ["new", "in_progress", "resolved", "closed"],
                        "allowed_statuses": ["new", "in_progress", "resolved", "closed", "canceled"],
                        "transitions": {
                            "new": ["in_progress", "canceled"],
                            "in_progress": [
                                {
                                    "to": "resolved",
                                    "allowed_roles": ["admin"],
                                    "required_fields": ["resolution_code"],
                                },
                                "canceled",
                            ],
                            "resolved": ["closed"],
                            "closed": [],
                            "canceled": [],
                        },
                    }
                ]
            },
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-status-gate",
            title="Проверка workflow gate",
            description="Переход должен быть заблокирован по роли.",
            status="in_progress",
            requester_id="user-status",
            queue_id=queue.id,
            ticket_type="incident",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/status",
        headers=_support_headers(),
        json={
            "to_status": "resolved",
            "resolution_code": "fixed_remote",
        },
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "WORKFLOW_POLICY_BLOCKED"
    assert "allowed_roles" in payload["error"]


@pytest.mark.asyncio
async def test_web_support_detail_exposes_closure_policy_requirements(test_client, test_engine):
    ticket_id = await _seed_support_ticket(
        test_engine,
        device_id=f"device-closure-req-{uuid.uuid4().hex[:6]}",
        status="in_progress",
    )
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.priority = "P1"
        ticket.custom_fields = {
            "priority_class": "P0",
            "request_template": {
                "key": "website_unavailable",
                "ticket_type": "incident",
                "approval_policy": {"required": True},
                "closure_policy": {
                    "before_resolved": {
                        "require_resolution_code": True,
                        "require_public_summary": True,
                        "require_internal_summary": True,
                    },
                    "allowed_resolution_codes": ["fixed_remote"],
                    "evidence": {
                        "require_evidence_for_priorities": ["P0"],
                        "require_operation_log_if_module_used": True,
                        "require_approval_if_approval_policy_used": True,
                    },
                },
            },
        }
        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="tool_call_started",
            payload={"event": "tool_call_started", "tool_name": "dns.resolve"},
            operation_id=str(uuid.uuid4()),
        )
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}",
        headers=_support_headers(),
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    requirements = payload["data"]["actions"]["closure_requirements"]
    by_key = {item["key"]: item for item in requirements}

    assert by_key["resolution_code"]["met"] is False
    assert by_key["public_summary"]["met"] is False
    assert by_key["internal_summary"]["met"] is False
    assert by_key["priority_evidence"]["met"] is False
    assert by_key["operation_log"]["met"] is False
    assert by_key["approval_evidence"]["met"] is False
    assert "Код решения" in by_key["resolution_code"]["label"]


@pytest.mark.asyncio
async def test_web_support_detail_exposes_approval_policy_summary(test_client, test_engine):
    ticket_id = await _seed_support_ticket(
        test_engine,
        device_id=f"device-approval-summary-{uuid.uuid4().hex[:6]}",
        status="waiting_on_approval",
    )
    requested_at = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.custom_fields = {
            "approval_runtime": {"approvals": {"1": {"reminded_at": "2026-01-01T13:00:00+00:00", "escalated_at": "2026-01-02T09:00:00+00:00"}}},
            "request_template": {
                "key": "access_request",
                "ticket_type": "access_request",
                "policy_refs": {"approval": f"approval_summary_{uuid.uuid4().hex[:8]}"},
                "approval_policy": {
                    "required": True,
                    "approval_mode": "sequential",
                    "approver_source": {"type": "service_owner", "fallback": "requester_manager"},
                    "statuses": {
                        "waiting_status": "waiting_on_approval",
                        "approved_transition": "in_progress",
                        "rejected_transition": "canceled",
                    },
                    "timeout": {"due_in": "2d", "reminder_after": "4h", "escalate_after": "1d"},
                    "require_comment_on_reject": True,
                },
            },
        }
        approval = TicketApproval(
            ticket_id=ticket_id,
            approval_type="service_owner",
            approver_id="owner-1",
            status="requested",
            reason="approval_policy_request",
            requested_by="support-test",
            requested_at=requested_at,
        )
        session.add(approval)
        await session.flush()
        ticket.custom_fields["approval_runtime"]["approvals"][str(approval.id)] = ticket.custom_fields[
            "approval_runtime"
        ]["approvals"].pop("1")
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}",
        headers=_support_headers(),
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    summary = payload["data"]["ticket"]["approval_summary"]

    assert summary["required"] is True
    assert summary["approval_mode"] == "sequential"
    assert summary["approver_source"] == "service_owner"
    assert summary["current_action_owner"] == "approver"
    assert summary["require_comment_on_reject"] is True
    assert summary["waiting_status"] == "waiting_on_approval"
    assert summary["approved_transition"] == "in_progress"
    assert summary["rejected_transition"] == "canceled"
    assert summary["pending_count"] == 1
    assert summary["items"][0]["approver_id"] == "owner-1"
    assert summary["items"][0]["current"] is True
    assert summary["items"][0]["due_at"] == "2026-01-03T09:00:00+00:00"
    assert summary["items"][0]["reminder_at"] == "2026-01-01T13:00:00+00:00"
    assert summary["items"][0]["escalation_at"] == "2026-01-02T09:00:00+00:00"
    assert summary["items"][0]["reminded_at"] == "2026-01-01T13:00:00+00:00"
    assert summary["items"][0]["escalated_at"] == "2026-01-02T09:00:00+00:00"
    assert payload["data"]["actions"]["approval"]["approved_transition"] == "in_progress"
    assert payload["data"]["actions"]["approval"]["rejected_transition"] == "canceled"
    assert payload["data"]["actions"]["approval"]["reject_requires_comment"] is True


async def _seed_approval_decision_ticket(
    test_engine,
    *,
    approver_id: str = "support-test",
    require_comment_on_reject: bool = True,
) -> tuple[str, int]:
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(
            session,
            code=f"approval_decision_{uuid.uuid4().hex[:8]}",
            name="Approval decision queue",
            members=["support-test", "op-a"],
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=f"device-approval-decision-{uuid.uuid4().hex[:6]}",
            title="Approval decision",
            description="Support approval decision endpoint should persist decisions.",
            status="waiting_on_approval",
            requester_id="requester-approval",
            queue_id=queue.id,
            ticket_type="access_request",
            custom_fields={
                "request_template": {
                    "key": "access_request",
                    "ticket_type": "access_request",
                    "approval_policy": {
                        "required": True,
                        "approval_mode": "any_one",
                        "approver_source": {"type": "explicit_user", "user_id": approver_id},
                        "statuses": {
                            "waiting_status": "waiting_on_approval",
                            "approved_transition": "in_progress",
                            "rejected_transition": "canceled",
                        },
                        "require_comment_on_reject": require_comment_on_reject,
                    },
                    "notification_policy": {
                        "on_approval_approved": {"queue": True},
                        "on_approval_rejected": {"queue": True},
                    },
                },
            },
        )
        session.add(ticket)
        approval = TicketApproval(
            ticket_id=ticket.ticket_id,
            approval_type="explicit_user",
            approver_id=approver_id,
            status="requested",
            reason="approval_policy_request",
            requested_by="support-test",
            requested_at=datetime.now(timezone.utc),
        )
        session.add(approval)
        await session.flush()
        ticket_id = ticket.ticket_id
        approval_id = int(approval.id)
        await session.commit()
        return ticket_id, approval_id


@pytest.mark.asyncio
async def test_web_support_approval_decision_approves_and_notifies(test_client, test_engine):
    ticket_id, approval_id = await _seed_approval_decision_ticket(test_engine)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision",
        headers=_support_headers(),
        json={"decision": "approved", "reason": "approved for live acceptance"},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["approval"]["status"] == "approved"
    assert payload["data"]["approval_summary"]["approved_count"] == 1

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        approval = await session.get(TicketApproval, approval_id)
        events = (
            await session.execute(
                select(TicketEvent.event_type, TicketEvent.payload)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "approval_approved")
            )
        ).all()
        notifications = (
            await session.execute(
                select(TicketNotification)
                .where(TicketNotification.ticket_id == ticket_id)
                .where(TicketNotification.event_type == "approval_approved")
            )
        ).scalars().all()

    assert approval.status == "approved"
    assert approval.decided_at is not None
    assert approval.reason == "approved for live acceptance"
    assert len(events) == 1
    assert events[0].payload["approval_id"] == approval_id
    assert {item.actor_id for item in notifications} == {"op-a"}


@pytest.mark.asyncio
async def test_web_support_approval_decision_reject_requires_comment(test_client, test_engine):
    ticket_id, approval_id = await _seed_approval_decision_ticket(test_engine, require_comment_on_reject=True)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision",
        headers=_support_headers(),
        json={"decision": "rejected"},
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "APPROVAL_COMMENT_REQUIRED"


@pytest.mark.asyncio
async def test_web_support_approval_decision_rejects_non_approver(test_client, test_engine):
    ticket_id, approval_id = await _seed_approval_decision_ticket(test_engine, approver_id="service-owner-1")

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision",
        headers=_support_headers(),
        json={"decision": "approved", "reason": "wrong actor"},
    )

    assert response.status == 403, await response.text()
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "APPROVAL_ACTOR_MISMATCH"


@pytest.mark.asyncio
async def test_web_support_ticket_tools_returns_typed_inventory(test_client, test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-tools",
            title="Нужен быстрый запуск диагностики",
            description="Оператор должен видеть список инструментов в новом workspace.",
            status="in_progress",
            requester_id="user-tools",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    class FakeToolExecutionService:
        def __init__(self, _state):
            pass

        async def get_tools_list(self, device_id):
            assert device_id == "device-tools"
            return [
                {
                    "tool": "network.diagnostics",
                    "module": "network",
                    "description": "Быстрая проверка сетевого контура",
                    "spec": {
                        "risk_level": "safe_read",
                        "params_schema": {
                            "type": "object",
                            "required": ["target"],
                            "properties": {
                                "target": {
                                    "type": "string",
                                    "title": "Хост",
                                    "description": "Что проверить"
                                }
                            },
                        },
                        "presets": [],
                    },
                    "metadata": {
                        "requires_consent": False,
                        "allow_roles": ["support", "admin"],
                        "domain": "network",
                        "tool_kind": "diagnostic",
                        "scopes": ["dns", "http"],
                    },
                }
            ]

        async def get_tools_from_server(self, device_id):
            assert device_id == "device-tools"
            return [
                {
                    "tool": "screen.collect",
                    "module": "screen",
                    "description": "Снимок экрана с установкой модуля при запуске",
                    "spec": {
                        "risk_level": "sensitive_read",
                        "params_schema": [],
                        "presets": [{"id": "full", "name": "Полный экран"}],
                    },
                    "metadata": {"requires_consent": True},
                    "install_required": True,
                }
            ]

    monkeypatch.setattr(support_handlers_module, "ToolExecutionService", FakeToolExecutionService)

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/tools",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["ticket_id"] == ticket_id
    assert payload["data"]["device_id"] == "device-tools"
    assert [item["tool_name"] for item in payload["data"]["tools"]] == [
        "network.diagnostics",
        "screen.collect",
    ]
    assert payload["data"]["tools"][0]["params_schema"] == [
        {
            "name": "target",
            "label": "Хост",
            "description": "Что проверить",
            "type": "string",
            "required": True,
            "default": None,
        }
    ]
    assert payload["data"]["tools"][0]["domain"] == "network"
    assert payload["data"]["tools"][0]["tool_kind"] == "diagnostic"
    assert payload["data"]["tools"][0]["required_permission"] == "module.tool.run.low_risk"
    assert payload["data"]["tools"][0]["allowed_roles"] == ["support", "admin"]
    assert payload["data"]["tools"][0]["policy_labels"] == [
        "permission:module.tool.run.low_risk",
        "roles:support,admin",
        "consent:not_required",
        "scopes:dns,http",
    ]
    assert payload["data"]["tools"][1]["install_required"] is True
    assert payload["data"]["tools"][1]["requires_consent"] is True
    assert payload["data"]["tools"][1]["required_permission"] == "module.tool.run.low_risk"
    assert "install:required" in payload["data"]["tools"][1]["policy_labels"]
    assert payload["data"]["tools"][1]["presets"] == [
        {"preset_id": "full", "label": "Полный экран", "description": None, "params": {}}
    ]


@pytest.mark.asyncio
async def test_web_support_tool_action_returns_typed_result_and_dispatches_run_tool(test_client, test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-tool-run",
            title="Нужно запустить инструмент из нового workspace",
            description="Typed web boundary должен прокинуть run_tool и вернуть operation_id.",
            status="in_progress",
            requester_id="user-tool-run",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    captured: dict[str, object] = {}

    class FakeToolExecutionService:
        def __init__(self, _state):
            pass

        async def run_tool(self, *, device_id, ticket_id, tool_name, params, call_id, auth_context, wait_for_result):
            captured.update(
                {
                    "device_id": device_id,
                    "ticket_id": ticket_id,
                    "tool_name": tool_name,
                    "params": params,
                    "call_id": call_id,
                    "actor_id": auth_context.actor_id,
                    "actor_role": auth_context.actor_role,
                    "wait_for_result": wait_for_result,
                }
            )
            return {
                "status": "accepted",
                "operation_id": params["_operation_id"],
                "trace_id": "trace-tool-run-1",
            }

    monkeypatch.setattr(support_handlers_module, "ToolExecutionService", FakeToolExecutionService)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/tools/run",
        headers=_support_headers(),
        json={
            "tool_name": "network.diagnostics",
            "params": {"target": "srv-gateway"},
        },
    )

    assert response.status == 202, await response.text()
    payload = await response.json()
    operation_id = captured["params"]["_operation_id"]

    assert payload["status"] == "success"
    assert payload["data"] == {
        "ticket_id": ticket_id,
        "device_id": "device-tool-run",
        "tool_name": "network.diagnostics",
        "dispatch_status": "accepted",
        "operation_id": operation_id,
        "poll_url": f"/api/operations/{operation_id}",
        "trace_id": "trace-tool-run-1",
        "message": "Инструмент поставлен в очередь выполнения",
    }
    assert captured["device_id"] == "device-tool-run"
    assert captured["ticket_id"] == ticket_id
    assert captured["tool_name"] == "network.diagnostics"
    assert captured["actor_id"] == "support-test"
    assert captured["actor_role"] == "support"
    assert captured["wait_for_result"] is False
    assert captured["params"] == {"target": "srv-gateway", "_operation_id": operation_id}


@pytest.mark.asyncio
async def test_web_support_tool_action_keeps_consent_required_tool_waiting(test_client, test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        now = datetime.now(timezone.utc)
        requester_person_id = str(uuid.uuid4())
        session.add(
            Device(
                device_id="device-tool-consent",
                protocol_version="ws_ticket_v3",
                agent_version="3.1.61",
                hostname="tool-consent-host",
                os="Windows",
                capabilities={},
                device_metadata={},
                first_seen_at=now,
                last_seen_at=now,
                last_handshake_at=now,
            )
        )
        session.add(
            RegistryPerson(
                person_id=requester_person_id,
                display_name="Tool Consent Requester",
                full_name="Tool Consent Requester",
                email="user-tool-consent@example.test",
                source="test",
                status="active",
            )
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-tool-consent",
            title="Нужен запуск инструмента с согласием",
            description="Typed support endpoint должен остановить consent-required tool до dispatch.",
            status="in_progress",
            requester_id="user-tool-consent",
            requester_person_id=requester_person_id,
            queue_id=queue.id,
            assignee_id="support-test",
        )
        ticket_id = ticket.ticket_id
        session.add(ticket)
        await session.commit()

    class FakeToolExecutionService:
        def __init__(self, _state):
            pass

        async def get_tools_list(self, device_id):
            assert device_id == "device-tool-consent"
            return []

        async def get_tools_from_server(self, device_id):
            assert device_id == "device-tool-consent"
            return [
                {
                    "tool": "observer_canary.consent_probe",
                    "module": "observer_canary",
                    "description": "Consent gate probe",
                    "spec": {
                        "risk_level": "sensitive_read",
                        "params_schema": {},
                        "metadata": {
                            "risk_level": "sensitive_read",
                            "requires_consent": True,
                            "allow_roles": ["admin", "support"],
                        },
                    },
                    "metadata": {
                        "risk_level": "sensitive_read",
                        "requires_consent": True,
                        "allow_roles": ["admin", "support"],
                    },
                    "install_required": True,
                }
            ]

        async def run_tool(self, **_kwargs):
            raise AssertionError("consent-required tool must not be dispatched before approval")

    monkeypatch.setattr(support_handlers_module, "ToolExecutionService", FakeToolExecutionService)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/tools/run",
        headers=_support_headers(),
        json={
            "tool_name": "observer_canary.consent_probe",
            "params": {"label": "stage23-consent"},
        },
    )

    assert response.status == 202, await response.text()
    payload = await response.json()
    operation_id = payload["data"]["operation_id"]

    assert payload["status"] == "success"
    assert payload["data"]["dispatch_status"] == "waiting_consent"
    assert payload["data"]["poll_url"] == f"/api/operations/{operation_id}"

    async with session_maker() as session:
        operation = await session.scalar(select(Operation).where(Operation.operation_id == operation_id))
        assert operation is not None
        assert operation.status == "waiting_consent"
        assert operation.ticket_id == ticket_id
        assert operation.device_id == "device-tool-consent"
        assert operation.tool_name == "observer_canary.consent_probe"
        consent = await session.scalar(select(UserConsentRequest).where(UserConsentRequest.subject_id == operation_id))
        assert consent is not None
        assert consent.status == "pending"
        assert consent.subject_type == "operation"
        assert consent.ticket_id == ticket_id
        assert consent.device_id == "device-tool-consent"
        assert consent.requester_person_id is not None
        assert consent.requested_action_payload_redacted["tool_name"] == "observer_canary.consent_probe"


@pytest.mark.asyncio
async def test_web_support_ticket_playbooks_returns_published_playbooks_for_ticket(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-playbooks",
            title="Нужен диагностический плейбук",
            description="Оператор должен запускать опубликованный плейбук из карточки тикета.",
            status="in_progress",
            requester_id="user-playbook",
            queue_id=queue.id,
            assignee_id="support-test",
            custom_fields={
                "request_template": {
                    "key": "website_unavailable",
                    "diagnostic_policy": {
                        "suggested_playbooks": ["diagnose.website", "diagnose.dns.basic"],
                        "auto_run": {"enabled": True, "only_for_priorities": ["P0", "P1"]},
                        "consent": {
                            "required_for_requester_device": True,
                            "required_for_high_risk_tools": True,
                        },
                        "attach_results": {
                            "to_timeline": True,
                            "to_passport": True,
                            "as_evidence": True,
                        },
                        "reroute_by_result": {
                            "DNS_FAIL": "networks",
                            "HTTP_500": "information_systems",
                        },
                    },
                }
            },
        )
        playbook = Playbook(key="printer.quick_diag", name="Быстрая диагностика принтера", domain="diagnostics")
        session.add_all([ticket, playbook])
        await session.flush()
        published_at = datetime.now(timezone.utc)
        version = PlaybookVersion(
            playbook_id=playbook.id,
            version="1.0.0",
            status="published",
            manifest_json={"required_tools": [{"tool": "system.collect", "install_policy": "preinstalled"}]},
            published_at=published_at,
        )
        session.add(version)
        await session.flush()
        session.add(
            PlaybookStep(
                playbook_version_id=version.id,
                step_key="collect",
                order_no=1,
                type="run_tool",
                tool="system.collect",
                params_template_json={},
            )
        )
        ticket_id = ticket.ticket_id
        version_id = version.id
        await session.commit()

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/playbooks",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["ticket_id"] == ticket_id
    assert payload["data"]["device_id"] == "device-playbooks"
    assert payload["data"]["diagnostic_policy"] == {
        "suggested_playbooks": ["diagnose.website", "diagnose.dns.basic"],
        "auto_run_enabled": True,
        "auto_run_priorities": ["P0", "P1"],
        "requester_consent_required": True,
        "high_risk_consent_required": True,
        "attach_to_timeline": True,
        "attach_to_passport": True,
        "attach_as_evidence": True,
        "reroute_by_result": {"DNS_FAIL": "networks", "HTTP_500": "information_systems"},
    }
    assert payload["data"]["playbooks"] == [
        {
            "playbook_version_id": version_id,
            "key": "printer.quick_diag",
            "name": "Быстрая диагностика принтера",
            "domain": "diagnostics",
            "version": "1.0.0",
            "status": "published",
            "blocks_count": 1,
            "required_tools": ["system.collect"],
            "missing_tools": [],
            "missing_params": [],
            "can_run": True,
            "readiness_label": "Готов к запуску",
            "updated_at": published_at.isoformat(),
        }
    ]
    assert payload["data"]["recent_runs"] == []


@pytest.mark.asyncio
async def test_web_support_playbook_action_starts_ticket_bound_run(test_client, test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-playbook-run",
            title="Запуск плейбука из тикета",
            description="Typed support endpoint должен запускать playbook run на устройстве тикета.",
            status="in_progress",
            requester_id="user-playbook-run",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        playbook = Playbook(key="network.quick_diag", name="Быстрая диагностика сети", domain="diagnostics")
        session.add_all([ticket, playbook])
        await session.flush()
        version = PlaybookVersion(
            playbook_id=playbook.id,
            version="1.0.0",
            status="published",
            manifest_json={},
            published_at=datetime.now(timezone.utc),
        )
        session.add(version)
        await session.flush()
        ticket_id = ticket.ticket_id
        version_id = version.id
        await session.commit()

    captured: dict[str, object] = {}

    async def fake_start_run(**kwargs):
        captured.update(kwargs)
        return 42, "operation-first"

    monkeypatch.setattr(support_handlers_module, "start_run", fake_start_run)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/playbooks/run",
        headers=_support_headers(),
        json={"playbook_version_id": version_id},
    )

    assert response.status == 202, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"] == {
        "ticket_id": ticket_id,
        "device_id": "device-playbook-run",
        "playbook_version_id": version_id,
        "playbook_run_id": 42,
        "status": "running",
        "first_operation_id": "operation-first",
        "observer_url": "/app/admin/observer?root_kind=playbook_run&playbook_run_id=42",
        "message": "Плейбук поставлен в очередь выполнения.",
    }
    assert captured["playbook_version_id"] == version_id
    assert captured["device_id"] == "device-playbook-run"
    assert captured["trigger_type"] == "support_ticket"
    assert captured["context_json"]["ticket_id"] == ticket_id
    assert captured["context_json"]["triggered_by"] == "support-test"
