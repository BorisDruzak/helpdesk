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
    DeviceOutbox,
    DispatchReadyDevice,
    Operation,
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
    operation_id = str(uuid.uuid4())
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
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=None,
                kind="command",
                actor_role="admin",
                trace_id=str(uuid.uuid4()),
                status="queued",
                command_name="get_status",
                queued_at=now,
            )
        )
        session.add(
            DeviceOutbox(
                device_id=device_id,
                command_id=operation_id,
                command="get_status",
                params={},
                status="pending",
                operation_id=operation_id,
                actor_role="admin",
                created_at=now,
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
    assert device.deleted_at is None


@pytest.mark.asyncio
async def test_web_admin_delete_device_alias_archives_device(test_client):
    device_id = str(uuid.uuid4())
    await _seed_device_with_related_rows(device_id)

    response = await test_client.delete(
        f"/api/web/admin/devices/{device_id}",
        headers=_admin_headers(),
        json={"reason": "inventory archive action"},
    )

    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["device_id"] == device_id
    assert payload["is_deleted"] is True
    assert payload["delete_reason"] == "inventory archive action"

    async with get_session() as session:
        device = await session.get(Device, device_id)

    assert device is not None
    assert device.deleted_at is not None
    assert device.delete_reason == "inventory archive action"


@pytest.mark.asyncio
async def test_web_admin_restore_device_requires_admin_role(test_client):
    device_id = str(uuid.uuid4())
    await _seed_device_with_related_rows(device_id)

    archive_response = await test_client.delete(
        f"/api/web/admin/devices/{device_id}",
        headers=_admin_headers(),
        json={"reason": "restore permission seed"},
    )
    assert archive_response.status == 200

    response = await test_client.post(
        f"/api/web/admin/devices/{device_id}/restore",
        headers=_support_headers(),
        json={"reason": "support must not restore"},
    )

    assert response.status == 403
    payload = await response.json()
    assert payload["error_code"] == "FORBIDDEN"

    async with get_session() as session:
        device = await session.get(Device, device_id)

    assert device is not None
    assert device.deleted_at is not None


@pytest.mark.asyncio
async def test_web_admin_restore_device_reactivates_record_without_reviving_tokens(test_client):
    device_id = str(uuid.uuid4())
    await _seed_device_with_related_rows(device_id)

    archive_response = await test_client.delete(
        f"/api/web/admin/devices/{device_id}",
        headers=_admin_headers(),
        json={"reason": "archived by mistake"},
    )
    assert archive_response.status == 200

    hidden_response = await test_client.get("/api/web/admin/devices", headers=_admin_headers())
    hidden_payload = await hidden_response.json()
    assert all(item["device_id"] != device_id for item in hidden_payload["data"]["devices"])

    archived_response = await test_client.get(
        "/api/web/admin/devices?include_archived=1",
        headers=_admin_headers(),
    )
    archived_payload = await archived_response.json()
    archived_item = next(item for item in archived_payload["data"]["devices"] if item["device_id"] == device_id)
    assert archived_item["is_deleted"] is True
    assert archived_item["deleted_at"]
    assert archived_item["delete_reason"] == "archived by mistake"
    assert archived_payload["data"]["summary"]["archived_count"] >= 1

    restore_response = await test_client.post(
        f"/api/web/admin/devices/{device_id}/restore",
        headers=_admin_headers(),
        json={"reason": "restore after accidental archive"},
    )

    assert restore_response.status == 200
    restore_payload = await restore_response.json()
    assert restore_payload["status"] == "success"
    assert restore_payload["data"]["device_id"] == device_id
    assert restore_payload["data"]["is_deleted"] is False
    assert restore_payload["data"]["tokens_restored"] is False
    assert restore_payload["data"]["sessions_restored"] is False

    active_response = await test_client.get("/api/web/admin/devices", headers=_admin_headers())
    active_payload = await active_response.json()
    active_item = next(item for item in active_payload["data"]["devices"] if item["device_id"] == device_id)
    assert active_item["is_deleted"] is False
    assert active_item["deleted_at"] is None

    async with get_session() as session:
        device = await session.get(Device, device_id)
        token_rows = (
            await session.execute(select(AgentToken).where(AgentToken.device_id == device_id))
        ).scalars().all()
        request_rows = (
            await session.execute(select(ConnectionRequest).where(ConnectionRequest.device_id == device_id))
        ).scalars().all()
        audit_rows = (
            await session.execute(
                select(AgentRuntimeAudit).where(
                    AgentRuntimeAudit.device_id == device_id,
                    AgentRuntimeAudit.event_type == "device_restored_from_archive",
                )
            )
        ).scalars().all()

    assert device is not None
    assert device.deleted_at is None
    assert device.deleted_by is None
    assert device.delete_reason is None
    assert len(token_rows) == 1
    assert token_rows[0].revoked_at is not None
    assert len(request_rows) == 1
    assert request_rows[0].status == "rejected"
    assert len(audit_rows) == 1
    assert audit_rows[0].details_json["tokens_restored"] is False
    assert audit_rows[0].details_json["sessions_restored"] is False


@pytest.mark.asyncio
async def test_delete_device_archives_device_and_preserves_history(test_client):
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
        json={"reason": "Дубликат агента"},
    )

    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["device_id"] == device_id
    assert payload["was_online"] is True
    assert payload["is_deleted"] is True
    assert payload["deleted_by"] == "admin-test"
    assert payload["delete_reason"] == "Дубликат агента"

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
        outbox_rows = (
            await session.execute(select(DeviceOutbox).where(DeviceOutbox.device_id == device_id))
        ).scalars().all()
        operation_rows = (
            await session.execute(select(Operation).where(Operation.device_id == device_id))
        ).scalars().all()

    assert device is not None
    assert device.deleted_at is not None
    assert device.deleted_by == "admin-test"
    assert device.delete_reason == "Дубликат агента"

    assert len(token_rows) == 1
    assert token_rows[0].revoked_at is not None

    assert len(request_rows) == 1
    assert request_rows[0].status == "rejected"
    assert request_rows[0].resolved_at is not None
    assert request_rows[0].request_metadata["archived_by"] == "admin-test"
    assert request_rows[0].request_metadata["archive_reason"] == "Дубликат агента"

    assert len(audit_rows) == 1
    assert audit_rows[0].event_type == "handshake_ok"

    assert dispatch_row is None

    assert len(outbox_rows) == 1
    assert outbox_rows[0].status == "failed"
    assert outbox_rows[0].error_code == "DEVICE_ARCHIVED"
    assert outbox_rows[0].failed_at is not None

    assert len(operation_rows) == 1
    assert operation_rows[0].status == "canceled"
    assert operation_rows[0].status_before_cancel == "queued"
    assert operation_rows[0].cancel_reason == "device_archived"
    assert operation_rows[0].finished_at is not None
    assert operation_rows[0].error_code == "DEVICE_ARCHIVED"


@pytest.mark.asyncio
async def test_archived_device_hidden_from_list_but_available_in_detail(test_client):
    device_id = str(uuid.uuid4())
    await _seed_device_with_related_rows(device_id)

    delete_response = await test_client.delete(
        f"/api/devices/{device_id}",
        headers=_admin_headers(),
    )
    assert delete_response.status == 200

    list_response = await test_client.get("/api/devices", headers=_admin_headers())
    detail_response = await test_client.get(f"/api/devices/{device_id}", headers=_admin_headers())

    list_payload = await list_response.json()
    detail_payload = await detail_response.json()

    assert list_response.status == 200
    assert all(item["device_id"] != device_id for item in list_payload["devices"])

    assert detail_response.status == 200
    assert detail_payload["device"]["device_id"] == device_id
    assert detail_payload["device"]["is_deleted"] is True
    assert detail_payload["device"]["deleted_at"]
