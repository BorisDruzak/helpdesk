#!/usr/bin/env python
"""
Register support-oriented managed modules on the server via /api/modules/create.

Modules:
- network_basic (dns.resolve, network.ping, tcp.connect, route.get, adapter.list)
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
        "module_name": "network_basic",
        "version": "1.0.0",
        "description": "Cross-platform network diagnostics pack with universal semantic tool ids.",
        "platforms": ["linux", "win32"],
        "risk_level": "safe_readonly",
        "requirements": ["psutil"],
        "tools": [
            {
                "tool_name": "dns.resolve",
                "method_name": "resolve_dns",
                "description": "Resolve hostname to IPv4/IPv6 addresses on the device.",
                "params_schema": [
                    {"name": "hostname", "type": "string", "required": True},
                    {"name": "family", "type": "string", "default": "any"},
                ],
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "hostname": {"type": "string"},
                        "best_ip": {"type": "string"},
                    },
                },
                "metadata": {
                    "domain": "dns",
                    "risk_level": "safe_readonly",
                    "requires_consent": False,
                    "timeout_sec": 15,
                    "idempotent": True,
                    "allow_roles": ["admin", "support", "agent", "llm"],
                    "scopes": ["network", "dns"],
                },
                "user_function_body": """
import socket as _socket

hostname = str(params.get("hostname") or params.get("host") or "").strip()
family_name = str(params.get("family") or "any").strip().lower()
family_map = {"any": _socket.AF_UNSPEC, "ipv4": _socket.AF_INET, "ipv6": _socket.AF_INET6}
if not hostname:
    return {"ok": False, "error_code": "MISSING_HOSTNAME", "error": "hostname is required", "addresses": []}
if family_name not in family_map:
    return {
        "ok": False,
        "error_code": "UNSUPPORTED_FAMILY",
        "error": "family must be one of any|ipv4|ipv6",
        "hostname": hostname,
        "addresses": [],
    }

records = []
seen = set()
try:
    info = _socket.getaddrinfo(hostname, None, family_map[family_name], _socket.SOCK_STREAM)
except _socket.gaierror as exc:
    return {
        "ok": False,
        "error_code": "DNS_RESOLUTION_FAILED",
        "error": str(exc),
        "hostname": hostname,
        "family": family_name,
        "addresses": [],
    }

for entry_family, _socktype, _proto, canonname, sockaddr in info:
    ip = sockaddr[0] if sockaddr else ""
    if not ip:
        continue
    family_label = "ipv6" if entry_family == _socket.AF_INET6 else "ipv4"
    key = (family_label, ip)
    if key in seen:
        continue
    seen.add(key)
    records.append(
        {
            "family": family_label,
            "ip": ip,
            "canonical_name": canonname or hostname,
        }
    )

return {
    "ok": True,
    "hostname": hostname,
    "family": family_name,
    "best_ip": records[0]["ip"] if records else "",
    "addresses": records,
    "address_count": len(records),
}
""".strip(),
            },
            {
                "tool_name": "network.ping",
                "aliases": ["ping.host"],
                "method_name": "ping_host",
                "description": "Ping a target from the device and return a cross-platform summary.",
                "params_schema": [
                    {"name": "target", "type": "string", "required": True},
                    {"name": "count", "type": "integer", "default": 4},
                    {"name": "timeout_ms", "type": "integer", "default": 1000},
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
import shutil as _shutil
import subprocess as _subprocess

target = str(params.get("target") or params.get("host") or "").strip()
if not target:
    return {"ok": False, "error_code": "MISSING_TARGET", "error": "target is required", "reachable": False}
if not _shutil.which("ping"):
    return {"ok": False, "error_code": "PING_NOT_AVAILABLE", "error": "ping command not found", "reachable": False}

count = max(1, min(10, int(params.get("count") or 4)))
timeout_ms = max(100, min(10000, int(params.get("timeout_ms") or 1000)))
system_name = (_platform.system() or "").lower()

if system_name.startswith("win"):
    command = ["ping", "-n", str(count), "-w", str(timeout_ms), target]
else:
    timeout_sec = max(1, int((timeout_ms + 999) / 1000))
    command = ["ping", "-c", str(count), "-W", str(timeout_sec), target]

proc = _subprocess.run(command, capture_output=True)
decode_encoding = "oem" if system_name.startswith("win") else (_locale.getpreferredencoding(False) or "utf-8")
stdout = (proc.stdout or b"").decode(decode_encoding, errors="replace").strip()
stderr = (proc.stderr or b"").decode(decode_encoding, errors="replace").strip()
summary = ""
for line in reversed(stdout.splitlines()):
    if line.strip():
        summary = line.strip()
        break

return {
    "ok": proc.returncode == 0,
    "target": target,
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
                "tool_name": "tcp.connect",
                "method_name": "connect_tcp",
                "description": "Attempt a TCP connection and report latency and resolved peer IP.",
                "params_schema": [
                    {"name": "host", "type": "string", "required": True},
                    {"name": "port", "type": "integer", "required": True},
                    {"name": "timeout_sec", "type": "number", "default": 3},
                ],
                "metadata": {
                    "domain": "tcp",
                    "risk_level": "safe_readonly",
                    "requires_consent": False,
                    "timeout_sec": 15,
                    "idempotent": True,
                    "allow_roles": ["admin", "support", "agent", "llm"],
                    "scopes": ["network", "tcp"],
                },
                "user_function_body": """
import socket as _socket
import time as _time

host = str(params.get("host") or params.get("target") or "").strip()
port = int(params.get("port") or 0)
timeout_sec = float(params.get("timeout_sec") or 3)
timeout_sec = min(30.0, max(0.2, timeout_sec))

if not host:
    return {"ok": False, "error_code": "MISSING_HOST", "error": "host is required", "reachable": False}
if port <= 0 or port > 65535:
    return {"ok": False, "error_code": "INVALID_PORT", "error": "port must be in range 1..65535", "reachable": False}

try:
    candidates = _socket.getaddrinfo(host, port, _socket.AF_UNSPEC, _socket.SOCK_STREAM)
except _socket.gaierror as exc:
    return {
        "ok": False,
        "error_code": "DNS_RESOLUTION_FAILED",
        "error": str(exc),
        "host": host,
        "port": port,
        "reachable": False,
    }

last_error = ""
for family, socktype, proto, _canonname, sockaddr in candidates:
    sock = _socket.socket(family, socktype, proto)
    sock.settimeout(timeout_sec)
    started = _time.perf_counter()
    try:
        sock.connect(sockaddr)
        latency_ms = int((_time.perf_counter() - started) * 1000)
        peer_ip = sockaddr[0] if sockaddr else ""
        local_ip = sock.getsockname()[0]
        sock.close()
        return {
            "ok": True,
            "host": host,
            "port": port,
            "peer_ip": peer_ip,
            "local_ip": local_ip,
            "latency_ms": latency_ms,
            "reachable": True,
            "timeout_sec": timeout_sec,
        }
    except OSError as exc:
        last_error = str(exc)
        sock.close()

return {
    "ok": False,
    "error_code": "TCP_CONNECT_FAILED",
    "error": last_error or "connection failed",
    "host": host,
    "port": port,
    "reachable": False,
    "timeout_sec": timeout_sec,
}
""".strip(),
            },
            {
                "tool_name": "route.get",
                "method_name": "get_route",
                "description": "Infer the egress local address for a target using a UDP socket probe.",
                "params_schema": [
                    {"name": "target", "type": "string", "required": True},
                    {"name": "port", "type": "integer", "default": 53},
                    {"name": "timeout_sec", "type": "number", "default": 2},
                ],
                "metadata": {
                    "domain": "route",
                    "risk_level": "safe_readonly",
                    "requires_consent": False,
                    "timeout_sec": 10,
                    "idempotent": True,
                    "allow_roles": ["admin", "support", "agent", "llm"],
                    "scopes": ["network", "route"],
                },
                "user_function_body": """
import socket as _socket

target = str(params.get("target") or params.get("host") or "").strip()
port = int(params.get("port") or 53)
timeout_sec = float(params.get("timeout_sec") or 2)
timeout_sec = min(10.0, max(0.2, timeout_sec))

if not target:
    return {"ok": False, "error_code": "MISSING_TARGET", "error": "target is required"}
if port <= 0 or port > 65535:
    return {"ok": False, "error_code": "INVALID_PORT", "error": "port must be in range 1..65535"}

try:
    candidates = _socket.getaddrinfo(target, port, _socket.AF_UNSPEC, _socket.SOCK_DGRAM)
except _socket.gaierror as exc:
    return {
        "ok": False,
        "error_code": "DNS_RESOLUTION_FAILED",
        "error": str(exc),
        "target": target,
        "port": port,
    }

last_error = ""
for family, socktype, proto, _canonname, sockaddr in candidates:
    sock = _socket.socket(family, socktype, proto)
    sock.settimeout(timeout_sec)
    try:
        sock.connect(sockaddr)
        local_addr = sock.getsockname()
        local_ip = local_addr[0] if local_addr else ""
        local_port = local_addr[1] if len(local_addr) > 1 else 0
        sock.close()
        return {
            "ok": True,
            "target": target,
            "target_ip": sockaddr[0] if sockaddr else "",
            "port": port,
            "local_ip": local_ip,
            "local_port": local_port,
            "strategy": "udp_socket_inference",
            "note": "Reports the selected source address for the current route decision.",
        }
    except OSError as exc:
        last_error = str(exc)
        sock.close()

return {
    "ok": False,
    "error_code": "ROUTE_PROBE_FAILED",
    "error": last_error or "route probe failed",
    "target": target,
    "port": port,
}
""".strip(),
            },
            {
                "tool_name": "adapter.list",
                "method_name": "list_adapters",
                "description": "List network adapters and their IPv4/IPv6 addresses.",
                "params_schema": [],
                "metadata": {
                    "domain": "adapter",
                    "risk_level": "safe_readonly",
                    "requires_consent": False,
                    "timeout_sec": 15,
                    "idempotent": True,
                    "allow_roles": ["admin", "support", "agent", "llm"],
                    "scopes": ["network", "adapter"],
                },
                "user_function_body": """
import socket as _socket

try:
    import psutil as _psutil
except Exception as exc:
    return {"ok": False, "error_code": "PSUTIL_NOT_AVAILABLE", "error": str(exc), "interfaces": []}

addrs = _psutil.net_if_addrs()
stats = _psutil.net_if_stats()
af_link = getattr(_psutil, "AF_LINK", None)
socket_af_link = getattr(_socket, "AF_LINK", None)
interfaces = []

for name, items in sorted(addrs.items()):
    stat = stats.get(name)
    payload = {
        "name": name,
        "is_up": bool(stat.isup) if stat else False,
        "speed_mbps": getattr(stat, "speed", 0) if stat else 0,
        "mtu": getattr(stat, "mtu", 0) if stat else 0,
        "ipv4": [],
        "ipv6": [],
        "mac": [],
    }
    for item in items:
        if item.family == _socket.AF_INET:
            payload["ipv4"].append(item.address)
        elif item.family == _socket.AF_INET6:
            payload["ipv6"].append(item.address.split("%", 1)[0])
        elif af_link is not None and item.family == af_link:
            payload["mac"].append(item.address)
        elif socket_af_link is not None and item.family == socket_af_link:
            payload["mac"].append(item.address)
    interfaces.append(payload)

return {
    "ok": True,
    "interface_count": len(interfaces),
    "interfaces": interfaces,
}
""".strip(),
            },
        ],
    },
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
