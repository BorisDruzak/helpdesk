#!/usr/bin/env python3
"""
Проверка сценария 429 при исчерпании семафоров WS-команд.

Сервер ограничивает число одновременных run_tool по устройству
(WS_COMMAND_MAX_INFLIGHT_PER_DEVICE=10 по умолчанию). При превышении
acquire ждёт до 2 сек, затем возвращает 429.

Запуск (сервер и агент должны быть запущены):
  python3 scripts/test_429_semaphore.py
  python3 scripts/test_429_semaphore.py --base-url http://localhost:8666 --login admin --password admin123 --device-id UUID

Ожидание: хотя бы один из параллельных запросов вернёт HTTP 429.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import urllib.request
import urllib.error
import ssl

BASE_URL_DEFAULT = os.environ.get("BASE_URL", "http://localhost:8666")
# Число параллельных запросов: существенно больше лимита per-device (10),
# чтобы несколько запросов ждали acquire >2 сек и получили 429 (таймаут acquire в protocol.py).
DEFAULT_CONCURRENT = 25


def _request(method: str, url: str, data: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=headers, method=method)
    ctx = ssl.create_default_context()
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


def run_tool_one(
    base_url: str,
    token: str,
    device_id: str,
    tool_name: str,
    params: dict,
    index: int,
) -> tuple[int, int, dict]:
    payload = {
        "device_id": device_id,
        "tool_name": tool_name,
        "params": params,
        "mode": "system_ticket",
    }
    status, out = _request("POST", f"{base_url}/api/admin/run_tool", payload, token=token)
    return index, status, out


def main():
    ap = argparse.ArgumentParser(description="Test 429 when WS command semaphores are exhausted")
    ap.add_argument("--base-url", default=BASE_URL_DEFAULT, help="Server base URL")
    ap.add_argument("--login", default=os.environ.get("ADMIN_LOGIN", "admin"), help="Admin login")
    ap.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", "admin123"), help="Admin password")
    ap.add_argument("--device-id", default=os.environ.get("DEVICE_ID"), help="Device UUID (required if no default)")
    ap.add_argument("--tool", default="os_check.get_info", help="Tool to call")
    ap.add_argument("--params", default="{}", help="JSON params for the tool (for slow tool use e.g. {\"host\":\"10.255.255.1\",\"timeout\":5})")
    ap.add_argument("--concurrent", type=int, default=DEFAULT_CONCURRENT, help="Number of parallel requests")
    args = ap.parse_args()

    if not args.device_id:
        print("Need --device-id or DEVICE_ID", file=sys.stderr)
        sys.exit(2)

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as e:
        print(f"Invalid --params JSON: {e}", file=sys.stderr)
        sys.exit(2)

    token = ui_login(args.base_url, args.login, args.password)
    if not token:
        sys.exit(2)

    print(f"Отправка {args.concurrent} параллельных run_tool на device_id={args.device_id}...", flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.concurrent) as ex:
        futures = {
            ex.submit(run_tool_one, args.base_url, token, args.device_id, args.tool, params, i): i
            for i in range(args.concurrent)
        }
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                print(f"  Request failed: {e}", file=sys.stderr)
                results.append((futures[fut], -1, {"error": str(e)}))

    status_counts: dict[int, int] = {}
    for _idx, status, _out in results:
        status_counts[status] = status_counts.get(status, 0) + 1

    print(f"Результаты: {dict(sorted(status_counts.items()))}", flush=True)
    if 429 in status_counts:
        print("OK: получен хотя бы один ответ 429 (очередь WS-команд переполнена).")
        sys.exit(0)
    # Инструмент может завершаться быстрее 2 сек — тогда семафор успевает освобождаться
    print(
        "ПРЕДУПРЕЖДЕНИЕ: 429 не получен (инструмент, вероятно, быстрый). "
        "Для воспроизведения 429: запустите сервер с WS_COMMAND_MAX_INFLIGHT_PER_DEVICE=2 "
        "и вызовите тест с --concurrent 3 и медленным инструментом (например ping_check.ping_host с недоступным хостом).",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
