from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import sys
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device
from inventory.scheduler import InventoryRefreshRuntime
from inventory.service import DeviceInventoryService


pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="DB-backed inventory v3 tests run on Linux/CI; local Windows test_engine fixture can block on DB startup.",
    ),
    pytest.mark.db_cleanup("full"),
]


def _device(device_id: str, *, hostname: str, last_seen_offset_minutes: int = 0) -> Device:
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.56",
        hostname=hostname,
        os="Linux",
        capabilities={},
        device_metadata={},
        last_seen_at=datetime.now(timezone.utc) - timedelta(minutes=last_seen_offset_minutes),
    )


def _snapshot(hostname: str, *, collected_at: datetime, disk: float = 42.0, apps: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "collected_at": collected_at.isoformat(),
        "identity": {"hostname": hostname, "current_user": "user"},
        "agent": {"version": "3.1.56", "protocol_version": "ws_ticket_v3"},
        "platform": {"os_name": "Linux", "os_version": "ALT"},
        "resources": {
            "cpu_percent": 12,
            "memory_percent": 44,
            "disks": [{"name": "/", "mount": "/", "used_percent": disk}],
        },
        "network": {"primary_ip": "192.168.100.17", "interfaces": []},
        "printers": {"default_printer": "Office", "items": [{"name": "Office", "status": "idle"}]},
        "software": {"key_apps": apps or [{"id": "libreoffice", "name": "LibreOffice", "present": True}]},
        "warnings": [],
    }


@pytest.mark.asyncio
async def test_binding_history_records_changed_fields_and_skips_identical_updates(test_engine) -> None:
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(_device(device_id, hostname="pc-01"))
        service = DeviceInventoryService(session)

        await service.upsert_binding(
            device_id,
            {"building": "HQ", "room": "401", "responsible_user": "Ivan"},
            updated_by="admin",
            reason="initial import",
        )
        await service.upsert_binding(
            device_id,
            {"building": "HQ", "room": "402", "responsible_user": "Ivan"},
            updated_by="admin",
            reason="move",
        )
        await service.upsert_binding(
            device_id,
            {"building": "HQ", "room": "402", "responsible_user": "Ivan"},
            updated_by="admin",
            reason="same payload",
        )
        await session.commit()

        history = await service.list_binding_history(device_id)

    assert len(history) == 2
    assert history[0].reason == "move"
    assert history[0].changed_fields == ["room"]
    assert history[0].old_binding["room"] == "401"
    assert history[0].new_binding["room"] == "402"
    assert history[1].old_binding is None
    assert sorted(history[1].changed_fields) == ["building", "responsible_user", "room"]


@pytest.mark.asyncio
async def test_binding_csv_import_dry_run_apply_and_export_escape_formula_cells(test_engine) -> None:
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    csv_text = (
        "device_id,hostname,building,room,department,responsible_user,inventory_number,status,tags,notes\n"
        f"{device_id},pc-01,HQ,401,Support,Ivan,=INV-42,active,\"laptop,shared\",normal\n"
        ",missing-host,HQ,402,Support,Petr,INV-404,active,,unknown device\n"
    )

    async with session_maker() as session:
        session.add(_device(device_id, hostname="pc-01"))
        service = DeviceInventoryService(session)

        dry_run = await service.import_bindings_csv(csv_text, dry_run=True, updated_by="admin", reason="dry")
        assert dry_run["dry_run"] is True
        assert dry_run["valid_rows"] == 1
        assert dry_run["error_rows"] == 1
        assert dry_run["changes"][0]["action"] == "update"
        assert dry_run["changes"][1]["action"] == "error"

        applied = await service.import_bindings_csv(csv_text, dry_run=False, updated_by="admin", reason="apply")
        await session.commit()
        assert applied["dry_run"] is False
        assert applied["valid_rows"] == 1

        exported = await service.export_bindings_csv()

    assert "device_id,hostname,building" in exported
    assert "'=INV-42" in exported
    assert "laptop;shared" in exported


@pytest.mark.asyncio
async def test_inventory_dashboard_and_export_report_fresh_stale_missing_and_gaps(test_engine) -> None:
    fresh_id = str(uuid.uuid4())
    stale_id = str(uuid.uuid4())
    missing_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                _device(fresh_id, hostname="fresh-pc"),
                _device(stale_id, hostname="stale-pc", last_seen_offset_minutes=60),
                _device(missing_id, hostname="missing-pc", last_seen_offset_minutes=120),
            ]
        )
        service = DeviceInventoryService(session)
        await service.persist_snapshot(
            fresh_id,
            _snapshot("fresh-pc", collected_at=now - timedelta(days=1), disk=91.0),
        )
        await service.persist_snapshot(
            stale_id,
            _snapshot(
                "stale-pc",
                collected_at=now - timedelta(days=12),
                apps=[{"id": "libreoffice", "name": "LibreOffice", "present": False}],
            ),
        )
        await service.upsert_binding(fresh_id, {"building": "HQ", "department": "Support", "room": "401"})
        await session.commit()

        dashboard = await service.build_dashboard(stale_days=7, now=now)
        export_csv = await service.export_inventory_csv(stale_days=7, now=now)

    assert dashboard["totals"]["devices"] == 3
    assert dashboard["totals"]["with_inventory"] == 2
    assert dashboard["totals"]["missing_inventory"] == 1
    assert dashboard["totals"]["fresh_inventory"] == 1
    assert dashboard["totals"]["stale_inventory"] == 1
    assert dashboard["binding_gaps"]["missing_room"] == 2
    assert dashboard["health"]["high_disk_usage"] == 1
    assert dashboard["health"]["missing_key_apps"][0]["device_id"] == stale_id
    assert "fresh-pc" in export_csv
    assert "stale" in export_csv
    assert "missing-pc" in export_csv


@pytest.mark.asyncio
async def test_refresh_runtime_records_dispatched_and_offline_runs(monkeypatch, test_engine) -> None:
    online_id = str(uuid.uuid4())
    offline_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all([_device(online_id, hostname="online-pc"), _device(offline_id, hostname="offline-pc")])
        service = DeviceInventoryService(session)
        online_policy = await service.upsert_refresh_policy(
            scope="device",
            device_id=online_id,
            enabled=True,
            interval_minutes=60,
        )
        offline_policy = await service.upsert_refresh_policy(
            scope="device",
            device_id=offline_id,
            enabled=True,
            interval_minutes=60,
        )
        online_policy.next_due_at = now - timedelta(minutes=1)
        offline_policy.next_due_at = now - timedelta(minutes=1)
        await session.commit()

    @asynccontextmanager
    async def _test_session():
        async with session_maker() as session:
            yield session

    monkeypatch.setattr("inventory.scheduler.get_session", _test_session)

    calls: list[dict] = []

    class FakeToolService:
        def __init__(self, state):
            self.state = state

        async def run_tool(self, **kwargs):
            calls.append(kwargs)
            return {"status": "accepted", "operation_id": kwargs["params"]["_operation_id"]}

    state = SimpleNamespace(
        connected_agents={online_id: object()},
        is_agent_online=lambda checked_device_id: checked_device_id == online_id,
    )
    runtime = InventoryRefreshRuntime(state=state, tool_service_factory=FakeToolService)

    result = await runtime.run_once(now=now)

    async with session_maker() as session:
        service = DeviceInventoryService(session)
        online_runs = await service.list_refresh_runs(device_id=online_id)
        offline_runs = await service.list_refresh_runs(device_id=offline_id)

    assert result["dispatched"] == 1
    assert result["skipped_offline"] == 1
    assert calls[0]["device_id"] == online_id
    assert online_runs[0].status == "dispatched"
    assert online_runs[0].job_id
    assert offline_runs[0].status == "skipped_offline"
