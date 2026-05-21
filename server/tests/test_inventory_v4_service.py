from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
import uuid
import zipfile
from io import BytesIO

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device
from inventory.service import DeviceInventoryService
from presence.service import DevicePresenceService


pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="DB-backed inventory v4 tests run on Linux/CI; local Windows test_engine fixture can block on DB startup.",
)


def _device(device_id: str, *, hostname: str, online: bool = True) -> Device:
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.56",
        hostname=hostname,
        os="Linux",
        capabilities={},
        device_metadata={},
        last_seen_at=datetime.now(timezone.utc) - timedelta(minutes=1 if online else 90),
    )


def _snapshot(hostname: str, *, collected_at: datetime, disk: float = 42.0) -> dict:
    return {
        "schema_version": "1.0",
        "collected_at": collected_at.isoformat(),
        "identity": {"hostname": hostname, "current_user": "user"},
        "agent": {"version": "3.1.56"},
        "platform": {"os_name": "Linux", "os_version": "ALT"},
        "resources": {"cpu_percent": 11, "memory_percent": 44, "disks": [{"mount": "/", "used_percent": disk}]},
        "network": {"primary_ip": "192.168.100.17"},
        "software": {"key_apps": [{"id": "libreoffice", "name": "LibreOffice", "present": False}]},
    }


@pytest.mark.asyncio
async def test_bulk_refresh_preview_operation_and_xlsx_export(test_engine) -> None:
    stale_id = str(uuid.uuid4())
    missing_id = str(uuid.uuid4())
    offline_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                _device(stale_id, hostname="stale-pc"),
                _device(missing_id, hostname="missing-pc"),
                _device(offline_id, hostname="offline-pc", online=False),
            ]
        )
        service = DeviceInventoryService(session)
        await service.persist_snapshot(stale_id, _snapshot("stale-pc", collected_at=now - timedelta(days=20), disk=95))
        await service.persist_snapshot(offline_id, _snapshot("offline-pc", collected_at=now - timedelta(days=30)))
        await session.commit()

        preview = await service.bulk_refresh_preview(
            mode="stale",
            filters={"stale_days": 7},
            wave={"batch_size": 1},
            now=now,
        )
        operation = await service.create_bulk_refresh_operation(
            preview=preview,
            mode="stale",
            filters={"stale_days": 7},
            wave={"batch_size": 1},
            requested_by="admin",
        )
        xlsx = await service.export_inventory_xlsx(stale_days=7)
        await session.commit()

    assert preview["selected_count"] == 2
    assert preview["estimated_waves"] == 1
    assert operation.total_count == 2
    assert operation.skipped_count == 1
    assert xlsx.startswith(b"PK")
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        names = set(archive.namelist())
    assert "xl/worksheets/sheet1.xml" in names
    assert "xl/workbook.xml" in names


@pytest.mark.asyncio
async def test_agent_profile_suggestion_apply_ignore_and_presence_summary(test_engine) -> None:
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(_device(device_id, hostname="pc-01"))
        inventory = DeviceInventoryService(session)
        suggestion = await inventory.create_or_update_binding_suggestion_from_profile(
            device_id=device_id,
            requester_id="ivanova",
            display_name="Иванова И.И.",
            profile={
                "full_name": "Иванова И.И.",
                "department": "Бухгалтерия",
                "building": "Администрация",
                "room": "214",
                "phone": "5-12",
            },
        )
        await session.flush()
        assert suggestion is not None

        await inventory.apply_binding_suggestion(
            device_id=device_id,
            suggestion_id=suggestion.id,
            fields=["building", "room", "department"],
            reviewed_by="it",
            reason="confirmed by IT",
        )
        ignored = await inventory.create_or_update_binding_suggestion_from_profile(
            device_id=device_id,
            requester_id="petrov",
            display_name="Петров П.П.",
            profile={"full_name": "Петров П.П.", "department": "ИТ", "building": "HQ", "room": "101"},
        )
        assert ignored is not None
        await inventory.ignore_binding_suggestion(
            device_id=device_id,
            suggestion_id=ignored.id,
            reviewed_by="it",
            reason="shared device",
        )

        presence = await DevicePresenceService(session).persist_snapshot(
            device_id=device_id,
            snapshot={
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "session": {"current_user": "ivanova", "session_state": "idle", "idle_seconds": 600, "locked": False},
                "today": {
                    "date": "2026-05-19",
                    "active_seconds": 3600,
                    "idle_seconds": 600,
                    "locked_seconds": 0,
                    "offline_seconds": 0,
                    "unknown_seconds": 0,
                },
            },
        )
        await session.commit()

        history = await inventory.list_binding_history(device_id)
        payload = await DevicePresenceService(session).build_device_payload(device_id)

    assert presence.session_state == "idle"
    assert history[0].reason == "confirmed by IT"
    assert payload["latest"]["session_state"] == "idle"
    assert payload["today"]["idle_seconds"] == 600
