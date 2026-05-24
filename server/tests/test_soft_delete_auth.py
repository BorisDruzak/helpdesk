from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import ConnectionRequest, Device

TEST_UI_ADMIN_TOKEN = "test-ui-admin-token"


@pytest.mark.asyncio
async def test_login_rejects_archived_device(test_client):
    device_id = str(uuid.uuid4())
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="archived-host",
                os="Windows",
                capabilities={},
                tools_version=None,
                current_toolset_hash=None,
                device_metadata={},
                deleted_at=datetime.now(timezone.utc),
                deleted_by="admin-test",
                delete_reason="manual",
            )
        )
        await session.commit()

    response = await test_client.post(
        "/api/login",
        json={"uuid": device_id},
        headers={"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"},
    )
    payload = await response.json()

    assert response.status == 409
    assert payload["status"] == "error"


@pytest.mark.asyncio
async def test_connection_request_rejects_archived_device_without_creating_pending(test_client):
    device_id = str(uuid.uuid4())
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="archived-host",
                os="Windows",
                capabilities={},
                tools_version=None,
                current_toolset_hash=None,
                device_metadata={},
                deleted_at=datetime.now(timezone.utc),
                deleted_by="admin-test",
                delete_reason="manual",
            )
        )
        await session.commit()

    response = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "archived-host"},
    )
    payload = await response.json()

    assert response.status == 409
    assert payload["status"] == "rejected"
    assert payload["error_code"] == "DEVICE_ARCHIVED"

    async with get_session() as session:
        rows = (
            await session.execute(
                select(ConnectionRequest).where(ConnectionRequest.device_id == device_id)
            )
        ).scalars().all()

    assert rows == []
