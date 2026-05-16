#!/usr/bin/env python3
"""Run the canonical self-hosted CI suite and store artifacts under artifacts/ci/<sha>/."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.ci_artifacts import (
        DEFAULT_WORKSPACE,
        detect_commit,
        summary_path_for_commit,
        webapp_bundle_archive_for_commit,
        webapp_bundle_dir_for_commit,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import (
        DEFAULT_WORKSPACE,
        detect_commit,
        summary_path_for_commit,
        webapp_bundle_archive_for_commit,
        webapp_bundle_dir_for_commit,
    )


DEFAULT_VERIFY_TIMEOUT_SECONDS = 10 * 60
DEFAULT_WEB_BUILD_TIMEOUT_SECONDS = 20 * 60
DEFAULT_SERVER_PYTEST_TIMEOUT_SECONDS = 45 * 60
DEFAULT_PC_AGENT_PYTEST_TIMEOUT_SECONDS = 30 * 60
DEFAULT_IDLE_TIMEOUT_SECONDS = 10 * 60
DEFAULT_PYTEST_WATCHDOG_SECONDS = 120
OUTPUT_POLL_INTERVAL_SECONDS = 0.2
STEP_TIMEOUT_EXIT_CODE = 124

SERVER_DB_API_LAYER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "server_pytest_db_knowledge",
        (
            "test_knowledge_*.py",
            "test_support_knowledge_provider.py",
        ),
    ),
    (
        "server_pytest_db_tickets",
        (
            "test_ticket_*.py",
            "test_helpdesk_*.py",
            "test_form_*.py",
            "test_policy_health*.py",
            "test_public_queue_privacy.py",
            "test_service_catalog_*.py",
            "test_reports_service_catalog.py",
            "test_requester_timeline_projection.py",
            "test_stage8.py",
            "test_support_playbook_readiness.py",
            "test_registry_*.py",
        ),
    ),
    (
        "server_pytest_db_observer_diagnostics",
        (
            "test_admin_tech_api.py",
            "test_control_plane_api.py",
            "test_diagnostic_*.py",
            "test_manual_capability_provider.py",
            "test_observer_*.py",
            "test_trace_overlay_api.py",
            "test_workflow_side_effect_observability.py",
            "test_zabbix_provider_no_db.py",
        ),
    ),
    (
        "server_pytest_db_agent_runtime",
        (
            "test_agent_*.py",
            "test_cancel_operations.py",
            "test_command_result_*.py",
            "test_device_*.py",
            "test_handshake_module_reconcile.py",
            "test_modules_*.py",
            "test_operation_*.py",
            "test_outbox_*.py",
            "test_protocol_*.py",
            "test_remote_assist_*.py",
            "test_state_manager_agent_registry.py",
            "test_subscription_registry.py",
            "test_tool_*.py",
            "test_tools_*.py",
        ),
    ),
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--commit")
    parser.add_argument(
        "--layer",
        action="append",
        default=[],
        help="Run only the named CI layer. May be supplied multiple times.",
    )
    parser.add_argument(
        "--keep-test-db",
        action="store_true",
        help="Keep isolated PostgreSQL test databases after DB-backed server layers.",
    )
    parser.add_argument("--verify-timeout", type=float, default=DEFAULT_VERIFY_TIMEOUT_SECONDS)
    parser.add_argument("--web-build-timeout", type=float, default=DEFAULT_WEB_BUILD_TIMEOUT_SECONDS)
    parser.add_argument("--server-pytest-timeout", type=float, default=DEFAULT_SERVER_PYTEST_TIMEOUT_SECONDS)
    parser.add_argument("--pc-agent-pytest-timeout", type=float, default=DEFAULT_PC_AGENT_PYTEST_TIMEOUT_SECONDS)
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=DEFAULT_IDLE_TIMEOUT_SECONDS,
        help="Fail a step if it produces no output for this many seconds. Use 0 to disable.",
    )
    return parser.parse_args(argv)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _command_text(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return " ".join(command)


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _pump_process_output(
    stream: subprocess.Popen[str].stdout, output_queue: "queue.Queue[str | None]"
) -> None:
    if stream is None:
        output_queue.put(None)
        return
    try:
        for line in iter(stream.readline, ""):
            output_queue.put(line)
    finally:
        stream.close()
        output_queue.put(None)


def _write_output(handle, text: str) -> None:
    handle.write(text)
    handle.flush()
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    except OSError:
        # Artifact logs are canonical; terminal mirroring is best-effort only.
        return
    try:
        sys.stdout.flush()
    except OSError:
        return


def _drain_output_queue(
    output_queue: "queue.Queue[str | None]",
    handle,
) -> tuple[bool, bool]:
    saw_output = False
    reader_closed = False
    while True:
        try:
            item = output_queue.get_nowait()
        except queue.Empty:
            break
        if item is None:
            reader_closed = True
            continue
        saw_output = True
        _write_output(handle, item)
    return saw_output, reader_closed


def _normalize_idle_timeout_seconds(idle_timeout_seconds: float | None) -> float | None:
    if idle_timeout_seconds is None or idle_timeout_seconds <= 0:
        return None
    return float(idle_timeout_seconds)


def run_and_capture(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    step_name: str,
    timeout_seconds: float,
    idle_timeout_seconds: float | None = DEFAULT_IDLE_TIMEOUT_SECONDS,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = now_iso()
    started_monotonic = time.monotonic()
    effective_idle_timeout_seconds = _normalize_idle_timeout_seconds(idle_timeout_seconds)
    idle_timeout_label = (
        f"{effective_idle_timeout_seconds:.1f}s"
        if effective_idle_timeout_seconds is not None
        else "disabled"
    )
    print(
        f"[ci] step={step_name} started timeout={timeout_seconds:.1f}s "
        f"idle_timeout={idle_timeout_label} log={log_path}"
    )
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write(f"[ci] step={step_name}\n")
        handle.write(f"[ci] started_at={started_at}\n")
        handle.write(f"[ci] cwd={cwd}\n")
        handle.write(f"[ci] timeout_seconds={timeout_seconds:.1f}\n")
        if effective_idle_timeout_seconds is None:
            handle.write("[ci] idle_timeout_seconds=disabled\n")
        else:
            handle.write(f"[ci] idle_timeout_seconds={effective_idle_timeout_seconds:.1f}\n")
        handle.write(f"[ci] command={_command_text(command)}\n\n")
        handle.flush()

        child_env = os.environ.copy()
        if env_overrides:
            child_env.update(env_overrides)

        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        output_queue: "queue.Queue[str | None]" = queue.Queue()
        reader = threading.Thread(
            target=_pump_process_output,
            args=(process.stdout, output_queue),
            daemon=True,
        )
        reader.start()
        timed_out = False
        timeout_reason: str | None = None
        last_output_monotonic = time.monotonic()
        reader_closed = False

        while True:
            saw_output, saw_reader_close = _drain_output_queue(output_queue, handle)
            if saw_output:
                last_output_monotonic = time.monotonic()
            reader_closed = reader_closed or saw_reader_close

            if process.poll() is not None:
                reader.join(timeout=OUTPUT_POLL_INTERVAL_SECONDS)
                saw_output, saw_reader_close = _drain_output_queue(output_queue, handle)
                if saw_output:
                    last_output_monotonic = time.monotonic()
                reader_closed = reader_closed or saw_reader_close
                if not reader.is_alive() and output_queue.empty():
                    break

            elapsed_seconds = time.monotonic() - started_monotonic
            if elapsed_seconds >= timeout_seconds:
                timed_out = True
                timeout_reason = "timeout"
                handle.write(
                    f"[ci] step timed out after {timeout_seconds:.1f}s; "
                    f"terminating pid={process.pid}\n"
                )
                handle.flush()
                _terminate_process_tree(process)
                reader.join(timeout=5)
                _drain_output_queue(output_queue, handle)
                break

            if (
                effective_idle_timeout_seconds is not None
                and time.monotonic() - last_output_monotonic >= effective_idle_timeout_seconds
            ):
                timed_out = True
                timeout_reason = "idle_timeout"
                handle.write(
                    f"[ci] step hit idle timeout after {effective_idle_timeout_seconds:.1f}s "
                    f"without output; terminating pid={process.pid}\n"
                )
                handle.flush()
                _terminate_process_tree(process)
                reader.join(timeout=5)
                _drain_output_queue(output_queue, handle)
                break

            time.sleep(OUTPUT_POLL_INTERVAL_SECONDS)

        duration_seconds = round(time.monotonic() - started_monotonic, 3)
        returncode = STEP_TIMEOUT_EXIT_CODE if timed_out else int(process.returncode or 0)
        finished_at = now_iso()
        handle.write("\n")
        handle.write(
            f"[ci] finished_at={finished_at} returncode={returncode} "
            f"timed_out={timed_out} timeout_reason={timeout_reason or 'none'} "
            f"duration_seconds={duration_seconds}\n"
        )
        handle.flush()

    print(
        f"[ci] step={step_name} finished returncode={returncode} "
        f"timed_out={timed_out} timeout_reason={timeout_reason or 'none'} "
        f"duration={duration_seconds:.3f}s"
    )
    return {
        "name": step_name,
        "command": command,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "timeout_reason": timeout_reason,
        "returncode": returncode,
        "log": str(log_path),
    }


def write_summary(summary_path: Path, summary: dict[str, object]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _test_db_domain_for_layer(layer_name: str) -> str:
    domain = layer_name
    for prefix in ("server_pytest_db_", "server_pytest_"):
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]
            break
    return re.sub(r"[^a-z0-9_]+", "_", domain.lower()).strip("_") or "server"


def _server_pytest_env(
    *,
    layer_name: str | None = None,
    commit: str | None = None,
    keep_test_db: bool = False,
) -> dict[str, str]:
    env = {"PC_CLIENT_PYTEST_WATCHDOG_SECONDS": str(DEFAULT_PYTEST_WATCHDOG_SECONDS)}
    if layer_name and layer_name != "server_pytest_no_db":
        env["PC_CLIENT_TEST_DB_DOMAIN"] = _test_db_domain_for_layer(layer_name)
        if commit:
            env["PC_CLIENT_TEST_DB_RUN_ID"] = commit[:12]
        if keep_test_db:
            env["PC_CLIENT_KEEP_TEST_DB"] = "1"
    return env


def _server_pytest_command(marker_expr: str, junit_path: Path, paths: list[Path | str] | None = None) -> list[str]:
    test_paths = [str(path) for path in (paths or ["server/tests"])]
    return [
        sys.executable,
        "-m",
        "pytest",
        *test_paths,
        "-m",
        marker_expr,
        "-vv",
        "--durations=80",
        "--junitxml",
        str(junit_path),
    ]


def _classify_server_db_api_test_file(filename: str) -> str:
    for layer_name, patterns in SERVER_DB_API_LAYER_RULES:
        if any(fnmatch.fnmatch(filename, pattern) for pattern in patterns):
            return layer_name
    return "server_pytest_db_web_api"


def _server_db_api_layer_paths(workspace: Path) -> list[tuple[str, list[Path]]]:
    tests_dir = workspace / "server" / "tests"
    test_files = sorted(tests_dir.glob("test_*.py"))
    if not test_files:
        return [("server_pytest_db_api", [Path("server/tests")])]

    grouped: dict[str, list[Path]] = {}
    for path in test_files:
        layer_name = _classify_server_db_api_test_file(path.name)
        grouped.setdefault(layer_name, []).append(path.relative_to(workspace))

    layer_order = [name for name, _patterns in SERVER_DB_API_LAYER_RULES] + ["server_pytest_db_web_api"]
    return [(name, grouped[name]) for name in layer_order if grouped.get(name)]


def _server_db_api_layer_steps(
    *,
    workspace: Path,
    artifact_dir: Path,
    logs_dir: Path,
    timeout_seconds: float,
    idle_timeout_seconds: float,
    commit: str,
    keep_test_db: bool,
) -> list[tuple[str, list[str], Path, float, float, dict[str, str]]]:
    steps = []
    for layer_name, paths in _server_db_api_layer_paths(workspace):
        junit_name = layer_name.replace("server_pytest_", "junit-server-").replace("_", "-")
        steps.append(
            (
                layer_name,
                _server_pytest_command(
                    "not manual and not no_db and not agent_ws",
                    artifact_dir / f"{junit_name}.xml",
                    paths,
                ),
                logs_dir / f"{layer_name}.log",
                timeout_seconds,
                idle_timeout_seconds,
                _server_pytest_env(layer_name=layer_name, commit=commit, keep_test_db=keep_test_db),
            )
        )
    return steps


def _filter_steps_by_layer(
    steps: list[tuple[str, list[str], Path, float, float, dict[str, str] | None]],
    requested_layers: list[str],
) -> list[tuple[str, list[str], Path, float, float, dict[str, str] | None]]:
    if not requested_layers:
        return steps
    requested = set(requested_layers)
    available = {step_name for step_name, *_rest in steps}
    unknown = sorted(requested - available)
    if unknown:
        available_text = ", ".join(sorted(available))
        raise SystemExit(f"Unknown CI layer(s): {', '.join(unknown)}. Available layers: {available_text}")
    return [step for step in steps if step[0] in requested]


def main() -> None:
    args = parse_args()
    commit = detect_commit(args.workspace, args.commit)
    summary_path = summary_path_for_commit(args.workspace, commit)
    artifact_dir = summary_path.parent
    logs_dir = artifact_dir / "logs"
    webapp_bundle_dir = webapp_bundle_dir_for_commit(args.workspace, commit)
    webapp_bundle_archive = webapp_bundle_archive_for_commit(args.workspace, commit)
    started_at = now_iso()

    steps = [
        (
            "verify_workspace",
            [
                sys.executable,
                str(args.workspace / "scripts" / "verify_workspace.py"),
                "--workspace",
                str(args.workspace),
            ],
            logs_dir / "verify_workspace.log",
            float(args.verify_timeout),
            float(args.idle_timeout),
            None,
        ),
        (
            "webapp_bundle",
            [
                sys.executable,
                str(args.workspace / "scripts" / "build_webapp_bundle.py"),
                "--workspace",
                str(args.workspace),
                "--output-dir",
                str(webapp_bundle_dir),
                "--archive",
                str(webapp_bundle_archive),
            ],
            logs_dir / "webapp_bundle.log",
            float(args.web_build_timeout),
            float(args.idle_timeout),
            None,
        ),
        (
            "server_pytest_no_db",
            _server_pytest_command("not manual and no_db", artifact_dir / "junit-server-no-db.xml"),
            logs_dir / "server_pytest_no_db.log",
            float(args.server_pytest_timeout),
            float(args.idle_timeout),
            _server_pytest_env(layer_name="server_pytest_no_db", commit=commit, keep_test_db=args.keep_test_db),
        ),
        *_server_db_api_layer_steps(
            workspace=args.workspace,
            artifact_dir=artifact_dir,
            logs_dir=logs_dir,
            timeout_seconds=float(args.server_pytest_timeout),
            idle_timeout_seconds=float(args.idle_timeout),
            commit=commit,
            keep_test_db=args.keep_test_db,
        ),
        (
            "server_pytest_agent_ws",
            _server_pytest_command("not manual and agent_ws", artifact_dir / "junit-server-agent-ws.xml"),
            logs_dir / "server_pytest_agent_ws.log",
            float(args.server_pytest_timeout),
            float(args.idle_timeout),
            _server_pytest_env(layer_name="server_pytest_agent_ws", commit=commit, keep_test_db=args.keep_test_db),
        ),
        (
            "pc_agent_pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "pc_agent/tests",
                "-m",
                "not manual",
                "--junitxml",
                str(artifact_dir / "junit-pc-agent.xml"),
            ],
            logs_dir / "pc_agent_pytest.log",
            float(args.pc_agent_pytest_timeout),
            float(args.idle_timeout),
            None,
        ),
    ]
    available_layers = [step_name for step_name, *_rest in steps]
    steps = _filter_steps_by_layer(steps, args.layer)

    results: list[dict[str, object]] = []
    status = "green"
    runner_error: str | None = None
    try:
        for step_name, command, log_path, timeout_seconds, idle_timeout_seconds, env_overrides in steps:
            result = run_and_capture(
                command,
                cwd=args.workspace,
                log_path=log_path,
                step_name=step_name,
                timeout_seconds=timeout_seconds,
                idle_timeout_seconds=idle_timeout_seconds,
                env_overrides=env_overrides,
            )
            results.append(result)
            if result["returncode"] != 0:
                status = "red"
                break
    except KeyboardInterrupt:
        status = "red"
        runner_error = "Interrupted by user"
        print("[ci] interrupted by user", file=sys.stderr)
    except Exception as exc:
        status = "red"
        runner_error = f"{type(exc).__name__}: {exc}"
        print(f"[ci] runner error: {runner_error}", file=sys.stderr)
    finally:
        summary = {
            "commit": commit,
            "status": status,
            "started_at": started_at,
            "finished_at": now_iso(),
            "requested_layers": args.layer,
            "available_layers": available_layers,
            "artifacts": {
                "summary": str(summary_path),
                "webapp_bundle_dir": str(webapp_bundle_dir),
                "webapp_bundle_archive": str(webapp_bundle_archive),
                "junit_server_no_db": str(artifact_dir / "junit-server-no-db.xml"),
                "junit_server_db_api_layers": {
                    layer_name: str(
                        artifact_dir
                        / f"{layer_name.replace('server_pytest_', 'junit-server-').replace('_', '-')}.xml"
                    )
                    for layer_name, _paths in _server_db_api_layer_paths(args.workspace)
                },
                "junit_server_agent_ws": str(artifact_dir / "junit-server-agent-ws.xml"),
                "junit_pc_agent": str(artifact_dir / "junit-pc-agent.xml"),
            },
            "steps": results,
        }
        if runner_error:
            summary["runner_error"] = runner_error
        write_summary(summary_path, summary)

    if status != "green":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
