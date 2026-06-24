#!/usr/bin/env python3
"""Run the canonical self-hosted CI suite and store artifacts under artifacts/ci/<sha>/."""

from __future__ import annotations

import argparse
import concurrent.futures
import fnmatch
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
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
    from scripts.summarize_fixture_timings import summarize_artifact_dir
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import (
        DEFAULT_WORKSPACE,
        detect_commit,
        summary_path_for_commit,
        webapp_bundle_archive_for_commit,
        webapp_bundle_dir_for_commit,
    )
    from scripts.summarize_fixture_timings import summarize_artifact_dir


DEFAULT_VERIFY_TIMEOUT_SECONDS = 10 * 60
DEFAULT_WEB_BUILD_TIMEOUT_SECONDS = 20 * 60
DEFAULT_WEB_TEST_TIMEOUT_SECONDS = 20 * 60
DEFAULT_SERVER_PYTEST_TIMEOUT_SECONDS = 45 * 60
DEFAULT_PC_AGENT_PYTEST_TIMEOUT_SECONDS = 30 * 60
DEFAULT_IDLE_TIMEOUT_SECONDS = 10 * 60
DEFAULT_PYTEST_WATCHDOG_SECONDS = 120
OUTPUT_POLL_INTERVAL_SECONDS = 0.2
STEP_TIMEOUT_EXIT_CODE = 124
DEFAULT_FLAKY_REGISTRY_PATH = Path("quality/flaky_registry.json")
CI_EVIDENCE_LAYERS = {
    "webapp_fixture_e2e": {
        "mode": "fixture_e2e",
        "surface": "browser",
        "canonical_live_browser": False,
        "description": "Playwright against the local fixture server; not a live browser signoff.",
    },
}

Step = tuple[str, list[str], Path, float, float, dict[str, str] | None]
MIGRATION_SCHEMA_TEST_PATH = Path("server/tests/test_migration_schema_contract.py")

SERVER_DB_WS_PARALLEL_LAYER_ORDER: tuple[str, ...] = (
    "server_pytest_db_web_api",
    "server_pytest_db_tickets",
    "server_pytest_db_knowledge",
    "server_pytest_db_observer_diagnostics",
    "server_pytest_db_agent_runtime",
    "server_pytest_agent_ws",
)

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
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run independent server DB/WS pytest layers in a bounded parallel group.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Maximum active subprocesses for --parallel. Defaults to 2.",
    )
    parser.add_argument(
        "--parallel-measurements",
        type=Path,
        help="Fixture timing summary JSON used to cap --parallel worker count from measured budget status.",
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
    parser.add_argument(
        "--flaky-registry",
        type=Path,
        default=DEFAULT_FLAKY_REGISTRY_PATH,
        help="JSON registry of allowed retry-pass flaky records. Unknown retry-pass records fail the CI summary.",
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
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1,
            )
        except subprocess.TimeoutExpired:
            process.kill()
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


def _write_output(handle, text: str, *, mirror_output: bool = True) -> None:
    handle.write(text)
    handle.flush()
    if not mirror_output:
        return
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
    *,
    mirror_output: bool = True,
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
        _write_output(handle, item, mirror_output=mirror_output)
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
    mirror_output: bool = True,
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
        f"idle_timeout={idle_timeout_label} log={log_path}",
        flush=True,
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
            saw_output, saw_reader_close = _drain_output_queue(
                output_queue,
                handle,
                mirror_output=mirror_output,
            )
            if saw_output:
                last_output_monotonic = time.monotonic()
            reader_closed = reader_closed or saw_reader_close

            if process.poll() is not None:
                reader.join(timeout=OUTPUT_POLL_INTERVAL_SECONDS)
                saw_output, saw_reader_close = _drain_output_queue(
                    output_queue,
                    handle,
                    mirror_output=mirror_output,
                )
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
                _drain_output_queue(output_queue, handle, mirror_output=mirror_output)
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
                _drain_output_queue(output_queue, handle, mirror_output=mirror_output)
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
        f"duration={duration_seconds:.3f}s",
        flush=True,
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


@dataclass
class WindowsParallelDbTunnel:
    env_overrides: dict[str, str]
    process: subprocess.Popen[str] | None = None
    owns_process: bool = False

    def close(self) -> None:
        if not self.owns_process or self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def _is_tcp_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _windows_parallel_db_tunnel_settings() -> tuple[str, int, str, str, str]:
    host = os.getenv("PC_CLIENT_TEST_DB_TUNNEL_HOST", "127.0.0.1")
    port = int(os.getenv("PC_CLIENT_TEST_DB_TUNNEL_PORT", "55432"))
    target = os.getenv("PC_CLIENT_TEST_DB_SSH_TARGET", "altserver@192.168.100.17")
    remote_bind = os.getenv("PC_CLIENT_TEST_DB_REMOTE_BIND", "127.0.0.1:5432")
    ssh_key = os.getenv(
        "PC_CLIENT_TEST_DB_SSH_KEY",
        r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519",
    )
    return host, port, target, remote_bind, ssh_key


def _windows_parallel_db_admin_url(host: str, port: int) -> str:
    return f"postgresql+asyncpg://chatbot:chatbot@{host}:{port}/postgres"


def _prepare_windows_parallel_db_tunnel() -> WindowsParallelDbTunnel:
    if os.name != "nt":
        return WindowsParallelDbTunnel(env_overrides={})

    if os.getenv("TEST_DATABASE_ADMIN_URL"):
        print("[ci-db-tunnel] using explicit TEST_DATABASE_ADMIN_URL", flush=True)
        return WindowsParallelDbTunnel(env_overrides={})

    host, port, target, remote_bind, ssh_key = _windows_parallel_db_tunnel_settings()
    admin_url = _windows_parallel_db_admin_url(host, port)
    if _is_tcp_port_open(host, port):
        print(f"[ci-db-tunnel] using existing tunnel {host}:{port}", flush=True)
        return WindowsParallelDbTunnel(
            env_overrides={
                "TEST_DATABASE_ADMIN_URL": admin_url,
                "PC_CLIENT_TEST_DB_TUNNEL_PARENT_OWNED": "existing",
            }
        )

    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-i",
        ssh_key,
        "-L",
        f"{port}:{remote_bind}",
        target,
        "-N",
    ]
    print(
        f"[ci-db-tunnel] starting parent-owned tunnel {host}:{port} -> {target} {remote_bind}",
        flush=True,
    )
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if _is_tcp_port_open(host, port):
            print(f"[ci-db-tunnel] parent-owned tunnel ready {host}:{port}", flush=True)
            return WindowsParallelDbTunnel(
                env_overrides={
                    "TEST_DATABASE_ADMIN_URL": admin_url,
                    "PC_CLIENT_TEST_DB_TUNNEL_PARENT_OWNED": "1",
                },
                process=proc,
                owns_process=True,
            )
        if proc.poll() is not None:
            stderr = (proc.stderr.read() if proc.stderr else "").strip()
            raise RuntimeError(
                "Failed to start parent-owned Windows test DB SSH tunnel: "
                f"{stderr or proc.returncode}"
            )
        time.sleep(0.2)

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    raise RuntimeError("Timed out waiting for parent-owned Windows test DB SSH tunnel to open")


def _is_server_db_ws_parallel_layer(step_name: str) -> bool:
    return step_name in SERVER_DB_WS_PARALLEL_LAYER_ORDER


def _merge_step_env(step: Step, env_overrides: dict[str, str]) -> Step:
    step_name, command, log_path, timeout_seconds, idle_timeout_seconds, step_env = step
    if not env_overrides:
        return step
    merged_env = dict(step_env or {})
    merged_env.update(env_overrides)
    return step_name, command, log_path, timeout_seconds, idle_timeout_seconds, merged_env


def _split_steps_for_parallel(steps: list[Step]) -> tuple[list[Step], list[Step], list[Step]]:
    db_steps = [step for step in steps if _is_server_db_ws_parallel_layer(step[0])]
    if not db_steps:
        return steps, [], []

    db_names = {step[0] for step in db_steps}
    first_idx = next(index for index, step in enumerate(steps) if step[0] in db_names)
    last_idx = max(index for index, step in enumerate(steps) if step[0] in db_names)
    before = [step for step in steps[:first_idx] if step[0] not in db_names]
    after = [step for step in steps[last_idx + 1 :] if step[0] not in db_names]
    by_name = {step[0]: step for step in db_steps}
    ordered_db_steps = [by_name[name] for name in SERVER_DB_WS_PARALLEL_LAYER_ORDER if name in by_name]
    return before, ordered_db_steps, after


def _parallel_measurement_decision(measurements_path: Path, *, requested_max_workers: int) -> dict[str, object]:
    try:
        payload = json.loads(measurements_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(measurements_path),
            "budget_status": "unreadable",
            "recommended_max_workers": 1,
            "effective_max_workers": 1,
            "reason": f"fixture timing measurements could not be read: {type(exc).__name__}",
            "violation_count": 0,
        }
    budget_status = str(payload.get("budget_status") or "unknown")
    budget_violations = payload.get("budget_violations")
    violation_count = len(budget_violations) if isinstance(budget_violations, list) else 0
    if budget_status == "fail":
        recommended_max_workers = 1
        reason = "fixture timing budget failed; run DB/WS layers sequentially until timings recover"
    elif budget_status == "pass":
        recommended_max_workers = 2
        reason = "fixture timing budget passed; bounded DB/WS parallelism allowed"
    else:
        recommended_max_workers = 2
        reason = f"fixture timing budget status is {budget_status}; use conservative parallelism"
    return {
        "path": str(measurements_path),
        "budget_status": budget_status,
        "recommended_max_workers": recommended_max_workers,
        "effective_max_workers": min(requested_max_workers, recommended_max_workers),
        "reason": reason,
        "violation_count": violation_count,
    }


def _resolve_workspace_path(workspace: Path, path: Path) -> Path:
    return path if path.is_absolute() else workspace / path


def _load_flaky_registry(registry_path: Path) -> tuple[list[dict[str, object]], str | None]:
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return [], None
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return [], "flaky registry must contain an entries list"
    normalized = [entry for entry in entries if isinstance(entry, dict)]
    if len(normalized) != len(entries):
        return [], "flaky registry entries must be objects"
    return normalized, None


def _first_error_message(result: dict[str, object]) -> str | None:
    errors = result.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0]
    if isinstance(first, dict):
        message = first.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    if isinstance(first, str) and first.strip():
        return first.strip()
    return None


def _result_artifacts(results: list[dict[str, object]]) -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for result in results:
        attachments = result.get("attachments")
        if not isinstance(attachments, list):
            continue
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            path = attachment.get("path")
            if not isinstance(path, str) or not path:
                continue
            artifacts.append(
                {
                    "name": str(attachment.get("name") or ""),
                    "path": path,
                    "content_type": str(attachment.get("contentType") or attachment.get("content_type") or ""),
                }
            )
    return artifacts


def _playwright_retry_records(layer_name: str, report_path: Path) -> tuple[list[dict[str, object]], str | None]:
    if not report_path.exists():
        return [], None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"{type(exc).__name__}: {exc}"

    records: list[dict[str, object]] = []

    def walk_suites(suites: object, inherited_file: str | None = None) -> None:
        if not isinstance(suites, list):
            return
        for suite in suites:
            if not isinstance(suite, dict):
                continue
            suite_file = suite.get("file") if isinstance(suite.get("file"), str) else inherited_file
            specs = suite.get("specs")
            if isinstance(specs, list):
                for spec in specs:
                    if not isinstance(spec, dict):
                        continue
                    spec_file = spec.get("file") if isinstance(spec.get("file"), str) else suite_file
                    if not spec_file:
                        spec_file = "unknown"
                    spec_title = str(spec.get("title") or "<untitled>")
                    tests = spec.get("tests")
                    if not isinstance(tests, list):
                        continue
                    for test in tests:
                        if not isinstance(test, dict):
                            continue
                        raw_results = test.get("results")
                        if not isinstance(raw_results, list) or len(raw_results) < 2:
                            continue
                        results = [result for result in raw_results if isinstance(result, dict)]
                        if len(results) < 2:
                            continue
                        final_status = str(results[-1].get("status") or "")
                        previous_results = results[:-1]
                        previous_failure = next(
                            (
                                result
                                for result in previous_results
                                if str(result.get("status") or "") not in {"passed", "skipped"}
                            ),
                            None,
                        )
                        if final_status != "passed" or previous_failure is None:
                            continue
                        project = str(test.get("projectName") or "").strip()
                        node_id = f"{spec_file}::{spec_title}"
                        if project:
                            node_id = f"{node_id} [{project}]"
                        records.append(
                            {
                                "layer": layer_name,
                                "node_id": node_id,
                                "file": spec_file,
                                "line": spec.get("line"),
                                "project": project or None,
                                "classification": "passed_after_retry",
                                "attempt_count": len(results),
                                "first_attempt_status": str(results[0].get("status") or ""),
                                "final_attempt_status": final_status,
                                "first_worker_index": results[0].get("workerIndex"),
                                "final_worker_index": results[-1].get("workerIndex"),
                                "seed": os.getenv("PLAYWRIGHT_RANDOM_SEED") or os.getenv("PYTEST_RANDOMLY_SEED"),
                                "previous_error": _first_error_message(previous_failure),
                                "artifacts": _result_artifacts(previous_results),
                            }
                        )
            walk_suites(suite.get("suites"), suite_file)

    walk_suites(payload.get("suites") if isinstance(payload, dict) else None)
    return records, None


def _flaky_registry_match(
    record: dict[str, object],
    entries: list[dict[str, object]],
) -> dict[str, object] | None:
    record_layer = str(record.get("layer") or "")
    record_node_id = str(record.get("node_id") or "")
    today = datetime.now(timezone.utc).date().isoformat()
    for entry in entries:
        entry_layer = str(entry.get("layer") or "*")
        if entry_layer not in {"*", record_layer}:
            continue
        pattern = str(entry.get("node_id") or "*")
        if not fnmatch.fnmatch(record_node_id, pattern):
            continue
        expires = str(entry.get("expires") or "")
        if expires and expires < today:
            continue
        return {
            "id": str(entry.get("id") or ""),
            "owner": str(entry.get("owner") or ""),
            "reason": str(entry.get("reason") or ""),
            "expires": expires or None,
        }
    return None


def _build_flaky_summary(
    *,
    registry_path: Path,
    report_paths: dict[str, Path],
) -> dict[str, object]:
    registry_entries, registry_error = _load_flaky_registry(registry_path)
    records: list[dict[str, object]] = []
    report_errors: dict[str, str] = {}
    missing_reports: list[str] = []
    for layer_name, report_path in report_paths.items():
        if not report_path.exists():
            missing_reports.append(layer_name)
            continue
        layer_records, report_error = _playwright_retry_records(layer_name, report_path)
        records.extend(layer_records)
        if report_error:
            report_errors[layer_name] = report_error

    allowed_records: list[dict[str, object]] = []
    unknown_records: list[dict[str, object]] = []
    for record in records:
        registry_match = _flaky_registry_match(record, registry_entries)
        if registry_match:
            record["registry_match"] = registry_match
            allowed_records.append(record)
        else:
            unknown_records.append(record)

    status = "pass"
    if registry_error or report_errors or unknown_records:
        status = "fail"

    return {
        "schema": "pc_client.flaky_summary.v1",
        "registry_path": str(registry_path),
        "reports": {layer_name: str(path) for layer_name, path in report_paths.items()},
        "status": status,
        "clean_green": not records,
        "records": records,
        "allowed_records": allowed_records,
        "unknown_records": unknown_records,
        "missing_reports": missing_reports,
        "report_errors": report_errors,
        "registry_error": registry_error,
    }


def _run_step(step: Step, *, workspace: Path, mirror_output: bool) -> dict[str, object]:
    step_name, command, log_path, timeout_seconds, idle_timeout_seconds, env_overrides = step
    return run_and_capture(
        command,
        cwd=workspace,
        log_path=log_path,
        step_name=step_name,
        timeout_seconds=timeout_seconds,
        idle_timeout_seconds=idle_timeout_seconds,
        env_overrides=env_overrides,
        mirror_output=mirror_output,
    )


def _run_parallel_steps(
    steps: list[Step],
    *,
    workspace: Path,
    max_workers: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    group_started_at = now_iso()
    group_started_monotonic = time.monotonic()
    layer_names = [step[0] for step in steps]
    print(
        "[ci] parallel group server-db started "
        f"max_workers={max_workers} layers={','.join(layer_names)}",
        flush=True,
    )
    results_by_name: dict[str, dict[str, object]] = {}
    skipped_layers: list[str] = []
    active: dict[concurrent.futures.Future[dict[str, object]], str] = {}
    next_index = 0
    failure_seen = False

    def submit_next(executor: concurrent.futures.ThreadPoolExecutor) -> None:
        nonlocal next_index
        if next_index >= len(steps):
            return
        step = steps[next_index]
        next_index += 1
        future = executor.submit(_run_step, step, workspace=workspace, mirror_output=False)
        active[future] = step[0]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for _ in range(min(max_workers, len(steps))):
            submit_next(executor)

        while active:
            done, _pending = concurrent.futures.wait(
                active,
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                step_name = active.pop(future)
                result = future.result()
                results_by_name[step_name] = result
                if result["returncode"] != 0:
                    failure_seen = True

            while not failure_seen and len(active) < max_workers and next_index < len(steps):
                submit_next(executor)

        if failure_seen and next_index < len(steps):
            skipped_layers = [step[0] for step in steps[next_index:]]

    status = "red" if any(result["returncode"] != 0 for result in results_by_name.values()) else "green"
    group_finished_at = now_iso()
    duration_seconds = round(time.monotonic() - group_started_monotonic, 3)
    print(
        "[ci] parallel group server-db finished "
        f"status={status} duration={duration_seconds:.3f}s skipped={','.join(skipped_layers) or 'none'}",
        flush=True,
    )
    metadata = {
        "name": "server-db",
        "layers": layer_names,
        "max_workers": max_workers,
        "started_at": group_started_at,
        "finished_at": group_finished_at,
        "duration_seconds": duration_seconds,
        "status": status,
        "skipped_layers": skipped_layers,
    }
    ordered_results = [results_by_name[step[0]] for step in steps if step[0] in results_by_name]
    return ordered_results, metadata


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
    timing_path: Path | None = None,
    use_template: bool = True,
) -> dict[str, str]:
    env = {"PC_CLIENT_PYTEST_WATCHDOG_SECONDS": str(DEFAULT_PYTEST_WATCHDOG_SECONDS)}
    if timing_path is not None:
        env["PC_CLIENT_TEST_TIMING"] = "1"
        env["PC_CLIENT_TEST_TIMING_PATH"] = str(timing_path)
    if layer_name and layer_name != "server_pytest_no_db":
        env["PC_CLIENT_TEST_DB_TEMPLATE"] = "1" if use_template else "0"
        if use_template:
            env["PC_CLIENT_TEST_DB_TEMPLATE_KEEP"] = "1"
        env["PC_CLIENT_TEST_DB_DOMAIN"] = _test_db_domain_for_layer(layer_name)
        if commit:
            env["PC_CLIENT_TEST_DB_RUN_ID"] = commit[:12]
        if keep_test_db:
            env["PC_CLIENT_KEEP_TEST_DB"] = "1"
    return env


def _server_fixture_timing_path(artifact_dir: Path, layer_name: str) -> Path:
    return artifact_dir / "fixture-timings" / f"{layer_name}.jsonl"


def _junit_artifacts(artifact_dir: Path, workspace: Path) -> dict[str, object]:
    return {
        "scripts_pytest_no_db": str(artifact_dir / "junit-scripts-no-db.xml"),
        "server_pytest_no_db": str(artifact_dir / "junit-server-no-db.xml"),
        "migration_schema": str(artifact_dir / "junit-migration-schema.xml"),
        "server_pytest_db_api_layers": {
            layer_name: str(
                artifact_dir / f"{layer_name.replace('server_pytest_', 'junit-server-').replace('_', '-')}.xml"
            )
            for layer_name, _paths in _server_db_api_layer_paths(workspace)
        },
        "server_pytest_agent_ws": str(artifact_dir / "junit-server-agent-ws.xml"),
        "pc_agent_pytest": str(artifact_dir / "junit-pc-agent.xml"),
    }


def _duration_baseline(junit_path: str, slowest_count: int) -> dict[str, object]:
    return {"pytest_durations": slowest_count, "junit": junit_path}


def _baseline_artifacts(
    *,
    junit_artifacts: dict[str, object],
    fixture_timings_dir: Path,
    fixture_timings_summary_path: Path,
) -> dict[str, object]:
    db_api_junit = junit_artifacts["server_pytest_db_api_layers"]
    return {
        "junit": junit_artifacts,
        "durations": {
            "scripts_pytest_no_db": _duration_baseline(str(junit_artifacts["scripts_pytest_no_db"]), 40),
            "server_pytest_no_db": _duration_baseline(str(junit_artifacts["server_pytest_no_db"]), 80),
            "migration_schema": _duration_baseline(str(junit_artifacts["migration_schema"]), 80),
            "server_pytest_db_api_layers": {
                layer_name: _duration_baseline(str(junit_path), 80) for layer_name, junit_path in db_api_junit.items()
            },
            "server_pytest_agent_ws": _duration_baseline(str(junit_artifacts["server_pytest_agent_ws"]), 80),
            "pc_agent_pytest": _duration_baseline(str(junit_artifacts["pc_agent_pytest"]), 80),
            "fixture_timings_dir": str(fixture_timings_dir),
            "fixture_timings_summary": str(fixture_timings_summary_path),
        },
        "retries": {
            "webapp_fixture_e2e": {
                "ci_retries": 1,
                "local_retries": 0,
                "trace": "on-first-retry",
                "first_attempt_failures_are_flaky": True,
                "passed_after_retry_status": "flaky",
            }
        },
    }


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


def _scripts_pytest_paths(workspace: Path) -> list[Path]:
    scripts_dir = workspace / "scripts"
    paths = sorted(path.relative_to(workspace) for path in scripts_dir.glob("test_*.py"))
    return paths or [Path("scripts")]


def _scripts_pytest_no_db_command(workspace: Path, junit_path: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        *[str(path) for path in _scripts_pytest_paths(workspace)],
        "-m",
        "not manual",
        "-vv",
        "--durations=40",
        "--junitxml",
        str(junit_path),
    ]


def _test_inventory_audit_command(workspace: Path) -> list[str]:
    return [
        sys.executable,
        str(workspace / "scripts" / "audit_test_inventory.py"),
        "--workspace",
        str(workspace),
        "--strict",
    ]


def _db_cleanup_profile_audit_command(workspace: Path) -> list[str]:
    return [
        sys.executable,
        str(workspace / "scripts" / "audit_db_cleanup_profiles.py"),
        "--tests-dir",
        str(workspace / "server" / "tests"),
        "--strict",
    ]


def _migration_schema_command(workspace: Path, junit_path: Path) -> list[str]:
    return _server_pytest_command(
        "not manual and not no_db and not agent_ws",
        junit_path,
        [MIGRATION_SCHEMA_TEST_PATH],
    )


def _classify_server_db_api_test_file(filename: str) -> str:
    if filename == MIGRATION_SCHEMA_TEST_PATH.name:
        return "migration_schema"
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
        if path.name == MIGRATION_SCHEMA_TEST_PATH.name:
            continue
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
                _server_pytest_env(
                    layer_name=layer_name,
                    commit=commit,
                    keep_test_db=keep_test_db,
                    timing_path=_server_fixture_timing_path(artifact_dir, layer_name),
                ),
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


def _resolve_command(name: str) -> str:
    candidates = [name]
    if os.name == "nt":
        candidates = [f"{name}.cmd", f"{name}.exe", name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return name


def _pnpm_webapp_command(workspace: Path, *args: str) -> list[str]:
    return [_resolve_command("pnpm"), "--dir", str(workspace / "webapp"), *args]


def _webapp_unit_test_command(workspace: Path) -> list[str]:
    # Keep the release gate deterministic on Windows: the default fork pool can
    # exhaust process memory and leave later route tests in a corrupted jsdom run.
    return _pnpm_webapp_command(workspace, "exec", "vitest", "run", "--pool=threads", "--maxWorkers=1")


def _webapp_fixture_e2e_command(workspace: Path) -> list[str]:
    return _pnpm_webapp_command(workspace, "exec", "playwright", "test", "--reporter=list,json")


def main() -> None:
    args = parse_args()
    max_workers = args.max_workers if args.max_workers is not None else (2 if args.parallel else 1)
    if max_workers < 1:
        raise SystemExit("--max-workers must be >= 1")
    parallel_measurement_decision: dict[str, object] | None = None
    if args.parallel and args.parallel_measurements:
        parallel_measurement_decision = _parallel_measurement_decision(
            args.parallel_measurements,
            requested_max_workers=max_workers,
        )
        max_workers = int(parallel_measurement_decision["effective_max_workers"])
    parallel_warning: str | None = None
    if args.parallel and max_workers > 3:
        parallel_warning = (
            f"--max-workers {max_workers} is allowed but risky for remote PostgreSQL/SSH tunnel load; "
            "start with --max-workers 2 unless the environment has been proven stable."
        )
        print(f"[ci] warning: {parallel_warning}", file=sys.stderr, flush=True)

    commit = detect_commit(args.workspace, args.commit)
    summary_path = summary_path_for_commit(args.workspace, commit)
    artifact_dir = summary_path.parent
    logs_dir = artifact_dir / "logs"
    fixture_timings_dir = artifact_dir / "fixture-timings"
    fixture_timings_summary_path = artifact_dir / "fixture-timings-summary.json"
    webapp_fixture_e2e_report = artifact_dir / "playwright-webapp-fixture-e2e.json"
    webapp_bundle_dir = webapp_bundle_dir_for_commit(args.workspace, commit)
    webapp_bundle_archive = webapp_bundle_archive_for_commit(args.workspace, commit)
    flaky_registry_path = _resolve_workspace_path(args.workspace, args.flaky_registry)
    started_at = now_iso()

    steps: list[Step] = [
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
            "webapp_unit_tests",
            _webapp_unit_test_command(args.workspace),
            logs_dir / "webapp_unit_tests.log",
            float(DEFAULT_WEB_TEST_TIMEOUT_SECONDS),
            float(args.idle_timeout),
            {"CI": "1"},
        ),
        (
            "webapp_fixture_e2e",
            _webapp_fixture_e2e_command(args.workspace),
            logs_dir / "webapp_fixture_e2e.log",
            float(DEFAULT_WEB_TEST_TIMEOUT_SECONDS),
            float(args.idle_timeout),
            {"CI": "1", "PLAYWRIGHT_JSON_OUTPUT_NAME": str(webapp_fixture_e2e_report)},
        ),
        (
            "test_inventory_audit",
            _test_inventory_audit_command(args.workspace),
            logs_dir / "test_inventory_audit.log",
            float(args.server_pytest_timeout),
            float(args.idle_timeout),
            None,
        ),
        (
            "db_cleanup_profile_audit",
            _db_cleanup_profile_audit_command(args.workspace),
            logs_dir / "db_cleanup_profile_audit.log",
            float(args.server_pytest_timeout),
            float(args.idle_timeout),
            None,
        ),
        (
            "scripts_pytest_no_db",
            _scripts_pytest_no_db_command(args.workspace, artifact_dir / "junit-scripts-no-db.xml"),
            logs_dir / "scripts_pytest_no_db.log",
            float(args.server_pytest_timeout),
            float(args.idle_timeout),
            None,
        ),
        (
            "server_pytest_no_db",
            _server_pytest_command("not manual and no_db", artifact_dir / "junit-server-no-db.xml"),
            logs_dir / "server_pytest_no_db.log",
            float(args.server_pytest_timeout),
            float(args.idle_timeout),
            _server_pytest_env(
                layer_name="server_pytest_no_db",
                commit=commit,
                keep_test_db=args.keep_test_db,
                timing_path=_server_fixture_timing_path(artifact_dir, "server_pytest_no_db"),
            ),
        ),
        (
            "migration_schema",
            _migration_schema_command(args.workspace, artifact_dir / "junit-migration-schema.xml"),
            logs_dir / "migration_schema.log",
            float(args.server_pytest_timeout),
            float(args.idle_timeout),
            _server_pytest_env(
                layer_name="migration_schema",
                commit=commit,
                keep_test_db=args.keep_test_db,
                timing_path=_server_fixture_timing_path(artifact_dir, "migration_schema"),
                use_template=False,
            ),
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
            _server_pytest_env(
                layer_name="server_pytest_agent_ws",
                commit=commit,
                keep_test_db=args.keep_test_db,
                timing_path=_server_fixture_timing_path(artifact_dir, "server_pytest_agent_ws"),
            ),
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
                "-vv",
                "--durations=80",
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
    parallel_groups: list[dict[str, object]] = []
    status = "green"
    runner_error: str | None = None
    fixture_timings_error: str | None = None
    flaky_gate_error: str | None = None
    try:
        if args.parallel:
            before_steps, parallel_steps, after_steps = _split_steps_for_parallel(steps)
        else:
            before_steps, parallel_steps, after_steps = steps, [], []

        if max_workers < 2 or len(parallel_steps) < 2:
            before_steps = steps
            parallel_steps = []
            after_steps = []

        for step in before_steps:
            result = _run_step(step, workspace=args.workspace, mirror_output=True)
            results.append(result)
            if result["returncode"] != 0:
                status = "red"
                break

        if status == "green" and parallel_steps:
            tunnel = _prepare_windows_parallel_db_tunnel()
            try:
                parallel_env = tunnel.env_overrides
                prepared_parallel_steps = [_merge_step_env(step, parallel_env) for step in parallel_steps]
                group_results, group_metadata = _run_parallel_steps(
                    prepared_parallel_steps,
                    workspace=args.workspace,
                    max_workers=max_workers,
                )
                results.extend(group_results)
                parallel_groups.append(group_metadata)
                if group_metadata["status"] != "green":
                    status = "red"
            finally:
                tunnel.close()

        if status == "green":
            for step in after_steps:
                result = _run_step(step, workspace=args.workspace, mirror_output=True)
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
        try:
            summarize_artifact_dir(artifact_dir)
        except Exception as exc:  # pragma: no cover - defensive CI artifact path.
            fixture_timings_error = f"{type(exc).__name__}: {exc}"
            print(f"[ci] fixture timing summary error: {fixture_timings_error}", file=sys.stderr)
        flaky_summary = _build_flaky_summary(
            registry_path=flaky_registry_path,
            report_paths={"webapp_fixture_e2e": webapp_fixture_e2e_report},
        )
        if status == "green" and flaky_summary["status"] != "pass":
            status = "red"
            flaky_gate_error = "Unknown or invalid retry-pass flaky records are present"
            print(f"[ci] flaky gate error: {flaky_gate_error}", file=sys.stderr)
        junit_artifacts = _junit_artifacts(artifact_dir, args.workspace)
        summary = {
            "commit": commit,
            "status": status,
            "started_at": started_at,
            "finished_at": now_iso(),
            "requested_layers": args.layer,
            "available_layers": available_layers,
            "parallel_enabled": bool(args.parallel),
            "max_workers": max_workers,
            "parallel_groups": parallel_groups,
            "evidence_layers": CI_EVIDENCE_LAYERS,
            "baseline_artifacts": _baseline_artifacts(
                junit_artifacts=junit_artifacts,
                fixture_timings_dir=fixture_timings_dir,
                fixture_timings_summary_path=fixture_timings_summary_path,
            ),
            "artifacts": {
                "summary": str(summary_path),
                "fixture_timings_dir": str(fixture_timings_dir),
                "fixture_timings_summary": str(fixture_timings_summary_path),
                "webapp_bundle_dir": str(webapp_bundle_dir),
                "webapp_bundle_archive": str(webapp_bundle_archive),
                "webapp_fixture_e2e_report": str(webapp_fixture_e2e_report),
                "junit_scripts_no_db": junit_artifacts["scripts_pytest_no_db"],
                "junit_server_no_db": junit_artifacts["server_pytest_no_db"],
                "junit_server_db_api_layers": junit_artifacts["server_pytest_db_api_layers"],
                "junit_server_agent_ws": junit_artifacts["server_pytest_agent_ws"],
                "junit_pc_agent": junit_artifacts["pc_agent_pytest"],
            },
            "flaky_summary": flaky_summary,
            "steps": results,
        }
        if runner_error:
            summary["runner_error"] = runner_error
        if parallel_warning:
            summary["parallel_warning"] = parallel_warning
        if parallel_measurement_decision:
            summary["parallel_measurement_decision"] = parallel_measurement_decision
        if fixture_timings_error:
            summary["fixture_timings_error"] = fixture_timings_error
        if flaky_gate_error:
            summary["flaky_gate_error"] = flaky_gate_error
        write_summary(summary_path, summary)

    if status != "green":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
