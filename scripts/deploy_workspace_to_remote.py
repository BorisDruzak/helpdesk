#!/usr/bin/env python3
"""Deploy the current local Git branch to the Linux working copy."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

try:
    from scripts.ci_artifacts import detect_commit, require_green_ci_artifact
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.ci_artifacts import detect_commit, require_green_ci_artifact

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
DEFAULT_REMOTE_NAME = "linux"
DEFAULT_REMOTE_HOST = "altserver@192.168.100.17"
DEFAULT_REMOTE_WORKTREE = "/var/chat_bot/pc_client"
DEFAULT_KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")
DEFAULT_GIT = Path(r"C:\Program Files\Git\bin\git.exe")
DEFAULT_SSH = Path(r"C:\Windows\System32\OpenSSH\ssh.exe")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--remote-name", default=DEFAULT_REMOTE_NAME)
    parser.add_argument("--remote-host", default=DEFAULT_REMOTE_HOST)
    parser.add_argument("--remote-worktree", default=DEFAULT_REMOTE_WORKTREE)
    parser.add_argument("--branch")
    parser.add_argument(
        "--allow-local-dirty",
        action="store_true",
        help=(
            "Deploy only the last committed Git revision even if the local workspace has "
            "uncommitted changes. Those local changes will stay only on Windows."
        ),
    )
    parser.add_argument(
        "--gate",
        choices=("full", "quick"),
        default="full",
        help=(
            "Verification gate for this deploy. `full` requires a green CI artifact for "
            "the target commit. `quick` is for staging/iteration and skips that full-CI "
            "artifact requirement."
        ),
    )
    parser.add_argument(
        "--skip-ci-check",
        action="store_true",
        help="Emergency bypass for the green CI artifact requirement; equivalent to quick gate.",
    )
    return parser.parse_args()


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    if DEFAULT_KEY.exists():
        key_arg = DEFAULT_KEY.as_posix()
        env["GIT_SSH_COMMAND"] = f'ssh -i "{key_arg}"'
    return env


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError as exc:
        if exc.stdout and exc.stdout.strip():
            print(exc.stdout.strip())
        if exc.stderr and exc.stderr.strip():
            print(exc.stderr.strip())
        raise
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip())
    return completed.stdout.strip()


def detect_branch(workspace: Path, env: dict[str, str]) -> str:
    git_binary = str(DEFAULT_GIT if DEFAULT_GIT.exists() else "git")
    branch = run([git_binary, "rev-parse", "--abbrev-ref", "HEAD"], cwd=workspace, env=env)
    if branch == "HEAD":
        raise SystemExit("Detached HEAD is not supported for deploy; checkout a branch first.")
    return branch


def get_local_dirty_entries(
    workspace: Path,
    env: dict[str, str],
    *,
    git_binary: str,
) -> list[str]:
    completed = subprocess.run(
        [git_binary, "status", "--short", "--untracked-files=normal"],
        cwd=workspace,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]


def build_local_dirty_message(entries: list[str]) -> str:
    preview_limit = 20
    preview_lines = entries[:preview_limit]
    preview = "\n".join(f"  {line}" for line in preview_lines)
    if len(entries) > preview_limit:
        preview = f"{preview}\n  ... and {len(entries) - preview_limit} more"
    return (
        "Local workspace has uncommitted changes.\n"
        "`python scripts/deploy_workspace_to_remote.py` deploys only committed Git state via "
        "push/pull, so these changes would NOT be copied to the Linux working copy:\n"
        f"{preview}\n"
        "Commit or stash them first. If you intentionally want to deploy only the last "
        "committed revision, rerun with `--allow-local-dirty`."
    )


def build_remote_command(remote_worktree: str, branch: str) -> str:
    safe_worktree = remote_worktree.replace('"', '\\"')
    safe_branch = branch.replace('"', '\\"')
    return (
        f'cd "{safe_worktree}" && '
        'dirty=$(git status --porcelain --untracked-files=no) && '
        'if [ -n "$dirty" ]; then '
        'echo "REMOTE_WORKTREE_DIRTY" >&2; '
        'echo "$dirty" >&2; '
        "exit 2; "
        'fi && '
        f'git pull --ff-only origin "{safe_branch}" && '
        "git rev-parse HEAD"
    )


def main() -> None:
    args = parse_args()
    env = git_env()
    git_binary = str(DEFAULT_GIT if DEFAULT_GIT.exists() else "git")
    ssh_binary = str(DEFAULT_SSH if DEFAULT_SSH.exists() else "ssh")
    dirty_entries = get_local_dirty_entries(args.workspace, env, git_binary=git_binary)

    if dirty_entries and not args.allow_local_dirty:
        raise SystemExit(build_local_dirty_message(dirty_entries))
    if dirty_entries:
        print(
            "WARNING: local workspace is dirty; deploying only the last committed Git revision "
            "because `--allow-local-dirty` was set."
        )

    branch = args.branch or detect_branch(args.workspace, env)
    print(f"Deploy branch: {branch}")
    commit = detect_commit(args.workspace)
    effective_gate = "quick" if args.skip_ci_check else args.gate
    if effective_gate == "full":
        summary_path = require_green_ci_artifact(args.workspace, commit)
        print(f"Using green CI artifact: {summary_path}")
    else:
        print(
            "WARNING: quick deploy gate selected; skipping green CI artifact requirement. "
            "Use full gate only after an explicit final release-checkpoint request."
        )

    try:
        run([git_binary, "push", args.remote_name, branch], cwd=args.workspace, env=env)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Git push failed with exit code {exc.returncode}.") from exc

    ssh_command = [ssh_binary]
    if DEFAULT_KEY.exists():
        ssh_command.extend(["-i", str(DEFAULT_KEY)])
    ssh_command.extend([args.remote_host, build_remote_command(args.remote_worktree, branch)])
    try:
        run(ssh_command, cwd=args.workspace)
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 2:
            raise SystemExit(
                "Remote working copy is dirty. Move Linux-only changes back to Windows, "
                "or commit/stash them on Linux before deploy."
            ) from exc
        raise SystemExit(f"Remote update failed with exit code {exc.returncode}.") from exc

    print(f"Remote workspace updated via Git: {args.remote_host}:{args.remote_worktree}")


if __name__ == "__main__":
    main()
