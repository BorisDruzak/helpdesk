from __future__ import annotations

import argparse
import json
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
