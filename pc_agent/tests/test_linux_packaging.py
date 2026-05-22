from pathlib import Path


def test_linux_agent_spec_collects_core_builtin_modules() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "pyinstaller_agent_linux.spec").read_text(encoding="utf-8")

    for module_name in ("system", "screen", "diag_logs", "inventory", "presence"):
        assert f'"pc_agent.modules.impl.{module_name}"' in text

