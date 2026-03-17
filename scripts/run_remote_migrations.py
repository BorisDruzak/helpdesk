#!/usr/bin/env python3
"""
Запуск миграций Alembic на удалённом Linux-хосте по SSH.

Требования:
- Код уже выложен на хост (python scripts/deploy_workspace_to_remote.py).
- На удалённом хосте в server/.env задан DATABASE_URL (один раз создать вручную или скопировать).

Использование (из корня репо):
  python scripts/run_remote_migrations.py              # upgrade head
  python scripts/run_remote_migrations.py current
  python scripts/run_remote_migrations.py upgrade head
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REMOTE = "altserver@192.168.100.17"
REMOTE_ROOT = "/var/chat_bot/pc_client"
SERVER_PYTHON = "/var/chat_bot/pc_client/server/venv/bin/python"
KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")


def ssh_cmd() -> list[str]:
    cmd = ["ssh"]
    if KEY.exists():
        cmd.extend(["-i", str(KEY)])
    return cmd


def main() -> int:
    argv = sys.argv[1:] if len(sys.argv) > 1 else ["upgrade", "head"]
    args_str = " ".join(argv)
    remote_cmd = (
        f"cd {REMOTE_ROOT}/server && {SERVER_PYTHON} scripts/run_migrations.py {args_str}"
    )
    full = [*ssh_cmd(), REMOTE, remote_cmd]
    return subprocess.run(full).returncode


if __name__ == "__main__":
    sys.exit(main())
