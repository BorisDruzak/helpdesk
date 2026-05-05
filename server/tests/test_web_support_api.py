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
    Device,
    Operation,
    Playbook,
    PlaybookStep,
    PlaybookVersion,
    HelpdeskPolicyAudit,
    ReportingPolicy,
    Ticket,
    TicketApproval,
    TicketEvent,
    TicketNotification,
    UiUser,
)
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.context import AuthContext, AuthType
from registry.service import RegistryIngestionService
from routes import setup_routes
from tickets.workflow_profiles import save_workflow_profiles
import web_api.support_handlers as support_handlers_module
from tests.conftest import TEST_UI_AUDITOR_TOKEN, TEST_UI_SUPPORT_TOKEN
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


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _auditor_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_AUDITOR_TOKEN}"}


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

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_a", password_hash="test", actor_role="support", is_active=True),
        ])
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test", "op_a"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-detail",
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
                device_id="device-detail",
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
            device_id="device-detail",
            hostname="ws-detail-host",
            os_name="Windows 11",
            agent_version="1.2.3",
        )
        await registry_service.ingest_requester_profile(
            device_id="device-detail",
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

        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id="device-detail",
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
            device_id="device-detail",
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
        session.add(
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id="device-detail",
                ticket_id=ticket_id,
                kind="run_tool",
                tool_name="network.diagnostics",
                command_name=None,
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="Связность подтверждена",
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
    assert payload["data"]["snapshot"]["latest_operations"][0]["tool_name"] == "network.diagnostics"
    assert payload["data"]["snapshot"]["presence"]["agent_online"] is False
    assert {item["value"] for item in payload["data"]["actions"]["status_options"]} >= {"in_progress"}


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
            title="РџСЂРѕРІРµСЂРєР° workflow gate",
            description="РџРµСЂРµС…РѕРґ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ Р·Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ РїРѕ СЂРѕР»Рё.",
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
                    "metadata": {"requires_consent": False},
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
    assert payload["data"]["tools"][1]["install_required"] is True
    assert payload["data"]["tools"][1]["requires_consent"] is True
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
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="device-tool-consent",
            title="Нужен запуск инструмента с согласием",
            description="Typed support endpoint должен остановить consent-required tool до dispatch.",
            status="in_progress",
            requester_id="user-tool-consent",
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
