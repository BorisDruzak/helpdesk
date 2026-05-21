from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

import scripts.release_server_to_remote as release
import scripts.write_restore_drill_marker as restore_marker


def test_write_release_marker_local_path(tmp_path: Path) -> None:
    marker_path = tmp_path / "release.json"

    release.write_release_status_marker(
        marker_path,
        branch="codex/helpdesk-process-model",
        commit="abc123",
        gate="quick",
        dirty=False,
        remote_profile="altserver@192.168.100.17",
        webapp_bundle_commit="abc123",
        alembic_current="20260519_097",
        alembic_head="20260519_097",
        migrations_skipped=False,
    )

    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["branch"] == "codex/helpdesk-process-model"
    assert payload["commit"] == "abc123"
    assert payload["gate"] == "quick"
    assert payload["dirty"] is False
    assert payload["alembic_current"] == payload["alembic_head"]
    assert "password" not in str(payload).lower()
    assert "token" not in str(payload).lower()


def test_main_writes_release_marker_after_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "release-flow.json"
    calls: list[str] = []

    def args() -> argparse.Namespace:
        return argparse.Namespace(
            workspace=Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
            branch="codex/helpdesk-process-model",
            remote="altserver@192.168.100.17",
            allow_local_dirty=True,
            gate="quick",
            skip_verify=True,
            skip_ci_check=False,
            skip_smoke=True,
            skip_migrations=True,
            leave_running=True,
            smoke_attempts=1,
            smoke_delay=0,
            release_status_path=marker_path,
            require_marker_write=True,
        )

    monkeypatch.setattr(release, "parse_args", args)
    monkeypatch.setattr(release, "detect_commit", lambda workspace: "abc123")
    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "release_temp" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(release, "upload_webapp_bundle", lambda *args, **kwargs: calls.append("upload"))
    monkeypatch.setattr(release, "run_step", lambda command, *, cwd, label: calls.append(label))

    release.main()

    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    assert payload["commit"] == "abc123"
    assert payload["gate"] == "quick"
    assert payload["branch"] == "codex/helpdesk-process-model"
    assert payload["migrations_skipped"] is True


def test_main_collects_alembic_current_and_head_after_migration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "release-flow-alembic.json"
    calls: list[str] = []

    def args() -> argparse.Namespace:
        return argparse.Namespace(
            workspace=Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
            branch="codex/helpdesk-process-model",
            remote="altserver@192.168.100.17",
            allow_local_dirty=True,
            gate="quick",
            skip_verify=True,
            skip_ci_check=False,
            skip_smoke=True,
            skip_migrations=False,
            leave_running=True,
            smoke_attempts=1,
            smoke_delay=0,
            release_status_path=marker_path,
            require_marker_write=True,
        )

    monkeypatch.setattr(release, "parse_args", args)
    monkeypatch.setattr(release, "detect_commit", lambda workspace: "abc123")
    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "release_temp" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(release, "upload_webapp_bundle", lambda *args, **kwargs: calls.append("upload"))
    monkeypatch.setattr(release, "run_step", lambda command, *, cwd, label: calls.append(label))
    monkeypatch.setattr(
        release,
        "collect_remote_alembic_revisions",
        lambda *, workspace, remote: ("20260519_097", "20260519_097"),
    )

    release.main()

    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    assert payload["alembic_current"] == "20260519_097"
    assert payload["alembic_head"] == "20260519_097"
    assert payload["migrations_skipped"] is False


def test_main_writes_release_marker_to_remote_worktree_path(monkeypatch: pytest.MonkeyPatch) -> None:
    remote_marker_path = "/var/chat_bot/pc_client/artifacts/tech/release_status.json"
    calls: list[str] = []
    remote_writes: list[tuple[str, dict[str, object]]] = []

    def args() -> argparse.Namespace:
        return argparse.Namespace(
            workspace=Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
            branch="codex/helpdesk-process-model",
            remote="altserver@192.168.100.17",
            allow_local_dirty=True,
            gate="quick",
            skip_verify=True,
            skip_ci_check=False,
            skip_smoke=True,
            skip_migrations=False,
            leave_running=True,
            smoke_attempts=1,
            smoke_delay=0,
            release_status_path=remote_marker_path,
            require_marker_write=True,
        )

    def write_remote(path: str, *, payload: dict[str, object], remote: str, cwd: Path) -> dict[str, object]:
        assert remote == "altserver@192.168.100.17"
        remote_writes.append((path, payload))
        return payload

    monkeypatch.setattr(release, "parse_args", args)
    monkeypatch.setattr(release, "detect_commit", lambda workspace: "abc123")
    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "release_temp" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(release, "upload_webapp_bundle", lambda *args, **kwargs: calls.append("upload"))
    monkeypatch.setattr(release, "run_step", lambda command, *, cwd, label: calls.append(label))
    monkeypatch.setattr(
        release,
        "collect_remote_alembic_revisions",
        lambda *, workspace, remote: ("20260519_097", "20260519_097"),
    )
    monkeypatch.setattr(release, "write_remote_release_status_marker", write_remote)

    release.main()

    assert len(remote_writes) == 1
    path, payload = remote_writes[0]
    assert path == remote_marker_path
    assert payload["commit"] == "abc123"
    assert payload["alembic_current"] == "20260519_097"
    assert payload["alembic_head"] == "20260519_097"
    assert "password" not in str(payload).lower()
    assert "token" not in str(payload).lower()


def test_remote_release_marker_path_respects_env_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PC_CLIENT_REMOTE_ROOT", "/srv/pc_client")

    assert release._is_remote_release_marker_path("/srv/pc_client/artifacts/tech/release_status.json")
    assert not release._is_remote_release_marker_path("/var/chat_bot/pc_client/artifacts/tech/release_status.json")


def test_main_forwards_https_smoke_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "release-flow-smoke.json"
    calls: list[str] = []
    smoke_commands: list[list[str]] = []

    def args() -> argparse.Namespace:
        return argparse.Namespace(
            workspace=Path(r"C:\Users\admin-2\CodexProjects\pc_client"),
            branch="codex/helpdesk-process-model",
            remote="altserver@192.168.100.17",
            allow_local_dirty=True,
            gate="quick",
            skip_verify=True,
            skip_ci_check=False,
            skip_smoke=False,
            skip_migrations=True,
            leave_running=True,
            smoke_attempts=1,
            smoke_delay=0,
            smoke_base_url="https://192.168.100.17:9443",
            smoke_insecure_tls=True,
            release_status_path=marker_path,
            require_marker_write=True,
        )

    def capture_smoke(command: list[str], *, cwd: Path, attempts: int, delay_seconds: float) -> None:
        smoke_commands.append(command)

    monkeypatch.setattr(release, "parse_args", args)
    monkeypatch.setattr(release, "detect_commit", lambda workspace: "abc123")
    monkeypatch.setattr(
        release,
        "prepare_webapp_bundle_archive",
        lambda workspace, commit, *, skip_ci_check: workspace / "artifacts" / "release_temp" / commit / "webapp-dist.tar.gz",
    )
    monkeypatch.setattr(release, "upload_webapp_bundle", lambda *args, **kwargs: calls.append("upload"))
    monkeypatch.setattr(release, "run_step", lambda command, *, cwd, label: calls.append(label))
    monkeypatch.setattr(release, "run_smoke_with_retries", capture_smoke)

    release.main()

    assert smoke_commands == [
        [
            sys.executable,
            str(Path(r"C:\Users\admin-2\CodexProjects\pc_client") / "scripts" / "manage_remote_stack.py"),
            "--remote",
            "altserver@192.168.100.17",
            "smoke",
            "server",
            "--base-url",
            "https://192.168.100.17:9443",
            "--insecure-tls",
        ]
    ]


def test_parse_alembic_revision_output_ignores_head_marker() -> None:
    assert release._parse_alembic_revision_output("097 (head)\n") == "097"
    assert release._parse_alembic_revision_output("20260519_097 (head)\n") == "20260519_097"
    assert release._parse_alembic_revision_output("head\n") is None


def test_restore_drill_marker_writer(tmp_path: Path) -> None:
    output = tmp_path / "restore-drill.json"

    payload = restore_marker.write_restore_drill_marker(
        output=output,
        status="success",
        target="pc_client_restore_test",
        duration_seconds=42,
        artifact="artifacts/restore/summary.txt",
    )

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == payload
    assert persisted["status"] == "success"
    assert persisted["target"] == "pc_client_restore_test"
    assert persisted["duration_seconds"] == 42
    assert "secret" not in str(persisted).lower()
