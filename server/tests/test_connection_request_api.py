"""
Tests for connection request API (device authorization flow).

- POST /api/connection_request (no auth)
- GET /api/connection_request/status (no auth)
- GET/PATCH /api/admin/connection_policy (admin)
- GET /api/admin/connection_requests, POST approve/reject (admin)
"""
import uuid
import pytest
from sqlalchemy import select, text
from app.db.models import ConnectionRequest
from tests.conftest import TEST_UI_ADMIN_TOKEN


def _admin_headers():
    return {"Authorization": "Bearer " + TEST_UI_ADMIN_TOKEN}


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

    # status endpoint returns pending
    r2 = await test_client.get("/api/connection_request/status", params={"device_id": device_id})
    assert r2.status == 200
    data2 = await r2.json()
    assert data2.get("status") == "pending"


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
    await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id, "hostname": "approve-pc"},
    )

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
    r3 = await test_client.get("/api/connection_request/status", params={"device_id": device_id})
    assert r3.status == 200
    data3 = await r3.json()
    assert data3.get("status") == "approved"
    assert "token" in data3

    # Second status call: no token (already consumed)
    r4 = await test_client.get("/api/connection_request/status", params={"device_id": device_id})
    assert r4.status == 200
    data4 = await r4.json()
    assert data4.get("status") == "approved"
    assert "token" not in data4 or data4.get("message", "").find("delivered") != -1


@pytest.mark.asyncio
async def test_admin_reject_request(test_client, test_engine):
    """Create pending, reject; status returns rejected."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    await test_client.post(
        "/api/connection_request",
        json={"device_id": device_id},
    )
    r = await test_client.post(
        f"/api/admin/connection_requests/{device_id}/reject",
        headers=_admin_headers(),
        json={},
    )
    assert r.status == 200
    r2 = await test_client.get("/api/connection_request/status", params={"device_id": device_id})
    assert r2.status == 200
    data2 = await r2.json()
    assert data2.get("status") == "rejected"


@pytest.mark.asyncio
async def test_status_token_is_db_backed_not_state(test_client, test_engine):
    """Approved token is consumed from DB without relying on StateManager memory."""
    await _set_policy(test_engine, "manual")
    device_id = str(uuid.uuid4())
    await test_client.post("/api/connection_request", json={"device_id": device_id})
    await test_client.post(
        f"/api/admin/connection_requests/{device_id}/approve",
        headers=_admin_headers(),
        json={},
    )

    # Simulate process-local state loss: DB path must still work.
    test_client.app["state"] = test_client.app["state"].__class__()

    r = await test_client.get("/api/connection_request/status", params={"device_id": device_id})
    assert r.status == 200
    payload = await r.json()
    assert payload.get("status") == "approved"
    assert payload.get("token")


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
