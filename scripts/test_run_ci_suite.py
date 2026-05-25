import sys
import threading
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


def test_run_and_capture_streams_output_before_process_exits(tmp_path):
    log_path = tmp_path / "streaming.log"
    script_path = tmp_path / "streaming_child.py"
    script_path.write_text(
        "import time\n"
        "print('stream-start', flush=True)\n"
        "time.sleep(1.5)\n"
        "print('stream-end', flush=True)\n",
        encoding="utf-8",
    )
    result_holder: dict[str, object] = {}

    def _runner() -> None:
        result_holder["result"] = run_ci_suite.run_and_capture(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            log_path=log_path,
            step_name="stream_step",
            timeout_seconds=5,
        )

    worker = threading.Thread(target=_runner)
    worker.start()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if log_path.exists() and "\nstream-start\n" in log_path.read_text(encoding="utf-8"):
            break
        time.sleep(0.05)
    else:
        pytest.fail("expected child output to be written to the log before the process exits")

    worker.join(timeout=5)
    assert not worker.is_alive()
    assert result_holder["result"]["returncode"] == 0
    log_text = log_path.read_text(encoding="utf-8")
    assert "stream-end" in log_text


def test_run_and_capture_idle_timeout_stops_silent_process(tmp_path):
    log_path = tmp_path / "idle-timeout.log"
    script_path = tmp_path / "idle_child.py"
    script_path.write_text(
        "import time\n"
        "print('idle-start', flush=True)\n"
        "time.sleep(5)\n",
        encoding="utf-8",
    )
    started = time.monotonic()

    result = run_ci_suite.run_and_capture(
        [sys.executable, str(script_path)],
        cwd=tmp_path,
        log_path=log_path,
        step_name="idle_step",
        timeout_seconds=10,
        idle_timeout_seconds=0.5,
    )

    elapsed = time.monotonic() - started
    assert elapsed < 4, "idle timeout should stop silent steps promptly"
    assert result["timed_out"] is True
    assert result["timeout_reason"] == "idle_timeout"
    assert result["returncode"] == 124
    log_text = log_path.read_text(encoding="utf-8")
    assert "idle-start" in log_text
    assert "idle timeout" in log_text.lower()


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


def test_write_output_falls_back_when_console_cannot_encode_unicode(monkeypatch, tmp_path):
    class FakeStdout:
        encoding = "cp1251"

        def __init__(self) -> None:
            self.parts: list[str] = []

        def write(self, text: str) -> int:
            text.encode(self.encoding)
            self.parts.append(text)
            return len(text)

        def flush(self) -> None:
            return None

    fake_stdout = FakeStdout()
    handle_path = tmp_path / "unicode.log"
    with handle_path.open("w", encoding="utf-8") as handle:
        monkeypatch.setattr(run_ci_suite.sys, "stdout", fake_stdout)
        run_ci_suite._write_output(handle, "vite ✓\n")

    assert fake_stdout.parts == ["vite ?\n"]
    assert handle_path.read_text(encoding="utf-8") == "vite ✓\n"


def test_write_output_ignores_console_oserror(monkeypatch, tmp_path):
    class BrokenStdout:
        encoding = "utf-8"

        def write(self, text: str) -> int:
            raise OSError(22, "Invalid argument")

        def flush(self) -> None:
            return None

    handle_path = tmp_path / "broken-console.log"
    with handle_path.open("w", encoding="utf-8") as handle:
        monkeypatch.setattr(run_ci_suite.sys, "stdout", BrokenStdout())
        run_ci_suite._write_output(handle, "mirror-safe\n")

    assert handle_path.read_text(encoding="utf-8") == "mirror-safe\n"


def test_main_runs_webapp_bundle_step_before_layered_pytests(tmp_path, monkeypatch):
    summary_path = tmp_path / "artifacts" / "ci" / "deadbeef" / "summary.json"
    steps_seen: list[tuple[str, list[str], Path, float | None, dict[str, str] | None, float]] = []
    tests_dir = tmp_path / "server" / "tests"
    tests_dir.mkdir(parents=True)
    for filename in (
        "test_knowledge_api.py",
        "test_ticket_closure_policy.py",
        "test_observer_diagnostics_api.py",
        "test_agent_services_pipeline.py",
        "test_web_admin_api.py",
    ):
        (tests_dir / filename).write_text("def test_placeholder(): pass\n", encoding="utf-8")

    monkeypatch.setattr(run_ci_suite, "detect_commit", lambda workspace, commit: "deadbeef")
    monkeypatch.setattr(run_ci_suite, "summary_path_for_commit", lambda workspace, commit: summary_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_ci_suite.py", "--workspace", str(tmp_path), "--commit", "deadbeef"],
    )

    def fake_run_and_capture(
        command: list[str],
        *,
        cwd: Path,
        log_path: Path,
        step_name: str,
        timeout_seconds: float,
        idle_timeout_seconds: float | None,
        env_overrides: dict[str, str] | None = None,
    ) -> dict[str, object]:
        steps_seen.append((step_name, command, log_path, idle_timeout_seconds, env_overrides, timeout_seconds))
        return {
            "name": step_name,
            "command": command,
            "started_at": "2026-04-20T00:00:00+00:00",
            "finished_at": "2026-04-20T00:00:01+00:00",
            "duration_seconds": 1.0,
            "timeout_seconds": timeout_seconds,
            "timed_out": False,
            "timeout_reason": None,
            "returncode": 0,
            "log": str(log_path),
        }

    monkeypatch.setattr(run_ci_suite, "run_and_capture", fake_run_and_capture)

    run_ci_suite.main()

    assert [step_name for step_name, _command, _log_path, _idle_timeout, _env, _timeout in steps_seen] == [
        "verify_workspace",
        "webapp_bundle",
        "webapp_unit_tests",
        "webapp_fixture_e2e",
        "server_pytest_no_db",
        "server_pytest_db_knowledge",
        "server_pytest_db_tickets",
        "server_pytest_db_observer_diagnostics",
        "server_pytest_db_agent_runtime",
        "server_pytest_db_web_api",
        "server_pytest_agent_ws",
        "pc_agent_pytest",
    ]
    build_step = next(
        command
        for step_name, command, _log_path, _idle_timeout, _env, _timeout in steps_seen
        if step_name == "webapp_bundle"
    )
    assert "build_webapp_bundle.py" in build_step[1]
    assert "--output-dir" in build_step
    assert "--archive" in build_step
    idle_by_step = {
        step_name: idle_timeout
        for step_name, _command, _log_path, idle_timeout, _env, _timeout in steps_seen
    }
    assert idle_by_step["verify_workspace"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["webapp_bundle"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["webapp_unit_tests"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["webapp_fixture_e2e"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["server_pytest_no_db"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["server_pytest_db_knowledge"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["server_pytest_db_web_api"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["server_pytest_agent_ws"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["pc_agent_pytest"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS

    command_by_step = {
        step_name: command
        for step_name, command, _log_path, _idle_timeout, _env, _timeout in steps_seen
    }
    assert command_by_step["webapp_unit_tests"] == run_ci_suite._pnpm_webapp_command(tmp_path, "run", "test")
    assert command_by_step["webapp_fixture_e2e"] == run_ci_suite._pnpm_webapp_command(tmp_path, "run", "test:e2e")
    assert command_by_step["server_pytest_no_db"][-6:] == [
        "-m",
        "not manual and no_db",
        "-vv",
        "--durations=80",
        "--junitxml",
        str(summary_path.parent / "junit-server-no-db.xml"),
    ]
    assert command_by_step["server_pytest_db_knowledge"][-6:] == [
        "-m",
        "not manual and not no_db and not agent_ws",
        "-vv",
        "--durations=80",
        "--junitxml",
        str(summary_path.parent / "junit-server-db-knowledge.xml"),
    ]
    expected_knowledge_path = (
        "server\\tests\\test_knowledge_api.py" if sys.platform == "win32" else "server/tests/test_knowledge_api.py"
    )
    expected_web_api_path = (
        "server\\tests\\test_web_admin_api.py" if sys.platform == "win32" else "server/tests/test_web_admin_api.py"
    )
    assert command_by_step["server_pytest_db_knowledge"][3] == expected_knowledge_path
    assert command_by_step["server_pytest_db_web_api"][3] == expected_web_api_path
    assert command_by_step["server_pytest_agent_ws"][-6:] == [
        "-m",
        "not manual and agent_ws",
        "-vv",
        "--durations=80",
        "--junitxml",
        str(summary_path.parent / "junit-server-agent-ws.xml"),
    ]
    env_by_step = {
        step_name: env
        for step_name, _command, _log_path, _idle_timeout, env, _timeout in steps_seen
    }
    assert env_by_step["webapp_unit_tests"] == {"CI": "1"}
    assert env_by_step["webapp_fixture_e2e"] == {"CI": "1"}
    assert env_by_step["server_pytest_no_db"] == {"PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120"}
    assert env_by_step["server_pytest_db_knowledge"] == {
        "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
        "PC_CLIENT_TEST_DB_DOMAIN": "knowledge",
        "PC_CLIENT_TEST_DB_RUN_ID": "deadbeef",
    }
    assert env_by_step["server_pytest_db_web_api"] == {
        "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
        "PC_CLIENT_TEST_DB_DOMAIN": "web_api",
        "PC_CLIENT_TEST_DB_RUN_ID": "deadbeef",
    }
    assert env_by_step["server_pytest_agent_ws"] == {
        "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
        "PC_CLIENT_TEST_DB_DOMAIN": "agent_ws",
        "PC_CLIENT_TEST_DB_RUN_ID": "deadbeef",
    }
    timeout_by_step = {
        step_name: timeout
        for step_name, _command, _log_path, _idle_timeout, _env, timeout in steps_seen
    }
    assert timeout_by_step["webapp_unit_tests"] == run_ci_suite.DEFAULT_WEB_TEST_TIMEOUT_SECONDS
    assert timeout_by_step["webapp_fixture_e2e"] == run_ci_suite.DEFAULT_WEB_TEST_TIMEOUT_SECONDS
    assert timeout_by_step["server_pytest_no_db"] == 45 * 60
    assert timeout_by_step["server_pytest_db_knowledge"] == 45 * 60
    assert timeout_by_step["server_pytest_db_web_api"] == 45 * 60
    assert timeout_by_step["server_pytest_agent_ws"] == 45 * 60


def test_server_db_api_layer_paths_groups_every_test_file_once(tmp_path):
    tests_dir = tmp_path / "server" / "tests"
    tests_dir.mkdir(parents=True)
    for filename in (
        "test_knowledge_search.py",
        "test_ticket_closure_policy.py",
        "test_observer_v2_api.py",
        "test_device_dispatch_runtime.py",
        "test_inventory_v3_service.py",
        "test_web_support_api.py",
    ):
        (tests_dir / filename).write_text("def test_placeholder(): pass\n", encoding="utf-8")

    layers = run_ci_suite._server_db_api_layer_paths(tmp_path)

    names = [name for name, _paths in layers]
    flattened = [path for _name, paths in layers for path in paths]
    assert names == [
        "server_pytest_db_knowledge",
        "server_pytest_db_tickets",
        "server_pytest_db_observer_diagnostics",
        "server_pytest_db_agent_runtime",
        "server_pytest_db_web_api",
    ]
    assert sorted(path.name for path in flattened) == sorted(path.name for path in tests_dir.glob("test_*.py"))
    assert len(flattened) == len(set(flattened))
    web_api_paths = dict(layers)["server_pytest_db_web_api"]
    assert Path("server/tests/test_inventory_v3_service.py") in web_api_paths


def test_main_can_run_single_layer_by_name(tmp_path, monkeypatch):
    summary_path = tmp_path / "artifacts" / "ci" / "deadbeef" / "summary.json"
    tests_dir = tmp_path / "server" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_knowledge_api.py").write_text("def test_placeholder(): pass\n", encoding="utf-8")
    steps_seen: list[str] = []

    monkeypatch.setattr(run_ci_suite, "detect_commit", lambda workspace, commit: "deadbeef")
    monkeypatch.setattr(run_ci_suite, "summary_path_for_commit", lambda workspace, commit: summary_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ci_suite.py",
            "--workspace",
            str(tmp_path),
            "--commit",
            "deadbeef",
            "--layer",
            "server_pytest_db_knowledge",
            "--keep-test-db",
        ],
    )

    def fake_run_and_capture(
        command: list[str],
        *,
        cwd: Path,
        log_path: Path,
        step_name: str,
        timeout_seconds: float,
        idle_timeout_seconds: float | None,
        env_overrides: dict[str, str] | None = None,
    ) -> dict[str, object]:
        steps_seen.append(step_name)
        assert env_overrides == {
            "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
            "PC_CLIENT_TEST_DB_DOMAIN": "knowledge",
            "PC_CLIENT_TEST_DB_RUN_ID": "deadbeef",
            "PC_CLIENT_KEEP_TEST_DB": "1",
        }
        return {
            "name": step_name,
            "command": command,
            "started_at": "2026-04-20T00:00:00+00:00",
            "finished_at": "2026-04-20T00:00:01+00:00",
            "duration_seconds": 1.0,
            "timeout_seconds": timeout_seconds,
            "timed_out": False,
            "timeout_reason": None,
            "returncode": 0,
            "log": str(log_path),
        }

    monkeypatch.setattr(run_ci_suite, "run_and_capture", fake_run_and_capture)

    run_ci_suite.main()

    assert steps_seen == ["server_pytest_db_knowledge"]
    summary = run_ci_suite.json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["requested_layers"] == ["server_pytest_db_knowledge"]
    assert "webapp_bundle" in summary["available_layers"]


def test_main_rejects_unknown_layer(tmp_path, monkeypatch):
    monkeypatch.setattr(run_ci_suite, "detect_commit", lambda workspace, commit: "deadbeef")
    monkeypatch.setattr(
        run_ci_suite,
        "summary_path_for_commit",
        lambda workspace, commit: tmp_path / "artifacts" / "ci" / "deadbeef" / "summary.json",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_ci_suite.py", "--workspace", str(tmp_path), "--commit", "deadbeef", "--layer", "missing"],
    )

    with pytest.raises(SystemExit) as exc_info:
        run_ci_suite.main()

    assert "Unknown CI layer" in str(exc_info.value)
