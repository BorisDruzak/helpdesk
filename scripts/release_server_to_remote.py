#!/usr/bin/env python3
"""Run the standard verified server deploy flow to the Linux host."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.ci_artifacts import (
        detect_commit,
        require_green_ci_artifact,
        require_live_release_summary,
        require_webapp_bundle_artifact,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import (
        detect_commit,
        require_green_ci_artifact,
        require_live_release_summary,
        require_webapp_bundle_artifact,
    )

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
DEFAULT_SMOKE_ATTEMPTS = 10
DEFAULT_SMOKE_DELAY_SECONDS = 2.0
DEFAULT_KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")
DEFAULT_SCP = Path(r"C:\Windows\System32\OpenSSH\scp.exe")
DEFAULT_REMOTE_WORKTREE = "/var/chat_bot/pc_client"


def _env_value(name: str, default: str) -> str:
    return str(os.environ.get(name) or default).strip() or default


def _default_remote() -> str:
    return _env_value("PC_CLIENT_REMOTE", "altserver@example.test")


def _default_remote_worktree() -> str:
    return _env_value("PC_CLIENT_REMOTE_ROOT", DEFAULT_REMOTE_WORKTREE).rstrip("/")


def _ssh_key() -> Path:
    return Path(_env_value("PC_CLIENT_SSH_KEY", str(DEFAULT_KEY)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--branch")
    parser.add_argument("--remote", default=_default_remote())
    parser.add_argument(
        "--allow-local-dirty",
        action="store_true",
        help=(
            "Deploy only the last committed Git revision even if the local workspace has "
            "uncommitted changes. Those local changes stay only on Windows."
        ),
    )
    parser.add_argument(
        "--gate",
        choices=("full", "quick"),
        default="full",
        help=(
            "Release verification gate. `full` requires a green CI artifact for the target "
            "commit. `quick` is for staging/iteration and runs the release flow without "
            "the full-CI artifact requirement."
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
        help="Emergency bypass for the green CI artifact requirement; equivalent to quick gate.",
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
    parser.add_argument(
        "--smoke-base-url",
        default=os.environ.get("REMOTE_SMOKE_BASE_URL", ""),
        help="Override remote smoke BASE_URL. Defaults to remote server env REMOTE_SMOKE_BASE_URL.",
    )
    parser.add_argument(
        "--smoke-insecure-tls",
        action="store_true",
        default=str(os.environ.get("REMOTE_SMOKE_INSECURE_TLS", "")).strip().lower() in {"1", "true", "yes", "on"},
        help="Allow self-signed HTTPS certs during remote smoke.",
    )
    parser.add_argument(
        "--environment",
        default="stand",
        help="Release environment name expected in artifacts/live/release-summary.json for full gate.",
    )
    parser.add_argument("--release-run-id", help="Optional release-run id expected in the live release summary.")
    parser.add_argument("--expected-schema-head", help="Optional schema head expected in the live release summary.")
    parser.add_argument(
        "--live-summary",
        type=Path,
        help="Path to pc_client.live_release_summary.v1 JSON. Defaults to artifacts/live/release-summary.json.",
    )
    parser.add_argument(
        "--release-status-path",
        default=None,
        help=(
            "Write a Tech Panel release marker JSON after successful release. "
            "Local paths are written locally; paths under /var/chat_bot/pc_client "
            "are written on the remote host over SSH. Defaults to TECH_RELEASE_STATUS_PATH."
        ),
    )
    parser.add_argument(
        "--require-marker-write",
        action="store_true",
        help="Fail release if writing the release status marker fails.",
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
    key = _ssh_key()
    if key.exists():
        scp_command.extend(["-i", str(key)])
        ssh_command.extend(["-i", str(key)])

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


def _parse_alembic_revision_output(output: str) -> str | None:
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith(("info ", "context impl", "will assume")):
            continue
        match = re.match(r"^([0-9A-Za-z][0-9A-Za-z_.-]*)\b", line)
        if match and any(ch.isdigit() for ch in match.group(1)):
            return match.group(1)
    return None


def _run_remote_migration_status(workspace: Path, remote: str, *alembic_args: str) -> str | None:
    command = [
        sys.executable,
        str(workspace / "scripts" / "run_remote_migrations.py"),
        "--remote",
        remote,
        *alembic_args,
    ]
    completed = subprocess.run(
        command,
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        if stderr:
            print(f"WARNING: alembic {' '.join(alembic_args)} failed: {stderr}", file=sys.stderr)
        return None
    return _parse_alembic_revision_output(completed.stdout)


def collect_remote_alembic_revisions(*, workspace: Path, remote: str) -> tuple[str | None, str | None]:
    current = _run_remote_migration_status(workspace, remote, "current")
    head = _run_remote_migration_status(workspace, remote, "heads")
    return current, head


def build_release_status_payload(
    *,
    branch: str | None,
    commit: str,
    gate: str,
    dirty: bool,
    remote_profile: str,
    webapp_bundle_commit: str | None = None,
    alembic_current: str | None = None,
    alembic_head: str | None = None,
    migrations_skipped: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "success",
        "branch": branch,
        "commit": commit,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "webapp_bundle_commit": webapp_bundle_commit or commit,
        "gate": gate,
        "dirty": dirty,
        "remote_profile": remote_profile,
        "migrations_skipped": bool(migrations_skipped),
    }
    if alembic_current:
        payload["alembic_current"] = alembic_current
    if alembic_head:
        payload["alembic_head"] = alembic_head
    return payload


def write_release_status_marker(
    path: Path | str,
    payload: dict[str, object] | None = None,
    *,
    branch: str | None = None,
    commit: str | None = None,
    gate: str | None = None,
    dirty: bool = False,
    remote_profile: str | None = None,
    webapp_bundle_commit: str | None = None,
    alembic_current: str | None = None,
    alembic_head: str | None = None,
    migrations_skipped: bool = False,
) -> dict[str, object]:
    if payload is None:
        if commit is None or gate is None or remote_profile is None:
            raise ValueError("commit, gate and remote_profile are required when payload is not provided")
        payload = build_release_status_payload(
            branch=branch,
            commit=commit,
            gate=gate,
            dirty=dirty,
            remote_profile=remote_profile,
            webapp_bundle_commit=webapp_bundle_commit,
            alembic_current=alembic_current,
            alembic_head=alembic_head,
            migrations_skipped=migrations_skipped,
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _normalize_posix_marker_path(path: Path | str) -> str:
    normalized = str(path).replace("\\", "/")
    if not normalized.startswith("/"):
        return normalized
    while normalized.startswith("//"):
        normalized = normalized[1:]
    return normalized


def _is_remote_release_marker_path(path: Path | str) -> bool:
    normalized = _normalize_posix_marker_path(path)
    remote_root = _default_remote_worktree()
    return normalized == remote_root or normalized.startswith(f"{remote_root}/")


def write_remote_release_status_marker(
    path: Path | str,
    *,
    payload: dict[str, object],
    remote: str,
    cwd: Path,
) -> dict[str, object]:
    remote_path = _normalize_posix_marker_path(path)
    writer = (
        "import pathlib, sys; "
        "p = pathlib.Path(sys.argv[1]); "
        "p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text(sys.stdin.read(), encoding='utf-8')"
    )
    command = [_ssh_binary()]
    key = _ssh_key()
    if key.exists():
        command.extend(["-i", str(key)])
    command.extend([remote, f"python3 -c {shlex.quote(writer)} {shlex.quote(remote_path)}"])
    subprocess.run(
        command,
        cwd=cwd,
        input=json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        text=True,
        encoding="utf-8",
        check=True,
    )
    return payload


def _workspace_dirty(workspace: Path) -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return bool(completed.stdout.strip())


def _release_marker_path(args: argparse.Namespace) -> str | None:
    configured = getattr(args, "release_status_path", None) or os.environ.get("TECH_RELEASE_STATUS_PATH")
    if not configured:
        return None
    return str(configured)


def main() -> None:
    args = parse_args()
    workspace = args.workspace
    started_server = False
    bundle_archive: Path | None = None
    alembic_current: str | None = None
    alembic_head: str | None = None

    try:
        commit = detect_commit(workspace)
        effective_gate = "quick" if args.skip_ci_check else args.gate
        if effective_gate == "full":
            summary_path = require_green_ci_artifact(workspace, commit)
            print(f"[ci] using green artifact {summary_path}")
            live_summary_path = require_live_release_summary(
                workspace,
                commit,
                args.environment,
                summary_path=args.live_summary,
                release_run_id=args.release_run_id,
                expected_schema_head=args.expected_schema_head,
            )
            print(f"[live] using release summary {live_summary_path}")
        else:
            print(
                "[ci] quick gate selected; skipping green CI artifact requirement. "
                "Use full gate only after an explicit final release-checkpoint request."
            )

        if not args.skip_verify:
            run_step(
                [sys.executable, str(workspace / "scripts" / "verify_workspace.py")],
                cwd=workspace,
                label="verify",
            )

        bundle_archive = prepare_webapp_bundle_archive(
            workspace,
            commit,
            skip_ci_check=effective_gate == "quick",
        )

        deploy_command = [sys.executable, str(workspace / "scripts" / "deploy_workspace_to_remote.py")]
        if args.branch:
            deploy_command.extend(["--branch", args.branch])
        if args.allow_local_dirty:
            deploy_command.append("--allow-local-dirty")
        deploy_command.extend(["--gate", effective_gate])
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
            alembic_current, alembic_head = collect_remote_alembic_revisions(
                workspace=workspace,
                remote=args.remote,
            )
        assert bundle_archive is not None
        upload_webapp_bundle(
            bundle_archive,
            cwd=workspace,
            remote=args.remote,
            remote_worktree=_default_remote_worktree(),
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
            smoke_command = [*remote_command_base, "smoke", "server"]
            smoke_base_url = getattr(args, "smoke_base_url", "")
            smoke_insecure_tls = bool(getattr(args, "smoke_insecure_tls", False))
            if smoke_base_url:
                smoke_command.extend(["--base-url", smoke_base_url])
            if smoke_insecure_tls:
                smoke_command.append("--insecure-tls")
            run_smoke_with_retries(
                smoke_command,
                cwd=workspace,
                attempts=args.smoke_attempts,
                delay_seconds=args.smoke_delay,
            )

        marker_path = _release_marker_path(args)
        if marker_path is not None:
            try:
                marker_payload = build_release_status_payload(
                    branch=args.branch,
                    commit=commit,
                    gate=effective_gate,
                    dirty=_workspace_dirty(workspace),
                    remote_profile=args.remote,
                    webapp_bundle_commit=commit,
                    alembic_current=alembic_current,
                    alembic_head=alembic_head,
                    migrations_skipped=bool(args.skip_migrations),
                )
                if _is_remote_release_marker_path(marker_path):
                    write_remote_release_status_marker(
                        marker_path,
                        payload=marker_payload,
                        remote=args.remote,
                        cwd=workspace,
                    )
                    print(f"[release-marker] wrote remote {args.remote}:{marker_path}")
                else:
                    write_release_status_marker(marker_path, marker_payload)
                    print(f"[release-marker] wrote {marker_path}")
            except Exception as exc:
                if getattr(args, "require_marker_write", False):
                    raise
                print(f"WARNING: failed to write release marker: {exc}", file=sys.stderr)

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
