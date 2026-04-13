import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ui_gui.main as gui_main_module
import ws_agent as ws_agent_module


class _FakeIdentityManager:
    uuid = "test-device"
    token = None


class _FakeDbManager:
    def __init__(self, token: str | None):
        self.token = token

    async def get_auth_token(self, device_id):
        return self.token


class _FakeAgent:
    instances = []

    def __init__(self, *args, **kwargs):
        self.identity_manager = _FakeIdentityManager()
        self.db_manager = None
        self.ui_api_server = None
        self.ui_api_task = None
        self.auth_token = None
        self.cleaned_up = False
        _FakeAgent.instances.append(self)

    async def initialize(self):
        return None

    @property
    def device_id(self):
        return "test-device"

    async def run(self):
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            # Эмулируем зависающий shutdown внутри agent.run().
            await asyncio.shield(asyncio.sleep(30))
            raise

    async def cleanup(self):
        self.cleaned_up = True


class _FakeAgentWithStoredToken(_FakeAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_manager = _FakeDbManager("stored-token")
        self.request_connection_calls = 0

    async def request_connection_flow(self, wait_for_approval_seconds=600):
        self.request_connection_calls += 1
        return False, False

    def _connection_rejected_flag_path(self):
        return Path.cwd() / "unused-rejected.flag"


class _FakeAgentUpdateExit(_FakeAgent):
    requested_exit_code = 42

    async def run(self):
        raise asyncio.CancelledError()


@pytest.mark.asyncio
async def test_main_async_does_not_hang_when_gui_stops_and_agent_cancel_is_slow(monkeypatch, tmp_path):
    async def fake_run_gui(host, port, stop_event=None, auth_complete_event=None, **kwargs):
        if auth_complete_event:
            auth_complete_event.set()
        if stop_event:
            stop_event.set()
        await asyncio.sleep(0)

    fake_config = SimpleNamespace(
        server=SimpleNamespace(ws_url="ws://127.0.0.1:8666/ws", api_url="http://127.0.0.1:8666/api"),
        logging=SimpleNamespace(level="DEBUG"),
        enabled_modules=["system"],
        ui=SimpleNamespace(host="127.0.0.1", port=8765, enabled=True, autostart_gui=False),
    )

    monkeypatch.setattr(gui_main_module, "run_gui", fake_run_gui)
    monkeypatch.setattr(ws_agent_module, "WSAgent", _FakeAgent)
    monkeypatch.setattr(ws_agent_module, "get_config", lambda: fake_config)

    await asyncio.wait_for(
        ws_agent_module.main_async(enable_gui=True, data_root=tmp_path, install_root=tmp_path / "install"),
        timeout=12,
    )

    assert _FakeAgent.instances
    assert _FakeAgent.instances[-1].cleaned_up is True


@pytest.mark.asyncio
async def test_main_async_does_not_request_connection_when_token_already_in_db(monkeypatch, tmp_path):
    _FakeAgent.instances.clear()

    async def fake_run_gui(host, port, stop_event=None, auth_complete_event=None, **kwargs):
        await asyncio.sleep(1.2)
        if auth_complete_event:
            auth_complete_event.set()
        if stop_event:
            stop_event.set()
        await asyncio.sleep(0)

    fake_config = SimpleNamespace(
        server=SimpleNamespace(ws_url="ws://127.0.0.1:8666/ws", api_url="http://127.0.0.1:8666/api"),
        logging=SimpleNamespace(level="DEBUG"),
        enabled_modules=["system"],
        ui=SimpleNamespace(host="127.0.0.1", port=8765, enabled=True, autostart_gui=False),
    )

    monkeypatch.setattr(gui_main_module, "run_gui", fake_run_gui)
    monkeypatch.setattr(ws_agent_module, "WSAgent", _FakeAgentWithStoredToken)
    monkeypatch.setattr(ws_agent_module, "get_config", lambda: fake_config)

    await asyncio.wait_for(
        ws_agent_module.main_async(enable_gui=True, data_root=tmp_path, install_root=tmp_path / "install"),
        timeout=12,
    )

    assert _FakeAgent.instances
    agent = _FakeAgent.instances[-1]
    assert agent.auth_token == "stored-token"
    assert agent.identity_manager.token == "stored-token"
    assert agent.request_connection_calls == 0


@pytest.mark.asyncio
async def test_main_async_returns_update_exit_code_when_agent_requests_self_update(monkeypatch, tmp_path):
    fake_config = SimpleNamespace(
        server=SimpleNamespace(ws_url="ws://127.0.0.1:8666/ws", api_url="http://127.0.0.1:8666/api"),
        logging=SimpleNamespace(level="DEBUG"),
        enabled_modules=["system"],
        ui=SimpleNamespace(host="127.0.0.1", port=8765, enabled=False, autostart_gui=False),
    )

    monkeypatch.setattr(ws_agent_module, "WSAgent", _FakeAgentUpdateExit)
    monkeypatch.setattr(ws_agent_module, "get_config", lambda: fake_config)

    exit_code = await ws_agent_module.main_async(
        enable_gui=False,
        data_root=tmp_path,
        install_root=tmp_path / "install",
    )

    assert exit_code == 42
