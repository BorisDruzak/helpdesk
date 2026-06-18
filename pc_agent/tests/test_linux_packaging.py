from pathlib import Path


def _assert_agent_spec_collects_core_builtin_modules(spec_name: str) -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / spec_name).read_text(encoding="utf-8")

    for module_name in ("system", "screen", "diag_logs", "inventory", "presence"):
        assert f'"pc_agent.modules.impl.{module_name}"' in text

    assert "pc_agent/ui_gui/assets" in text


def test_linux_agent_spec_collects_core_builtin_modules() -> None:
    _assert_agent_spec_collects_core_builtin_modules("pyinstaller_agent_linux.spec")


def test_windows_agent_specs_collect_core_builtin_modules() -> None:
    _assert_agent_spec_collects_core_builtin_modules("pyinstaller_agent_win.spec")
    _assert_agent_spec_collects_core_builtin_modules("pyinstaller_agent_win_release.spec")
