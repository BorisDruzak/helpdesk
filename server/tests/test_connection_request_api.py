"""
Tests for connection request API (device authorization flow).

- POST /api/connection_request (no auth)
- GET /api/connection_request/status (no auth)
- GET/PATCH /api/admin/connection_policy (admin)
- GET /api/admin/connection_requests, POST approve/reject (admin)
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select, text
from app.db.models import ConnectionRequest, Device
from app.db import get_session
from app_keys import STATE_APP_KEY, replace_bound_app_value
from auth.connection_request_service import ConnectionRequestService
from tests.conftest import TEST_UI_ADMIN_TOKEN


def _admin_headers():
    return {"Authorization": "Bearer " + TEST_UI_ADMIN_TOKEN}


def _poll_params(device_id: str, payload: dict) -> dict:
    return {
        "device_id": device_id,
        "request_id": payload["request_id"],
        "poll_secret": payload["poll_secret"],
    }


async def _set_policy(engine, policy: str):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO server_config (key, value) VALUES ('connection_policy', :p) "
                "ON CONFLICT (key) DO UPDATE SET value = :p"
            ),
            {"p": policy},
        )


@pytest.mark.asyncio
async def test_connection_request_reject_all(test_client, test_engine):
    """Policy reject_all: POST connection_request returns 403."""
    await _set_policy(test_engine, "reject_all")
    device_id = str(uuid.uuid4())
    r = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "test-pc"},
    )
    assert r.status == 403
    data = await r.json()
    assert data.get("status") == "rejected"
    assert "CONNECTION_REJECTED" in (data.get("error_code") or "")


@pytest.mark.asyncio
async def test_connection_request_accept_all(test_client, test_engine):
    """Policy accept_all: POST connection_request returns 200 and token."""
    await _set_policy(test_engine, "accept_all")
    device_id = str(uuid.uuid4())
    r = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "test-pc"},
    )
    assert r.status == 200
    data = await r.json()
    assert data.get("status") == "approved"
    assert "token" in data


@pytest.mark.asyncio
async def test_connection_request_accept_all_resolves_existing_pending(test_client, test_engine):
    """Auto-approve must not leave stale pending requests behind."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    pending = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "pending-pc"},
    )
    assert pending.status == 200
    pending_payload = await pending.json()
    assert pending_payload.get("status") == "pending"

    await _set_policy(test_engine, "accept_all")
    approved = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "pending-pc"},
    )
    assert approved.status == 200
    approved_payload = await approved.json()
    assert approved_payload.get("status") == "approved"
    assert approved_payload.get("token")

    async with test_engine.connect() as conn:
        rows = (
            await conn.execute(
                select(ConnectionRequest.status, ConnectionRequest.resolved_at)
                .where(ConnectionRequest.device_id == device_id)
                .order_by(ConnectionRequest.created_at.desc())
            )
        ).all()

    assert rows
    assert all(row.status != "pending" for row in rows)
    assert any(row.status == "approved" and row.resolved_at is not None for row in rows)


@pytest.mark.asyncio
async def test_connection_request_defaults_to_accept_all_when_policy_missing(test_client):
    """Fresh environment without explicit policy should auto-approve in P0."""
    device_id = str(uuid.uuid4())
    r = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "agent_version": "1.0.0", "os_type": "windows"},
    )
    assert r.status == 200
    data = await r.json()
    assert data.get("status") == "approved"
    assert isinstance(data.get("token"), str) and data.get("token")
    assert data.get("device_id") == device_id


@pytest.mark.asyncio
async def test_connection_request_manual_pending(test_client, test_engine):
    """Policy manual: POST connection_request returns 200 pending."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    r = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "manual-pc"},
    )
    assert r.status == 200
    data = await r.json()
    assert data.get("status") == "pending"
    assert data.get("request_id")
    assert data.get("poll_secret")

    # status endpoint returns pending
    legacy = await test_client.get("/api/connection_request/status", params={"device_id": device_id})
    assert legacy.status == 400
    r2 = await test_client.get("/api/connection_request/status", params=_poll_params(device_id, data))
    assert r2.status == 200
    data2 = await r2.json()
    assert data2.get("status") == "pending"


@pytest.mark.asyncio
async def test_connection_request_manual_does_not_block_on_old_token_count(test_client, test_engine):
    device_id = str(uuid.uuid4())
    await _set_policy(test_engine, "accept_all")

    for _ in range(2):
        response = await test_client.post(
            "/api/connection_request",
            json={"device_id": device_id, "hostname": "token-limit-pc"},
        )
        assert response.status == 200

    await _set_policy(test_engine, "manual")
    response = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "token-limit-pc"},
    )
    payload = await response.json()

    assert response.status == 200
    assert payload["status"] == "pending"

    status_response = await test_client.get("/api/connection_request/status", params=_poll_params(device_id, payload))
    status_payload = await status_response.json()

    assert status_response.status == 200
    assert status_payload["status"] == "pending"

    list_response = await test_client.get("/api/admin/connection_requests", headers=_admin_headers())
    list_payload = await list_response.json()
    request_row = next(req for req in list_payload.get("connection_requests") or [] if req.get("device_id") == device_id)
    assert request_row["metadata"].get("reason") != "token_limit_exceeded"


@pytest.mark.asyncio
async def test_admin_policy_get_patch(test_client):
    """GET and PATCH /api/admin/connection_policy require admin."""
    r = await test_client.get("/api/admin/connection_policy", headers=_admin_headers())
    assert r.status == 200
    data = await r.json()
    assert "policy" in data

    r2 = await test_client.patch(
        "/api/admin/connection_policy",
        headers=_admin_headers(),
        json={"policy": "reject_all"},
    )
    assert r2.status == 200
    data2 = await r2.json()
    assert data2.get("policy") == "reject_all"


@pytest.mark.asyncio
async def test_admin_connection_requests_list_approve_reject(test_client, test_engine):
    """Create pending request, list, approve, then status returns token."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    # Create pending
    created = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "approve-pc"},
    )
    created_payload = await created.json()

    # List (admin)
    r = await test_client.get("/api/admin/connection_requests", headers=_admin_headers())
    assert r.status == 200
    data = await r.json()
    assert data.get("status") == "ok"
    requests_list = data.get("connection_requests") or []
    assert any(req.get("device_id") == device_id for req in requests_list)

    # Approve (admin)
    r2 = await test_client.post(
        f"/api/admin/connection_requests/{device_id}/approve",
        headers=_admin_headers(),
        json={},
    )
    assert r2.status == 200
    data2 = await r2.json()
    assert data2.get("status") == "ok"

    # Status returns token once
    r3 = await test_client.get("/api/connection_request/status", params=_poll_params(device_id, created_payload))
    assert r3.status == 200
    data3 = await r3.json()
    assert data3.get("status") == "approved"
    assert "token" in data3

    # Second status call: no token (already consumed)
    r4 = await test_client.get("/api/connection_request/status", params=_poll_params(device_id, created_payload))
    assert r4.status == 200
    data4 = await r4.json()
    assert data4.get("status") == "approved"
    assert "token" not in data4 or data4.get("message", "").find("delivered") != -1


@pytest.mark.asyncio
async def test_manual_heartbeat_after_approval_does_not_create_second_pending(test_client, test_engine):
    """Agent heartbeat can race with admin approval; it must not create a second prompt."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())

    initial = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "race-pc"},
    )
    assert initial.status == 200
    initial_payload = await initial.json()

    approved = await test_client.post(
        f"/api/admin/connection_requests/{device_id}/approve",
        headers=_admin_headers(),
        json={},
    )
    assert approved.status == 200

    heartbeat = await test_client.post(
        "/api/connection_request",
        json={
            "device_id": device_id,
            "hostname": "race-pc",
            "request_id": initial_payload["request_id"],
            "poll_secret": initial_payload["poll_secret"],
        },
    )
    heartbeat_payload = await heartbeat.json()

    assert heartbeat.status == 200
    assert heartbeat_payload["status"] == "pending"

    async with test_engine.connect() as conn:
        rows = (
            await conn.execute(
                select(ConnectionRequest.status)
                .where(ConnectionRequest.device_id == device_id)
                .order_by(ConnectionRequest.created_at.asc())
            )
        ).all()

    assert [row.status for row in rows] == ["approved"]

    status = await test_client.get("/api/connection_request/status", params=_poll_params(device_id, initial_payload))
    status_payload = await status.json()
    assert status.status == 200
    assert status_payload["status"] == "approved"
    assert status_payload["token"]


@pytest.mark.asyncio
async def test_status_rejects_legacy_pending_without_poll_secret(test_client, test_engine):
    """Legacy rows without poll_secret_hash cannot deliver tokens by device_id only."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())

    async with get_session() as session:
        session.add(
            ConnectionRequest(
                device_id=device_id,
                status="approved",
                request_id="legacy-no-secret",
                ip_address="127.0.0.1",
                hostname="legacy-race",
                request_metadata={},
                created_at=datetime.now(timezone.utc) - timedelta(seconds=30),
                last_request_at=datetime.now(timezone.utc) - timedelta(seconds=30),
                resolved_at=datetime.now(timezone.utc) - timedelta(seconds=30),
                approved_token="legacy-duplicate-token",
                approved_token_delivered_at=None,
            )
        )
        await session.commit()

    first = await test_client.get(
        "/api/connection_request/status",
        params={"device_id": device_id, "request_id": "legacy-no-secret", "poll_secret": "anything"},
    )
    first_payload = await first.json()
    assert first.status == 403
    assert first_payload["error_code"] == "INVALID_POLL_SECRET"


@pytest.mark.asyncio
async def test_admin_reject_request(test_client, test_engine):
    """Create pending, reject; status returns rejected."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    created = await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id},
    )
    created_payload = await created.json()
    r = await test_client.post(
        f"/api/admin/connection_requests/{device_id}/reject",
        headers=_admin_headers(),
        json={},
    )
    assert r.status == 200
    r2 = await test_client.get("/api/connection_request/status", params=_poll_params(device_id, created_payload))
    assert r2.status == 200
    data2 = await r2.json()
    assert data2.get("status") == "rejected"


@pytest.mark.asyncio
async def test_connection_request_status_reports_archived_rejection(test_client, test_engine):
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    created = await test_client.post("/api/connection_request", json={"device_id": device_id})
    created_payload = await created.json()

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
                protocol_version="ws_ticket_v3",
                agent_version="3.1.0",
                hostname="archived-host",
                os="Windows",
                capabilities={},
                tools_version=None,
                current_toolset_hash=None,
                device_metadata={},
            )
        )
        await session.commit()

    await test_client.delete(f"/api/devices/{device_id}", headers=_admin_headers())

    response = await test_client.get("/api/connection_request/status", params=_poll_params(device_id, created_payload))
    payload = await response.json()

    assert response.status == 200
    assert payload["status"] == "rejected"
    assert payload["error_code"] == "DEVICE_ARCHIVED"


@pytest.mark.asyncio
async def test_status_token_is_not_delivered_after_process_memory_loss(test_client, test_engine):
    """Approved raw token is not stored in DB; process memory loss yields approved without token."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    created = await test_client.post("/api/connection_request", json={"device_id": device_id})
    created_payload = await created.json()
    await test_client.post(
        f"/api/admin/connection_requests/{device_id}/approve",
        headers=_admin_headers(),
        json={},
    )

    # Simulate process-local state loss: DB path must still work.
    replace_bound_app_value(
        test_client.app,
        key=STATE_APP_KEY,
        legacy_name="state",
        value=test_client.app["state"].__class__(),
    )
    ConnectionRequestService._APPROVED_TOKENS.clear()

    r = await test_client.get("/api/connection_request/status", params=_poll_params(device_id, created_payload))
    assert r.status == 200
    payload = await r.json()
    assert payload.get("status") == "approved"
    assert not payload.get("token")


@pytest.mark.asyncio
async def test_connection_request_missing_device_id(test_client):
    """POST without device_id returns 400."""
    r = await test_client.post("/api/connection_request", json={})
    assert r.status == 400


@pytest.mark.asyncio
async def test_connection_request_rejects_mismatched_metadata_machine_id(test_client):
    device_id = str(uuid.uuid4())
    other_machine_id = str(uuid.uuid4())
    r = await test_client.post(
        "/api/connection_request",
        json={
            "device_id": device_id,
            "metadata": {
                "machine_id": other_machine_id,
                "install_id": str(uuid.uuid4()),
            },
        },
    )
    assert r.status == 400
    payload = await r.json()
    assert payload.get("error") == "metadata.machine_id must match device_id"


@pytest.mark.asyncio
async def test_connection_request_list_keeps_identity_metadata(test_client, test_engine):
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    install_id = str(uuid.uuid4())
    await test_client.post(
        "/api/connection_request",
        json={
            "device_id": device_id,
            "hostname": "meta-pc",
            "metadata": {
                "machine_id": device_id,
                "install_id": install_id,
                "machine_id_source": "env_uuid",
                "identity_scheme": "machine_id_v1",
            },
        },
    )

    r = await test_client.get("/api/admin/connection_requests", headers=_admin_headers())
    assert r.status == 200
    data = await r.json()
    request_row = next(req for req in data.get("connection_requests") or [] if req.get("device_id") == device_id)
    assert request_row["metadata"]["machine_id"] == device_id
    assert request_row["metadata"]["install_id"] == install_id
