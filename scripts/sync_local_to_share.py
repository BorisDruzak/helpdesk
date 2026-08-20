#!/usr/bin/env python3
"""Preview or apply a sync from the local workspace to an explicit destination."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DEFAULT_SOURCE = Path(r"C:\Users\admin-2\CodexProjects\pc_client")

RELATIVE_EXCLUDED_DIRS = [
    ".git",
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
    "pc_agent\\venv",
    "pc_agent\\data",
    "pc_agent\\build",
    "pc_agent\\dist",
]

EXCLUDED_DIR_NAMES = ["__pycache__", ".pytest_cache", "venv"]
EXCLUDED_FILES = ["*.pyc", "*.pyo", "*.log", "*.tmp", "*.bak", "*.zip", "*.rar"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Apply changes instead of preview only")
    parser.add_argument("--mirror", action="store_true", help="Use /MIR instead of /E")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode_flag = "/MIR" if args.mirror else "/E"
    command = ["robocopy", str(args.source), str(args.dest), mode_flag, "/R:1", "/W:1", "/FFT"]
    if not args.apply:
        command.append("/L")

    excluded_dirs = [str(args.source / rel) for rel in RELATIVE_EXCLUDED_DIRS]
    excluded_dirs.extend(EXCLUDED_DIR_NAMES)
    command.append("/XD")
    command.extend(excluded_dirs)
    command.append("/XF")
    command.extend(EXCLUDED_FILES)

    print("Running:", " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode > 7:
        raise SystemExit(result.returncode)

    if args.apply:
        print(f"Share sync complete: {args.dest}")
    else:
        print("Preview complete. Re-run with --apply to copy files.")


if __name__ == "__main__":
    main()
