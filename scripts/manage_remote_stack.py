#!/usr/bin/env python3
"""Manage remote pc_client services over SSH via the canonical runtime stack CLI."""

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path

DEFAULT_REMOTE = "altserver@192.168.100.17"
DEFAULT_KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")
REMOTE_ROOT = "/var/chat_bot/pc_client"
REMOTE_SERVER_PYTHON = "/var/chat_bot/pc_client/server/venv/bin/python"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "smoke", "logs"])
    parser.add_argument("target", choices=["server", "agent", "control", "all"])
    parser.add_argument("--lines", type=int, default=80, help="Used by logs")
    parser.add_argument("--follow", action="store_true", help="Used by logs: follow output until interrupted")
    parser.add_argument("--levels", default="", help="Used by logs: comma-separated levels")
    parser.add_argument("--contains", default="", help="Used by logs: substring search")
    parser.add_argument("--json", action="store_true", help="Return machine-readable JSON where supported")
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    return parser.parse_args()


def ssh_base_command() -> list[str]:
    command = ["ssh"]
    if DEFAULT_KEY.exists():
        command.extend(["-i", str(DEFAULT_KEY)])
    return command


def build_remote_command(args: argparse.Namespace) -> str:
    command = [
        shlex.quote(REMOTE_SERVER_PYTHON),
        "scripts/runtime_stack.py",
        shlex.quote(args.action),
        shlex.quote(args.target),
    ]
    if args.action == "logs":
        command.extend(["--lines", shlex.quote(str(args.lines))])
        if args.follow:
            command.append("--follow")
        if args.levels:
            command.extend(["--levels", shlex.quote(args.levels)])
        if args.contains:
            command.extend(["--contains", shlex.quote(args.contains)])
    if args.json:
        command.append("--json")
    return f"cd {shlex.quote(REMOTE_ROOT)} && {' '.join(command)}"


def main() -> None:
    args = parse_args()
    command = [*ssh_base_command(), args.remote, build_remote_command(args)]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
