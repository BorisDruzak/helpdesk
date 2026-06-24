from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.service import ToolExecutionService, ToolService


class _FakeSession:
    async def commit(self):
        return None


@asynccontextmanager
async def _fake_session_ctx():
    yield _FakeSession()


@pytest.mark.no_db
def test_inventory_collect_is_treated_as_agent_builtin():
    service = ToolService(SimpleNamespace())

    async def unexpected_resolve(*_args, **_kwargs):  # pragma: no cover - should stay unreachable
        raise AssertionError("built-in tools must not use server module registry preflight")

    with patch("tools.service.DB_AVAILABLE", True), \
         patch.object(service, "_resolve_preferred_server_module_for_tool", new=unexpected_resolve):
        result = asyncio.run(service._ensure_module_installed("device-1", "inventory.collect"))
        presence_result = asyncio.run(service._ensure_module_installed("device-1", "presence.collect"))

    assert result is None
    assert presence_result is None


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
         patch.object(ToolService, "_session_context", new=staticmethod(_fake_session_ctx)), \
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
         patch.object(ToolService, "_session_context", new=staticmethod(_fake_session_ctx)), \
         patch.object(service, "_resolve_preferred_server_module_for_tool", new=fake_resolve), \
         patch("app.repos.ToolsetSnapshotsRepo", FakeToolsetSnapshotsRepo), \
         patch("app.repos.DeviceModulesRepo", FakeDeviceModulesRepo), \
         patch("app.repos.devices_repo.DevicesRepo", FakeDevicesRepo), \
         patch("modules.reconcile.set_desired_installed", new=fake_set_desired_installed), \
         patch("websocket.protocol.send_ws_command", new=unexpected_send_ws_command):
        result = asyncio.run(service._ensure_module_installed("device-1", "dns.resolve"))

    assert result is None
    assert desired_calls and desired_calls[0]["desired_version"] == "2.0.0"


@pytest.mark.no_db
def test_run_tool_does_not_mutate_caller_params():
    state = SimpleNamespace(get_session_by_ticket=lambda _ticket_id: None)
    service = ToolService(state)
    captured = {}

    async def fake_ensure_module_installed(*_args, **_kwargs):
        return None

    async def fake_send_ws_command(**kwargs):
        captured.update(kwargs)
        return {"status": "accepted", "operation_id": kwargs["params"]["_operation_id"]}

    params = {"_operation_id": "op-tool-immut-1", "message": "hello"}

    with patch.object(service, "_ensure_module_installed", new=fake_ensure_module_installed), \
         patch("websocket.protocol.send_ws_command", new=fake_send_ws_command):
        result = asyncio.run(
            service.run_tool(
                device_id="device-tool-immut-1",
                ticket_id="",
                tool_name="system.echo",
                params=params,
                call_id="call-tool-immut-1",
                wait_for_result=False,
            )
        )

    assert result["operation_id"] == "op-tool-immut-1"
    assert params == {"_operation_id": "op-tool-immut-1", "message": "hello"}
    assert captured["params"]["_operation_id"] == "op-tool-immut-1"
    assert captured["params"]["params"] == {"message": "hello"}


@pytest.mark.no_db
def test_run_tool_deferred_outbox_uses_enqueue_without_online_precheck():
    state = SimpleNamespace(get_session_by_ticket=lambda _ticket_id: None)
    service = ToolService(state)
    captured = {}

    async def unexpected_ensure_module_installed(*_args, **_kwargs):  # pragma: no cover - should stay unreachable
        raise AssertionError("deferred outbox dispatch must not require online module install precheck")

    async def unexpected_send_ws_command(**kwargs):  # pragma: no cover - should stay unreachable
        raise AssertionError(f"deferred outbox dispatch must not call send_ws_command: {kwargs}")

    async def fake_enqueue_command_async(**kwargs):
        captured.update(kwargs)
        return kwargs["operation_id"]

    params = {
        "_operation_id": "op-deferred-1",
        "_trace_id": "trace-deferred-1",
        "_job_id": "job-deferred-1",
        "message": "approved",
    }

    with patch.object(service, "_ensure_module_installed", new=unexpected_ensure_module_installed), \
         patch("websocket.protocol.enqueue_command_async", new=fake_enqueue_command_async), \
         patch("websocket.protocol.send_ws_command", new=unexpected_send_ws_command):
        result = asyncio.run(
            service.run_tool(
                device_id="device-deferred-1",
                ticket_id="ticket-deferred-1",
                tool_name="system.echo",
                params=params,
                call_id="call-deferred-1",
                wait_for_result=False,
                require_online=False,
            )
        )

    assert result == {
        "status": "accepted",
        "operation_id": "op-deferred-1",
        "trace_id": "trace-deferred-1",
    }
    assert captured["command"] == "run_tool"
    assert captured["operation_id"] == "op-deferred-1"
    assert captured["trace_id"] == "trace-deferred-1"
    assert captured["ticket_id"] == "ticket-deferred-1"
    assert captured["job_id"] == "job-deferred-1"
    assert captured["actor_role"] == "support"
    assert captured["require_online"] is False
    assert captured["params"]["params"] == {"message": "approved"}
    assert "_operation_id" not in captured["params"]


@pytest.mark.no_db
def test_resume_approved_operation_dispatches_through_deferred_run_tool():
    state = SimpleNamespace(get_session_by_ticket=lambda _ticket_id: None)
    service = ToolExecutionService(state)
    captured = {}
    operation = SimpleNamespace(
        operation_id="op-approved-1",
        device_id="device-approved-1",
        ticket_id="ticket-approved-1",
        job_id="job-approved-1",
        kind="tool_call",
        tool_name="system.echo",
        status="queued",
        trace_id="trace-approved-1",
        actor_role="support",
    )

    class FakeOperationsRepo:
        def __init__(self, _session):
            pass

        async def get_by_operation_id(self, operation_id):
            assert operation_id == "op-approved-1"
            return operation

    class FakeDeviceOutboxRepo:
        def __init__(self, _session):
            pass

        async def get_latest_by_operation_id(self, operation_id):
            assert operation_id == "op-approved-1"
            return None

    async def fake_restore_params(_session, *, operation_id, ticket_id):
        assert operation_id == "op-approved-1"
        assert ticket_id == "ticket-approved-1"
        return {"message": "approved"}

    async def fake_run_tool(**kwargs):
        captured.update(kwargs)
        return {"status": "accepted", "operation_id": kwargs["params"]["_operation_id"]}

    with patch("tools.service.DB_AVAILABLE", True), \
         patch("tools.service.ENABLE_DB_PERSISTENCE", True), \
         patch.object(ToolExecutionService, "_session_context", new=staticmethod(_fake_session_ctx)), \
         patch("app.repos.operations_repo.OperationsRepo", FakeOperationsRepo), \
         patch("app.repos.device_outbox_repo.DeviceOutboxRepo", FakeDeviceOutboxRepo), \
         patch.object(service, "_restore_approved_operation_params", new=fake_restore_params), \
         patch.object(service, "run_tool", new=fake_run_tool):
        result = asyncio.run(service.resume_approved_operation("op-approved-1"))

    assert result == {"status": "accepted", "operation_id": "op-approved-1"}
    assert captured["device_id"] == "device-approved-1"
    assert captured["ticket_id"] == "ticket-approved-1"
    assert captured["tool_name"] == "system.echo"
    assert captured["params"] == {
        "message": "approved",
        "_operation_id": "op-approved-1",
        "_trace_id": "trace-approved-1",
        "_job_id": "job-approved-1",
    }
    assert captured["call_id"] == "op-approved-1"
    assert captured["auth_context"].actor_role == "support"
    assert captured["wait_for_result"] is False
    assert captured["require_online"] is False
