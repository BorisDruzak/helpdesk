#!/usr/bin/env python3
"""Manage remote pc_client server and agent over SSH."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DEFAULT_REMOTE = "altserver@192.168.100.17"
DEFAULT_KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")
REMOTE_ROOT = "/var/chat_bot/pc_client"
SERVER_PYTHON = "/var/chat_bot/pc_client/server/venv/bin/python"
AGENT_PYTHON = "/var/chat_bot/pc_client/pc_agent/venv/bin/python"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "smoke", "logs"])
    parser.add_argument("target", choices=["server", "agent", "all"])
    parser.add_argument("--lines", type=int, default=80, help="Used by logs")
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    return parser.parse_args()


def ssh_base_command() -> list[str]:
    command = ["ssh"]
    if DEFAULT_KEY.exists():
        command.extend(["-i", str(DEFAULT_KEY)])
    return command


def systemd_run(unit: str, description: str, command: str) -> str:
    escaped = command.replace("'", "'\"'\"'")
    return (
        f"systemctl --user reset-failed {unit} >/dev/null 2>&1 || true; "
        f"systemctl --user stop {unit} >/dev/null 2>&1 || true; "
        f"systemd-run --user --unit={unit} --description='{description}' "
        f"/bin/bash -lc '{escaped}'"
    )


def remote_command(action: str, target: str, lines: int) -> str:
    if action == "status":
        if target == "server":
            return "systemctl --user status pc-client-server --no-pager || true"
        if target == "agent":
            return "systemctl --user status pc-client-agent --no-pager || true"
        return (
            "systemctl --user status pc-client-server --no-pager || true; "
            "systemctl --user status pc-client-agent --no-pager || true"
        )

    if action == "logs":
        if target == "server":
            return f"journalctl --user -u pc-client-server -n {lines} --no-pager || true"
        if target == "agent":
            return f"journalctl --user -u pc-client-agent -n {lines} --no-pager || true"
        return (
            f"journalctl --user -u pc-client-server -n {lines} --no-pager || true; "
            f"journalctl --user -u pc-client-agent -n {lines} --no-pager || true"
        )

    if action == "smoke":
        return f"cd {REMOTE_ROOT} && BASE_URL=http://192.168.100.17:8666 {SERVER_PYTHON} scripts/smoke_test.py"

    if action == "start":
        if target == "server":
            return systemd_run(
                "pc-client-server",
                "pc_client server",
                f"cd {REMOTE_ROOT} && {SERVER_PYTHON} scripts/run_server.py",
            )
        if target == "agent":
            return systemd_run(
                "pc-client-agent",
                "pc_client agent",
                f"cd {REMOTE_ROOT} && {AGENT_PYTHON} scripts/run_agent.py",
            )
        return (
            systemd_run(
                "pc-client-server",
                "pc_client server",
                f"cd {REMOTE_ROOT} && {SERVER_PYTHON} scripts/run_server.py",
            )
            + " && "
            + systemd_run(
                "pc-client-agent",
                "pc_client agent",
                f"cd {REMOTE_ROOT} && {AGENT_PYTHON} scripts/run_agent.py",
            )
        )

    if action == "stop":
        if target == "server":
            return (
                f"cd {REMOTE_ROOT} && {SERVER_PYTHON} scripts/stop_server.py || true; "
                "systemctl --user stop pc-client-server || true"
            )
        if target == "agent":
            return (
                f"cd {REMOTE_ROOT} && {AGENT_PYTHON} scripts/stop_agent.py || true; "
                "systemctl --user stop pc-client-agent || true"
            )
        return (
            f"cd {REMOTE_ROOT} && {SERVER_PYTHON} scripts/stop_server.py || true; "
            f"cd {REMOTE_ROOT} && {AGENT_PYTHON} scripts/stop_agent.py || true; "
            "systemctl --user stop pc-client-server || true; "
            "systemctl --user stop pc-client-agent || true"
        )

    if action == "restart":
        if target == "server":
            return (
                f"cd {REMOTE_ROOT} && {SERVER_PYTHON} scripts/stop_server.py || true; "
                "systemctl --user stop pc-client-server || true; "
                + systemd_run(
                    "pc-client-server",
                    "pc_client server",
                    f"cd {REMOTE_ROOT} && {SERVER_PYTHON} scripts/run_server.py",
                )
            )
        if target == "agent":
            return (
                f"cd {REMOTE_ROOT} && {AGENT_PYTHON} scripts/stop_agent.py || true; "
                "systemctl --user stop pc-client-agent || true; "
                + systemd_run(
                    "pc-client-agent",
                    "pc_client agent",
                    f"cd {REMOTE_ROOT} && {AGENT_PYTHON} scripts/run_agent.py",
                )
            )
        return (
            f"cd {REMOTE_ROOT} && {SERVER_PYTHON} scripts/stop_server.py || true; "
            f"cd {REMOTE_ROOT} && {AGENT_PYTHON} scripts/stop_agent.py || true; "
            "systemctl --user stop pc-client-server || true; "
            "systemctl --user stop pc-client-agent || true; "
            + systemd_run(
                "pc-client-server",
                "pc_client server",
                f"cd {REMOTE_ROOT} && {SERVER_PYTHON} scripts/run_server.py",
            )
            + " && "
            + systemd_run(
                "pc-client-agent",
                "pc_client agent",
                f"cd {REMOTE_ROOT} && {AGENT_PYTHON} scripts/run_agent.py",
            )
        )

    raise ValueError(f"Unsupported action: {action}")


def main() -> None:
    args = parse_args()
    command = [*ssh_base_command(), args.remote, remote_command(args.action, args.target, args.lines)]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
