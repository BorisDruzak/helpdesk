from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, UiUser
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from auth.context import AuthContext, AuthType
from routes import setup_routes
from tests.conftest import TEST_UI_ADMIN_TOKEN
import web_api.settings_handlers as settings_handlers_module


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
            condition_json={"request_kind": "access"},
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
    assert payload["data"]["sla_policies"][0]["calendar_name"] == "Будни"
    assert payload["data"]["sla_policies"][0]["targets"][0]["priority"] == "P1"
    assert payload["data"]["calendars"][0]["code"] == "weekday_ru"
    assert payload["data"]["resolution_codes"][0]["usage_count"] == 1
    assert payload["data"]["audit"][0]["trace_id"] == "trace-settings-1"


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
