#!/usr/bin/env python3
"""
Запуск Alembic с подгрузкой server/.env.

Использование (из каталога server/):
  python scripts/run_migrations.py [alembic args...]
  python scripts/run_migrations.py              # по умолчанию: upgrade head
  python scripts/run_migrations.py current
  python scripts/run_migrations.py upgrade head

Требует: в server/.env задан DATABASE_URL (или в окружении).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Каталог server/ (родитель каталога scripts/)
SERVER_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SERVER_DIR / ".env"


def main() -> int:
    # Подгрузить .env из server/
    if ENV_FILE.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE)
        except ImportError:
            pass

    if not os.getenv("DATABASE_URL"):
        print("DATABASE_URL не задан. Создайте server/.env с DATABASE_URL или задайте переменную окружения.", file=sys.stderr)
        return 1

    argv = sys.argv[1:] if len(sys.argv) > 1 else ["upgrade", "head"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SERVER_DIR)

    cmd = [sys.executable, "-m", "alembic"] + argv
    return subprocess.run(cmd, cwd=SERVER_DIR, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
