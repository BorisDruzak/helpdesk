#!/usr/bin/env python3
"""Run the standard verified server deploy flow to the Linux host."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
DEFAULT_SMOKE_ATTEMPTS = 10
DEFAULT_SMOKE_DELAY_SECONDS = 2.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--branch")
    parser.add_argument("--remote", default="altserver@192.168.100.17")
    parser.add_argument(
        "--allow-local-dirty",
        action="store_true",
        help=(
            "Deploy only the last committed Git revision even if the local workspace has "
            "uncommitted changes. Those local changes stay only on Windows."
        ),
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip local workspace verification before deploy.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip remote smoke check after starting the server.",
    )
    parser.add_argument(
        "--leave-running",
        action="store_true",
        help="Leave the remote server running after the flow completes.",
    )
    parser.add_argument(
        "--smoke-attempts",
        type=int,
        default=DEFAULT_SMOKE_ATTEMPTS,
        help="How many times to retry remote smoke before failing.",
    )
    parser.add_argument(
        "--smoke-delay",
        type=float,
        default=DEFAULT_SMOKE_DELAY_SECONDS,
        help="Seconds to wait between remote smoke retries.",
    )
    return parser.parse_args()


def run_step(command: list[str], *, cwd: Path, label: str) -> None:
    print(f"[{label}] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def run_smoke_with_retries(
    command: list[str],
    *,
    cwd: Path,
    attempts: int,
    delay_seconds: float,
) -> None:
    if attempts < 1:
        raise ValueError("smoke attempts must be at least 1")

    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, attempts + 1):
        label = f"smoke {attempt}/{attempts}"
        print(f"[{label}] {' '.join(command)}")
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.returncode == 0:
            if completed.stderr.strip():
                print(completed.stderr.strip())
            return

        last_error = subprocess.CalledProcessError(
            returncode=completed.returncode,
            cmd=command,
            output=completed.stdout,
            stderr=completed.stderr,
        )
        if attempt == attempts:
            break
        print(f"Smoke attempt {attempt}/{attempts} failed; waiting {delay_seconds:.1f}s before retry.")
        time.sleep(delay_seconds)
    assert last_error is not None
    if last_error.stderr and last_error.stderr.strip():
        print(last_error.stderr.strip(), file=sys.stderr)
    raise last_error


def main() -> None:
    args = parse_args()
    workspace = args.workspace
    started_server = False

    try:
        if not args.skip_verify:
            run_step(
                [sys.executable, str(workspace / "scripts" / "verify_workspace.py")],
                cwd=workspace,
                label="verify",
            )

        deploy_command = [sys.executable, str(workspace / "scripts" / "deploy_workspace_to_remote.py")]
        if args.branch:
            deploy_command.extend(["--branch", args.branch])
        if args.allow_local_dirty:
            deploy_command.append("--allow-local-dirty")
        run_step(deploy_command, cwd=workspace, label="deploy")

        remote_command_base = [
            sys.executable,
            str(workspace / "scripts" / "manage_remote_stack.py"),
            "--remote",
            args.remote,
        ]
        run_step([*remote_command_base, "start", "control"], cwd=workspace, label="start-control")
        run_step([*remote_command_base, "start", "server"], cwd=workspace, label="start")
        started_server = True

        if not args.skip_smoke:
            run_smoke_with_retries(
                [*remote_command_base, "smoke", "server"],
                cwd=workspace,
                attempts=args.smoke_attempts,
                delay_seconds=args.smoke_delay,
            )

    finally:
        if started_server and not args.leave_running:
            try:
                run_step(
                    [
                        sys.executable,
                        str(workspace / "scripts" / "manage_remote_stack.py"),
                        "--remote",
                        args.remote,
                        "stop",
                        "server",
                    ],
                    cwd=workspace,
                    label="stop",
                )
            except subprocess.CalledProcessError:
                print("WARNING: failed to stop the remote server cleanly.", file=sys.stderr)
                raise

    print("Remote server release flow completed successfully.")


if __name__ == "__main__":
    main()
