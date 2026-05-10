import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pc_agent.config.config_loader import ConfigLoader


def _reset_config_loader_singleton() -> None:
    ConfigLoader._instance = None
    ConfigLoader._config = None


def test_load_always_keeps_core_modules_enabled(tmp_path):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        "enabled_modules:\n"
        "  - system\n"
        "  - screen\n",
        encoding="utf-8",
    )

    _reset_config_loader_singleton()
    settings = ConfigLoader().load(config_path, create_dirs=False)

    assert settings.enabled_modules == ["system", "screen", "diag_logs"]

    _reset_config_loader_singleton()
