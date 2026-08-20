#!/usr/bin/env python3
"""Stop the server process launched from this workspace."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
RUN_DIR = Path(
    os.getenv(
        "HELPDESK_RUNTIME_DIR",
        str(WORKSPACE / ".run" if os.name == "nt" else "/var/lib/helpdesk/run"),
    )
)
PID_FILE = RUN_DIR / 'server.pid'
DEFAULT_SERVER_PORT = 8666


def kill_pid(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        print(f'[stop_server] No permission to stop process {pid}', file=sys.stderr)
        return False


def _find_windows_pid_by_port(port: int):
    try:
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, timeout=10, check=False)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    target = f':{port}'
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr, state, pid = parts[1], parts[3], parts[4]
        if target not in local_addr or state.upper() != 'LISTENING':
            continue
        try:
            return int(pid)
        except ValueError:
            continue
    return None


def _kill_windows_server_fallback() -> bool:
    pid = _find_windows_pid_by_port(DEFAULT_SERVER_PORT)
    if pid is None:
        return False
    result = subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, text=True, timeout=10, check=False)
    if result.returncode == 0:
        print(f'[stop_server] Stopped process on port {DEFAULT_SERVER_PORT} (PID {pid}).')
        return True
    return False


def main():
    if not PID_FILE.exists():
        if os.name == 'nt':
            ok = _kill_windows_server_fallback()
            if not ok:
                print('[stop_server] PID file not found and no listening process detected on port 8666.', file=sys.stderr)
            sys.exit(0 if ok else 1)
        result = subprocess.run(['pkill', '-f', 'python server.py'], capture_output=True, timeout=5, check=False)
        if result.returncode == 0:
            print('[stop_server] Server process stopped (pkill).')
        else:
            print('[stop_server] PID file not found. Server may not have been started by scripts/run_server.py.', file=sys.stderr)
        sys.exit(0 if result.returncode == 0 else 1)

    try:
        pid = int(PID_FILE.read_text(encoding='utf-8').strip())
    except (ValueError, OSError) as exc:
        print(f'[stop_server] Failed to read PID: {exc}', file=sys.stderr)
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)

    if not kill_pid(pid):
        PID_FILE.unlink(missing_ok=True)
        print('[stop_server] Process does not exist, stale PID file removed.', file=sys.stderr)
        sys.exit(0)

    for _ in range(25):
        time.sleep(0.4)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
    else:
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, text=True, timeout=10, check=False)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    PID_FILE.unlink(missing_ok=True)
    print('[stop_server] Server stopped.')


if __name__ == '__main__':
    main()
