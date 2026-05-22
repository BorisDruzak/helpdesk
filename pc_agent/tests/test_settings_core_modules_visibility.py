from __future__ import annotations

import inspect

import pytest

from pc_agent.config.config_loader import CORE_ENABLED_MODULES, ConfigLoader
from pc_agent.ui_bridge.settings_service import AgentSettingsService
from pc_agent.ui_gui.main_window import MainWindow


def _reset_config_loader_singleton() -> None:
    ConfigLoader._instance = None
    ConfigLoader._config = None


@pytest.mark.asyncio
async def test_settings_payload_exposes_core_and_configured_modules(tmp_path, monkeypatch):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        "enabled_modules:\n"
        "  - system\n"
        "  - screen\n"
        "  - diag_logs\n",
        encoding="utf-8",
    )

    _reset_config_loader_singleton()
    ConfigLoader().load(config_path, create_dirs=False)

    service = AgentSettingsService(data_root=tmp_path)
    monkeypatch.setattr(service, "_get_device_id", lambda: "device-1")

    async def no_token(_device_id: str):
        return None

    monkeypatch.setattr(service, "_get_active_token", no_token)

    payload = await service.get_settings()

    assert payload["enabled_modules"] == list(CORE_ENABLED_MODULES)
    assert payload["configured_enabled_modules"] == ["system", "screen", "diag_logs"]
    assert payload["core_enabled_modules"] == list(CORE_ENABLED_MODULES)

    _reset_config_loader_singleton()


def test_main_window_settings_page_has_core_modules_readonly_surface():
    setup_source = inspect.getsource(MainWindow._setup_ui)
    apply_source = inspect.getsource(MainWindow._apply_settings_to_form)

    assert "core_modules_label" in setup_source
    assert "core_enabled_modules" in apply_source
    assert "inventory" in setup_source
    assert "presence" in setup_source
