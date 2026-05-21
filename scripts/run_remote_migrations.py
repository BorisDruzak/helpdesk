#!/usr/bin/env python3
"""Run Alembic migrations on the remote Linux host over SSH.

Requirements:
- Code is already deployed to the host (`python scripts/deploy_workspace_to_remote.py`).
- The remote `server/.env` contains a valid `DATABASE_URL`.

Examples:
  python scripts/run_remote_migrations.py
  python scripts/run_remote_migrations.py current
  python scripts/run_remote_migrations.py upgrade head
  python scripts/run_remote_migrations.py --remote altserver@192.168.100.17 downgrade -1
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_REMOTE = "altserver@192.168.100.17"
REMOTE_ROOT = "/var/chat_bot/pc_client"
SERVER_PYTHON = "/var/chat_bot/pc_client/server/venv/bin/python"
KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")


def _env_value(name: str, default: str) -> str:
    return str(os.environ.get(name) or default).strip() or default


def _remote_root() -> str:
    return _env_value("PC_CLIENT_REMOTE_ROOT", REMOTE_ROOT).rstrip("/")


def _server_python() -> str:
    return _env_value("PC_CLIENT_REMOTE_SERVER_PYTHON", f"{_remote_root()}/server/venv/bin/python")


def _ssh_key() -> Path:
    return Path(_env_value("PC_CLIENT_SSH_KEY", str(KEY)))


def ssh_cmd() -> list[str]:
    cmd = ["ssh"]
    key = _ssh_key()
    if key.exists():
        cmd.extend(["-i", str(key)])
    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", default=_env_value("PC_CLIENT_REMOTE", DEFAULT_REMOTE))
    parser.add_argument(
        "alembic_args",
        nargs="*",
        help="Arguments passed to scripts/run_migrations.py on the remote host.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    alembic_args = args.alembic_args or ["upgrade", "head"]
    args_str = " ".join(alembic_args)
    remote_cmd = (
        f"cd {_remote_root()}/server && {_server_python()} scripts/run_migrations.py {args_str}"
    )
    full = [*ssh_cmd(), args.remote, remote_cmd]
    return subprocess.run(full).returncode


if __name__ == "__main__":
    sys.exit(main())
