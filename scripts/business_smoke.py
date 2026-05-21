#!/usr/bin/env python3
"""Business acceptance smoke that writes a Tech Panel marker."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


class HttpStepError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class HttpResponse:
    status: int
    payload: dict[str, Any]
    headers: dict[str, str]


class UrlLibClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def request(self, method: str, path: str, json_body: dict | None = None) -> HttpResponse:
        data = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            urllib.parse.urljoin(self.base_url + "/", path.lstrip("/")),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                payload = json.loads(raw) if raw.strip() else {}
                return HttpResponse(response.status, payload if isinstance(payload, dict) else {}, dict(response.headers.items()))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except ValueError:
                payload = {"error": raw[:200]}
            message = str(payload.get("error") or payload.get("message") or exc)
            raise HttpStepError(exc.code, message) from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step(key: str, status: str, started: float, *, error: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"key": key, "status": status, "duration_ms": round((time.monotonic() - started) * 1000)}
    if error:
        item["error"] = error[:240]
    return item


def _set_cookie_header(headers: dict[str, str]) -> str:
    for key, value in headers.items():
        if key.lower() == "set-cookie":
            return value
    return ""


def _cookie_flags_ok(set_cookie: str) -> bool:
    lowered = set_cookie.lower()
    return "pc_client_web_session=" in lowered and "secure" in lowered and "httponly" in lowered and "samesite" in lowered


def _write_marker(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_business_smoke(
    *,
    base_url: str,
    username: str,
    password: str,
    output: Path,
    client: Any | None = None,
    timeout: float = 15.0,
    require_https: bool = False,
    require_secure_cookie: bool = False,
    device_id: str | None = None,
) -> dict[str, Any]:
    started_at = _now()
    steps: list[dict[str, Any]] = []
    smoke_client = client or UrlLibClient(base_url, timeout)
    failed = False

    def fail_fast(key: str, message: str, started: float) -> None:
        nonlocal failed
        failed = True
        steps.append(_step(key, "failed", started, error=message))

    if require_https:
        started = time.monotonic()
        if not base_url.lower().startswith("https://"):
            fail_fast("require_https", "base_url must use https://", started)

    login_headers: dict[str, str] = {}
    if not failed:
        started = time.monotonic()
        try:
            response = smoke_client.request("POST", "/api/web/session/login", {"login": username, "password": password})
            login_headers = response.headers
            steps.append(_step("web_session_login", "success", started))
        except HttpStepError as exc:
            fail_fast("web_session_login", f"HTTP {exc.status}: {exc}", started)

    if require_secure_cookie and not failed:
        started = time.monotonic()
        if _cookie_flags_ok(_set_cookie_header(login_headers)):
            steps.append(_step("secure_cookie_flags", "success", started))
        else:
            fail_fast("secure_cookie_flags", "Set-Cookie is missing Secure/HttpOnly/SameSite evidence", started)

    for key, path in [
        ("session_me", "/api/web/session/me"),
        ("support_bootstrap", "/api/web/support/bootstrap"),
        ("command_center", "/api/web/support/command-center"),
        ("approval_center", "/api/web/support/approvals"),
        ("tech_snapshot", "/api/web/admin/tech/snapshot"),
    ]:
        if failed:
            break
        started = time.monotonic()
        try:
            smoke_client.request("GET", path)
            steps.append(_step(key, "success", started))
        except HttpStepError as exc:
            fail_fast(key, f"HTTP {exc.status}: {exc}", started)

    if device_id and not failed:
        started = time.monotonic()
        try:
            smoke_client.request("GET", f"/api/web/admin/device-operations/{urllib.parse.quote(device_id)}")
            steps.append(_step("device_operations_optional", "success", started))
        except HttpStepError as exc:
            fail_fast("device_operations_optional", f"HTTP {exc.status}: {exc}", started)

    payload = {
        "status": "failed" if failed else "success",
        "started_at": started_at,
        "finished_at": _now(),
        "base_url": base_url,
        "steps": steps,
        "artifact": None,
    }
    _write_marker(output, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--device-id")
    parser.add_argument("--skip-agent-step", action="store_true")
    parser.add_argument("--require-https", action="store_true")
    parser.add_argument("--require-secure-cookie", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_business_smoke(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        output=args.output,
        timeout=args.timeout,
        require_https=args.require_https,
        require_secure_cookie=args.require_secure_cookie,
        device_id=None if args.skip_agent_step else args.device_id,
    )
    print(json.dumps({"status": payload["status"], "output": str(args.output)}, ensure_ascii=False))
    if payload["status"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
