#!/usr/bin/env python3
"""
Остановка сервера (stop_server) и запуск в фоне через run_server.py.
Вызов из корня репозитория: python scripts/restart_server.py
"""
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SCRIPT_DIR = WORKSPACE / "scripts"


def main():
    stop = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "stop_server.py")],
        cwd=WORKSPACE,
        timeout=15,
    )
    # Запускаем в фоне (не ждём завершения)
    subprocess.Popen(
        [sys.executable, str(SCRIPT_DIR / "run_server.py")],
        cwd=WORKSPACE,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print("[restart_server] Сервер перезапущен (запуск в фоне).")
    sys.exit(0)


if __name__ == "__main__":
    main()
