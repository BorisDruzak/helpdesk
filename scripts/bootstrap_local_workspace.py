#!/usr/bin/env python3
"""Bootstrap or refresh the local pc_client workspace from an explicit source."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

DEFAULT_DEST = Path(r"C:\Users\admin-2\CodexProjects\pc_client")

RELATIVE_EXCLUDED_DIRS = [
    ".venvs",
    ".local-agent",
    ".run",
    ".cursor",
    ".vscode",
    ".pytest_cache",
    "data",
    "temp",
    "uploads",
    "build",
    "dist",
    "server\\venv",
    "server\\data",
    "server\\uploads",
    "server\\reports",
]

EXCLUDED_DIR_NAMES = ["__pycache__", ".pytest_cache", "venv"]
EXCLUDED_FILES = ["*.pyc", "*.pyo", "*.log", "*.tmp", "*.bak", "*.zip", "*.rar"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--mirror", action="store_true", help="Use /MIR instead of /E")
    return parser.parse_args()


def run_robocopy(source: Path, dest: Path, mirror: bool, keep_local_git: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    mode_flag = "/MIR" if mirror else "/E"
    command = ["robocopy", str(source), str(dest), mode_flag, "/R:1", "/W:1", "/FFT"]

    excluded_dirs = [str(source / rel) for rel in RELATIVE_EXCLUDED_DIRS]
    excluded_dirs.extend(EXCLUDED_DIR_NAMES)
    if keep_local_git:
        excluded_dirs.append(str(source / ".git"))

    if excluded_dirs:
        command.append("/XD")
        command.extend(excluded_dirs)
    if EXCLUDED_FILES:
        command.append("/XF")
        command.extend(EXCLUDED_FILES)

    print("Running:", " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode > 7:
        raise SystemExit(result.returncode)


def cleanup_destination(dest: Path) -> None:
    for rel in RELATIVE_EXCLUDED_DIRS:
        path = dest / rel
        if path.exists():
            shutil.rmtree(path)
    for path in dest.rglob("*"):
        if path.is_dir() and path.name in EXCLUDED_DIR_NAMES:
            shutil.rmtree(path)


def main() -> None:
    args = parse_args()
    keep_local_git = (args.dest / ".git").exists()
    run_robocopy(args.source, args.dest, args.mirror, keep_local_git=keep_local_git)
    cleanup_destination(args.dest)
    print(f"Local workspace is ready: {args.dest}")


if __name__ == "__main__":
    main()
