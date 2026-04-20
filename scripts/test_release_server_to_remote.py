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
        "skip_ci_check": False,
        "skip_smoke": False,
        "skip_migrations": False,
        "leave_running": False,
        "smoke_attempts": 10,
        "smoke_delay": 2.0,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_main_runs_standard_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: make_args(skip_ci_check=True))
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append((label, command))

    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "ci" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(
        release,
        "upload_webapp_bundle",
        lambda archive, *, cwd, remote, remote_worktree: calls.append(("upload-webapp", [str(archive), remote, remote_worktree])),
    )
    monkeypatch.setattr(release, "run_step", fake_run_step)
    monkeypatch.setattr(release, "run_smoke_with_retries", lambda command, *, cwd, attempts, delay_seconds: calls.append(("smoke", command)))

    release.main()

    assert [label for label, _command in calls] == [
        "verify",
        "deploy",
        "migrate",
        "upload-webapp",
        "start-control",
        "start",
        "smoke",
        "stop",
    ]
    assert "verify_workspace.py" in calls[0][1][1]
    assert "deploy_workspace_to_remote.py" in calls[1][1][1]
    assert "run_remote_migrations.py" in calls[2][1][1]
    assert calls[2][1][-4:] == ["--remote", "altserver@192.168.100.17", "upgrade", "head"]
    assert calls[4][1][-2:] == ["start", "control"]
    assert calls[5][1][-2:] == ["start", "server"]
    assert calls[6][1][-2:] == ["smoke", "server"]
    assert calls[7][1][-2:] == ["stop", "server"]


def test_main_passes_allow_local_dirty_to_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: make_args(allow_local_dirty=True, skip_ci_check=True))
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append((label, command))

    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "ci" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(release, "upload_webapp_bundle", lambda archive, *, cwd, remote, remote_worktree: None)
    monkeypatch.setattr(release, "run_step", fake_run_step)
    monkeypatch.setattr(release, "run_smoke_with_retries", lambda command, *, cwd, attempts, delay_seconds: calls.append(("smoke", command)))

    release.main()

    deploy_command = next(command for label, command in calls if label == "deploy")
    assert "--allow-local-dirty" in deploy_command


def test_main_passes_skip_ci_check_to_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: make_args(skip_ci_check=True))
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append((label, command))

    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "ci" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(release, "upload_webapp_bundle", lambda archive, *, cwd, remote, remote_worktree: None)
    monkeypatch.setattr(release, "run_step", fake_run_step)
    monkeypatch.setattr(release, "run_smoke_with_retries", lambda command, *, cwd, attempts, delay_seconds: calls.append(("smoke", command)))

    release.main()

    deploy_command = next(command for label, command in calls if label == "deploy")
    assert "--skip-ci-check" in deploy_command


def test_main_skips_optional_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        release,
        "parse_args",
        lambda: make_args(
            skip_verify=True,
            skip_smoke=True,
            skip_migrations=True,
            leave_running=True,
            skip_ci_check=True,
        ),
    )
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append((label, command))

    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "ci" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(
        release,
        "upload_webapp_bundle",
        lambda archive, *, cwd, remote, remote_worktree: calls.append(("upload-webapp", [str(archive), remote, remote_worktree])),
    )
    monkeypatch.setattr(release, "run_step", fake_run_step)

    release.main()

    assert [label for label, _command in calls] == ["deploy", "upload-webapp", "start-control", "start"]


def test_main_stops_server_when_smoke_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: make_args(skip_ci_check=True))
    calls: list[str] = []

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append(label)

    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "ci" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(release, "upload_webapp_bundle", lambda archive, *, cwd, remote, remote_worktree: calls.append("upload-webapp"))
    monkeypatch.setattr(release, "run_step", fake_run_step)
    def fake_smoke(command: list[str], *, cwd: Path, attempts: int, delay_seconds: float) -> None:
        calls.append("smoke")
        raise subprocess.CalledProcessError(returncode=1, cmd=command)

    monkeypatch.setattr(release, "run_smoke_with_retries", fake_smoke)

    with pytest.raises(subprocess.CalledProcessError):
        release.main()

    assert calls == ["verify", "deploy", "migrate", "upload-webapp", "start-control", "start", "smoke", "stop"]


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


def test_main_requires_green_ci_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: make_args())
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(release, "detect_commit", lambda workspace: "abc123")

    def fake_run_step(command: list[str], *, cwd: Path, label: str) -> None:
        calls.append((label, command))

    recorded: list[tuple[Path, str]] = []

    def fake_require_green(workspace: Path, commit: str) -> Path:
        recorded.append((workspace, commit))
        return workspace / "artifacts" / "ci" / commit / "summary.json"

    monkeypatch.setattr(release, "require_green_ci_artifact", fake_require_green)
    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "ci" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(release, "upload_webapp_bundle", lambda archive, *, cwd, remote, remote_worktree: calls.append(("upload-webapp", [str(archive), remote, remote_worktree])))
    monkeypatch.setattr(release, "run_step", fake_run_step)
    monkeypatch.setattr(release, "run_smoke_with_retries", lambda command, *, cwd, attempts, delay_seconds: calls.append(("smoke", command)))

    release.main()

    assert recorded == [(Path(r"C:\Users\admin-2\CodexProjects\pc_client"), "abc123")]


def test_prepare_webapp_bundle_archive_uses_existing_ci_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[tuple[Path, str]] = []

    def fake_require(workspace: Path, commit: str) -> Path:
        recorded.append((workspace, commit))
        return workspace / "artifacts" / "ci" / commit / "webapp-dist.tar.gz"

    monkeypatch.setattr(release, "require_webapp_bundle_artifact", fake_require)

    result = release.prepare_webapp_bundle_archive(
        Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
        "abc123",
        skip_ci_check=False,
    )

    assert result == Path(r"C:\Users\admin-2\CodexProjects\pc_client") / "artifacts" / "ci" / "abc123" / "webapp-dist.tar.gz"
    assert recorded == [(Path(r"C:\Users\admin-2\CodexProjects\pc_client"), "abc123")]
