import uuid
from datetime import datetime, timezone

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select

from app_keys import STATE_APP_KEY, bind_app_value
from app.db.engine import async_sessionmaker
from app.db.models import Device, RegistryPerson, Ticket, UserConsentRequest
from auth.context import AuthContext, AuthType
from tools.handlers import handle_tools_run
from tests.test_helpers import TEST_ECHO_TOOL


def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.61",
        hostname="legacy-tools-device",
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


@pytest.fixture(autouse=True)
def allow_ticket_device_match(monkeypatch):
    async def _allow_ticket_device_match(**_kwargs):
        return None

    monkeypatch.setattr("tools.handlers._require_ticket_device_match", _allow_ticket_device_match)


@pytest.fixture
async def test_client_no_db():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="support-test",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    bind_app_value(app, key=STATE_APP_KEY, legacy_name="state", value=object())
    app.router.add_post("/api/tools/run", handle_tools_run)
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_async_returns_poll_url(test_client_no_db, monkeypatch):
    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _fake_run_tool(self, **_kwargs):
        return {
            "status": "accepted",
            "device_id": "device-async-1",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    async def _allow_account_access(**_kwargs):
        return None

    monkeypatch.setattr("tools.handlers._require_agent_tool_account_access", _allow_account_access)

    response = await test_client_no_db.post(
        "/api/tools/run",
        json={
            "device_id": "device-async-1",
            "ticket_id": "ticket-async-1",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "hello"},
        },
    )
    assert response.status == 202
    payload = await response.json()

    assert payload["status"] == "accepted"
    assert payload["operation_id"]
    assert payload["poll_url"] == f"/api/operations/{payload['operation_id']}"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_rejects_agent_token_for_different_device_context(monkeypatch):
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="device-owned",
            actor_role="agent",
            auth_type=AuthType.AGENT_TOKEN,
            token="agent-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    bind_app_value(app, key=STATE_APP_KEY, legacy_name="state", value=object())
    app.router.add_post("/api/tools/run", handle_tools_run)

    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _unexpected_run_tool(self, **_kwargs):
        pytest.fail("agent device context mismatch reached dispatch")

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _unexpected_run_tool)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/tools/run",
            json={
                "device_id": "device-other",
                "ticket_id": "ticket-other-device",
                "tool_name": "screen.collect",
                "params": {},
            },
        )
        payload = await response.json()

    assert response.status == 403
    assert payload["status"] == "error"
    assert payload["error_code"] == "DEVICE_CONTEXT_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_rejects_ticket_device_mismatch_before_dispatch(test_client_no_db, monkeypatch):
    async def _fake_ticket_device_guard(**_kwargs):
        return web.json_response(
            {
                "status": "error",
                "error": "Ticket is bound to a different device",
                "error_code": "DEVICE_MISMATCH",
            },
            status=403,
        )

    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _unexpected_run_tool(self, **_kwargs):
        pytest.fail("ticket/device mismatch reached run_tool dispatch")

    monkeypatch.setattr("tools.handlers._require_ticket_device_match", _fake_ticket_device_guard, raising=False)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _unexpected_run_tool)

    response = await test_client_no_db.post(
        "/api/tools/run",
        json={
            "device_id": "device-b",
            "ticket_id": "ticket-owned-by-device-a",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"marker": "ticket-device-mismatch"},
        },
    )
    payload = await response.json()

    assert response.status == 403
    assert payload["status"] == "error"
    assert payload["error_code"] == "DEVICE_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_uses_server_registry_metadata_when_device_snapshot_is_stale(monkeypatch):
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="device-async-2",
            actor_role="agent",
            auth_type=AuthType.AGENT_TOKEN,
            token="agent-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    bind_app_value(app, key=STATE_APP_KEY, legacy_name="state", value=object())
    app.router.add_post("/api/tools/run", handle_tools_run)

    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return [
            {
                "tool": "network_ping.ping",
                "module": "network_ping",
                "aliases": ["ping"],
                "spec": {
                    "metadata": {
                        "risk_level": "safe_read",
                        "requires_consent": False,
                        "allow_roles": ["admin", "support", "agent", "llm"],
                    }
                },
            }
        ]

    async def _fake_run_tool(self, **_kwargs):
        return {
            "status": "accepted",
            "device_id": "device-async-2",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    async def _allow_account_access(**_kwargs):
        return None

    monkeypatch.setattr("tools.handlers._require_agent_tool_account_access", _allow_account_access)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/tools/run",
            json={
                "device_id": "device-async-2",
                "ticket_id": "ticket-async-2",
                "tool_name": "network_ping.ping",
                "params": {"host": "127.0.0.1"},
            },
        )
        payload = await response.json()

    assert response.status == 202
    assert payload["status"] == "accepted"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_requires_agent_account_session(monkeypatch):
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="device-async-3",
            actor_role="agent",
            auth_type=AuthType.AGENT_TOKEN,
            token="agent-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    bind_app_value(app, key=STATE_APP_KEY, legacy_name="state", value=object())
    app.router.add_post("/api/tools/run", handle_tools_run)

    async def _deny_account_access(**_kwargs):
        return web.json_response(
            {
                "status": "error",
                "error": "account_session_invalid",
                "error_code": "ACCOUNT_SESSION_REQUIRED",
            },
            status=403,
        )

    async def _unexpected_run_tool(self, **_kwargs):
        pytest.fail("run_tool must not dispatch without account session")

    monkeypatch.setattr("tools.handlers._require_agent_tool_account_access", _deny_account_access)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _unexpected_run_tool)

    async with TestClient(TestServer(app)) as client:
        response = await client.post(
            "/api/tools/run",
            json={
                "device_id": "device-async-3",
                "ticket_id": "ticket-async-3",
                "tool_name": "screen.collect",
                "params": {},
            },
        )
        payload = await response.json()

    assert response.status == 403
    assert payload["error_code"] == "ACCOUNT_SESSION_REQUIRED"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_async_surfaces_dispatch_error(test_client_no_db, monkeypatch):
    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _fake_run_tool(self, **kwargs):
        operation_id = kwargs["params"]["_operation_id"]
        return {
            "status": "error",
            "error": "WS command queue full",
            "error_code": "WS_COMMAND_QUEUE_FULL",
            "operation_id": operation_id,
            "trace_id": "trace-async-failure",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    response = await test_client_no_db.post(
        "/api/tools/run",
        json={
            "device_id": "device-async-fail",
            "ticket_id": "ticket-async-fail",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "hello"},
        },
    )
    assert response.status == 429
    payload = await response.json()

    assert payload["status"] == "error"
    assert payload["error_code"] == "WS_COMMAND_QUEUE_FULL"
    assert payload["operation_id"]
    assert payload["poll_url"] == f"/api/operations/{payload['operation_id']}"
    assert payload["trace_id"] == "trace-async-failure"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_tools_run_wait_mode_surfaces_dispatch_error(test_client_no_db, monkeypatch):
    async def _fake_get_tools_list(self, _device_id):
        return []

    async def _fake_get_tools_from_server(self, _device_id):
        return []

    async def _fake_run_tool(self, **kwargs):
        operation_id = kwargs["params"]["_operation_id"]
        return {
            "status": "error",
            "error": "Agent not connected",
            "error_code": "AGENT_NOT_CONNECTED",
            "operation_id": operation_id,
            "trace_id": "trace-sync-failure",
        }

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.run_tool", _fake_run_tool)

    response = await test_client_no_db.post(
        "/api/tools/run?wait=1",
        json={
            "device_id": "device-sync-fail",
            "ticket_id": "ticket-sync-fail",
            "tool_name": TEST_ECHO_TOOL,
            "params": {"message": "hello"},
        },
    )
    assert response.status == 503
    payload = await response.json()

    assert payload["status"] == "error"
    assert payload["error_code"] == "AGENT_NOT_CONNECTED"
    assert payload["operation_id"]
    assert payload["poll_url"] == f"/api/operations/{payload['operation_id']}"
    assert payload["trace_id"] == "trace-sync-failure"


@pytest.mark.asyncio
async def test_legacy_tools_run_creates_user_consent_for_waiting_operation(
    test_client,
    test_engine,
    monkeypatch,
):
    device_id = str(uuid.uuid4())
    ticket_id = str(uuid.uuid4())
    requester_person_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add(_device(device_id))
        session.add(
            RegistryPerson(
                person_id=requester_person_id,
                display_name="Legacy Tool Requester",
                full_name="Legacy Tool Requester",
                email=f"legacy-tool-{requester_person_id}@example.test",
                source="test",
                status="active",
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Legacy consent ticket",
                description="Ticket for legacy tools/run consent coverage.",
                status="in_progress",
                requester_id="legacy-tool-requester",
                requester_person_id=requester_person_id,
            )
        )
        await session.commit()

    async def _fake_get_tools_list(self, device_id_arg):
        assert device_id_arg == device_id
        return [
            {
                "tool": "observer_canary.consent_probe",
                "spec": {
                    "metadata": {
                        "risk_level": "safe_read",
                        "requires_consent": True,
                    }
                },
            }
        ]

    async def _fake_get_tools_from_server(self, device_id_arg):
        assert device_id_arg == device_id
        return []

    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_list", _fake_get_tools_list)
    monkeypatch.setattr("tools.handlers.ToolExecutionService.get_tools_from_server", _fake_get_tools_from_server)

    response = await test_client.post(
        "/api/tools/run",
        json={
            "device_id": device_id,
            "ticket_id": ticket_id,
            "tool_name": "observer_canary.consent_probe",
            "params": {"label": "legacy-consent", "session_token": "must-redact"},
        },
    )

    assert response.status == 202, await response.text()
    payload = await response.json()
    assert payload["status"] == "waiting_consent"
    operation_id = payload["operation_id"]

    async with session_maker() as session:
        consent = (
            await session.execute(
                select(UserConsentRequest).where(
                    UserConsentRequest.subject_type == "operation",
                    UserConsentRequest.subject_id == operation_id,
                )
            )
        ).scalar_one_or_none()
        assert consent is not None
        assert consent.status == "pending"
        assert consent.ticket_id == ticket_id
        assert consent.device_id == device_id
        assert consent.requester_person_id == requester_person_id
        assert consent.requested_action_payload_redacted["tool_name"] == "observer_canary.consent_probe"
        assert consent.requested_action_payload_redacted["params"]["session_token"] == "<redacted>"
