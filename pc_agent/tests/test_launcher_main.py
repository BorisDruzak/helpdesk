import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pc_agent.launcher import launcher_main


def test_launcher_rolls_back_after_repeated_immediate_crash(monkeypatch, tmp_path):
    install_root = tmp_path / "install"
    versions_dir = install_root / "versions"
    version_bad_dir = versions_dir / "3.1.20"
    version_prev_dir = versions_dir / "3.1.19"
    version_bad_dir.mkdir(parents=True, exist_ok=True)
    version_prev_dir.mkdir(parents=True, exist_ok=True)
    current_path = install_root / "current.json"
    current_path.write_text(
        json.dumps({"version": "3.1.20", "previous": "3.1.19"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    data_root = tmp_path / "data"

    launches = []
    launch_argvs = []
    exit_codes = iter([101, 101, 101, 0])
    monotonic_values = iter([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 40.0])

    class _FakeProc:
        def __init__(self, code):
            self._code = code

        def wait(self):
            return self._code

    def _fake_find_agent_binary(version_dir):
        return version_dir / "pc_agent"

    def _fake_popen(argv, **kwargs):
        launches.append(Path(argv[0]).parent.name)
        launch_argvs.append(list(argv))
        return _FakeProc(next(exit_codes))

    monkeypatch.setattr(launcher_main, "resolve_data_root", lambda cli_value=None: data_root)
    monkeypatch.setattr(launcher_main, "resolve_install_root", lambda cli_value=None: install_root)
    monkeypatch.setattr(launcher_main, "_find_agent_binary", _fake_find_agent_binary)
    monkeypatch.setattr(launcher_main.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(launcher_main.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(launcher_main.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sys, "argv", ["launcher.py", "--no-gui"])

    with pytest.raises(SystemExit) as exc_info:
        launcher_main.main()

    assert exc_info.value.code == 0
    assert json.loads(current_path.read_text(encoding="utf-8")) == {"version": "3.1.19", "previous": "3.1.20"}
    assert launches == ["3.1.20", "3.1.20", "3.1.20", "3.1.19"]
    assert all(argv[-1] == "--no-gui" for argv in launch_argvs)

    failed_launch = json.loads((data_root / "updates" / "last_failed_launch.json").read_text(encoding="utf-8"))
    assert failed_launch["reason"] == "startup_crash_rollback"
    assert failed_launch["crashed_version"] == "3.1.20"
    assert failed_launch["rollback_version"] == "3.1.19"
