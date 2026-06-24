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
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "test_ci_helper.py").write_text("def test_placeholder(): pass\n", encoding="utf-8")
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
        mirror_output: bool = True,
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
        "test_inventory_audit",
        "db_cleanup_profile_audit",
        "fixture_builder_audit",
        "branch_coverage_audit",
        "mutation_smoke",
        "scripts_pytest_no_db",
        "server_pytest_no_db",
        "migration_schema",
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
    assert idle_by_step["test_inventory_audit"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["db_cleanup_profile_audit"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["fixture_builder_audit"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["branch_coverage_audit"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["mutation_smoke"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["scripts_pytest_no_db"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["server_pytest_no_db"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["migration_schema"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["server_pytest_db_knowledge"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["server_pytest_db_web_api"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["server_pytest_agent_ws"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS
    assert idle_by_step["pc_agent_pytest"] == run_ci_suite.DEFAULT_IDLE_TIMEOUT_SECONDS

    command_by_step = {
        step_name: command
        for step_name, command, _log_path, _idle_timeout, _env, _timeout in steps_seen
    }
    assert command_by_step["webapp_unit_tests"] == run_ci_suite._webapp_unit_test_command(tmp_path)
    assert command_by_step["webapp_unit_tests"][-2:] == ["--pool=threads", "--maxWorkers=1"]
    assert command_by_step["webapp_fixture_e2e"] == run_ci_suite._webapp_fixture_e2e_command(tmp_path)
    assert command_by_step["test_inventory_audit"] == [
        sys.executable,
        str(tmp_path / "scripts" / "audit_test_inventory.py"),
        "--workspace",
        str(tmp_path),
        "--strict",
    ]
    assert command_by_step["db_cleanup_profile_audit"] == [
        sys.executable,
        str(tmp_path / "scripts" / "audit_db_cleanup_profiles.py"),
        "--tests-dir",
        str(tmp_path / "server" / "tests"),
        "--strict",
    ]
    assert command_by_step["fixture_builder_audit"] == [
        sys.executable,
        str(tmp_path / "scripts" / "audit_fixture_builders.py"),
        "--workspace",
        str(tmp_path),
        "--strict",
    ]
    assert command_by_step["branch_coverage_audit"] == [
        sys.executable,
        str(tmp_path / "scripts" / "audit_branch_coverage.py"),
        "--workspace",
        str(tmp_path),
        "--strict",
    ]
    assert command_by_step["mutation_smoke"] == [
        sys.executable,
        str(tmp_path / "scripts" / "run_mutation_smoke.py"),
        "--workspace",
        str(tmp_path),
    ]
    assert command_by_step["scripts_pytest_no_db"][3] == (
        "scripts\\test_ci_helper.py" if sys.platform == "win32" else "scripts/test_ci_helper.py"
    )
    assert command_by_step["scripts_pytest_no_db"][-6:] == [
        "-m",
        "not manual",
        "-vv",
        "--durations=40",
        "--junitxml",
        str(summary_path.parent / "junit-scripts-no-db.xml"),
    ]
    assert command_by_step["server_pytest_no_db"][-6:] == [
        "-m",
        "not manual and no_db",
        "-vv",
        "--durations=80",
        "--junitxml",
        str(summary_path.parent / "junit-server-no-db.xml"),
    ]
    expected_migration_path = (
        "server\\tests\\test_migration_schema_contract.py"
        if sys.platform == "win32"
        else "server/tests/test_migration_schema_contract.py"
    )
    assert command_by_step["migration_schema"][3] == expected_migration_path
    assert command_by_step["migration_schema"][-6:] == [
        "-m",
        "not manual and not no_db and not agent_ws",
        "-vv",
        "--durations=80",
        "--junitxml",
        str(summary_path.parent / "junit-migration-schema.xml"),
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
    assert command_by_step["pc_agent_pytest"][-7:] == [
        "pc_agent/tests",
        "-m",
        "not manual",
        "-vv",
        "--durations=80",
        "--junitxml",
        str(summary_path.parent / "junit-pc-agent.xml"),
    ]
    env_by_step = {
        step_name: env
        for step_name, _command, _log_path, _idle_timeout, env, _timeout in steps_seen
    }
    assert env_by_step["webapp_unit_tests"] == {"CI": "1"}
    assert env_by_step["webapp_fixture_e2e"] == {
        "CI": "1",
        "PLAYWRIGHT_JSON_OUTPUT_NAME": str(summary_path.parent / "playwright-webapp-fixture-e2e.json"),
    }
    assert env_by_step["test_inventory_audit"] is None
    assert env_by_step["db_cleanup_profile_audit"] is None
    assert env_by_step["fixture_builder_audit"] is None
    assert env_by_step["branch_coverage_audit"] is None
    assert env_by_step["mutation_smoke"] is None
    assert env_by_step["scripts_pytest_no_db"] is None
    assert env_by_step["server_pytest_no_db"] == {
        "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
        "PC_CLIENT_TEST_TIMING": "1",
        "PC_CLIENT_TEST_TIMING_PATH": str(summary_path.parent / "fixture-timings" / "server_pytest_no_db.jsonl"),
    }
    assert env_by_step["migration_schema"] == {
        "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
        "PC_CLIENT_TEST_TIMING": "1",
        "PC_CLIENT_TEST_TIMING_PATH": str(summary_path.parent / "fixture-timings" / "migration_schema.jsonl"),
        "PC_CLIENT_TEST_DB_TEMPLATE": "0",
        "PC_CLIENT_TEST_DB_DOMAIN": "migration_schema",
        "PC_CLIENT_TEST_DB_RUN_ID": "deadbeef",
    }
    assert env_by_step["server_pytest_db_knowledge"] == {
        "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
        "PC_CLIENT_TEST_TIMING": "1",
        "PC_CLIENT_TEST_TIMING_PATH": str(
            summary_path.parent / "fixture-timings" / "server_pytest_db_knowledge.jsonl"
        ),
        "PC_CLIENT_TEST_DB_TEMPLATE": "1",
        "PC_CLIENT_TEST_DB_TEMPLATE_KEEP": "1",
        "PC_CLIENT_TEST_DB_DOMAIN": "knowledge",
        "PC_CLIENT_TEST_DB_RUN_ID": "deadbeef",
    }
    assert env_by_step["server_pytest_db_web_api"] == {
        "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
        "PC_CLIENT_TEST_TIMING": "1",
        "PC_CLIENT_TEST_TIMING_PATH": str(
            summary_path.parent / "fixture-timings" / "server_pytest_db_web_api.jsonl"
        ),
        "PC_CLIENT_TEST_DB_TEMPLATE": "1",
        "PC_CLIENT_TEST_DB_TEMPLATE_KEEP": "1",
        "PC_CLIENT_TEST_DB_DOMAIN": "web_api",
        "PC_CLIENT_TEST_DB_RUN_ID": "deadbeef",
    }
    assert env_by_step["server_pytest_agent_ws"] == {
        "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
        "PC_CLIENT_TEST_TIMING": "1",
        "PC_CLIENT_TEST_TIMING_PATH": str(summary_path.parent / "fixture-timings" / "server_pytest_agent_ws.jsonl"),
        "PC_CLIENT_TEST_DB_TEMPLATE": "1",
        "PC_CLIENT_TEST_DB_TEMPLATE_KEEP": "1",
        "PC_CLIENT_TEST_DB_DOMAIN": "agent_ws",
        "PC_CLIENT_TEST_DB_RUN_ID": "deadbeef",
    }
    timeout_by_step = {
        step_name: timeout
        for step_name, _command, _log_path, _idle_timeout, _env, timeout in steps_seen
    }
    assert timeout_by_step["webapp_unit_tests"] == run_ci_suite.DEFAULT_WEB_TEST_TIMEOUT_SECONDS
    assert timeout_by_step["webapp_fixture_e2e"] == run_ci_suite.DEFAULT_WEB_TEST_TIMEOUT_SECONDS
    assert timeout_by_step["test_inventory_audit"] == 45 * 60
    assert timeout_by_step["db_cleanup_profile_audit"] == 45 * 60
    assert timeout_by_step["fixture_builder_audit"] == 45 * 60
    assert timeout_by_step["branch_coverage_audit"] == 45 * 60
    assert timeout_by_step["mutation_smoke"] == 45 * 60
    assert timeout_by_step["scripts_pytest_no_db"] == 45 * 60
    assert timeout_by_step["server_pytest_no_db"] == 45 * 60
    assert timeout_by_step["migration_schema"] == 45 * 60
    assert timeout_by_step["server_pytest_db_knowledge"] == 45 * 60
    assert timeout_by_step["server_pytest_db_web_api"] == 45 * 60
    assert timeout_by_step["server_pytest_agent_ws"] == 45 * 60

    summary = run_ci_suite.json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["evidence_layers"]["webapp_fixture_e2e"] == {
        "mode": "fixture_e2e",
        "surface": "browser",
        "canonical_live_browser": False,
        "description": "Playwright against the local fixture server; not a live browser signoff.",
    }
    assert summary["baseline_artifacts"]["junit"]["scripts_pytest_no_db"] == str(
        summary_path.parent / "junit-scripts-no-db.xml"
    )
    assert summary["baseline_artifacts"]["junit"]["server_pytest_db_api_layers"]["server_pytest_db_knowledge"] == str(
        summary_path.parent / "junit-server-db-knowledge.xml"
    )
    assert summary["baseline_artifacts"]["junit"]["migration_schema"] == str(
        summary_path.parent / "junit-migration-schema.xml"
    )
    assert summary["baseline_artifacts"]["durations"]["scripts_pytest_no_db"] == {
        "pytest_durations": 40,
        "junit": str(summary_path.parent / "junit-scripts-no-db.xml"),
    }
    assert summary["baseline_artifacts"]["durations"]["server_pytest_db_api_layers"]["server_pytest_db_web_api"] == {
        "pytest_durations": 80,
        "junit": str(summary_path.parent / "junit-server-db-web-api.xml"),
    }
    assert summary["baseline_artifacts"]["durations"]["migration_schema"] == {
        "pytest_durations": 80,
        "junit": str(summary_path.parent / "junit-migration-schema.xml"),
    }
    assert summary["baseline_artifacts"]["durations"]["pc_agent_pytest"] == {
        "pytest_durations": 80,
        "junit": str(summary_path.parent / "junit-pc-agent.xml"),
    }
    assert summary["baseline_artifacts"]["durations"]["fixture_timings_dir"] == str(
        summary_path.parent / "fixture-timings"
    )
    assert summary["baseline_artifacts"]["durations"]["fixture_timings_summary"] == str(
        summary_path.parent / "fixture-timings-summary.json"
    )
    assert summary["baseline_artifacts"]["retries"]["webapp_fixture_e2e"] == {
        "ci_retries": 1,
        "local_retries": 0,
        "trace": "on-first-retry",
        "first_attempt_failures_are_flaky": True,
        "passed_after_retry_status": "flaky",
    }


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
        mirror_output: bool = True,
    ) -> dict[str, object]:
        steps_seen.append(step_name)
        assert env_overrides == {
            "PC_CLIENT_PYTEST_WATCHDOG_SECONDS": "120",
            "PC_CLIENT_TEST_TIMING": "1",
            "PC_CLIENT_TEST_TIMING_PATH": str(
                summary_path.parent / "fixture-timings" / "server_pytest_db_knowledge.jsonl"
            ),
            "PC_CLIENT_TEST_DB_TEMPLATE": "1",
            "PC_CLIENT_TEST_DB_TEMPLATE_KEEP": "1",
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


def _write_layer_test_files(tmp_path: Path) -> None:
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


def _fake_ci_result(step_name: str, log_path: Path, timeout_seconds: float, returncode: int = 0) -> dict[str, object]:
    return {
        "name": step_name,
        "command": [step_name],
        "started_at": "2026-04-20T00:00:00+00:00",
        "finished_at": "2026-04-20T00:00:01+00:00",
        "duration_seconds": 1.0,
        "timeout_seconds": timeout_seconds,
        "timed_out": False,
        "timeout_reason": None,
        "returncode": returncode,
        "log": str(log_path),
    }


def test_parallel_mode_groups_only_server_db_ws_layers_and_respects_max_workers(tmp_path, monkeypatch):
    summary_path = tmp_path / "artifacts" / "ci" / "deadbeef" / "summary.json"
    _write_layer_test_files(tmp_path)
    db_active = 0
    max_db_active = 0
    started_db_layers: list[str] = []
    completed_steps: list[str] = []
    lock = threading.Lock()
    db_layer_names = set(run_ci_suite.SERVER_DB_WS_PARALLEL_LAYER_ORDER)

    monkeypatch.setenv("TEST_DATABASE_ADMIN_URL", "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres")
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
            "--parallel",
            "--max-workers",
            "2",
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
        mirror_output: bool = True,
    ) -> dict[str, object]:
        nonlocal db_active, max_db_active
        if step_name in db_layer_names:
            assert mirror_output is False
            with lock:
                db_active += 1
                max_db_active = max(max_db_active, db_active)
                started_db_layers.append(step_name)
            time.sleep(0.05)
            with lock:
                db_active -= 1
        else:
            assert mirror_output is True
        completed_steps.append(step_name)
        return _fake_ci_result(step_name, log_path, timeout_seconds)

    monkeypatch.setattr(run_ci_suite, "run_and_capture", fake_run_and_capture)

    run_ci_suite.main()

    assert max_db_active == 2
    assert started_db_layers[:2] == [
        "server_pytest_db_web_api",
        "server_pytest_db_tickets",
    ]
    assert set(started_db_layers) == db_layer_names
    assert completed_steps[:12] == [
        "verify_workspace",
        "webapp_bundle",
        "webapp_unit_tests",
        "webapp_fixture_e2e",
        "test_inventory_audit",
        "db_cleanup_profile_audit",
        "fixture_builder_audit",
        "branch_coverage_audit",
        "mutation_smoke",
        "scripts_pytest_no_db",
        "server_pytest_no_db",
        "migration_schema",
    ]
    assert completed_steps[-1] == "pc_agent_pytest"
    summary = run_ci_suite.json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["parallel_enabled"] is True
    assert summary["max_workers"] == 2
    assert len(summary["parallel_groups"]) == 1
    group = summary["parallel_groups"][0]
    assert group["name"] == "server-db"
    assert group["layers"] == list(run_ci_suite.SERVER_DB_WS_PARALLEL_LAYER_ORDER)
    assert group["max_workers"] == 2
    assert group["status"] == "green"
    assert group["skipped_layers"] == []
    assert group["duration_seconds"] > 0
    assert group["started_at"]
    assert group["finished_at"]


def test_parallel_mode_stops_launching_queued_db_layers_after_first_failure(tmp_path, monkeypatch):
    summary_path = tmp_path / "artifacts" / "ci" / "deadbeef" / "summary.json"
    _write_layer_test_files(tmp_path)
    started: list[str] = []
    lock = threading.Lock()
    db_layer_names = set(run_ci_suite.SERVER_DB_WS_PARALLEL_LAYER_ORDER)

    monkeypatch.setenv("TEST_DATABASE_ADMIN_URL", "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres")
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
            "--parallel",
            "--max-workers",
            "2",
            "--layer",
            "server_pytest_db_web_api",
            "--layer",
            "server_pytest_db_tickets",
            "--layer",
            "server_pytest_db_knowledge",
            "--layer",
            "server_pytest_db_observer_diagnostics",
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
        mirror_output: bool = True,
    ) -> dict[str, object]:
        assert step_name in db_layer_names
        assert mirror_output is False
        with lock:
            started.append(step_name)
        if step_name == "server_pytest_db_web_api":
            time.sleep(0.02)
            return _fake_ci_result(step_name, log_path, timeout_seconds, returncode=1)
        time.sleep(0.2)
        return _fake_ci_result(step_name, log_path, timeout_seconds)

    monkeypatch.setattr(run_ci_suite, "run_and_capture", fake_run_and_capture)

    with pytest.raises(SystemExit) as exc_info:
        run_ci_suite.main()

    assert exc_info.value.code == 1
    assert started == [
        "server_pytest_db_web_api",
        "server_pytest_db_tickets",
    ]
    summary = run_ci_suite.json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "red"
    assert summary["parallel_groups"][0]["status"] == "red"
    assert summary["parallel_groups"][0]["skipped_layers"] == [
        "server_pytest_db_knowledge",
        "server_pytest_db_observer_diagnostics",
    ]


def test_parallel_single_requested_db_layer_runs_sequentially(tmp_path, monkeypatch):
    summary_path = tmp_path / "artifacts" / "ci" / "deadbeef" / "summary.json"
    _write_layer_test_files(tmp_path)
    seen: list[tuple[str, bool]] = []

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
            "--parallel",
            "--layer",
            "server_pytest_db_agent_runtime",
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
        mirror_output: bool = True,
    ) -> dict[str, object]:
        seen.append((step_name, mirror_output))
        return _fake_ci_result(step_name, log_path, timeout_seconds)

    monkeypatch.setattr(run_ci_suite, "run_and_capture", fake_run_and_capture)

    run_ci_suite.main()

    assert seen == [("server_pytest_db_agent_runtime", True)]
    summary = run_ci_suite.json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["parallel_enabled"] is True
    assert summary["parallel_groups"] == []


def test_parallel_measurements_cap_workers_after_budget_failure(tmp_path):
    measurements = tmp_path / "fixture-timings-summary.json"
    measurements.write_text(
        run_ci_suite.json.dumps(
            {
                "schema": "pc_client.fixture_timings_summary.v1",
                "budget_status": "fail",
                "budget_violations": [
                    {
                        "fixture": "cleanup_db",
                        "phase": "setup",
                        "metric": "p95_seconds",
                        "actual_seconds": 45.0,
                        "budget_seconds": 30.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    decision = run_ci_suite._parallel_measurement_decision(measurements, requested_max_workers=3)

    assert decision == {
        "path": str(measurements),
        "budget_status": "fail",
        "recommended_max_workers": 1,
        "effective_max_workers": 1,
        "reason": "fixture timing budget failed; run DB/WS layers sequentially until timings recover",
        "violation_count": 1,
    }


def test_parallel_measurements_can_disable_parallel_group(tmp_path, monkeypatch):
    summary_path = tmp_path / "artifacts" / "ci" / "deadbeef" / "summary.json"
    measurements = tmp_path / "fixture-timings-summary.json"
    measurements.write_text(
        run_ci_suite.json.dumps(
            {"schema": "pc_client.fixture_timings_summary.v1", "budget_status": "fail", "budget_violations": []}
        ),
        encoding="utf-8",
    )
    _write_layer_test_files(tmp_path)
    seen: list[tuple[str, bool]] = []

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
            "--parallel",
            "--parallel-measurements",
            str(measurements),
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
        mirror_output: bool = True,
    ) -> dict[str, object]:
        seen.append((step_name, mirror_output))
        return _fake_ci_result(step_name, log_path, timeout_seconds)

    monkeypatch.setattr(run_ci_suite, "run_and_capture", fake_run_and_capture)

    run_ci_suite.main()

    assert all(mirror_output for _step_name, mirror_output in seen)
    summary = run_ci_suite.json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["parallel_enabled"] is True
    assert summary["max_workers"] == 1
    assert summary["parallel_groups"] == []
    assert summary["parallel_measurement_decision"]["effective_max_workers"] == 1


def _write_playwright_retry_report(path: Path, *, status: str = "passed") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        run_ci_suite.json.dumps(
            {
                "suites": [
                    {
                        "title": "webapp tests",
                        "suites": [
                            {
                                "title": "requester-workspace.spec.ts",
                                "file": "webapp/tests/requester-workspace.spec.ts",
                                "specs": [
                                    {
                                        "title": "renders requester dashboard",
                                        "file": "webapp/tests/requester-workspace.spec.ts",
                                        "line": 42,
                                        "tests": [
                                            {
                                                "projectName": "chromium",
                                                "expectedStatus": "passed",
                                                "status": "flaky",
                                                "results": [
                                                    {
                                                        "retry": 0,
                                                        "workerIndex": 1,
                                                        "status": "failed",
                                                        "errors": [{"message": "locator timeout"}],
                                                        "attachments": [
                                                            {
                                                                "name": "trace",
                                                                "path": "test-results/trace.zip",
                                                                "contentType": "application/zip",
                                                            }
                                                        ],
                                                    },
                                                    {
                                                        "retry": 1,
                                                        "workerIndex": 2,
                                                        "status": status,
                                                        "errors": [],
                                                        "attachments": [],
                                                    },
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_flaky_summary_fails_unknown_retry_pass(tmp_path):
    report_path = tmp_path / "playwright-report.json"
    registry_path = tmp_path / "flaky-registry.json"
    _write_playwright_retry_report(report_path)
    registry_path.write_text(
        run_ci_suite.json.dumps({"schema": "pc_client.flaky_registry.v1", "entries": []}),
        encoding="utf-8",
    )

    summary = run_ci_suite._build_flaky_summary(
        registry_path=registry_path,
        report_paths={"webapp_fixture_e2e": report_path},
    )

    assert summary["status"] == "fail"
    assert len(summary["records"]) == 1
    assert summary["records"][0]["node_id"] == (
        "webapp/tests/requester-workspace.spec.ts::renders requester dashboard [chromium]"
    )
    assert summary["records"][0]["first_attempt_status"] == "failed"
    assert summary["records"][0]["final_attempt_status"] == "passed"
    assert summary["records"][0]["previous_error"] == "locator timeout"
    assert summary["records"][0]["artifacts"] == [
        {
            "name": "trace",
            "path": "test-results/trace.zip",
            "content_type": "application/zip",
        }
    ]
    assert summary["unknown_records"] == [summary["records"][0]]
    assert summary["allowed_records"] == []


def test_flaky_summary_allows_registry_match_without_clean_green(tmp_path):
    report_path = tmp_path / "playwright-report.json"
    registry_path = tmp_path / "flaky-registry.json"
    _write_playwright_retry_report(report_path)
    registry_path.write_text(
        run_ci_suite.json.dumps(
            {
                "schema": "pc_client.flaky_registry.v1",
                "entries": [
                    {
                        "id": "fixture-requester-dashboard-retry",
                        "layer": "webapp_fixture_e2e",
                        "node_id": "webapp/tests/requester-workspace.spec.ts::*",
                        "owner": "webapp",
                        "reason": "documented fixture retry while live gate remains separate",
                        "expires": "2026-07-31",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = run_ci_suite._build_flaky_summary(
        registry_path=registry_path,
        report_paths={"webapp_fixture_e2e": report_path},
    )

    assert summary["status"] == "pass"
    assert summary["records"][0]["classification"] == "passed_after_retry"
    assert summary["records"][0]["registry_match"]["id"] == "fixture-requester-dashboard-retry"
    assert summary["clean_green"] is False
    assert summary["allowed_records"] == summary["records"]
    assert summary["unknown_records"] == []


def test_windows_parallel_tunnel_uses_explicit_admin_url_without_starting_ssh(monkeypatch):
    monkeypatch.setattr(run_ci_suite.os, "name", "nt")
    monkeypatch.setenv("TEST_DATABASE_ADMIN_URL", "postgresql+asyncpg://example/postgres")
    monkeypatch.setattr(
        run_ci_suite.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("explicit TEST_DATABASE_ADMIN_URL must not start ssh"),
    )

    tunnel = run_ci_suite._prepare_windows_parallel_db_tunnel()

    assert tunnel.env_overrides == {}
    tunnel.close()


def test_windows_parallel_tunnel_uses_existing_port_without_owning_it(monkeypatch):
    monkeypatch.setattr(run_ci_suite.os, "name", "nt")
    monkeypatch.delenv("TEST_DATABASE_ADMIN_URL", raising=False)
    monkeypatch.setattr(run_ci_suite, "_is_tcp_port_open", lambda host, port: True)
    monkeypatch.setattr(
        run_ci_suite.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("open tunnel port must be reused"),
    )

    tunnel = run_ci_suite._prepare_windows_parallel_db_tunnel()

    assert tunnel.env_overrides == {
        "TEST_DATABASE_ADMIN_URL": "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres",
        "PC_CLIENT_TEST_DB_TUNNEL_PARENT_OWNED": "existing",
    }
    tunnel.close()


def test_windows_parallel_tunnel_starts_ssh_from_env_defaults(monkeypatch):
    class FakeProcess:
        stderr = None

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            self.killed = True

    process = FakeProcess()
    commands: list[list[str]] = []
    port_checks = iter([False, True])

    monkeypatch.setattr(run_ci_suite.os, "name", "nt")
    monkeypatch.delenv("TEST_DATABASE_ADMIN_URL", raising=False)
    monkeypatch.setenv("PC_CLIENT_TEST_DB_TUNNEL_HOST", "127.0.0.2")
    monkeypatch.setenv("PC_CLIENT_TEST_DB_TUNNEL_PORT", "65432")
    monkeypatch.setenv("PC_CLIENT_TEST_DB_SSH_TARGET", "ci@example")
    monkeypatch.setenv("PC_CLIENT_TEST_DB_REMOTE_BIND", "10.0.0.5:5432")
    monkeypatch.setenv("PC_CLIENT_TEST_DB_SSH_KEY", "C:\\tmp\\key")
    monkeypatch.setattr(run_ci_suite, "_is_tcp_port_open", lambda host, port: next(port_checks))

    def fake_popen(command: list[str], **kwargs):
        commands.append(command)
        return process

    monkeypatch.setattr(run_ci_suite.subprocess, "Popen", fake_popen)

    tunnel = run_ci_suite._prepare_windows_parallel_db_tunnel()

    assert commands == [
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-i",
            "C:\\tmp\\key",
            "-L",
            "65432:10.0.0.5:5432",
            "ci@example",
            "-N",
        ]
    ]
    assert tunnel.env_overrides == {
        "TEST_DATABASE_ADMIN_URL": "postgresql+asyncpg://chatbot:chatbot@127.0.0.2:65432/postgres",
        "PC_CLIENT_TEST_DB_TUNNEL_PARENT_OWNED": "1",
    }
    tunnel.close()
    assert process.terminated is True
    assert process.killed is False


def test_parallel_tunnel_noops_off_windows(monkeypatch):
    monkeypatch.setattr(run_ci_suite.os, "name", "posix")
    monkeypatch.setattr(
        run_ci_suite.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("non-Windows tunnel helper must not start ssh"),
    )

    tunnel = run_ci_suite._prepare_windows_parallel_db_tunnel()

    assert tunnel.env_overrides == {}
    tunnel.close()


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


def test_pnpm_webapp_command_resolves_windows_cmd_shim(monkeypatch, tmp_path):
    monkeypatch.setattr(run_ci_suite.os, "name", "nt")
    monkeypatch.setattr(
        run_ci_suite.shutil,
        "which",
        lambda name: str(tmp_path / "pnpm.cmd") if name == "pnpm.cmd" else None,
    )

    assert run_ci_suite._pnpm_webapp_command(tmp_path, "run", "test") == [
        str(tmp_path / "pnpm.cmd"),
        "--dir",
        str(tmp_path / "webapp"),
        "run",
        "test",
    ]
