import json
from pathlib import Path

import pytest

from scripts.ci_artifacts import require_green_ci_artifact


def write_summary(workspace: Path, commit: str, payload: dict[str, object]) -> Path:
    summary_path = workspace / "artifacts" / "ci" / commit / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload), encoding="utf-8")
    return summary_path


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
