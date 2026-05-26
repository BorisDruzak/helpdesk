import builtins
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_server_api_import_does_not_import_qt(monkeypatch):
    for module_name in list(sys.modules):
        if module_name == "pc_agent.ui_gui" or module_name.startswith("pc_agent.ui_gui."):
            sys.modules.pop(module_name)

    original_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        if name == "PySide6" or name.startswith("PySide6."):
            raise AssertionError(f"Qt imported during non-GUI API import: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    module = importlib.import_module("pc_agent.ui_gui.server_api")

    assert module.TicketApiClient is not None
