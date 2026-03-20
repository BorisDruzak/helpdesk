from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.db import get_session
from app.db.models import AgentBuild, Device
from app.db.engine import async_sessionmaker
from app.repos.operations_repo import OperationsRepo
from tests.conftest import TEST_UI_ADMIN_TOKEN
from websocket.agent_handshake import handle_handshake
from websocket.agent_services import CommandResultService
from websocket.contexts import AgentConnectionContext


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


async def _insert_device(device_id: str, *, os_name: str = "Windows", metadata: dict | None = None) -> None:
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="test-host",
                os=os_name,
                capabilities={},
                device_metadata=metadata or {},
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def _insert_build(*, target: str, channel: str = "stable", version: str | None = None) -> str:
    resolved_version = version or ("9.9.9-" + uuid.uuid4().hex[:8])
    sha = uuid.uuid4().hex + uuid.uuid4().hex
    async with get_session() as session:
        session.add(
            AgentBuild(
                target=target,
                channel=channel,
                version=resolved_version,
                sha256=sha[:64],
                size=123456,
                storage_path=f"{target}/{channel}/{resolved_version}/agent.zip",
                artifact_filename=f"pc_agent-{target}-{resolved_version}.zip",
                archive_type="zip",
                mime_type="application/zip",
                uploaded_by="admin",
            )
        )
        await session.commit()
    return resolved_version


@pytest.mark.asyncio
async def test_devices_contract_includes_provisioning_and_update_summary(test_client):
    device_id = str(uuid.uuid4())
    await _insert_device(
        device_id,
        metadata={
            "applied_update_version": "2.1.0",
            "last_update_operation_id": "op-123",
        },
    )

    resp = await test_client.get("/api/devices", headers=_admin_headers())
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
    assert data["devices"]

    row = next(d for d in data["devices"] if d["device_id"] == device_id)
    assert "provisioning_summary" in row
    assert "update_summary" in row
    assert row["update_summary"]["applied_update_version"] == "2.1.0"
    assert row["update_summary"]["last_update_operation_id"] == "op-123"


@pytest.mark.asyncio
async def test_single_update_response_has_operation_object(test_client):
    device_id = str(uuid.uuid4())
    await _insert_device(device_id, os_name="Windows")
    version = await _insert_build(target="windows_amd64")

    # keep this test focused on response shape
    test_client.app["state"].is_agent_online = lambda _device_id: True
    with patch("agents.agent_builds_handlers.enqueue_command_async") as mocked_enqueue:
        async def _noop(**kwargs):
            return "ok"
        mocked_enqueue.side_effect = _noop

        resp = await test_client.post(
            f"/api/devices/{device_id}/agent/update",
            headers={**_admin_headers(), "Content-Type": "application/json"},
            json={"target": "windows_amd64", "channel": "stable", "version": version},
        )

    assert resp.status == 202
    data = await resp.json()
    assert data["status"] == "accepted"
    assert data["device_id"] == device_id
    assert data["operation"]["operation_id"] == data["operation_id"]
    assert data["operation"]["status"] == "queued"
    assert data["build"]["target"] == "windows_amd64"


@pytest.mark.asyncio
async def test_bulk_update_returns_skipped_for_offline_devices(test_client):
    device_id = str(uuid.uuid4())
    await _insert_device(device_id, os_name="Windows")
    version = await _insert_build(target="windows_amd64")

    # No online agents => device should be skipped as AGENT_OFFLINE
    with patch("agents.service.AgentService.get_agents_list", return_value=[]):
        resp = await test_client.post(
            "/api/agents/update_bulk",
            headers={**_admin_headers(), "Content-Type": "application/json"},
            json={
                "rollout_mode": "bulk",
                "channel": "stable",
                "version": version,
                "device_ids": [device_id],
                "require_canary_confirmed": False,
            },
        )

    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
    assert data["rollout_mode"] == "bulk"
    assert data["operations"] == []
    assert data["errors"] == []
    assert data["skipped"]
    assert data["skipped"][0]["device_id"] == device_id
    assert data["skipped"][0]["error_code"] == "AGENT_OFFLINE"


@pytest.mark.asyncio
async def test_bulk_update_requires_server_verified_canary_operation(test_client):
    device_id = str(uuid.uuid4())
    await _insert_device(device_id, os_name="Windows")
    version = await _insert_build(target="windows_amd64")

    resp = await test_client.post(
        "/api/agents/update_bulk",
        headers={**_admin_headers(), "Content-Type": "application/json"},
        json={
            "rollout_mode": "bulk",
            "channel": "stable",
            "version": version,
            "device_ids": [device_id],
            "require_canary_confirmed": True,
            "canary_confirmed": True,
        },
    )
    assert resp.status == 409
    data = await resp.json()
    assert data["status"] == "error"
    assert data["error_code"] == "CANARY_OPERATION_REQUIRED"


@pytest.mark.asyncio
async def test_bulk_update_rejects_nonexistent_canary_operation(test_client):
    device_id = str(uuid.uuid4())
    await _insert_device(device_id, os_name="Windows")
    version = await _insert_build(target="windows_amd64")

    resp = await test_client.post(
        "/api/agents/update_bulk",
        headers={**_admin_headers(), "Content-Type": "application/json"},
        json={
            "rollout_mode": "bulk",
            "channel": "stable",
            "version": version,
            "device_ids": [device_id],
            "require_canary_confirmed": True,
            "canary_confirmed": True,
            "canary_operation_id": str(uuid.uuid4()),
        },
    )
    assert resp.status == 409
    data = await resp.json()
    assert data["status"] == "error"
    assert data["error_code"] == "CANARY_NOT_SUCCEEDED"


class _HandshakeWsStub:
    def __init__(self) -> None:
        self.closed = False
        self.close_code = None
        self.close_message = None
        self.sent_payloads = []

    async def close(self, code=None, message=None):
        self.closed = True
        self.close_code = code
        self.close_message = message

    async def send_json(self, payload):
        self.sent_payloads.append(payload)


@pytest.mark.asyncio
async def test_agent_update_marked_succeeded_only_after_handshake_confirm(test_client, test_engine):
    device_id = str(uuid.uuid4())
    await _insert_device(device_id, os_name="Windows")
    version = await _insert_build(target="windows_amd64")

    # 1) Create update operation.
    test_client.app["state"].is_agent_online = lambda _device_id: True
    with patch("agents.agent_builds_handlers.enqueue_command_async") as mocked_enqueue:
        async def _noop(**kwargs):
            return "ok"
        mocked_enqueue.side_effect = _noop
        update_resp = await test_client.post(
            f"/api/devices/{device_id}/agent/update",
            headers={**_admin_headers(), "Content-Type": "application/json"},
            json={"target": "windows_amd64", "channel": "stable", "version": version},
        )
    assert update_resp.status == 202
    operation_id = (await update_resp.json())["operation_id"]

    # 2) command_result(success) for agent_update must NOT finalize operation.
    command_result_service = CommandResultService()
    ctx = AgentConnectionContext(
        ws=SimpleNamespace(),
        request=SimpleNamespace(),
        state=test_client.app["state"],
        agent_id=device_id,
    )
    await command_result_service.handle(
        {
            "type": "command_result",
            "request_id": operation_id,
            "payload": {"status": "success", "data": {"observations": {"stage": "scheduled"}}, "error": {}, "meta": {}},
        },
        ctx,
    )

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        operation = await op_repo.get_by_operation_id(operation_id)
        assert operation is not None
        assert operation.status == "running"
        assert operation.finished_at is None

    # 3) Simulate reconnect handshake confirming applied version and operation id.
    policy_resp = await test_client.patch(
        "/api/admin/connection_policy",
        headers={**_admin_headers(), "Content-Type": "application/json"},
        json={"policy": "accept_all"},
    )
    assert policy_resp.status == 200
    req_resp = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "agent_version": "1.0.0", "os_type": "windows"},
    )
    assert req_resp.status == 200
    token = (await req_resp.json())["token"]

    ws = _HandshakeWsStub()
    request = SimpleNamespace(remote="127.0.0.1", headers={"User-Agent": "pytest"})
    handshake_message = {
        "type": "handshake",
        "protocol_version": "ws_ticket_v3",
        "token": token,
        "meta": {"capabilities": ["protocol_v3", "envelope_v3", "outbox_ack_v3"]},
        "payload": {
            "device_id": device_id,
            "agent_version": "1.0.0",
            "os": "Windows",
            "os_type": "windows",
            "modules": [],
            "applied_update_version": version,
            "last_update_operation_id": operation_id,
        },
    }
    _, _, _, authenticated = await handle_handshake(
        ws=ws,
        data=handshake_message,
        request=request,
        state=test_client.app["state"],
    )
    assert authenticated is True
    assert ws.closed is False

    async with session_maker() as session:
        op_repo = OperationsRepo(session)
        operation = await op_repo.get_by_operation_id(operation_id)
        assert operation is not None
        assert operation.status == "succeeded"
        assert operation.finished_at is not None
