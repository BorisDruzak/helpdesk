from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.service import ToolService


class _FakeSession:
    async def commit(self):
        return None


@asynccontextmanager
async def _fake_session_ctx():
    yield _FakeSession()


@pytest.mark.no_db
def test_ensure_module_installed_reinstalls_when_snapshot_has_tool_but_active_version_is_old():
    service = ToolService(SimpleNamespace())
    desired_calls = []
    install_calls = []
    module = SimpleNamespace(module_name="network_basic", version="1.1.0", sha256="a" * 64, size=1024)

    async def fake_resolve(_session, _tool_name):
        return {
            "status": "ok",
            "module": module,
            "manifest": {"platforms": ["win32"]},
            "tool_entry": {"tool": "dns.resolve", "aliases": ["network_basic.resolve"]},
        }

    class FakeToolsetSnapshotsRepo:
        def __init__(self, _session):
            pass

        async def get_latest_snapshot(self, _device_id):
            return SimpleNamespace(toolset_json={"tools": [{"tool": "dns.resolve"}]})

    class FakeDeviceModulesRepo:
        def __init__(self, _session):
            pass

        async def get_device_modules(self, _device_id, active_only=False):
            assert active_only is False
            return [SimpleNamespace(module_name="network_basic", version="1.0.0", installed=True, active=True)]

    class FakeDevicesRepo:
        def __init__(self, _session):
            pass

        async def get_by_device_id(self, _device_id):
            return SimpleNamespace(os="windows")

    async def fake_set_desired_installed(**kwargs):
        desired_calls.append(kwargs)

    async def fake_send_ws_command(**kwargs):
        install_calls.append(kwargs)
        return {"payload": {"status": "success"}}

    with patch("tools.service.DB_AVAILABLE", True), \
         patch("tools.service.get_session", new=_fake_session_ctx), \
         patch.object(service, "_resolve_preferred_server_module_for_tool", new=fake_resolve), \
         patch("app.repos.ToolsetSnapshotsRepo", FakeToolsetSnapshotsRepo), \
         patch("app.repos.DeviceModulesRepo", FakeDeviceModulesRepo), \
         patch("app.repos.devices_repo.DevicesRepo", FakeDevicesRepo), \
         patch("modules.reconcile.set_desired_installed", new=fake_set_desired_installed), \
         patch("websocket.protocol.send_ws_command", new=fake_send_ws_command):
        result = asyncio.run(service._ensure_module_installed("device-1", "dns.resolve"))

    assert result is None
    assert desired_calls and desired_calls[0]["desired_version"] == "1.1.0"
    assert install_calls and install_calls[0]["params"]["module_version"] == "1.1.0"


@pytest.mark.no_db
def test_ensure_module_installed_only_persists_desired_state_when_preferred_version_is_already_active():
    service = ToolService(SimpleNamespace())
    desired_calls = []
    module = SimpleNamespace(module_name="network_basic", version="2.0.0", sha256="b" * 64, size=2048)

    async def fake_resolve(_session, _tool_name):
        return {
            "status": "ok",
            "module": module,
            "manifest": {"platforms": ["win32"]},
            "tool_entry": {"tool": "dns.resolve", "aliases": ["network_basic.resolve"]},
        }

    class FakeToolsetSnapshotsRepo:
        def __init__(self, _session):
            pass

        async def get_latest_snapshot(self, _device_id):
            return SimpleNamespace(toolset_json={"tools": [{"tool": "dns.resolve"}]})

    class FakeDeviceModulesRepo:
        def __init__(self, _session):
            pass

        async def get_device_modules(self, _device_id, active_only=False):
            assert active_only is False
            return [SimpleNamespace(module_name="network_basic", version="2.0.0", installed=True, active=True)]

    class FakeDevicesRepo:
        def __init__(self, _session):
            pass

        async def get_by_device_id(self, _device_id):
            return SimpleNamespace(os="windows")

    async def fake_set_desired_installed(**kwargs):
        desired_calls.append(kwargs)

    async def unexpected_send_ws_command(**kwargs):  # pragma: no cover - should stay unreachable
        raise AssertionError(f"install_module_package should not be called: {kwargs}")

    with patch("tools.service.DB_AVAILABLE", True), \
         patch("tools.service.get_session", new=_fake_session_ctx), \
         patch.object(service, "_resolve_preferred_server_module_for_tool", new=fake_resolve), \
         patch("app.repos.ToolsetSnapshotsRepo", FakeToolsetSnapshotsRepo), \
         patch("app.repos.DeviceModulesRepo", FakeDeviceModulesRepo), \
         patch("app.repos.devices_repo.DevicesRepo", FakeDevicesRepo), \
         patch("modules.reconcile.set_desired_installed", new=fake_set_desired_installed), \
         patch("websocket.protocol.send_ws_command", new=unexpected_send_ws_command):
        result = asyncio.run(service._ensure_module_installed("device-1", "dns.resolve"))

    assert result is None
    assert desired_calls and desired_calls[0]["desired_version"] == "2.0.0"
