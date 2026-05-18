from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DiagnosticCapability, DiagnosticProvider
from inventory.service import DeviceInventoryService, extract_tool_result_payload


INVENTORY_SCHEMA = {
    "version": "1.0",
    "kind": "tool_result",
    "title": "Inventory",
    "blocks": [{"type": "field_grid", "fields": [{"path": "identity.hostname", "label": "Host"}]}],
    "fallback": {"show_raw_json": True},
}

OVERRIDE_SCHEMA = {
    "version": "1.0",
    "kind": "tool_result",
    "title": "Inventory override",
    "blocks": [{"type": "field_grid", "fields": [{"path": "network.primary_ip", "label": "IP"}]}],
}

OUTPUT_CONTRACT = {
    "kind": "device.inventory.snapshot",
    "version": "1.0",
    "device_card": {"eligible": True, "slots": ["identity", "health", "network"], "priority": 100},
}


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


def _snapshot(hostname: str, *, collected_at: datetime) -> dict:
    return {
        "schema_version": "1.0",
        "collected_at": collected_at.isoformat(),
        "identity": {"hostname": hostname, "current_user": "user"},
        "agent": {"version": "3.1.56", "protocol_version": "ws_ticket_v3"},
        "platform": {"os_name": "Windows", "os_version": "11"},
        "resources": {"cpu_percent": 12, "memory_percent": 44, "disks": []},
        "network": {"primary_ip": "192.168.100.54", "interfaces": []},
        "printers": {"default_printer": "", "items": []},
        "software": {"key_apps": []},
        "warnings": [],
    }


async def _seed_device_and_capability(test_engine, *, device_id: str) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.56",
                hostname="pc-01",
                os="Windows",
                capabilities={},
                device_metadata={},
            )
        )
        session.add(
            DiagnosticProvider(
                provider_id="inventory",
                provider_type="managed_module",
                title="Inventory",
                status="available",
            )
        )
        await session.flush()
        session.add(
            DiagnosticCapability(
                capability_id="inventory.collect",
                provider_id="inventory",
                execution_target="agent_builtin",
                title="Inventory Collect",
                status="active",
                latest_version="1.0",
                descriptor_json={
                    "id": "inventory.collect",
                    "title": "Inventory Collect",
                    "provider_id": "inventory",
                    "provider_type": "managed_module",
                    "execution_target": "agent_builtin",
                    "presentation_schema": INVENTORY_SCHEMA,
                    "output_contract": OUTPUT_CONTRACT,
                    "output_schema": {"type": "object"},
                },
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_inventory_service_persists_latest_and_history(test_engine) -> None:
    device_id = str(uuid.uuid4())
    newer_at = datetime.now(timezone.utc)
    older_at = newer_at - timedelta(hours=2)

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = DeviceInventoryService(session)
        older = await service.persist_snapshot(device_id, _snapshot("old-pc", collected_at=older_at))
        newer = await service.persist_snapshot(device_id, _snapshot("new-pc", collected_at=newer_at))
        await session.commit()

        latest = await service.get_latest(device_id)
        history = await service.list_history(device_id)

    assert latest is not None
    assert latest.id == newer.id
    assert older.snapshot_hash
    assert history[0].id == newer.id
    assert history[1].id == older.id


@pytest.mark.asyncio
async def test_extract_tool_result_payload_unwraps_tool_response_shape() -> None:
    payload = {
        "result": {
            "error": None,
            "output": {"schema_version": "1.0", "identity": {"hostname": "pc-01"}},
        }
    }

    assert extract_tool_result_payload(payload) == {"schema_version": "1.0", "identity": {"hostname": "pc-01"}}
    assert extract_tool_result_payload({"result": {"schema_version": "1.0"}}) == {"schema_version": "1.0"}
    assert extract_tool_result_payload({"result": "not-json"}) is None


@pytest.mark.asyncio
async def test_device_inventory_api_returns_effective_schema_and_history(test_client, test_engine) -> None:
    device_id = str(uuid.uuid4())
    collected_at = datetime.now(timezone.utc)
    await _seed_device_and_capability(test_engine, device_id=device_id)

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await DeviceInventoryService(session).persist_snapshot(device_id, _snapshot("pc-01", collected_at=collected_at))
        await session.commit()

    put_override = await test_client.put(
        "/api/web/tool-presentations?tool_id=inventory.collect",
        headers=_admin_headers(),
        json={"presentation_schema": OVERRIDE_SCHEMA, "enabled": True},
    )
    assert put_override.status == 200, await put_override.text()

    response = await test_client.get(f"/api/web/admin/devices/{device_id}/inventory", headers=_admin_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()
    data = payload["data"]

    latest = data["latest_snapshot"]
    assert latest["source_tool"] == "inventory.collect"
    assert latest["result"]["identity"]["hostname"] == "pc-01"
    assert latest["presentation_schema"] == INVENTORY_SCHEMA
    assert latest["effective_presentation_schema"] == OVERRIDE_SCHEMA
    assert latest["presentation_schema_source"] == "server_override"
    assert latest["device_card_slots"] == ["identity", "health", "network"]
    assert data["history"][0]["summary"].startswith("pc-01")


@pytest.mark.asyncio
async def test_device_inventory_api_handles_empty_state(test_client, test_engine) -> None:
    device_id = str(uuid.uuid4())
    await _seed_device_and_capability(test_engine, device_id=device_id)

    response = await test_client.get(f"/api/web/admin/devices/{device_id}/inventory", headers=_admin_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["data"]["device_id"] == device_id
    assert payload["data"]["latest_snapshot"] is None
    assert payload["data"]["history"] == []
