#!/usr/bin/env python3
"""Run the canonical self-hosted CI suite and store artifacts under artifacts/ci/<sha>/."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.ci_artifacts import DEFAULT_WORKSPACE, detect_commit, summary_path_for_commit
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import DEFAULT_WORKSPACE, detect_commit, summary_path_for_commit


DEFAULT_VERIFY_TIMEOUT_SECONDS = 10 * 60
DEFAULT_SERVER_PYTEST_TIMEOUT_SECONDS = 30 * 60
DEFAULT_PC_AGENT_PYTEST_TIMEOUT_SECONDS = 30 * 60
STEP_TIMEOUT_EXIT_CODE = 124


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--commit")
    parser.add_argument("--verify-timeout", type=float, default=DEFAULT_VERIFY_TIMEOUT_SECONDS)
    parser.add_argument("--server-pytest-timeout", type=float, default=DEFAULT_SERVER_PYTEST_TIMEOUT_SECONDS)
    parser.add_argument("--pc-agent-pytest-timeout", type=float, default=DEFAULT_PC_AGENT_PYTEST_TIMEOUT_SECONDS)
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
        )
    else:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_and_capture(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    step_name: str,
    timeout_seconds: float,
) -> dict[str, object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = now_iso()
    started_monotonic = time.monotonic()
    print(
        f"[ci] step={step_name} started timeout={timeout_seconds:.1f}s "
        f"log={log_path}"
    )
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write(f"[ci] step={step_name}\n")
        handle.write(f"[ci] started_at={started_at}\n")
        handle.write(f"[ci] cwd={cwd}\n")
        handle.write(f"[ci] timeout_seconds={timeout_seconds:.1f}\n")
        handle.write(f"[ci] command={_command_text(command)}\n\n")
        handle.flush()

        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        timed_out = False
        output = ""
        try:
            stdout_data, _ = process.communicate(timeout=timeout_seconds)
            output = stdout_data or ""
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            output = exc.stdout or ""
            if output:
                handle.write(output)
                if not output.endswith("\n"):
                    handle.write("\n")
            handle.write(
                f"[ci] step timed out after {timeout_seconds:.1f}s; "
                f"terminating pid={process.pid}\n"
            )
            handle.flush()
            _terminate_process_tree(process)
        else:
            if output:
                handle.write(output)

        duration_seconds = round(time.monotonic() - started_monotonic, 3)
        returncode = STEP_TIMEOUT_EXIT_CODE if timed_out else int(process.returncode or 0)
        finished_at = now_iso()
        handle.write("\n")
        handle.write(
            f"[ci] finished_at={finished_at} returncode={returncode} "
            f"timed_out={timed_out} duration_seconds={duration_seconds}\n"
        )
        handle.flush()

    print(
        f"[ci] step={step_name} finished returncode={returncode} "
        f"timed_out={timed_out} duration={duration_seconds:.3f}s"
    )
    return {
        "name": step_name,
        "command": command,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "returncode": returncode,
        "log": str(log_path),
    }


def write_summary(summary_path: Path, summary: dict[str, object]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    args = parse_args()
    commit = detect_commit(args.workspace, args.commit)
    summary_path = summary_path_for_commit(args.workspace, commit)
    artifact_dir = summary_path.parent
    logs_dir = artifact_dir / "logs"
    started_at = now_iso()

    steps = [
        (
            "verify_workspace",
            [sys.executable, str(args.workspace / "scripts" / "verify_workspace.py")],
            logs_dir / "verify_workspace.log",
            float(args.verify_timeout),
        ),
        (
            "server_pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "server/tests",
                "-m",
                "not manual",
                "--junitxml",
                str(artifact_dir / "junit-server.xml"),
            ],
            logs_dir / "server_pytest.log",
            float(args.server_pytest_timeout),
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
        ),
    ]

    results: list[dict[str, object]] = []
    status = "green"
    runner_error: str | None = None
    try:
        for step_name, command, log_path, timeout_seconds in steps:
            result = run_and_capture(
                command,
                cwd=args.workspace,
                log_path=log_path,
                step_name=step_name,
                timeout_seconds=timeout_seconds,
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
            "steps": results,
        }
        if runner_error:
            summary["runner_error"] = runner_error
        write_summary(summary_path, summary)

    if status != "green":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
