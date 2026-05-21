#!/usr/bin/env python3
"""Business acceptance smoke that writes a Tech Panel marker."""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
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


SECRET_PATTERN = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key|authorization|cookie)\b\s*[:=]\s*[^,\s;&]+"
)


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
    def __init__(self, base_url: str, timeout: float, *, insecure_tls: bool | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        handlers: list[Any] = [urllib.request.HTTPCookieProcessor(self.cookie_jar)]
        if insecure_tls is None:
            insecure_tls = _truthy_env("BUSINESS_SMOKE_INSECURE_TLS") or _truthy_env("REMOTE_SMOKE_INSECURE_TLS")
        if insecure_tls and urllib.parse.urlparse(self.base_url).scheme.lower() == "https":
            handlers.append(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
        self.opener = urllib.request.build_opener(*handlers)

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


def _truthy_env(key: str) -> bool:
    return str(os.environ.get(key) or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _response_payload(response: Any) -> dict[str, Any]:
    payload = getattr(response, "payload", {})
    return payload if isinstance(payload, dict) else {}


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _redact_error(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "step failed"
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=***REDACTED***", text)[:240]


def run_browser_https_wss_check(*, base_url: str, username: str, password: str, timeout: float) -> list[dict[str, Any]]:
    started = time.monotonic()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on optional runtime
        return [
            _step("browser_mixed_content", "failed", started, error=f"Playwright unavailable: {_redact_error(exc)}"),
            _step("browser_wss", "failed", started, error="Playwright unavailable"),
        ]

    mixed_content_errors: list[str] = []
    websocket_urls: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.on(
                "console",
                lambda message: mixed_content_errors.append(message.text)
                if "mixed content" in message.text.lower()
                else None,
            )
            page.on("websocket", lambda websocket: websocket_urls.append(websocket.url))
            login_response = context.request.post(
                f"{base_url.rstrip('/')}/api/web/session/login",
                data=json.dumps({"login": username, "password": password}),
                headers={"Content-Type": "application/json"},
                timeout=timeout * 1000,
            )
            if not login_response.ok:
                raise RuntimeError(f"login failed with HTTP {login_response.status}")
            page.goto(f"{base_url.rstrip('/')}/app/admin/tech", wait_until="networkidle", timeout=timeout * 1000)
            browser.close()
    except Exception as exc:  # pragma: no cover - exercised through script/live runs
        return [
            _step("browser_mixed_content", "failed", started, error=_redact_error(exc)),
            _step("browser_wss", "failed", started, error=_redact_error(exc)),
        ]

    steps = []
    if mixed_content_errors:
        steps.append(_step("browser_mixed_content", "failed", started, error=mixed_content_errors[0][:240]))
    else:
        steps.append(_step("browser_mixed_content", "success", started))
    insecure_ws = [url for url in websocket_urls if url.lower().startswith("ws://")]
    if insecure_ws:
        steps.append(_step("browser_wss", "failed", started, error=f"insecure websocket URL observed: {insecure_ws[0]}"))
    else:
        steps.append(_step("browser_wss", "success", started))
    return steps


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
    insecure_tls: bool | None = None,
    browser_check: bool = False,
    device_id: str | None = None,
    create_test_ticket: bool = False,
    run_safe_tool: str | None = None,
    operation_wait_seconds: float = 0.0,
    check_update_recommendation: bool = False,
) -> dict[str, Any]:
    started_at = _now()
    steps: list[dict[str, Any]] = []
    smoke_client = client or UrlLibClient(base_url, timeout, insecure_tls=insecure_tls)
    failed = False
    created_ticket_id: str | None = None
    safe_tool_operation_id: str | None = None

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

    if browser_check and not failed:
        browser_steps = run_browser_https_wss_check(
            base_url=base_url,
            username=username,
            password=password,
            timeout=timeout,
        )
        steps.extend(browser_steps)
        if any(step.get("status") == "failed" for step in browser_steps):
            failed = True

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

    if check_update_recommendation and device_id and not failed:
        started = time.monotonic()
        try:
            smoke_client.request("GET", f"/api/web/admin/devices/{urllib.parse.quote(device_id)}/updates")
            steps.append(_step("update_recommendation", "success", started))
        except HttpStepError as exc:
            fail_fast("update_recommendation", f"HTTP {exc.status}: {exc}", started)

    if create_test_ticket and not failed:
        started = time.monotonic()
        if not device_id:
            fail_fast("ticket_create_optional", "--create-test-ticket requires --device-id", started)
        else:
            try:
                response = smoke_client.request(
                    "POST",
                    "/api/tickets/create",
                    {
                        "device_id": device_id,
                        "title": "Business smoke test ticket",
                        "description": "Automated business smoke test ticket. Safe to close after validation.",
                        "user_display_name": "business-smoke",
                        "urgency": "low",
                        "importance": "low",
                    },
                )
                payload = _response_payload(response)
                created_ticket_id = str(_nested(payload, "ticket", "ticket_id") or "").strip() or None
                if not created_ticket_id:
                    raise HttpStepError(response.status, "ticket_id missing in create response")
                steps.append(_step("ticket_create_optional", "success", started))
            except HttpStepError as exc:
                fail_fast("ticket_create_optional", f"HTTP {exc.status}: {exc}", started)

    if created_ticket_id and not failed:
        started = time.monotonic()
        try:
            smoke_client.request("GET", f"/api/web/support/tickets/{urllib.parse.quote(created_ticket_id)}/workspace")
            steps.append(_step("support_queue_action", "success", started))
        except HttpStepError as exc:
            fail_fast("support_queue_action", f"HTTP {exc.status}: {exc}", started)

    if run_safe_tool and not failed:
        started = time.monotonic()
        if run_safe_tool != "inventory.collect":
            fail_fast("safe_tool_inventory_collect", "only inventory.collect is allowed by this first-cut smoke", started)
        elif not created_ticket_id:
            fail_fast("safe_tool_inventory_collect", "--run-safe-tool requires --create-test-ticket in this first cut", started)
        else:
            try:
                response = smoke_client.request(
                    "POST",
                    f"/api/web/support/tickets/{urllib.parse.quote(created_ticket_id)}/tools/run",
                    {"tool_name": run_safe_tool, "preset_id": None, "params": {}},
                )
                payload = _response_payload(response)
                safe_tool_operation_id = str(
                    _nested(payload, "data", "operation_id") or payload.get("operation_id") or ""
                ).strip() or None
                if not safe_tool_operation_id:
                    raise HttpStepError(response.status, "operation_id missing in tool response")
                steps.append(_step("safe_tool_inventory_collect", "success", started))
            except HttpStepError as exc:
                fail_fast("safe_tool_inventory_collect", f"HTTP {exc.status}: {exc}", started)

    if safe_tool_operation_id and operation_wait_seconds > 0 and not failed:
        started = time.monotonic()
        deadline = time.monotonic() + operation_wait_seconds
        last_status = "unknown"
        try:
            while True:
                response = smoke_client.request("GET", f"/api/operations/{urllib.parse.quote(safe_tool_operation_id)}")
                payload = _response_payload(response)
                last_status = str(_nested(payload, "operation", "status") or payload.get("status") or "unknown")
                if last_status in {"succeeded", "failed", "timed_out", "cancelled", "canceled", "waiting_consent"}:
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(min(0.5, max(0.05, deadline - time.monotonic())))
            if last_status in {"succeeded", "waiting_consent"}:
                steps.append(_step("operation_result_check", "success", started))
            else:
                fail_fast("operation_result_check", f"operation status={last_status}", started)
        except HttpStepError as exc:
            fail_fast("operation_result_check", f"HTTP {exc.status}: {exc}", started)

    payload = {
        "status": "failed" if failed else "success",
        "started_at": started_at,
        "finished_at": _now(),
        "base_url": base_url,
        "steps": steps,
        "artifact": None,
    }
    if created_ticket_id:
        payload["created_ticket_id"] = created_ticket_id
    if safe_tool_operation_id:
        payload["safe_tool_operation_id"] = safe_tool_operation_id
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
    parser.add_argument("--insecure-tls", action="store_true", help="Allow self-signed HTTPS certificates for stand smoke.")
    parser.add_argument("--browser-check", action="store_true")
    parser.add_argument("--create-test-ticket", action="store_true")
    parser.add_argument("--run-safe-tool", choices=("inventory.collect",))
    parser.add_argument("--operation-wait-seconds", type=float, default=0.0)
    parser.add_argument("--check-update-recommendation", action="store_true")
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
        insecure_tls=True if args.insecure_tls else None,
        browser_check=args.browser_check,
        device_id=None if args.skip_agent_step else args.device_id,
        create_test_ticket=args.create_test_ticket,
        run_safe_tool=args.run_safe_tool,
        operation_wait_seconds=args.operation_wait_seconds,
        check_update_recommendation=args.check_update_recommendation,
    )
    print(json.dumps({"status": payload["status"], "output": str(args.output)}, ensure_ascii=False))
    if payload["status"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
