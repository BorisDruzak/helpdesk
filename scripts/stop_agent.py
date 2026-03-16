#!/usr/bin/env python3
"""
Остановка агента по PID из .run/agent.pid (процесс, запущенный через run_agent.py).
Если PID-файла нет или процесс не найден — пробуем pkill и удаляем устаревший PID-файл.
"""
import os
import signal
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
RUN_DIR = WORKSPACE / ".run"
PID_FILE = RUN_DIR / "agent.pid"


def kill_pid(pid: int) -> bool:
    """Отправить SIGTERM процессу. Возвращает True, если процесс существовал."""
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        print(f"[stop_agent] Нет прав для остановки процесса {pid}", file=sys.stderr)
        return False


def main():
    if not PID_FILE.exists():
        import subprocess
        r = subprocess.run(
            ["pkill", "-f", "pc_agent.ws_agent"],
            capture_output=True,
            timeout=5,
        )
        if r.returncode == 0:
            print("[stop_agent] Процесс агента завершён (pkill).")
        else:
            print("[stop_agent] PID-файл отсутствует. Агент, возможно, не был запущен через scripts/run_agent.py.", file=sys.stderr)
        sys.exit(0 if r.returncode == 0 else 1)

    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError) as e:
        print(f"[stop_agent] Не удалось прочитать PID: {e}", file=sys.stderr)
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)

    if not kill_pid(pid):
        PID_FILE.unlink(missing_ok=True)
        print("[stop_agent] Процесс уже не существует, PID-файл удалён.", file=sys.stderr)
        sys.exit(0)

    for _ in range(30):
        time.sleep(0.5)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    PID_FILE.unlink(missing_ok=True)
    print("[stop_agent] Агент остановлен.")


if __name__ == "__main__":
    main()
