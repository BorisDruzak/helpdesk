import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "run_server.py"
STOP_SCRIPT = Path(__file__).resolve().parent / "stop_server.py"


def _load_run_server_module():
    spec = importlib.util.spec_from_file_location("run_server_runtime_paths", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_stop_server_module():
    spec = importlib.util.spec_from_file_location("stop_server_runtime_paths", STOP_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_server_uses_server_data_root_for_mutable_pid_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PC_CLIENT_SERVER_DATA_ROOT", str(tmp_path))

    module = _load_run_server_module()

    assert module.resolve_run_dir() == tmp_path / "run"


def test_stop_server_uses_server_data_root_for_mutable_pid_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PC_CLIENT_SERVER_DATA_ROOT", str(tmp_path))

    module = _load_stop_server_module()

    assert module.resolve_run_dir() == tmp_path / "run"


def test_server_runtime_wrappers_honor_explicit_runtime_directory(monkeypatch, tmp_path) -> None:
    explicit_run_dir = tmp_path / "explicit-run"
    monkeypatch.setenv("PC_CLIENT_SERVER_DATA_ROOT", str(tmp_path / "data-root"))
    monkeypatch.setenv("HELPDESK_RUNTIME_DIR", str(explicit_run_dir))

    assert _load_run_server_module().resolve_run_dir() == explicit_run_dir
    assert _load_stop_server_module().resolve_run_dir() == explicit_run_dir
