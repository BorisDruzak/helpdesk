#!/usr/bin/env python3
"""Upload the local workspace to the remote Linux host as a tar.gz archive."""

from __future__ import annotations

import argparse
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

DEFAULT_WORKSPACE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")
DEFAULT_REMOTE = "altserver@192.168.100.17"
DEFAULT_REMOTE_ROOT = "/var/chat_bot/pc_client"
DEFAULT_KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")
RSYNC_EXCLUDES = [
    ".git/",
    ".run/",
    ".cursor/",
    ".vscode/",
    ".pytest_cache/",
    "data/",
    "temp/",
    "uploads/",
    "build/",
    "dist/",
    "server/venv/",
    "server/data/",
    "server/uploads/",
    "server/reports/",
    "pc_agent/venv/",
    "pc_agent/data/",
    "pc_agent/build/",
    "pc_agent/dist/",
    "src/venv/",
]

SKIP_PARTS = {
    ".git",
    ".run",
    ".cursor",
    ".vscode",
    ".pytest_cache",
    "__pycache__",
    "venv",
    "data",
    "build",
    "dist",
    "uploads",
    "reports",
    "temp",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".bak", ".zip", ".rar"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT)
    parser.add_argument("--archive-name", default=f"pc_client_sync_{int(time.time())}.tar.gz")
    return parser.parse_args()


def ssh_base_command() -> list[str]:
    command = ["ssh"]
    if DEFAULT_KEY.exists():
        command.extend(["-i", str(DEFAULT_KEY)])
    return command


def scp_base_command() -> list[str]:
    command = ["scp"]
    if DEFAULT_KEY.exists():
        command.extend(["-i", str(DEFAULT_KEY)])
    return command


def should_skip(path: Path, workspace: Path) -> bool:
    relative = path.relative_to(workspace)
    if any(part in SKIP_PARTS for part in relative.parts):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def build_archive(workspace: Path, archive_path: Path) -> None:
    with tarfile.open(archive_path, "w:gz") as tar:
        for path in workspace.rglob("*"):
            if should_skip(path, workspace):
                continue
            tar.add(path, arcname=path.relative_to(workspace))


def main() -> None:
    args = parse_args()
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / args.archive_name
        build_archive(args.workspace, archive_path)

        remote_archive = f"/tmp/{args.archive_name}"
        scp_command = [*scp_base_command(), str(archive_path), f"{args.remote}:{remote_archive}"]
        print("Uploading archive...")
        subprocess.run(scp_command, check=True)

        remote_unpack_dir = f"/tmp/pc_client_unpack_{int(time.time())}"
        rsync_excludes = " ".join(f"--exclude='{item}'" for item in RSYNC_EXCLUDES)
        remote_command = (
            f"rm -rf {remote_unpack_dir} && "
            f"mkdir -p {remote_unpack_dir} {args.remote_root} && "
            f"tar -xzf {remote_archive} -C {remote_unpack_dir} && "
            f"rsync -rlt --delete --omit-dir-times {rsync_excludes} "
            f"{remote_unpack_dir}/ {args.remote_root}/ && "
            f"mkdir -p {args.remote_root}/server/uploads && "
            f"rsync -rlt --include='*/' --include='*.py' --exclude='*' "
            f"{remote_unpack_dir}/server/uploads/ {args.remote_root}/server/uploads/ && "
            f"rm -rf {remote_unpack_dir} {remote_archive}"
        )
        ssh_command = [*ssh_base_command(), args.remote, remote_command]
        print("Extracting archive on remote host...")
        subprocess.run(ssh_command, check=True)

    print(f"Remote workspace updated: {args.remote}:{args.remote_root}")


if __name__ == "__main__":
    main()
