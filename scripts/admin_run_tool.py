#!/usr/bin/env python3
"""
Вызов инструмента агента через Admin API (run_tool) из командной строки / Codex.

Требуется токен админки. Варианты:
  1) ADMIN_TOKEN=... python scripts/admin_run_tool.py ...
  2) Логин/пароль: скрипт сам вызовет POST /api/ui_login и возьмёт token.

Примеры:
  # Токен из переменной окружения
  ADMIN_TOKEN=your_token python scripts/admin_run_tool.py --device-id UUID --tool os_check.get_info

  # Логин + запуск
  python scripts/admin_run_tool.py --base-url http://localhost:8666 \\
    --login admin --password admin123 \\
    --device-id 832c3c33-f72f-41d7-9f02-0be47967fe7d --tool os_check.get_info

  # С параметрами (JSON)
  python scripts/admin_run_tool.py --login admin --password admin123 \\
    --device-id UUID --tool some_module.some_tool --params '{"key":"value"}'
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import urllib.request
import urllib.error
import ssl

BASE_URL_DEFAULT = os.environ.get("BASE_URL", "http://localhost:8666")


def _request(method: str, url: str, data: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=headers, method=method)
    ctx = ssl.create_default_context() if ssl else None
    if ctx:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            body = r.read().decode()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else "{}"
        return e.code, json.loads(body) if body else {"error": str(e)}
    except Exception as e:
        return -1, {"error": str(e)}


def ui_login(base_url: str, login: str, password: str) -> str | None:
    status, out = _request("POST", f"{base_url}/api/ui_login", {"login": login, "password": password})
    if status != 200 or out.get("status") != "success":
        print(f"Login failed: {status} {out}", file=sys.stderr)
        return None
    return out.get("token")


def run_tool(base_url: str, token: str, device_id: str, tool_name: str, params: dict | None = None) -> tuple[int, dict]:
    payload = {
        "device_id": device_id,
        "tool_name": tool_name,
        "params": params or {},
        "mode": "system_ticket",
    }
    return _request("POST", f"{base_url}/api/admin/run_tool", payload, token=token)


def main():
    ap = argparse.ArgumentParser(description="Run agent tool via Admin API")
    ap.add_argument("--base-url", default=BASE_URL_DEFAULT, help="Server base URL")
    ap.add_argument("--token", default=os.environ.get("ADMIN_TOKEN"), help="Admin UI token (or ADMIN_TOKEN)")
    ap.add_argument("--login", help="Login (to get token if --token not set)")
    ap.add_argument("--password", help="Password for --login")
    ap.add_argument("--device-id", required=True, help="Device UUID")
    ap.add_argument("--tool", required=True, help="Tool name, e.g. os_check.get_info")
    ap.add_argument("--params", default="{}", help="JSON object of params")
    args = ap.parse_args()

    token = args.token
    if not token and args.login and args.password:
        token = ui_login(args.base_url, args.login, args.password)
    if not token:
        print("Need either ADMIN_TOKEN, --token, or --login/--password", file=sys.stderr)
        sys.exit(2)

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as e:
        print(f"Invalid --params JSON: {e}", file=sys.stderr)
        sys.exit(2)

    status, out = run_tool(args.base_url, token, args.device_id, args.tool, params)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if status == 200 and out.get("status") in ("ok", "success") else 1)


if __name__ == "__main__":
    main()
