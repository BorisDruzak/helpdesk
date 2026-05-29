from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.db import get_session
from app.db.models import Device
from tests.conftest import TEST_UI_ADMIN_TOKEN
from websocket.agent_handshake import handle_handshake


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


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


@pytest.mark.asyncio
async def test_screen_tool_metadata_allows_agent_for_stale_snapshot():
    from core.policy_engine import PolicyEngine

    engine = PolicyEngine()
    metadata = engine.get_tool_metadata(
        "screen.collect",
        tools_list=[
            {
                "tool": "screen.collect",
                "spec": {
                    "metadata": {
                        "risk_level": "sensitive_read",
                        "requires_consent": True,
                        "allow_roles": ["admin", "support"],
                    }
                },
            }
        ],
    )

    assert metadata is not None
    assert metadata.requires_consent is False
    assert set(metadata.allow_roles or []) == {"user", "agent", "llm", "support", "admin"}


@pytest.mark.asyncio
async def test_handshake_reconciles_after_modules_inventory_sync(test_client):
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="handshake-host",
                os="Windows",
                capabilities={},
                device_metadata={"os_type": "windows"},
                first_seen_at=now,
                last_seen_at=now,
                last_handshake_at=now,
            )
        )
        await session.commit()

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
            "modules": ["system", "screen"],
            "modules_inventory": [
                {"name": "system", "version": "1.0.0", "state": "active", "active": True},
                {"name": "screen", "version": "1.0.0", "state": "active", "active": True},
            ],
        },
    }

    sync_mock = AsyncMock()
    reconcile_mock = AsyncMock()
    with patch("websocket.modules_sync.sync_modules_inventory", new=sync_mock), \
         patch("modules.reconcile.reconcile_device", new=reconcile_mock):
        _, _, _, authenticated = await handle_handshake(
            ws=ws,
            data=handshake_message,
            request=request,
            state=test_client.app["state"],
        )

    assert authenticated is True
    sync_mock.assert_awaited_once()
    reconcile_mock.assert_awaited_once()
    kwargs = reconcile_mock.await_args.kwargs
    assert kwargs["device_id"] == device_id
    assert kwargs["reason"] == "handshake_modules_inventory"


@pytest.mark.asyncio
async def test_handshake_enqueues_list_tools_when_toolset_hash_changes(test_client):
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="handshake-host",
                os="Windows",
                capabilities={},
                current_toolset_hash="old-toolset-hash",
                current_toolset_snapshot_id=42,
                device_metadata={"os_type": "windows"},
                first_seen_at=now,
                last_seen_at=now,
                last_handshake_at=now,
            )
        )
        await session.commit()

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
            "toolset_hash": "new-toolset-hash",
            "modules": ["system"],
            "modules_inventory": [
                {"name": "system", "version": "1.0.0", "state": "active", "active": True},
            ],
        },
    }

    enqueue_mock = AsyncMock(return_value="cmd-list-tools")
    with patch("websocket.protocol.enqueue_command_async", new=enqueue_mock), \
         patch("modules.reconcile.reconcile_device", new=AsyncMock()):
        _, _, _, authenticated = await handle_handshake(
            ws=ws,
            data=handshake_message,
            request=request,
            state=test_client.app["state"],
        )

    assert authenticated is True
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.kwargs["device_id"] == device_id
    assert enqueue_mock.await_args.kwargs["command"] == "list_tools"
