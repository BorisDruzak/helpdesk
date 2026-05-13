#!/usr/bin/env python3
"""
Удаляет build агента из server-side registry через HTTP API.

Поддерживает два варианта аутентификации:
  1) ADMIN_TOKEN=... python scripts/drop_agent_build.py ...
  2) Логин/пароль: скрипт сам вызовет POST /api/ui_login и получит token.

По умолчанию сервер не даст удалить build, который назначен как rollout policy.
Для operator-flow можно передать --clear-rollout-first: тогда скрипт сначала
снимет rollout assignment для target, если он указывает ровно на этот build.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import quote
import ssl


BASE_URL_DEFAULT = os.environ.get("BASE_URL", "https://192.168.100.17:9443")


def _request(
    method: str,
    url: str,
    data: dict | None = None,
    *,
    token: str | None = None,
) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else "{}"
        return exc.code, json.loads(body) if body else {"error": str(exc)}
    except Exception as exc:
        return -1, {"error": str(exc)}


def ui_login(base_url: str, login: str, password: str) -> str | None:
    status, payload = _request(
        "POST",
        f"{base_url}/api/ui_login",
        {"login": login, "password": password},
    )
    if status != 200 or payload.get("status") != "success":
        print(f"Login failed: {status} {payload}", file=sys.stderr)
        return None
    return payload.get("token")


def get_rollout_policy(base_url: str, token: str) -> tuple[int, dict]:
    return _request("GET", f"{base_url}/api/agent_updates/rollout_policy", token=token)


def clear_rollout_assignment(base_url: str, token: str, target: str) -> tuple[int, dict]:
    return _request(
        "PATCH",
        f"{base_url}/api/agent_updates/rollout_policy",
        {"target": target, "clear": True},
        token=token,
    )


def delete_build(base_url: str, token: str, *, target: str, channel: str, version: str) -> tuple[int, dict]:
    return _request(
        "DELETE",
        f"{base_url}/api/agent_builds/{quote(target, safe='')}/{quote(channel, safe='')}/{quote(version, safe='')}",
        token=token,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete agent build from server registry")
    parser.add_argument("--base-url", default=BASE_URL_DEFAULT, help="Server base URL")
    parser.add_argument("--token", default=os.environ.get("ADMIN_TOKEN"), help="Admin UI token or ADMIN_TOKEN")
    parser.add_argument("--login", help="Admin login if --token is not provided")
    parser.add_argument("--password", help="Password for --login")
    parser.add_argument("--target", required=True, help="Build target, e.g. windows_amd64 or linux_alt_x86_64")
    parser.add_argument("--channel", default="stable", help="Build channel, default stable")
    parser.add_argument("--version", required=True, help="Build version to delete")
    parser.add_argument(
        "--clear-rollout-first",
        action="store_true",
        help="Clear rollout policy first if it points to this exact build",
    )
    args = parser.parse_args()

    token = args.token
    if not token and args.login and args.password:
        token = ui_login(args.base_url, args.login, args.password)
    if not token:
        print("Need either ADMIN_TOKEN, --token, or --login/--password", file=sys.stderr)
        return 2

    if args.clear_rollout_first:
        status, rollout_payload = get_rollout_policy(args.base_url, token)
        if status != 200 or rollout_payload.get("status") != "ok":
            print(json.dumps({"status": "error", "stage": "get_rollout_policy", "payload": rollout_payload}, ensure_ascii=False, indent=2))
            return 1
        assignment = next(
            (
                item
                for item in rollout_payload.get("assignments", [])
                if item.get("target") == args.target
                and item.get("channel") == args.channel
                and item.get("version") == args.version
            ),
            None,
        )
        if assignment:
            status, clear_payload = clear_rollout_assignment(args.base_url, token, args.target)
            print(
                json.dumps(
                    {"status": "ok" if status == 200 else "error", "stage": "clear_rollout_policy", "payload": clear_payload},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            if status != 200 or clear_payload.get("status") != "ok":
                return 1

    status, payload = delete_build(
        args.base_url,
        token,
        target=args.target,
        channel=args.channel,
        version=args.version,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == 200 and payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
