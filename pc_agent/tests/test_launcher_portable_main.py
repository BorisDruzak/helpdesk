import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent import launcher_portable_main


def test_seed_auth_token_from_primary_install_uses_primary_data_dir(monkeypatch, tmp_path):
    portable_data = tmp_path / "portable-data"
    primary_data = tmp_path / "primary-data"
    calls = {}

    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.setattr(launcher_portable_main, "_default_primary_agent_data_dir", lambda: primary_data)

    def _fake_import(source_root, target_root, *, log_message=None):
        calls["source_root"] = Path(source_root)
        calls["target_root"] = Path(target_root)
        return True

    monkeypatch.setattr(
        launcher_portable_main,
        "import_missing_auth_token_from_data_roots",
        _fake_import,
    )

    imported = launcher_portable_main._seed_auth_token_from_primary_install(portable_data)

    assert imported is True
    assert calls == {
        "source_root": primary_data,
        "target_root": portable_data,
    }


def test_seed_auth_token_from_primary_install_skips_when_auth_token_env_is_set(monkeypatch, tmp_path):
    portable_data = tmp_path / "portable-data"
    monkeypatch.setenv("AUTH_TOKEN", "env-token")

    called = {"importer": 0}

    def _fake_import(source_root, target_root, *, log_message=None):
        called["importer"] += 1
        return True

    monkeypatch.setattr(
        launcher_portable_main,
        "import_missing_auth_token_from_data_roots",
        _fake_import,
    )

    imported = launcher_portable_main._seed_auth_token_from_primary_install(portable_data)

    assert imported is False
    assert called["importer"] == 0


def test_launcher_rolls_back_after_repeated_immediate_crash(monkeypatch, tmp_path):
    install_root = tmp_path / "install"
    versions_dir = install_root / "versions"
    version_bad_dir = versions_dir / "3.1.12"
    version_prev_dir = versions_dir / "3.1.11"
    version_bad_dir.mkdir(parents=True, exist_ok=True)
    version_prev_dir.mkdir(parents=True, exist_ok=True)
    current_path = install_root / "current.json"
    current_path.write_text(
        json.dumps({"version": "3.1.12", "previous": "3.1.11"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    data_root = tmp_path / "data"

    class _FakeLock:
        def __init__(self, _path):
            self.released = False

        def acquire(self):
            return True

        def release(self):
            self.released = True

    launches = []
    exit_codes = iter([101, 101, 101, 0])
    monotonic_values = iter([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 35.0])

    class _FakeProc:
        def __init__(self, code):
            self._code = code

        def wait(self):
            return self._code

    def _fake_find_agent_binary(version_dir):
        return version_dir / "pc_agent.exe"

    def _fake_popen(argv, **kwargs):
        launches.append(Path(argv[0]).parent.name)
        stdout = kwargs.get("stdout")
        if stdout is not None:
            stdout.write(b"Traceback: bad startup\n")
            stdout.flush()
        return _FakeProc(next(exit_codes))

    monkeypatch.setattr(launcher_portable_main, "resolve_data_root", lambda cli_value=None: data_root)
    monkeypatch.setattr(launcher_portable_main, "resolve_install_root", lambda cli_value=None: install_root)
    monkeypatch.setattr(launcher_portable_main, "SingleInstanceLock", _FakeLock)
    monkeypatch.setattr(launcher_portable_main, "_seed_auth_token_from_primary_install", lambda _data_root: False)
    monkeypatch.setattr(launcher_portable_main, "_find_agent_binary", _fake_find_agent_binary)
    monkeypatch.setattr(launcher_portable_main.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(launcher_portable_main.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(launcher_portable_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sys, "argv", ["launcher.exe"])

    launcher_portable_main.main()

    current = json.loads(current_path.read_text(encoding="utf-8"))
    assert current == {"version": "3.1.11", "previous": "3.1.12"}
    assert launches == ["3.1.12", "3.1.12", "3.1.12", "3.1.11"]

    updates_dir = data_root / "updates"
    failed_launch = json.loads((updates_dir / "last_failed_launch.json").read_text(encoding="utf-8"))
    assert failed_launch["reason"] == "startup_crash_rollback"
    assert failed_launch["crashed_version"] == "3.1.12"
    assert failed_launch["rollback_version"] == "3.1.11"

    history = json.loads((updates_dir / "update_history.json").read_text(encoding="utf-8"))
    assert history[-1]["success"] is False
    assert history[-1]["reason"] == "startup_crash_rollback"
    assert history[-1]["previous_version"] == "3.1.11"


def test_launcher_stops_when_agent_reports_existing_instance(monkeypatch, tmp_path):
    install_root = tmp_path / "install"
    versions_dir = install_root / "versions"
    version_dir = versions_dir / "3.1.13"
    version_dir.mkdir(parents=True, exist_ok=True)
    current_path = install_root / "current.json"
    current_path.write_text(
        json.dumps({"version": "3.1.13", "previous": "3.1.13"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    data_root = tmp_path / "data"
    shown_errors = []

    class _FakeLock:
        def __init__(self, _path):
            self.released = False

        def acquire(self):
            return True

        def release(self):
            self.released = True

    launches = []

    class _FakeProc:
        def wait(self):
            return launcher_portable_main.AGENT_EXIT_ALREADY_RUNNING

    def _fake_find_agent_binary(version_dir):
        return version_dir / "pc_agent.exe"

    def _fake_popen(argv, **kwargs):
        launches.append(Path(argv[0]).parent.name)
        stdout = kwargs.get("stdout")
        if stdout is not None:
            stdout.write(b"Another agent instance is already running; exiting.\n")
            stdout.flush()
        return _FakeProc()

    monkeypatch.setattr(launcher_portable_main, "resolve_data_root", lambda cli_value=None: data_root)
    monkeypatch.setattr(launcher_portable_main, "resolve_install_root", lambda cli_value=None: install_root)
    monkeypatch.setattr(launcher_portable_main, "SingleInstanceLock", _FakeLock)
    monkeypatch.setattr(launcher_portable_main, "_seed_auth_token_from_primary_install", lambda _data_root: False)
    monkeypatch.setattr(launcher_portable_main, "_find_agent_binary", _fake_find_agent_binary)
    monkeypatch.setattr(launcher_portable_main.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(launcher_portable_main, "_show_user_error", lambda title, message: shown_errors.append((title, message)))
    monkeypatch.setattr(sys, "argv", ["launcher.exe"])

    with pytest.raises(SystemExit) as exc_info:
        launcher_portable_main.main()

    assert launches == ["3.1.13"]
    assert exc_info.value.code == 0
    assert json.loads(current_path.read_text(encoding="utf-8"))["version"] == "3.1.13"
    assert not (data_root / "updates" / "last_failed_launch.json").exists()
    assert shown_errors == [
        (
            "Maria Agent is already running",
            "Another Maria Agent instance is already using this portable data folder.",
        )
    ]


def test_launcher_shows_error_when_launcher_lock_is_taken(monkeypatch, tmp_path):
    install_root = tmp_path / "install"
    install_root.mkdir(parents=True, exist_ok=True)
    data_root = tmp_path / "data"
    shown_errors = []

    class _FakeLock:
        def __init__(self, _path):
            self.released = False

        def acquire(self):
            return False

        def release(self):
            self.released = True

    monkeypatch.setattr(launcher_portable_main, "resolve_data_root", lambda cli_value=None: data_root)
    monkeypatch.setattr(launcher_portable_main, "resolve_install_root", lambda cli_value=None: install_root)
    monkeypatch.setattr(launcher_portable_main, "SingleInstanceLock", _FakeLock)
    monkeypatch.setattr(launcher_portable_main, "_show_user_error", lambda title, message: shown_errors.append((title, message)))
    monkeypatch.setattr(sys, "argv", ["launcher.exe"])

    with pytest.raises(SystemExit) as exc_info:
        launcher_portable_main.main()

    assert exc_info.value.code == 0
    assert shown_errors == [
        (
            "Maria Agent is already running",
            "Maria Agent is already running from this portable folder.",
        )
    ]
