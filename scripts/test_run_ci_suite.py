import sys
import time
from pathlib import Path

import pytest

from scripts import run_ci_suite


def test_run_and_capture_times_out_and_writes_partial_log(tmp_path):
    log_path = tmp_path / "ci-step.log"
    started = time.monotonic()

    result = run_ci_suite.run_and_capture(
        [sys.executable, "-c", "import time; print('before-timeout', flush=True); time.sleep(5)"],
        cwd=tmp_path,
        log_path=log_path,
        step_name="slow_step",
        timeout_seconds=0.5,
    )

    elapsed = time.monotonic() - started
    assert elapsed < 4, "run_and_capture should stop hanging commands promptly"
    assert result["name"] == "slow_step"
    assert result["timed_out"] is True
    assert result["returncode"] == 124
    assert result["duration_seconds"] >= 0
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "before-timeout" in log_text
    assert "timed out" in log_text.lower()


def test_main_writes_red_summary_when_interrupted(tmp_path, monkeypatch):
    summary_path = tmp_path / "artifacts" / "ci" / "deadbeef" / "summary.json"
    monkeypatch.setattr(run_ci_suite, "detect_commit", lambda workspace, commit: "deadbeef")
    monkeypatch.setattr(run_ci_suite, "summary_path_for_commit", lambda workspace, commit: summary_path)
    monkeypatch.setattr(
        run_ci_suite,
        "run_and_capture",
        lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_ci_suite.py", "--workspace", str(tmp_path), "--commit", "deadbeef"],
    )

    with pytest.raises(SystemExit) as exc_info:
        run_ci_suite.main()

    assert exc_info.value.code == 1
    assert summary_path.exists()
    summary = run_ci_suite.json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "red"
    assert summary["runner_error"] == "Interrupted by user"
    assert summary["steps"] == []


def test_run_and_capture_replaces_invalid_utf8_output(tmp_path):
    log_path = tmp_path / "encoding.log"

    result = run_ci_suite.run_and_capture(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'bad:\\xd3\\n'); sys.stdout.flush()",
        ],
        cwd=tmp_path,
        log_path=log_path,
        step_name="encoding_step",
        timeout_seconds=5,
    )

    assert result["returncode"] == 0
    log_text = log_path.read_text(encoding="utf-8")
    assert "bad:" in log_text
