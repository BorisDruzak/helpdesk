#!/usr/bin/env python3
"""Run the standard verified server deploy flow to the Linux host."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    from scripts.ci_artifacts import (
        detect_commit,
        require_green_ci_artifact,
        require_webapp_bundle_artifact,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import (
        detect_commit,
        require_green_ci_artifact,
        require_webapp_bundle_artifact,
    )

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
DEFAULT_SMOKE_ATTEMPTS = 10
DEFAULT_SMOKE_DELAY_SECONDS = 2.0
DEFAULT_KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")
DEFAULT_SCP = Path(r"C:\Windows\System32\OpenSSH\scp.exe")
DEFAULT_REMOTE_WORKTREE = "/var/chat_bot/pc_client"


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
        "--skip-ci-check",
        action="store_true",
        help="Skip the green CI artifact requirement for the target commit.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip remote smoke check after starting the server.",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip remote Alembic migrations after deploy.",
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


def prepare_webapp_bundle_archive(
    workspace: Path,
    commit: str,
    *,
    skip_ci_check: bool,
) -> Path:
    if not skip_ci_check:
        return require_webapp_bundle_artifact(workspace, commit)

    with tempfile.TemporaryDirectory(prefix="pc_client_release_webapp_") as _temp_root:
        temp_root = Path(_temp_root)
        archive_path = temp_root / "webapp-dist.tar.gz"
        output_dir = temp_root / "webapp-dist"
        run_step(
            [
                sys.executable,
                str(workspace / "scripts" / "build_webapp_bundle.py"),
                "--workspace",
                str(workspace),
                "--output-dir",
                str(output_dir),
                "--archive",
                str(archive_path),
            ],
            cwd=workspace,
            label="build-webapp",
        )
        persistent_archive = workspace / "artifacts" / "release_temp" / commit / "webapp-dist.tar.gz"
        persistent_archive.parent.mkdir(parents=True, exist_ok=True)
        persistent_archive.write_bytes(archive_path.read_bytes())
        return persistent_archive


def _scp_binary() -> str:
    return str(DEFAULT_SCP if DEFAULT_SCP.exists() else "scp")


def _ssh_binary() -> str:
    return "ssh"


def _remote_command(remote_worktree: str, remote_archive: str) -> str:
    safe_worktree = shlex.quote(remote_worktree)
    safe_archive = shlex.quote(remote_archive)
    return (
        f"mkdir -p {safe_worktree}/webapp && "
        f"rm -rf {safe_worktree}/webapp/dist && "
        f"tar -xzf {safe_archive} -C {safe_worktree}/webapp && "
        f"rm -f {safe_archive}"
    )


def upload_webapp_bundle(
    archive_path: Path,
    *,
    cwd: Path,
    remote: str,
    remote_worktree: str,
) -> None:
    remote_archive = f"/tmp/{archive_path.name}"
    scp_command = [_scp_binary()]
    ssh_command = [_ssh_binary()]
    if DEFAULT_KEY.exists():
        scp_command.extend(["-i", str(DEFAULT_KEY)])
        ssh_command.extend(["-i", str(DEFAULT_KEY)])

    scp_command.extend([str(archive_path), f"{remote}:{remote_archive}"])
    run_step(scp_command, cwd=cwd, label="upload-webapp-copy")

    ssh_command.extend([remote, _remote_command(remote_worktree, remote_archive)])
    run_step(ssh_command, cwd=cwd, label="upload-webapp-unpack")


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
    bundle_archive: Path | None = None

    try:
        commit = detect_commit(workspace)
        if not args.skip_ci_check:
            summary_path = require_green_ci_artifact(workspace, commit)
            print(f"[ci] using green artifact {summary_path}")

        if not args.skip_verify:
            run_step(
                [sys.executable, str(workspace / "scripts" / "verify_workspace.py")],
                cwd=workspace,
                label="verify",
            )

        bundle_archive = prepare_webapp_bundle_archive(
            workspace,
            commit,
            skip_ci_check=args.skip_ci_check,
        )

        deploy_command = [sys.executable, str(workspace / "scripts" / "deploy_workspace_to_remote.py")]
        if args.branch:
            deploy_command.extend(["--branch", args.branch])
        if args.allow_local_dirty:
            deploy_command.append("--allow-local-dirty")
        if args.skip_ci_check:
            deploy_command.append("--skip-ci-check")
        run_step(deploy_command, cwd=workspace, label="deploy")
        if not args.skip_migrations:
            run_step(
                [
                    sys.executable,
                    str(workspace / "scripts" / "run_remote_migrations.py"),
                    "--remote",
                    args.remote,
                    "upgrade",
                    "head",
                ],
                cwd=workspace,
                label="migrate",
            )
        assert bundle_archive is not None
        upload_webapp_bundle(
            bundle_archive,
            cwd=workspace,
            remote=args.remote,
            remote_worktree=DEFAULT_REMOTE_WORKTREE,
        )

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
