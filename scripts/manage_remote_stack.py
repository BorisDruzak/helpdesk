#!/usr/bin/env python3
"""Manage the Helpdesk system services on its dedicated deployment host."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from scripts.helpdesk_remote_profile import RemoteProfile

DEFAULT_REMOTE = RemoteProfile.from_environment().remote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "smoke", "logs"])
    parser.add_argument("target", choices=["server", "control", "all"])
    parser.add_argument("--lines", type=int, default=80, help="Used by logs")
    parser.add_argument("--follow", action="store_true", help="Used by logs: follow output until interrupted")
    parser.add_argument("--levels", default="", help="Used by logs: comma-separated levels")
    parser.add_argument("--contains", default="", help="Used by logs: substring search")
    parser.add_argument("--json", action="store_true", help="Return machine-readable output where supported")
    parser.add_argument("--remote", default=RemoteProfile.from_environment().remote)
    parser.add_argument("--base-url", default="", help="Used by smoke: override Helpdesk base URL")
    parser.add_argument("--insecure-tls", action="store_true", help="Used by smoke: allow self-signed HTTPS certs")
    return parser.parse_args()


def ssh_base_command() -> list[str]:
    command = ["ssh"]
    key = RemoteProfile.from_environment().ssh_key
    if key.exists():
        command.extend(["-i", str(key)])
    return command


def build_remote_command(args: argparse.Namespace) -> str:
    units = {
        "server": ["helpdesk-server.service"],
        "control": ["helpdesk-control.service"],
        "all": ["helpdesk-server.service", "helpdesk-control.service"],
    }[args.target]
    quoted_units = " ".join(shlex.quote(unit) for unit in units)

    if args.action in {"start", "stop", "restart"}:
        return f"sudo systemctl {args.action} {quoted_units}"
    if args.action == "status":
        return f"sudo systemctl status {quoted_units} --no-pager"
    if args.action == "logs":
        command = ["sudo", "journalctl"]
        for unit in units:
            command.extend(["-u", unit])
        command.extend(["-n", str(max(1, args.lines)), "--no-pager"])
        if args.follow:
            command.append("-f")
        return " ".join(shlex.quote(item) for item in command)
    if args.action == "smoke":
        base_url = (args.base_url or "http://127.0.0.1:8080").rstrip("/")
        curl_args = ["curl", "--fail", "--silent", "--show-error"]
        if args.insecure_tls:
            curl_args.append("--insecure")
        curl_args.append(f"{base_url}/api/health")
        return " ".join(shlex.quote(item) for item in curl_args)
    raise ValueError(f"Unsupported action: {args.action}")


def main() -> None:
    args = parse_args()
    command = [*ssh_base_command(), args.remote, build_remote_command(args)]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
