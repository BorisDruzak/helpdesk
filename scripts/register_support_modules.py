#!/usr/bin/env python
"""
Register support-oriented managed modules on the server via /api/modules/create.

Modules:
- network_ping.ping
- fsnav.navigate
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


MODULE_SPECS = [
    {
        "module_name": "network_ping",
        "version": "1.0.0",
        "tool_name": "ping",
        "method_name": "run_ping",
        "description": "Ping a host from the device and return the response summary.",
        "platforms": ["linux", "win32"],
        "risk_level": "safe_readonly",
        "params_schema": [
            {"name": "host", "type": "string", "required": True},
            {"name": "count", "type": "integer", "default": 4},
            {"name": "timeout_ms", "type": "integer", "default": 1000},
        ],
        "presets": [
            {
                "id": "localhost",
                "name": "Localhost",
                "description": "Ping localhost from the device",
                "params": {"host": "127.0.0.1", "count": 2, "timeout_ms": 1000},
            },
            {
                "id": "dns",
                "name": "Public DNS",
                "description": "Ping 8.8.8.8 from the device",
                "params": {"host": "8.8.8.8", "count": 4, "timeout_ms": 1000},
            },
        ],
        "metadata": {
            "domain": "network",
            "risk_level": "safe_readonly",
            "requires_consent": False,
            "timeout_sec": 30,
            "idempotent": True,
            "allow_roles": ["admin", "support", "agent", "llm"],
            "scopes": ["network"],
        },
        "user_function_body": """
import locale as _locale
import platform as _platform
import subprocess as _subprocess

host = str(params.get("host") or "").strip()
if not host:
    return {"ok": False, "error": "host is required", "reachable": False}

count = max(1, min(10, int(params.get("count") or 4)))
timeout_ms = max(100, min(10000, int(params.get("timeout_ms") or 1000)))

if _platform.system().lower().startswith("win"):
    command = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
else:
    timeout_sec = max(1, int((timeout_ms + 999) / 1000))
    command = ["ping", "-c", str(count), "-W", str(timeout_sec), host]

proc = _subprocess.run(command, capture_output=True)
decode_encoding = "oem" if _platform.system().lower().startswith("win") else (_locale.getpreferredencoding(False) or "utf-8")
stdout = (proc.stdout or b"").decode(decode_encoding, errors="replace").strip()
stderr = (proc.stderr or b"").decode(decode_encoding, errors="replace").strip()
summary = ""
for line in reversed(stdout.splitlines()):
    if line.strip():
        summary = line.strip()
        break

return {
    "ok": proc.returncode == 0,
    "host": host,
    "count": count,
    "timeout_ms": timeout_ms,
    "reachable": proc.returncode == 0,
    "exit_code": proc.returncode,
    "command": command,
    "summary": summary or ("pong" if proc.returncode == 0 else "no response"),
    "stdout": stdout,
    "stderr": stderr,
}
""".strip(),
    },
    {
        "module_name": "fsnav",
        "version": "1.0.0",
        "tool_name": "navigate",
        "method_name": "navigate",
        "description": "Read-only filesystem navigation with pwd, cd, ls and stat style actions.",
        "platforms": ["any"],
        "risk_level": "safe_readonly",
        "params_schema": [
            {"name": "action", "type": "string", "default": "pwd"},
            {"name": "path", "type": "string", "default": ""},
            {"name": "cwd", "type": "string", "default": ""},
            {"name": "limit", "type": "integer", "default": 50},
            {"name": "include_hidden", "type": "boolean", "default": False},
        ],
        "presets": [
            {
                "id": "pwd",
                "name": "PWD",
                "description": "Return the current working directory",
                "params": {"action": "pwd"},
            },
            {
                "id": "home_ls",
                "name": "Home LS",
                "description": "List the user home directory",
                "params": {"action": "ls", "path": "~", "limit": 30},
            },
        ],
        "metadata": {
            "domain": "filesystem",
            "risk_level": "safe_readonly",
            "requires_consent": False,
            "timeout_sec": 30,
            "idempotent": True,
            "allow_roles": ["admin", "support", "agent", "llm"],
            "scopes": ["filesystem"],
        },
        "user_function_body": """
from pathlib import Path as _Path

action = str(params.get("action") or "pwd").strip().lower()
raw_cwd = str(params.get("cwd") or "").strip()
raw_path = str(params.get("path") or "").strip()
limit = max(1, min(200, int(params.get("limit") or 50)))
include_hidden = bool(params.get("include_hidden", False))

base = _Path(raw_cwd).expanduser() if raw_cwd else _Path.cwd()
base = base.resolve()
target_hint = _Path(raw_path).expanduser() if raw_path else base
target = target_hint.resolve() if target_hint.is_absolute() else (base / target_hint).resolve()

def _entry_payload(entry):
    stat = entry.stat()
    return {
        "name": entry.name,
        "path": str(entry),
        "is_dir": entry.is_dir(),
        "size_bytes": stat.st_size,
    }

if action in {"pwd", "cd"}:
    if not target.exists() or not target.is_dir():
        return {"ok": False, "error": "directory_not_found", "cwd": str(base), "target": str(target)}
    return {"ok": True, "action": action, "cwd": str(target), "target": str(target), "entries": []}

if action == "ls":
    if not target.exists() or not target.is_dir():
        return {"ok": False, "error": "directory_not_found", "cwd": str(base), "target": str(target)}
    total_entries = 0
    entries = []
    for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if not include_hidden and child.name.startswith("."):
            continue
        total_entries += 1
        entries.append(_entry_payload(child))
        if len(entries) >= limit:
            break
    return {
        "ok": True,
        "action": action,
        "cwd": str(target),
        "target": str(target),
        "entries": entries,
        "returned_count": len(entries),
        "truncated": total_entries > len(entries),
    }

if action == "stat":
    if not target.exists():
        return {"ok": False, "error": "path_not_found", "cwd": str(base), "target": str(target)}
    return {
        "ok": True,
        "action": action,
        "cwd": str(base),
        "target": str(target),
        "entry": _entry_payload(target),
    }

return {
    "ok": False,
    "error": "unsupported_action",
    "supported_actions": ["pwd", "cd", "ls", "stat"],
    "cwd": str(base),
    "target": str(target),
}
""".strip(),
    },
]


def _post_json(base_url: str, token: str, path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=base_url.rstrip("/") + path,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"status": "error", "error": raw or str(exc)}
        payload["_http_status"] = exc.code
        return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Register support managed modules on a server.")
    parser.add_argument("--server-url", default=os.environ.get("PC_CLIENT_SERVER_URL", "http://127.0.0.1:8666"))
    parser.add_argument("--admin-token", default=os.environ.get("PC_CLIENT_ADMIN_TOKEN", ""))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.admin_token:
        print("Admin token is required via --admin-token or PC_CLIENT_ADMIN_TOKEN", file=sys.stderr)
        return 2

    results = []
    for spec in MODULE_SPECS:
        payload = dict(spec)
        payload["overwrite"] = args.overwrite
        result = _post_json(args.server_url, args.admin_token, "/api/modules/create", payload)
        results.append({"module_name": spec["module_name"], "version": spec["version"], "result": result})

    print(json.dumps({"server_url": args.server_url, "results": results}, ensure_ascii=False, indent=2))
    failed = [item for item in results if item["result"].get("status") != "success"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
