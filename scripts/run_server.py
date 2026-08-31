#!/usr/bin/env python3
"""
Обёртка запуска сервера: пишет PID в .run/server.pid и перехватывает сигналы.
Позволяет надёжно останавливать сервер через scripts/stop_server.py (kill по PID).
Запуск: из корня репозитория: python scripts/run_server.py
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from scripts.server_runtime_paths import resolve_run_dir as _resolve_run_dir


def resolve_run_dir() -> Path:
    return _resolve_run_dir(WORKSPACE)


RUN_DIR = resolve_run_dir()
PID_FILE = RUN_DIR / "server.pid"


def main():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    PID_FILE.write_text(str(pid), encoding="utf-8")
    print(f"[run_server] PID {pid} -> {PID_FILE}", flush=True)
    env = os.environ.copy()
    existing_pythonpath = str(env.get("PYTHONPATH") or "").strip()
    pythonpath_parts = [str(WORKSPACE)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=WORKSPACE / "server",
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def on_signal(signum, frame):
        proc.terminate()
        try:
            proc.wait(timeout=10)
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
