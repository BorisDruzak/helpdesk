import json
import subprocess
from pathlib import Path

import pytest

import scripts.ci_artifacts as ci_artifacts
from scripts.ci_artifacts import require_green_ci_artifact


def write_summary(workspace: Path, commit: str, payload: dict[str, object]) -> Path:
    summary_path = workspace / "artifacts" / "ci" / commit / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload), encoding="utf-8")
    return summary_path


def git(workspace: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def initialize_repository(workspace: Path) -> None:
    git(workspace, "init")
    git(workspace, "config", "user.email", "tests@example.invalid")
    git(workspace, "config", "user.name", "CI artifact tests")
    (workspace / "base.txt").write_text("base\n", encoding="utf-8")
    git(workspace, "add", "base.txt")
    git(workspace, "commit", "-m", "base")


def green_full_summary(commit: str) -> dict[str, object]:
    return {
        "commit": commit,
        "status": "green",
        "gate_mode": "full",
        "parallel_enabled": True,
        "full_merge_gate_satisfied": True,
        "requested_layers": [],
    }


def test_resolve_green_ci_artifact_reuses_tree_identical_merge_parent(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    git(tmp_path, "checkout", "-b", "source")
    (tmp_path / "source.txt").write_text("source\n", encoding="utf-8")
    git(tmp_path, "add", "source.txt")
    git(tmp_path, "commit", "-m", "source")
    source_commit = git(tmp_path, "rev-parse", "HEAD")
    source_summary = write_summary(tmp_path, source_commit, green_full_summary(source_commit))
    git(tmp_path, "checkout", "master")
    git(tmp_path, "merge", "--no-ff", "source", "-m", "merge source")
    merge_commit = git(tmp_path, "rev-parse", "HEAD")

    summary_path, artifact_commit, reused = ci_artifacts.resolve_green_ci_artifact(tmp_path, merge_commit)

    assert summary_path == source_summary
    assert artifact_commit == source_commit
    assert reused is True


def test_resolve_green_ci_artifact_rejects_tree_different_merge(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    git(tmp_path, "checkout", "-b", "source")
    (tmp_path / "source.txt").write_text("source\n", encoding="utf-8")
    git(tmp_path, "add", "source.txt")
    git(tmp_path, "commit", "-m", "source")
    source_commit = git(tmp_path, "rev-parse", "HEAD")
    write_summary(tmp_path, source_commit, green_full_summary(source_commit))
    git(tmp_path, "checkout", "master")
    (tmp_path / "base-only.txt").write_text("base only\n", encoding="utf-8")
    git(tmp_path, "add", "base-only.txt")
    git(tmp_path, "commit", "-m", "base change")
    git(tmp_path, "merge", "--no-ff", "source", "-m", "merge source")
    merge_commit = git(tmp_path, "rev-parse", "HEAD")

    with pytest.raises(SystemExit, match="Missing:"):
        ci_artifacts.resolve_green_ci_artifact(tmp_path, merge_commit)


def test_require_green_ci_artifact_accepts_exact_green_commit(tmp_path: Path) -> None:
    summary_path = write_summary(tmp_path, "abc123", {"commit": "abc123", "status": "green"})

    assert require_green_ci_artifact(tmp_path, "abc123") == summary_path


def test_require_green_ci_artifact_rejects_summary_for_different_commit(tmp_path: Path) -> None:
    write_summary(tmp_path, "abc123", {"commit": "old456", "status": "green"})

    with pytest.raises(SystemExit) as exc_info:
        require_green_ci_artifact(tmp_path, "abc123")

    message = str(exc_info.value)
    assert "exact target commit" in message
    assert "old456" in message
    assert "abc123" in message
    assert "Do not commit after full CI" in message


def test_require_green_ci_artifact_rejects_missing_artifact_with_freeze_hint(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        require_green_ci_artifact(tmp_path, "abc123")

    message = str(exc_info.value)
    assert "Missing:" in message
    assert "release candidate commit is frozen" in message


def test_require_green_ci_artifact_rejects_red_artifact_with_quick_gate_hint(tmp_path: Path) -> None:
    write_summary(tmp_path, "abc123", {"commit": "abc123", "status": "red"})

    with pytest.raises(SystemExit) as exc_info:
        require_green_ci_artifact(tmp_path, "abc123")

    message = str(exc_info.value)
    assert "status='red'" in message
    assert "--gate quick" in message


def test_require_green_ci_artifact_rejects_affected_or_selected_gate_summary(tmp_path: Path) -> None:
    write_summary(
        tmp_path,
        "abc123",
        {
            "commit": "abc123",
            "status": "green",
            "gate_mode": "affected",
            "full_merge_gate_required": True,
            "full_merge_gate_satisfied": False,
            "effective_layers": ["verify_workspace", "server_pytest_db_tickets"],
        },
    )

    with pytest.raises(SystemExit) as exc_info:
        require_green_ci_artifact(tmp_path, "abc123")

    message = str(exc_info.value)
    assert "full merge gate" in message
    assert "affected" in message
    assert "python scripts/run_ci_suite.py" in message


def test_require_green_ci_artifact_rejects_shared_db_fallback_in_db_layer_log(tmp_path: Path) -> None:
    log_path = tmp_path / "artifacts" / "ci" / "abc123" / "logs" / "server_pytest_db_web_api.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        "RuntimeWarning: test DB pc_support_test. shared test DB fallback: not valid for full DB/API gate.\n",
        encoding="utf-8",
    )
    write_summary(
        tmp_path,
        "abc123",
        {
            "commit": "abc123",
            "status": "green",
            "steps": [
                {
                    "name": "server_pytest_db_web_api",
                    "returncode": 0,
                    "log": str(log_path),
                }
            ],
        },
    )

    with pytest.raises(SystemExit) as exc_info:
        require_green_ci_artifact(tmp_path, "abc123")

    message = str(exc_info.value)
    assert "shared test DB fallback" in message
    assert "not valid for full release gate" in message
    assert "TEST_DATABASE_ADMIN_URL" in message
