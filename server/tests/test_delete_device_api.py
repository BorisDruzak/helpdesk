from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    AgentRuntimeAudit,
    AgentToken,
    ConnectionRequest,
    Device,
    DispatchReadyDevice,
)


TEST_UI_SUPPORT_TOKEN = "test-ui-support-token"
TEST_UI_ADMIN_TOKEN = "test-ui-admin-token"


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


class _WsStub:
    def __init__(self) -> None:
        self.closed = False
        self.close_code = None
        self.close_message = None

    async def close(self, code=None, message=None):
        self.closed = True
        self.close_code = code
        self.close_message = message


async def _seed_device_with_related_rows(device_id: str) -> None:
    now = datetime.now(timezone.utc)
    token = f"seed-token-{device_id}"
    async with get_session() as session:
        device = Device(
            device_id=device_id,
            first_seen_at=now,
            last_seen_at=now,
            last_handshake_at=now,
            protocol_version="ws_ticket_v3",
            agent_version="3.0.1",
            hostname="device-host",
            os="Windows",
            capabilities={"protocol_v3": True},
            tools_version="tools-v1",
            current_toolset_hash="hash-1",
            device_metadata={"modules": ["system"]},
        )
        session.add(device)
        await session.flush()
        session.add(
            AgentToken(
                token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                token_prefix=token[:8],
                device_id=device_id,
                created_at=now,
                expires_at=None,
                revoked_at=None,
                replaced_by_token_hash=None,
                rotated_at=None,
                last_used_at=None,
            )
        )
        session.add(
            ConnectionRequest(
                device_id=device_id,
                status="pending",
                ip_address="127.0.0.1",
                hostname="device-host",
                created_at=now,
                last_request_at=now,
                resolved_at=None,
                request_metadata={"reason": "seed"},
                approved_token=None,
                approved_token_delivered_at=None,
            )
        )
        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                event_type="handshake_ok",
                severity="info",
                source="test",
                operation_id=None,
                ticket_id=None,
                actor_id=device_id,
                actor_role="agent",
                details_json={"seed": True},
                created_at=now,
            )
        )
        session.add(
            DispatchReadyDevice(
                device_id=device_id,
                shard_key=1,
                next_attempt_at=now,
                lease_owner=None,
                lease_until=None,
                updated_at=now,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_delete_device_requires_admin_role(test_client):
    device_id = str(uuid.uuid4())
    await _seed_device_with_related_rows(device_id)

    response = await test_client.delete(
        f"/api/devices/{device_id}",
        headers=_support_headers(),
    )

    assert response.status == 403
    payload = await response.json()
    assert payload["error_code"] == "FORBIDDEN"

    async with get_session() as session:
        device = await session.get(Device, device_id)

    assert device is not None


@pytest.mark.asyncio
async def test_delete_device_closes_live_session_and_cleans_related_rows(test_client):
    device_id = str(uuid.uuid4())
    await _seed_device_with_related_rows(device_id)

    ws = _WsStub()
    state = test_client.app["state"]
    state.register_agent(
        device_id,
        ws,
        {
            "device_id": device_id,
            "status": "online",
            "connected_at": datetime.now(timezone.utc).timestamp(),
        },
    )
    state._ws_command_per_device_semaphores = {device_id: object()}
    state._ws_command_per_device_run_tool_semaphores = {device_id: object()}

    response = await test_client.delete(
        f"/api/devices/{device_id}",
        headers=_admin_headers(),
    )

    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["device_id"] == device_id
    assert payload["was_online"] is True

    assert ws.closed is True
    assert ws.close_code == 4001
    assert state.get_agent(device_id) is None
    assert device_id not in state._ws_command_per_device_semaphores
    assert device_id not in state._ws_command_per_device_run_tool_semaphores

    async with get_session() as session:
        device = await session.get(Device, device_id)
        token_rows = (
            await session.execute(select(AgentToken).where(AgentToken.device_id == device_id))
        ).scalars().all()
        request_rows = (
            await session.execute(select(ConnectionRequest).where(ConnectionRequest.device_id == device_id))
        ).scalars().all()
        audit_rows = (
            await session.execute(select(AgentRuntimeAudit).where(AgentRuntimeAudit.device_id == device_id))
        ).scalars().all()
        dispatch_row = await session.get(DispatchReadyDevice, device_id)

    assert device is None
    assert token_rows == []
    assert request_rows == []
    assert audit_rows == []
    assert dispatch_row is None
