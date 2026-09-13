import subprocess
import sys
from pathlib import Path

import scripts.verify_workspace as verify


def test_verify_workspace_tracks_harness_text_files() -> None:
    assert ".mdc" in verify.TEXT_SUFFIXES
    assert ".ps1" in verify.TEXT_SUFFIXES
    assert ".cursor" not in verify.SKIP_DIRS


def test_run_docs_links_returns_no_failures_on_success(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=b"ok\n", stderr=b"")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.run_docs_links(tmp_path) == []


def test_run_docs_links_returns_output_on_failure(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout=b"broken\n", stderr=b"details\n")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.run_docs_links(tmp_path) == ["broken", "details"]


def test_run_docs_links_calls_docs_inventory_check(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    verify.run_docs_links(tmp_path)

    assert calls == [[sys.executable, str(tmp_path / "scripts" / "docs_inventory.py"), "--check-links"]]


def test_forbidden_tracked_files_reports_local_config(monkeypatch, tmp_path: Path) -> None:
    def fake_run(cmd, **kwargs):
        assert cmd == ["git", "ls-files", "--", "server/.env", "db_config.json"]
        return subprocess.CompletedProcess(cmd, 0, stdout=b"server/.env\ndb_config.json\n", stderr=b"")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.check_forbidden_tracked_files(tmp_path) == [
        "forbidden local config is tracked by git: server/.env",
        "forbidden local config is tracked by git: db_config.json",
    ]
