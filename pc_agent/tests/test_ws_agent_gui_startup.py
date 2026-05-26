import builtins
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pc_agent.ws_agent as ws_agent_module


def test_gui_import_failure_exits_without_headless_fallback(monkeypatch, tmp_path):
    class _FakeLock:
        def __init__(self, _path):
            self.released = False

        def acquire(self):
            return True

        def release(self):
            self.released = True

    main_async_calls = []

    async def _fake_main_async(*args, **kwargs):
        main_async_calls.append((args, kwargs))
        return 0

    original_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        if name == "qasync" or name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("Qt runtime missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(ws_agent_module.runtime_paths, "resolve_data_root", lambda cli_value=None: tmp_path / "data")
    monkeypatch.setattr(ws_agent_module.runtime_paths, "resolve_install_root", lambda cli_value=None: tmp_path / "install")
    monkeypatch.setattr(ws_agent_module, "SingleInstanceLock", _FakeLock)
    monkeypatch.setattr(ws_agent_module, "init_config", lambda data_root: None)
    monkeypatch.setattr(ws_agent_module, "get_config", lambda: SimpleNamespace(ui=SimpleNamespace(autostart_gui=True)))
    monkeypatch.setattr(ws_agent_module, "main_async", _fake_main_async)
    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    monkeypatch.setattr(sys, "argv", ["ws_agent.py", "--gui", "--data-dir", str(tmp_path / "data")])

    with pytest.raises(SystemExit) as exc_info:
        ws_agent_module.main()

    assert exc_info.value.code == 1
    assert main_async_calls == []
