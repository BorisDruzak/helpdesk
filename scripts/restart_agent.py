#!/usr/bin/env python3
"""
Остановка агента (stop_agent) и запуск в фоне через run_agent.py.
Вызов из корня репозитория: python scripts/restart_agent.py
"""
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SCRIPT_DIR = WORKSPACE / "scripts"


def main():
    stop = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "stop_agent.py")],
        cwd=WORKSPACE,
        timeout=20,
    )
    subprocess.Popen(
        [sys.executable, str(SCRIPT_DIR / "run_agent.py")],
        cwd=WORKSPACE,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print("[restart_agent] Агент перезапущен (запуск в фоне).")
    sys.exit(0)


if __name__ == "__main__":
    main()
