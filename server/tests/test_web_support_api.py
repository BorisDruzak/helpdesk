import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, Operation, Ticket, UiUser
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.context import AuthContext, AuthType
from routes import setup_routes
import web_api.support_handlers as support_handlers_module
from tests.conftest import TEST_UI_SUPPORT_TOKEN
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
    assert {item["value"] for item in payload["data"]["filters"]["status_options"]} >= {"all", "in_progress", "new"}

    mine_response = await test_client.get("/api/web/support/queue?scope=mine", headers=_support_headers())
    assert mine_response.status == 200, await mine_response.text()
    mine_payload = await mine_response.json()

    assert mine_payload["data"]["scope"] == "mine"
    assert [item["title"] for item in mine_payload["data"]["tickets"]] == ["Visible by assignee"]


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
    assert payload["data"]["snapshot"]["device"]["hostname"] == "ws-detail-host"
    assert payload["data"]["snapshot"]["device"]["agent_version"] == "1.2.3"
    assert payload["data"]["snapshot"]["latest_operations"][0]["tool_name"] == "network.diagnostics"
    assert payload["data"]["snapshot"]["presence"]["agent_online"] is False
    assert {item["value"] for item in payload["data"]["actions"]["status_options"]} >= {"in_progress"}


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
        {"preset_id": "full", "label": "Полный экран"}
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
