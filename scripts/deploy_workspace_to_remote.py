#!/usr/bin/env python3
"""Deploy the current local Git branch to the Linux working copy."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

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

    branch = args.branch or detect_branch(args.workspace, env)
    print(f"Deploy branch: {branch}")

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
