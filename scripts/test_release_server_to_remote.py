import argparse
import subprocess
from pathlib import Path

import pytest

import scripts.release_server_to_remote as release


def make_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "workspace": Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
        "branch": None,
        "remote": "altserver@192.168.100.17",
        "allow_local_dirty": False,
        "skip_verify": False,
        "skip_smoke": False,
        "leave_running": False,
        "smoke_attempts": 10,
        "smoke_delay": 2.0,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_main_runs_standard_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: make_args())
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append((label, command))

    monkeypatch.setattr(release, "run_step", fake_run_step)
    monkeypatch.setattr(release, "run_smoke_with_retries", lambda command, *, cwd, attempts, delay_seconds: calls.append(("smoke", command)))

    release.main()

    assert [label for label, _command in calls] == ["verify", "deploy", "start", "smoke", "stop"]
    assert "verify_workspace.py" in calls[0][1][1]
    assert "deploy_workspace_to_remote.py" in calls[1][1][1]
    assert calls[2][1][-2:] == ["start", "server"]
    assert calls[3][1][-2:] == ["smoke", "server"]
    assert calls[4][1][-2:] == ["stop", "server"]


def test_main_passes_allow_local_dirty_to_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: make_args(allow_local_dirty=True))
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append((label, command))

    monkeypatch.setattr(release, "run_step", fake_run_step)
    monkeypatch.setattr(release, "run_smoke_with_retries", lambda command, *, cwd, attempts, delay_seconds: calls.append(("smoke", command)))

    release.main()

    deploy_command = next(command for label, command in calls if label == "deploy")
    assert "--allow-local-dirty" in deploy_command


def test_main_skips_optional_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        release,
        "parse_args",
        lambda: make_args(skip_verify=True, skip_smoke=True, leave_running=True),
    )
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append((label, command))

    monkeypatch.setattr(release, "run_step", fake_run_step)

    release.main()

    assert [label for label, _command in calls] == ["deploy", "start"]


def test_main_stops_server_when_smoke_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: make_args())
    calls: list[str] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append(label)

    monkeypatch.setattr(release, "run_step", fake_run_step)
    def fake_smoke(command: list[str], *, cwd: Path, attempts: int, delay_seconds: float) -> None:
        calls.append("smoke")
        raise subprocess.CalledProcessError(returncode=1, cmd=command)

    monkeypatch.setattr(release, "run_smoke_with_retries", fake_smoke)

    with pytest.raises(subprocess.CalledProcessError):
        release.main()

    assert calls == ["verify", "deploy", "start", "smoke", "stop"]


def test_run_smoke_with_retries_retries_until_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class Result:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_subprocess_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
        encoding: str,
    ) -> Result:
        calls.append(command)
        if len(calls) < 3:
            return Result(returncode=1, stdout="not ready")
        return Result(returncode=0, stdout="ok")

    monkeypatch.setattr(release.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(release.time, "sleep", lambda seconds: None)

    release.run_smoke_with_retries(["smoke"], cwd=Path("."), attempts=3, delay_seconds=0.1)

    assert calls == [["smoke"], ["smoke"], ["smoke"]]
