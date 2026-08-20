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
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from scripts.helpdesk_remote_profile import RemoteProfile

DEFAULT_REMOTE = RemoteProfile.from_environment().remote


def ssh_cmd() -> list[str]:
    cmd = ["ssh"]
    key = RemoteProfile.from_environment().ssh_key
    if key.exists():
        cmd.extend(["-i", str(key)])
    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", default=RemoteProfile.from_environment().remote)
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
        f"cd {RemoteProfile.from_environment().root}/server && "
        f"{RemoteProfile.from_environment().server_python} scripts/run_migrations.py {args_str}"
    )
    full = [*ssh_cmd(), args.remote, remote_cmd]
    return subprocess.run(full).returncode


if __name__ == "__main__":
    sys.exit(main())
