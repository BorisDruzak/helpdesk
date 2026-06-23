from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, UiUser
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from auth.context import AuthContext, AuthType
from routes import setup_routes
from tests.conftest import TEST_UI_SUPPORT_TOKEN
from tests.test_ticket_queue_routing_contracts import _seed_queue
import web_api.reports_handlers as reports_handlers_module

pytestmark = pytest.mark.db_cleanup("full")


@pytest.fixture
async def web_reports_client():
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


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_reports_summary_returns_typed_fallback_when_db_is_unavailable(
    web_reports_client,
    monkeypatch,
):
    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(reports_handlers_module, "get_session", failing_session)

    response = await web_reports_client.get("/api/web/reports/summary?days=7")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["period"]["days"] == 7
    assert payload["data"]["summary"]["open_backlog_count"] == 0
    assert payload["data"]["daily_trend"] == []


@pytest.mark.asyncio
async def test_web_reports_summary_returns_real_metrics_payload(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add_all(
            [
                UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
                UiUser(user_login="op_a", password_hash="test", actor_role="support", is_active=True),
            ]
        )
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test", "op_a"])
        session.add_all(
            [
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    device_id="device-open",
                    title="Открытый тикет",
                    description="Открытый backlog",
                    status="in_progress",
                    requester_id="req-open",
                    queue_id=queue.id,
                    priority="P2",
                    ticket_type="incident",
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(hours=4),
                    custom_fields={"request_kind": "access"},
                    first_response_due_at=now - timedelta(days=1),
                    resolution_due_at=now + timedelta(days=1),
                ),
                Ticket(
                    ticket_id=str(uuid.uuid4()),
                    device_id="device-closed",
                    title="Закрытый тикет",
                    description="Тикет в отчёте",
                    status="closed",
                    requester_id="req-closed",
                    queue_id=queue.id,
                    priority="P3",
                    ticket_type="request",
                    created_at=now - timedelta(days=3),
                    updated_at=now - timedelta(hours=2),
                    closed_at=now - timedelta(hours=1),
                    resolved_at=now - timedelta(hours=1),
                    resolution_at=now - timedelta(hours=1),
                    first_response_at=now - timedelta(days=2, hours=20),
                    first_response_due_at=now - timedelta(days=2, hours=18),
                    resolution_due_at=now - timedelta(hours=3),
                    reopen_count=1,
                    custom_fields={"request_kind": "software_install"},
                ),
            ]
        )
        await session.commit()

    response = await test_client.get("/api/web/reports/summary?days=14", headers=_support_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["summary"]["open_backlog_count"] == 1
    assert payload["data"]["summary"]["closed_in_period_count"] == 1
    assert payload["data"]["summary"]["reopen_rate_percent"] == 100.0
    assert payload["data"]["filters"]["queue_options"][0]["label"] == "ServiceDesk L1"
    assert any(item["label"] == "Доступ" for item in payload["data"]["request_kinds"])
    assert payload["data"]["top_queues"][0]["queue_label"] == "ServiceDesk L1"
    assert payload["data"]["recent_tickets"][0]["queue_label"] == "ServiceDesk L1"


@pytest.mark.asyncio
async def test_web_reports_summary_uses_current_form_catalog_for_request_kind_labels(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        repo = TicketFormPacksRepo(session)
        custom_pack = {
            "pack_key": "request_forms",
            "version": "9.9.9",
            "title": "Каталог заявок",
            "description": "Кастомный каталог для отчётов",
            "forms": [
                {
                    "key": "software_install",
                    "request_kind": "software_install",
                    "title": "Установка из каталога",
                    "description": "",
                    "fields": [
                        {
                            "key": "software_name",
                            "label": "ПО",
                            "type": "text",
                            "required": True,
                        }
                    ],
                }
            ],
        }
        await repo.upsert_pack(
            pack_key="request_forms",
            version="9.9.9",
            schema_json=custom_pack,
            created_by="admin1",
            notes="reports-test",
        )
        await repo.set_preferred(pack_key="request_forms", version="9.9.9", updated_by="admin1")
        session.add(
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="device-report-form",
                title="Установка ПО",
                description="Нужен Photoshop",
                status="in_progress",
                requester_id="req-form",
                queue_id=queue.id,
                ticket_type="software_install",
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(hours=3),
                custom_fields={"request_kind": "software_install"},
            )
        )
        await session.commit()

    response = await test_client.get("/api/web/reports/summary?days=14", headers=_support_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    assert any(item["label"] == "Установка из каталога" for item in payload["data"]["request_kinds"])
