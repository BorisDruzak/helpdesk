#!/usr/bin/env python3
"""
Обёртка запуска агента: пишет PID в .run/agent.pid и перехватывает сигналы.
Позволяет надёжно останавливать агент через scripts/stop_agent.py (kill по PID).
Запуск: из корня репозитория: python scripts/run_agent.py
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
RUN_DIR = WORKSPACE / ".run"
PID_FILE = RUN_DIR / "agent.pid"


def main():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    PID_FILE.write_text(str(pid), encoding="utf-8")
    print(f"[run_agent] PID {pid} -> {PID_FILE}", flush=True)

    # Проброс аргументов (--data-dir, --gui и т.д.) для E2E и тестов
    args = [sys.executable, "-m", "pc_agent.ws_agent"] + sys.argv[1:]
    proc = subprocess.Popen(
        args,
        cwd=WORKSPACE,
        stdin=subprocess.DEVNULL,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=os.environ.copy(),
    )

    def on_signal(signum, frame):
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except OSError:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    try:
        sys.exit(proc.wait())
    finally:
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
