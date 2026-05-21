import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AgentRuntimeAudit,
    AgentToken,
    ConnectionRequest,
    Device,
    DeviceDesiredModule,
    DeviceInventoryBinding,
    DeviceInventoryRefreshRun,
    DeviceInventorySnapshot,
    DeviceModule,
    DeviceOutbox,
    Operation,
    ObserverTrace,
    RemoteAccessSession,
    UiUser,
)
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _requester_headers(actor_id: str = "requester-device-ops") -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_USER_PREFIX}{actor_id}"}


@pytest.mark.asyncio
async def test_device_operations_rejects_requester_role(test_client):
    response = await test_client.get(
        "/api/web/admin/device-operations/device-requester-denied",
        headers=_requester_headers(),
    )

    assert response.status == 403


@pytest.mark.asyncio
async def test_device_operations_returns_compact_context(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"device-ops-{uuid.uuid4().hex[:8]}"
    operation_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.56",
                hostname="ops-workstation-01",
                os="Windows 11",
                capabilities={"tools": ["inventory.collect", "screen.collect"]},
                current_toolset_hash="hash-1",
                device_metadata={"arch": "x64", "os_version": "23H2", "config_status": "synced"},
                first_seen_at=now - timedelta(days=10),
                last_seen_at=now - timedelta(minutes=5),
                last_handshake_at=now - timedelta(minutes=5),
            )
        )
        await session.flush()
        session.add(
            DeviceInventorySnapshot(
                id=str(uuid.uuid4()),
                device_id=device_id,
                snapshot={"raw": "not returned by device operations"},
                normalized={"summary": {"cpu": "Intel", "ram_gb": 16}},
                summary="Windows workstation inventory",
                collected_at=now - timedelta(minutes=20),
                received_at=now - timedelta(minutes=19),
            )
        )
        session.add(
            DeviceInventoryBinding(
                device_id=device_id,
                building="HQ",
                room="401",
                department="Support",
                responsible_user="Ivan Petrov",
                inventory_number="INV-42",
                status="confirmed",
                tags=["laptop"],
                updated_at=now - timedelta(days=1),
                updated_by="admin",
            )
        )
        session.add(
            DeviceInventoryRefreshRun(
                id=str(uuid.uuid4()),
                device_id=device_id,
                requested_at=now - timedelta(minutes=30),
                requested_by="admin",
                status="failed",
                error="Agent did not answer",
                completed_at=now - timedelta(minutes=25),
            )
        )
        session.add_all(
            [
                DeviceDesiredModule(
                    device_id=device_id,
                    module_name="inventory",
                    desired_version="1.2.0",
                    state="installed",
                    reason="policy",
                ),
                DeviceModule(
                    device_id=device_id,
                    module_name="inventory",
                    version="1.1.0",
                    installed=True,
                    active=True,
                    state="active",
                    last_seen_at=now - timedelta(minutes=5),
                ),
                DeviceModule(
                    device_id=device_id,
                    module_name="observer_canary",
                    version="0.9.0",
                    installed=True,
                    active=False,
                    state="failed",
                    last_error_message="Import failed",
                    last_seen_at=now - timedelta(minutes=6),
                ),
            ]
        )
        session.add(
            DeviceOutbox(
                device_id=device_id,
                command_id=str(uuid.uuid4()),
                command="inventory.collect",
                params={"tool": "inventory.collect"},
                status="pending",
                actor_role="admin",
                operation_id=operation_id,
                created_at=now - timedelta(minutes=3),
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=str(uuid.uuid4()),
                kind="tool",
                tool_name="inventory.collect",
                actor_role="support",
                trace_id=trace_id,
                status="failed",
                queued_at=now - timedelta(minutes=4),
                started_at=now - timedelta(minutes=4),
                finished_at=now - timedelta(minutes=2),
                error_message="Collector failed",
            )
        )
        session.add(
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id=device_id,
                ticket_id=str(uuid.uuid4()),
                kind="tool",
                tool_name="system.collect",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=now - timedelta(minutes=1),
                started_at=now - timedelta(minutes=1),
                finished_at=now,
                result_summary="{'raw': 'result payload must not become primary operation summary'}",
            )
        )
        session.add(
            ObserverTrace(
                trace_id=trace_id,
                root_span_id=str(uuid.uuid4()),
                root_kind="tool_call",
                device_id=device_id,
                operation_id=operation_id,
                status="failed",
                started_at=now - timedelta(minutes=4),
                finished_at=now - timedelta(minutes=2),
                error_count=1,
                attrs_json={"title": "inventory.collect failed", "latest_error": "Collector failed"},
            )
        )
        session.add(
            RemoteAccessSession(
                id=str(uuid.uuid4()),
                ticket_id=str(uuid.uuid4()),
                device_id=device_id,
                operator_id="support-test",
                requester_id="requester-1",
                mode="view_only",
                status="waiting_consent",
                reason="Need visual check",
                consent_required=True,
                consent_status="pending",
                requested_at=now - timedelta(minutes=2),
                expires_at=now + timedelta(minutes=10),
                max_duration_sec=900,
            )
        )
        session.add(
            AgentToken(
                token_hash="a" * 64,
                token_prefix="aaaaaaaa",
                device_id=device_id,
                created_at=now - timedelta(days=2),
                last_used_at=now - timedelta(minutes=5),
            )
        )
        session.add(
            ConnectionRequest(
                device_id=device_id,
                status="pending",
                hostname="ops-workstation-01",
                created_at=now - timedelta(minutes=7),
                last_request_at=now - timedelta(minutes=1),
                request_metadata={"last_error": "Waiting admin approval"},
            )
        )
        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                event_type="agent_auth_failed",
                severity="warning",
                source="agent_auth",
                details_json={"error": "Invalid token"},
                created_at=now - timedelta(minutes=1),
            )
        )
        await session.commit()

    response = await test_client.get(
        f"/api/web/admin/device-operations/{device_id}?trace_limit=5&outbox_limit=5&operation_limit=5",
        headers=_admin_headers(),
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    data = payload["data"]
    assert data["device"]["device_id"] == device_id
    assert data["device"]["hostname"] == "ops-workstation-01"
    assert data["agent"]["connection_state"] in {"online", "offline", "unknown"}
    assert data["agent"]["version"] == "3.1.56"
    assert data["inventory"]["summary"] == {"cpu": "Intel", "ram_gb": 16}
    assert data["inventory"]["latest_refresh_run"]["status"] == "failed"
    assert data["binding"]["department"] == "Support"
    assert data["modules"]["outdated_count"] >= 1
    assert data["modules"]["failed_count"] == 1
    assert data["outbox"]["pending_count"] == 1
    assert data["operations"]["recent_failed_count"] == 1
    success_operation = next(item for item in data["operations"]["items"] if item["tool_name"] == "system.collect")
    assert success_operation["error_summary"] is None
    assert data["observer"]["trace_count"] == 1
    assert data["remote_assist"]["availability"] == "requires_consent"
    assert data["provisioning"]["state"] == "pending"
    assert data["signals"]["failed_recent_operation"] is True
    assert data["signals"]["outbox_backlog"] is True
    assert data["signals"]["auth_error"] is True
    assert data["links"]["device_card"] == f"/app/admin/device?device={device_id}"


@pytest.mark.asyncio
async def test_device_operations_handles_missing_inventory_and_offline_agent(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = f"device-ops-offline-{uuid.uuid4().hex[:8]}"

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.55",
                hostname="offline-device",
                os="ALT Linux",
                first_seen_at=now - timedelta(days=3),
                last_seen_at=now - timedelta(days=2),
                last_handshake_at=now - timedelta(days=2),
            )
        )
        await session.commit()

    response = await test_client.get(f"/api/web/admin/device-operations/{device_id}", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()
    data = payload["data"]
    assert data["inventory"]["freshness"] == "missing"
    assert data["inventory"]["can_request_refresh"] is False
    assert data["agent"]["connection_state"] == "offline"
    assert data["signals"]["agent_offline"] is True
    assert data["remote_assist"]["availability"] == "offline"


@pytest.mark.asyncio
async def test_device_operations_unknown_device_returns_404(test_client):
    response = await test_client.get("/api/web/admin/device-operations/not-found-device", headers=_admin_headers())

    assert response.status == 404
