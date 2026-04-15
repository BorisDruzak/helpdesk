from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import Device, DeviceDesiredModule, DeviceModule, DeviceToolsetSnapshot, Module, ServerConfig
from tools.service import ToolService


def _module_manifest(module_name: str, version: str) -> dict:
    return {
        "manifest_version": 2,
        "module_name": module_name,
        "module_version": version,
        "module_api_version": "1.0.0",
        "owner_scope": "core",
        "platforms": ["win32"],
        "tools": [
            {
                "tool": "dns.resolve",
                "aliases": [f"{module_name}.resolve"],
                "method": "resolve_dns",
                "contract_version": "1.0.0",
                "dependencies": {"min_agent_version": "1.0.0"},
                "lifecycle": "stable",
                "error_codes": ["DNS_NXDOMAIN"],
                "artifact_types": [],
                "redaction": {"enabled": True, "allow_raw_sensitive_data": False},
                "resources": {"max_runtime_sec": 15, "max_artifact_count": 0, "max_artifact_bytes": 0},
                "description": "Resolve DNS",
                "params_schema": {},
                "output_schema": {},
                "presets": [],
                "capabilities": [],
                "metadata": {
                    "domain": "dns",
                    "platforms": ["win32"],
                    "risk_level": "safe_read",
                    "requires_consent": False,
                    "timeout_sec": 15,
                    "idempotent": True,
                    "side_effects": False,
                    "allow_roles": ["admin"],
                    "scopes": ["network"],
                    "origin": "managed",
                },
            }
        ],
    }


async def _seed_device(device_id: str) -> None:
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="tool-host",
                os="windows",
                capabilities={},
                device_metadata={"os_type": "Windows"},
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                last_handshake_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def _seed_module(module_name: str, version: str) -> None:
    async with get_session() as session:
        session.add(
            Module(
                module_name=module_name,
                version=version,
                sha256=(uuid.uuid4().hex + uuid.uuid4().hex)[:64],
                size=1024,
                storage_path=f"{module_name}/{version}/module.zip",
                uploaded_by="admin",
                manifest_json=_module_manifest(module_name, version),
                validation_json={"validation_status": "passed"},
                manifest_summary={"tools": [{"tool": "dns.resolve"}]},
            )
        )
        await session.commit()


async def _seed_module_preferred(module_name: str, version: str) -> None:
    async with get_session() as session:
        session.add(
            ServerConfig(
                key=f"module_preferred:{module_name}",
                value=f'{{"module_name":"{module_name}","version":"{version}","updated_by":"admin"}}',
            )
        )
        await session.commit()


async def _seed_installed_module(device_id: str, module_name: str, version: str, *, active: bool) -> None:
    async with get_session() as session:
        session.add(
            DeviceModule(
                device_id=device_id,
                module_name=module_name,
                version=version,
                installed=True,
                active=active,
                state="active" if active else "installed",
                installed_at=datetime.now(timezone.utc),
                activated_at=datetime.now(timezone.utc) if active else None,
                last_updated_at=datetime.now(timezone.utc),
                source="handshake",
            )
        )
        await session.commit()


async def _seed_snapshot(device_id: str, tool_name: str) -> None:
    async with get_session() as session:
        session.add(
            DeviceToolsetSnapshot(
                device_id=device_id,
                captured_at=datetime.now(timezone.utc),
                agent_version="1.0.0",
                toolset_hash=uuid.uuid4().hex,
                toolset_json={"tools": [{"tool": tool_name}]},
                tool_count=1,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_ensure_module_installed_upgrades_preferred_version_even_when_snapshot_has_tool():
    device_id = str(uuid.uuid4())
    module_name = f"network_basic_{uuid.uuid4().hex[:8]}"
    await _seed_device(device_id)
    await _seed_module(module_name, "1.0.0")
    await _seed_module(module_name, "1.1.0")
    await _seed_installed_module(device_id, module_name, "1.0.0", active=True)
    await _seed_snapshot(device_id, "dns.resolve")

    service = ToolService(SimpleNamespace())
    issued = []

    async def fake_send_ws_command(**kwargs):
        issued.append(kwargs)
        return {"payload": {"status": "success"}}

    with patch("websocket.protocol.send_ws_command", new=fake_send_ws_command):
        result = await service._ensure_module_installed(device_id, "dns.resolve")

    assert result is None
    assert issued
    assert issued[0]["command"] == "install_module_package"
    assert issued[0]["params"]["module_version"] == "1.1.0"

    async with get_session() as session:
        desired = (
            await session.execute(
                select(DeviceDesiredModule).where(
                    DeviceDesiredModule.device_id == device_id,
                    DeviceDesiredModule.module_name == module_name,
                )
            )
        ).scalar_one()
        assert desired.desired_version == "1.1.0"
        assert desired.reason == "run_tool"


@pytest.mark.asyncio
async def test_ensure_module_installed_persists_desired_state_without_reinstall_when_preferred_is_active():
    device_id = str(uuid.uuid4())
    module_name = f"network_basic_{uuid.uuid4().hex[:8]}"
    await _seed_device(device_id)
    await _seed_module(module_name, "2.0.0")
    await _seed_installed_module(device_id, module_name, "2.0.0", active=True)
    await _seed_snapshot(device_id, "dns.resolve")

    service = ToolService(SimpleNamespace())

    async def unexpected_send_ws_command(**kwargs):  # pragma: no cover - should never run
        raise AssertionError(f"install_module_package should not be called: {kwargs}")

    with patch("websocket.protocol.send_ws_command", new=unexpected_send_ws_command):
        result = await service._ensure_module_installed(device_id, "dns.resolve")

    assert result is None
    async with get_session() as session:
        desired = (
            await session.execute(
                select(DeviceDesiredModule).where(
                    DeviceDesiredModule.device_id == device_id,
                    DeviceDesiredModule.module_name == module_name,
                )
            )
        ).scalar_one()
        assert desired.desired_version == "2.0.0"
        assert desired.reason == "run_tool"


@pytest.mark.asyncio
async def test_ensure_module_installed_blocks_when_agent_version_too_old():
    device_id = str(uuid.uuid4())
    module_name = f"network_basic_{uuid.uuid4().hex[:8]}"
    await _seed_device(device_id)
    await _seed_module(module_name, "3.0.0")

    async with get_session() as session:
        device = await session.get(Device, device_id)
        device.agent_version = "0.9.0"
        await session.commit()

    service = ToolService(SimpleNamespace())
    result = await service._ensure_module_installed(device_id, "dns.resolve")

    assert result is not None
    assert result["error_code"] == "AGENT_VERSION_TOO_OLD"


@pytest.mark.asyncio
async def test_ensure_module_installed_uses_server_preferred_assignment_over_latest_semver():
    device_id = str(uuid.uuid4())
    module_name = f"network_basic_{uuid.uuid4().hex[:8]}"
    await _seed_device(device_id)
    await _seed_module(module_name, "1.0.0")
    await _seed_module(module_name, "2.0.0")
    await _seed_module_preferred(module_name, "1.0.0")

    service = ToolService(SimpleNamespace())
    issued = []

    async def fake_send_ws_command(**kwargs):
        issued.append(kwargs)
        return {"payload": {"status": "success"}}

    with patch("websocket.protocol.send_ws_command", new=fake_send_ws_command):
        result = await service._ensure_module_installed(device_id, "dns.resolve")

    assert result is None
    assert issued
    assert issued[0]["params"]["module_version"] == "1.0.0"
