from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import AccessGroup, AccessGroupMember, AccessGroupPermission, Ticket, UiUser
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from auth.context import AuthContext, AuthType
from routes import setup_routes
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN
import web_api.settings_handlers as settings_handlers_module

pytestmark = pytest.mark.db_cleanup("full")


@pytest.fixture
async def web_settings_client():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="admin1",
            actor_role="admin",
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        yield client


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


async def _grant_support_permissions(test_engine, permissions: list[str]) -> None:
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="secret", actor_role="support", is_active=True))
        group = AccessGroup(
            code="settings_grant",
            name="Settings grant",
            description=None,
            is_active=True,
        )
        session.add(group)
        await session.flush()
        session.add(AccessGroupMember(group_id=group.id, actor_id="support-test"))
        for permission in permissions:
            session.add(AccessGroupPermission(group_id=group.id, permission_code=permission))
        await session.commit()


async def _assert_settings_forbidden(response, permission: str) -> None:
    assert response.status == 403, await response.text()
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "FORBIDDEN"
    assert payload["required_permission"] == permission
    assert permission in payload["error"]


@pytest.mark.asyncio
async def test_web_settings_queue_write_requires_manage_queues_permission(test_client):
    response = await test_client.post(
        "/api/web/settings/queues",
        headers=_support_headers(),
        json={
            "code": "rbac_queue_denied",
            "name": "RBAC denied queue",
            "is_triage": False,
            "auto_assign_enabled": True,
        },
    )

    await _assert_settings_forbidden(response, "settings.manage_queues")


@pytest.mark.asyncio
async def test_web_settings_queue_write_allows_manage_queues_group_permission(test_client, test_engine):
    await _grant_support_permissions(test_engine, ["settings.manage_queues"])

    response = await test_client.post(
        "/api/web/settings/queues",
        headers=_support_headers(),
        json={
            "code": "rbac_queue_allowed",
            "name": "RBAC allowed queue",
            "is_triage": False,
            "auto_assign_enabled": True,
        },
    )

    assert response.status == 201, await response.text()
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["queue"]["code"] == "rbac_queue_allowed"


@pytest.mark.asyncio
async def test_web_settings_routing_write_requires_manage_routing_permission(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = TicketAdminConfigRepo(session)
        queue = await repo.create_queue("rbac_routing_target", "RBAC routing target")
        queue_id = queue.id
        await session.commit()

    response = await test_client.post(
        "/api/web/settings/routing_rules",
        headers=_support_headers(),
        json={
            "enabled": True,
            "priority_order": 20,
            "target_queue_id": queue_id,
            "condition_json": {"field": "request_kind", "op": "eq", "value": "access"},
        },
    )

    await _assert_settings_forbidden(response, "settings.manage_routing")


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_settings_returns_typed_fallback_when_db_is_unavailable(
    web_settings_client,
    monkeypatch,
):
    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(settings_handlers_module, "get_session", failing_session)

    response = await web_settings_client.get("/api/web/settings")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["capabilities"]["can_write"] is True
    assert payload["data"]["routing_builder"]["fields"]
    assert payload["data"]["ticket_settings"]["governance"]["fsm_mode"] == "soft"
    assert payload["data"]["ticket_settings"]["governance"]["passport_enabled"] is True
    assert {item["value"] for item in payload["data"]["ticket_settings"]["internal_statuses"]} >= {
        "new",
        "in_progress",
        "waiting_on_user",
        "resolved",
        "closed",
    }
    assert payload["data"]["queues"] == []
    assert payload["data"]["audit"] == []


@pytest.mark.asyncio
async def test_web_settings_returns_aggregated_real_payload(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add_all(
            [
                UiUser(user_login="admin", password_hash="secret", actor_role="admin", is_active=True),
                UiUser(user_login="support-test", password_hash="secret", actor_role="support", is_active=True),
            ]
        )
        repo = TicketAdminConfigRepo(session)
        policy_repo = HelpdeskPolicyRepo(session)
        audit_repo = TicketAdminAuditRepo(session)

        queue = await repo.create_queue("servicedesk_l1", "ServiceDesk L1", is_triage=True, auto_assign_enabled=True)
        await repo.put_queue_member(queue.id, "support-test", role_in_queue="owner")
        await repo.replace_ola_targets(
            queue.id,
            [
                {"priority": "P1", "ack_min": 5, "processing_min": 30},
                {"priority": "P2", "ack_min": 15, "processing_min": 120},
            ],
        )
        routing_rule = await repo.create_routing_rule(
            target_queue_id=queue.id,
            priority_order=10,
            condition_json={"field": "request_kind", "op": "eq", "value": "access"},
            enabled=True,
        )
        calendar = await repo.create_calendar(
            code="weekday_ru",
            name="Будни",
            timezone="Asia/Yekaterinburg",
            weekly_hours_json={"mon": [["09:00", "18:00"]]},
            holidays_json={"dates": ["2026-01-01"]},
        )
        policy = await repo.create_sla_policy(
            name="Стандартная",
            timezone="Asia/Yekaterinburg",
            business_hours_json={"mode": "calendar"},
            calendar_id=calendar.id,
            is_default=True,
        )
        policy_id = policy.id
        await repo.replace_sla_targets(
            policy.id,
            [
                {"priority": "P1", "first_response_min": 15, "resolution_min": 120},
                {"priority": "P2", "first_response_min": 30, "resolution_min": 240},
            ],
        )
        await repo.replace_priority_matrix(
            policy.id,
            [
                {"impact": 1, "urgency": 1, "priority": "P4"},
                {"impact": 1, "urgency": 2, "priority": "P3"},
                {"impact": 1, "urgency": 3, "priority": "P2"},
                {"impact": 2, "urgency": 1, "priority": "P3"},
                {"impact": 2, "urgency": 2, "priority": "P2"},
                {"impact": 2, "urgency": 3, "priority": "P1"},
                {"impact": 3, "urgency": 1, "priority": "P2"},
                {"impact": 3, "urgency": 2, "priority": "P1"},
                {"impact": 3, "urgency": 3, "priority": "P1"},
            ],
        )
        await repo.create_resolution_code("solved_remotely", "Решено удалённо", is_active=True, sort_order=10)
        await policy_repo.publish_ticket_type(
            code="incident",
            title="Incident",
            default_workflow_profile_id="incident_default",
            default_priority_policy_code="incident_priority",
            default_routing_policy_code="incident_routing",
            default_sla_policy_id=policy_id,
            default_sla_policy_code="incident_sla",
            default_ola_policy_code="incident_ola",
            default_closure_policy_code="incident_closure",
            feature_flags={"sla_required": True, "diagnostics_allowed": True, "portal_visible": True},
            actor_id="admin",
            actor_role="admin",
        )
        session.add(
            Ticket(
                ticket_id="00000000-0000-0000-0000-000000000111",
                device_id="device-settings",
                title="Тикет для open count",
                description="Используется в payload",
                status="in_progress",
                requester_id="requester-1",
                queue_id=queue.id,
                sla_policy_id=policy.id,
                resolution_code="solved_remotely",
            )
        )
        await audit_repo.add(
            entity_type="routing_rule",
            entity_id=str(routing_rule.id),
            action="create",
            actor_id="admin",
            actor_role="admin",
            after_json={"target_queue_id": queue.id},
            trace_id="trace-settings-1",
        )
        await session.commit()

    response = await test_client.get("/api/web/settings", headers=_admin_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["capabilities"]["can_write"] is True
    assert payload["data"]["overview"]["queues_count"] == 1
    assert payload["data"]["queues"][0]["members"][0]["actor_id"] == "support-test"
    assert payload["data"]["queues"][0]["ola_targets"][0]["priority"] == "P1"
    assert payload["data"]["routing_rules"][0]["target_queue_name"] == "ServiceDesk L1"
    assert payload["data"]["ticket_settings"]["requester_statuses"][0]["label"] == "Обращение принято"
    assert payload["data"]["ticket_settings"]["next_action_owners"][0]["value"] == "support"
    workflow_profiles = {item["ticket_type"]: item for item in payload["data"]["ticket_settings"]["workflow_profiles"]}
    assert workflow_profiles["incident"]["purpose"] == "restore_service"
    assert workflow_profiles["incident"]["transitions"]["new"]
    assert workflow_profiles["access_request"]["requires_approval"] is True
    assert "waiting_on_approval" in workflow_profiles["access_request"]["suggested_path"]
    ticket_types = {item["code"]: item for item in payload["data"]["ticket_settings"]["ticket_types"]}
    assert ticket_types["incident"]["default_workflow_profile_id"] == "incident_default"
    assert ticket_types["incident"]["default_sla_policy_id"] == policy_id
    assert ticket_types["incident"]["feature_flags"]["sla_required"] is True
    assert payload["data"]["ticket_settings"]["operational_flags"]["take_queue_mode"]
    process_schema = {item["key"]: item for item in payload["data"]["ticket_settings"]["process_schema"]}
    assert process_schema["request_template"]["meaning"] == "Каталог обращений собирает факты и порождает процессный контекст"
    assert process_schema["ticket_type_workflow_profile"]["meaning"] == "Тип заявки выбирает профиль workflow"
    assert process_schema["routing"]["meaning"] == "Роутинг выбирает очередь"
    assert process_schema["queue"]["meaning"] == "Очередь определяет группу ответственных"
    assert process_schema["sla"]["label"] == "Сроки ответа и решения"
    assert process_schema["sla"]["meaning"] == "Показывает, за какое время пользователю должны ответить и решить обращение"
    assert process_schema["ola"]["label"] == "Внутренние сроки очередей"
    assert process_schema["ola"]["meaning"] == "Задаёт сроки принятия и обработки внутри групп поддержки"
    assert process_schema["support_line"]["status"] == "planned"
    assert {item["code"] for item in payload["data"]["ticket_settings"]["support_lines"]} == {"L1", "L2", "L3"}
    request_templates = {item["id"]: item for item in payload["data"]["ticket_settings"]["request_templates"]}
    assert request_templates["breakage"]["public_title"] == "Поломка"
    assert request_templates["breakage"]["classification"]["ticket_type"] == "incident"
    assert request_templates["breakage"]["form"]["form_schema_id"] == "breakage_form"
    assert request_templates["breakage"]["form"]["required_fields_count"] >= 1
    assert request_templates["breakage"]["form"]["on_behalf_policy"]["allowed"] is False
    assert request_templates["breakage"]["workflow"]["workflow_profile_id"] == "incident"
    assert request_templates["breakage"]["priority"]["policy_id"] == "inline:breakage:priority_policy"
    assert request_templates["breakage"]["sla"]["policy_id"] is None
    assert "closure_policy" in request_templates["breakage"]["policies_missing"]
    assert payload["data"]["ticket_settings"]["priority_model"]["direct_user_priority_choice"] is False
    assert "deadline_today" in payload["data"]["ticket_settings"]["priority_model"]["modifiers"]
    routing_fields = {item["field"] for item in payload["data"]["routing_builder"]["fields"]}
    assert "ticket_type" in routing_fields
    assert "request_kind" in routing_fields
    assert "request_form_data.room" in routing_fields
    assert payload["data"]["sla_policies"][0]["calendar_name"] == "Будни"
    assert payload["data"]["sla_policies"][0]["targets"][0]["priority"] == "P1"
    assert payload["data"]["calendars"][0]["code"] == "weekday_ru"
    assert payload["data"]["resolution_codes"][0]["usage_count"] == 1
    assert payload["data"]["audit"][0]["trace_id"] == "trace-settings-1"


@pytest.mark.asyncio
async def test_web_settings_accepts_list_shaped_calendar_json(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        repo = TicketAdminConfigRepo(session)
        await repo.create_calendar(
            code="legacy_list_calendar",
            name="Legacy list calendar",
            timezone="Asia/Yekaterinburg",
            weekly_hours_json=[{"day": 1, "start": "09:00", "end": "18:00"}],
            holidays_json=[],
        )
        await session.commit()

    response = await test_client.get("/api/web/settings", headers=_admin_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    calendars = payload["data"]["calendars"]
    assert calendars[0]["code"] == "legacy_list_calendar"
    assert calendars[0]["weekly_hours_json"] == [{"day": 1, "start": "09:00", "end": "18:00"}]
    assert calendars[0]["holidays_json"] == []


@pytest.mark.asyncio
async def test_web_settings_routing_rule_rejects_legacy_like_condition_json(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="admin", password_hash="secret", actor_role="admin", is_active=True))
        repo = TicketAdminConfigRepo(session)
        queue = await repo.create_queue("servicedesk_l1", "ServiceDesk L1", is_triage=True, auto_assign_enabled=True)
        queue_id = queue.id
        await session.commit()

    response = await test_client.post(
        "/api/web/settings/routing_rules",
        headers=_admin_headers(),
        json={
            "enabled": True,
            "priority_order": 10,
            "target_queue_id": queue_id,
            "condition_json": {"request_kind": "access"},
        },
    )

    assert response.status == 400, await response.text()
    payload = await response.json()

    assert payload["status"] == "error"
    assert payload["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_web_settings_queue_alias_reuses_real_admin_config_handlers(test_client):
    response = await test_client.post(
        "/api/web/settings/queues",
        headers=_admin_headers(),
        json={
            "code": "network",
            "name": "Network",
            "is_triage": False,
            "auto_assign_enabled": True,
        },
    )

    assert response.status == 201, await response.text()
    payload = await response.json()

    assert payload["status"] == "ok"
    assert payload["queue"]["code"] == "network"


@pytest.mark.asyncio
async def test_web_settings_ola_targets_accept_process_priority_p0(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="admin", password_hash="secret", actor_role="admin", is_active=True))
        repo = TicketAdminConfigRepo(session)
        queue = await repo.create_queue("p0_ola", "P0 OLA", is_triage=True, auto_assign_enabled=False)
        queue_id = queue.id
        await session.commit()

    response = await test_client.put(
        f"/api/web/settings/queues/{queue_id}/ola_targets",
        headers=_admin_headers(),
        json={"ola_targets": [{"priority": "P0", "ack_min": 5, "processing_min": 30}]},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "ok"
    assert payload["ola_targets"] == [{"priority": "P0", "ack_min": 5, "processing_min": 30}]


@pytest.mark.asyncio
async def test_web_settings_can_save_workflow_profiles(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(UiUser(user_login="admin", password_hash="secret", actor_role="admin", is_active=True))
        await session.commit()

    response = await test_client.put(
        "/api/web/settings/workflow_profiles",
        headers=_admin_headers(),
        json={
            "workflow_profiles": [
                {
                    "ticket_type": "incident",
                    "label": "Авария",
                    "purpose": "restore_service",
                    "suggested_path": ["new", "queued", "in_progress", "resolved", "closed"],
                    "allowed_statuses": ["new", "queued", "in_progress", "resolved", "closed", "canceled"],
                    "required_create_fields": ["affected_object"],
                    "required_resolve_fields": ["resolution_code"],
                    "requires_approval": False,
                    "requires_change_plan": False,
                    "requires_action_log": False,
                    "evidence_required_for_priorities": ["P0"],
                    "transitions": {
                        "new": ["queued", "canceled"],
                        "queued": ["in_progress", "canceled"],
                        "in_progress": [
                            {
                                "to": "resolved",
                                "required_comment_type": "public",
                                "require_evidence": True,
                                "log_fields": ["resolution_code"],
                                "actions": {
                                    "notify": ["assignee"],
                                    "sla": "pause",
                                    "approval": "create_request",
                                },
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

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "ok"
    assert "incident" in payload["diff"]["changed"]
    profiles = {item["ticket_type"]: item for item in payload["workflow_profiles"]}
    assert profiles["incident"]["label"] == "Авария"
    assert profiles["incident"]["transitions"]["new"] == ["queued", "canceled"]
    assert profiles["incident"]["transition_gates"]["in_progress"]["resolved"] == {
        "to": "resolved",
        "required_comment": "public",
        "require_evidence": True,
        "log_fields": ["resolution_code"],
        "actions": {
            "notify": ["assignee"],
            "sla": "pause",
            "approval": "create_request",
        },
    }

    settings_response = await test_client.get("/api/web/settings", headers=_admin_headers())
    assert settings_response.status == 200, await settings_response.text()
    settings_payload = await settings_response.json()
    settings_profiles = {
        item["ticket_type"]: item
        for item in settings_payload["data"]["ticket_settings"]["workflow_profiles"]
    }
    assert settings_profiles["incident"]["label"] == "Авария"
    assert settings_profiles["incident"]["required_create_fields"] == ["affected_object"]
