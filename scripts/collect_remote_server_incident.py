#!/usr/bin/env python3
"""Collect targeted remote service incident evidence with basic redaction."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_REMOTE = "altserver@192.168.100.17"
DEFAULT_KEY = Path(r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519")

SECRET_QUERY_RE = re.compile(r"([?&](?:token|session_token|account_session_token|access_token)=)[^\\s\"&]+", re.I)
BEARER_RE = re.compile(r"(Bearer\\s+)[A-Za-z0-9._~+/=-]{16,}", re.I)


def _redact(text: str) -> str:
    text = SECRET_QUERY_RE.sub(r"\\1<redacted>", text)
    return BEARER_RE.sub(r"\\1<redacted>", text)


def _ssh(remote: str, key: Path, script: str) -> str:
    command = ["ssh"]
    if key.exists():
        command.extend(["-i", str(key)])
    command.extend([remote, "bash -s"])
    completed = subprocess.run(
        command,
        input=script,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return _redact(completed.stdout)


def build_remote_script(since: str, until: str) -> str:
    return f"""
set +e
echo "=== metadata ==="
date --iso-8601=seconds
hostnamectl 2>/dev/null | sed -n '1,8p'
echo "=== server lifecycle ==="
journalctl --user -u pc-client-server.service --since {since!r} --until {until!r} --no-pager | grep -E "Stopped|Stopping|Started|Main process|code=killed|status=9|Killed|SIGKILL|signal|Failed|Consumed" || true
echo "=== related lifecycle ==="
journalctl --user --since {since!r} --until {until!r} --no-pager | grep -E "pc-client-(server|control|https-proxy)|code=killed|status=9|SIGKILL|Killed|Stopping|Stopped|Started" || true
echo "=== kernel oom ==="
journalctl -k --since {since!r} --until {until!r} --no-pager | grep -Ei "oom|killed process|out of memory|memory cgroup|kill" || true
echo "=== current server unit ==="
systemctl --user show pc-client-server.service -p Type -p Restart -p RestartUSec -p NRestarts -p ExecStart -p MainPID -p ActiveState -p SubState -p Result -p ExecMainCode -p ExecMainStatus || true
echo "=== current status excerpt ==="
systemctl --user status pc-client-server.service --no-pager | head -40 || true
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default=os.environ.get("PC_CLIENT_REMOTE", DEFAULT_REMOTE))
    parser.add_argument("--ssh-key", default=os.environ.get("PC_CLIENT_SSH_KEY", str(DEFAULT_KEY)))
    parser.add_argument("--since", default="2026-05-27 00:15:30")
    parser.add_argument("--until", default="2026-05-27 00:17:30")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    output = Path(args.output) if args.output else Path("artifacts") / f"remote-server-incident-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    body = _ssh(args.remote, Path(args.ssh_key), build_remote_script(args.since, args.until))
    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "remote": args.remote,
        "since": args.since,
        "until": args.until,
        "output": str(output),
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n\n" + body, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
