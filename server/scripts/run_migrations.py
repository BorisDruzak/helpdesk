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
    production = os.getenv("APP_ENV", "").strip().lower() == "prod"
    if production and argv != ["upgrade", "head"]:
        # Global Alembic options can hide a write command from argv[0]. Only
        # explicitly bounded read operations may bypass the backup gate.
        if argv not in (["current"], ["heads"], ["history"]):
            print("Production accepts upgrade head or bounded read commands only; recovery requires separate review.", file=sys.stderr)
            return 1
    if production and argv == ["upgrade", "head"]:
        sys.path.insert(0, str(SERVER_DIR.parent))
        from scripts.helpdesk_database_backup import create_verified_backup
        from shared.production_security import production_config_errors
        import json
        try:
            errors = production_config_errors(os.environ)
            if errors:
                raise ValueError("insecure production configuration")
            identity = json.loads((SERVER_DIR.parent / "release-identity.json").read_text(encoding="utf-8"))
            data_root = Path(os.environ["PC_CLIENT_SERVER_DATA_ROOT"])
            if not data_root.is_absolute() or data_root.resolve() == SERVER_DIR.parent.resolve() or SERVER_DIR.parent.resolve() in data_root.resolve().parents:
                raise ValueError("backup storage must be outside the immutable release")
            create_verified_backup(os.environ["DATABASE_URL"], data_root / "backups",
                                   Path(os.environ["TECH_BACKUP_STATUS_PATH"]), identity["helpdesk_git_sha"])
        except (ValueError, RuntimeError, OSError, KeyError):
            print("Production migration blocked: secure config and verified backup required.", file=sys.stderr)
            return 1
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SERVER_DIR)

    cmd = [sys.executable, "-m", "alembic"] + argv
    return subprocess.run(cmd, cwd=SERVER_DIR, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
