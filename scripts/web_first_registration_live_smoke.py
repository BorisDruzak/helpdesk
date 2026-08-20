from __future__ import annotations

import argparse
import asyncio
import http.cookiejar
import json
import ssl
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib import error, parse, request

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.db import get_session, init_db, shutdown_db
from app.db.models import Device, RegistryDepartment, RegistryLocation, UiUser
from auth.service import AuthService
from config import DATABASE_URL


SECRET_KEY_PARTS = ("authorization", "cookie", "password", "secret", "token", "pairing_code", "manual_code")


class SmokeFailure(RuntimeError):
    pass


def _now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    return completed.stdout.strip() or None


def _origin(url: str) -> str:
    parsed = parse.urlsplit(url)
    return parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def sanitize_for_report(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower().replace("-", "_")
            if any(part in lowered for part in SECRET_KEY_PARTS):
                result[str(key)] = "<redacted>"
            else:
                result[str(key)] = sanitize_for_report(item)
        return result
    if isinstance(value, list):
        return [sanitize_for_report(item) for item in value]
    return value


def _json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    text = raw.decode("utf-8", errors="replace")
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"non-JSON response from {response.geturl()}: {text[:500]}") from exc


class HttpClient:
    def __init__(self, *, base_url: str, insecure_tls: bool, token: str | None = None, cookies: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.origin = _origin(self.base_url)
        self.token = token
        handlers: list[Any] = []
        if self.base_url.startswith("https://"):
            context = ssl._create_unverified_context() if insecure_tls else ssl.create_default_context()
            handlers.append(request.HTTPSHandler(context=context))
        self.cookie_jar: http.cookiejar.CookieJar | None = http.cookiejar.CookieJar() if cookies else None
        if self.cookie_jar is not None:
            handlers.append(request.HTTPCookieProcessor(self.cookie_jar))
        self.opener = request.build_opener(*handlers)

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expect_success: bool = True,
    ) -> dict[str, Any]:
        method = method.upper()
        request_headers = {"Accept": "application/json", **(headers or {})}
        if self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if self.cookie_jar is not None and method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            request_headers.setdefault("Origin", self.origin)
        req = request.Request(f"{self.base_url}{path}", data=data, headers=request_headers, method=method)
        try:
            with self.opener.open(req, timeout=45) as response:
                body = _json_response(response)
                status = int(getattr(response, "status", 200))
                response_headers = dict(response.headers.items())
        except error.HTTPError as exc:
            body = _json_response(exc)
            status = exc.code
            response_headers = dict(exc.headers.items())
            if expect_success:
                raise SmokeFailure(f"{method} {path} failed with HTTP {status}: {sanitize_for_report(body)}") from exc
        except error.URLError as exc:
            raise SmokeFailure(f"{method} {path} failed: {exc}") from exc
        if expect_success and body.get("status") not in {"success", "ok"}:
            raise SmokeFailure(f"{method} {path} returned non-success payload: {sanitize_for_report(body)}")
        return {"http_status": status, "headers": response_headers, "body": body}

    def data(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        body = self.request(method, path, **kwargs)["body"]
        if body.get("status") == "success":
            return body.get("data") or {}
        return {key: value for key, value in body.items() if key != "status"}


async def _seed_reference_data(run_id: str) -> dict[str, str]:
    auth = AuthService(SimpleNamespace(users={}))
    admin_login = f"webfirst-admin-{run_id}"
    admin_token = await auth.generate_ui_token(admin_login, "admin", expires_hours=4)
    support_login = f"webfirst-support-{run_id}"
    support_token = await auth.generate_ui_token(support_login, "support", expires_hours=4)
    device_id = str(uuid.uuid4())
    agent_token = await auth.generate_agent_token(
        device_id=device_id,
        expires_hours=4,
        replace_existing=True,
        max_active_tokens=20,
    )
    suffix = run_id[-12:]
    user_department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())

    async with get_session() as session:
        session.add_all(
            [
                UiUser(user_login=admin_login, password_hash="live-smoke", actor_role="admin", is_active=True),
                UiUser(user_login=support_login, password_hash="live-smoke", actor_role="support", is_active=True),
                RegistryDepartment(
                    department_id=user_department_id,
                    code=f"webfirst-user-{suffix}",
                    name=f"Web First User Department {suffix}",
                    status="active",
                    source="live_smoke",
                    metadata_json={},
                ),
                RegistryLocation(
                    location_id=location_id,
                    building=f"Web First Building {suffix}",
                    floor="1",
                    room="101",
                    display_name=f"Web First Building {suffix} / 101",
                    status="active",
                    source="live_smoke",
                    metadata_json={},
                ),
            ]
        )
        device = await session.get(Device, device_id)
        _require(device is not None, "agent token did not create device placeholder")
        device.protocol_version = "ws_ticket_v3"
        device.agent_version = "web-first-live-smoke"
        device.hostname = f"webfirst-{suffix}"
        device.os = "Windows live smoke"
        device.capabilities = {"protocol_v3": True, "web_first_registration_live_smoke": True}
        device.device_metadata = {"web_first_registration_run_id": run_id}
        device.last_seen_at = datetime.now(timezone.utc)
        device.last_handshake_at = device.last_seen_at

        await session.commit()

    return {
        "admin_login": admin_login,
        "admin_token": admin_token,
        "support_login": support_login,
        "support_token": support_token,
        "device_id": device_id,
        "agent_token": agent_token,
        "department_id": user_department_id,
        "location_id": location_id,
    }


class WebFirstRegistrationLiveSmoke:
    def __init__(self, *, base_url: str, run_id: str, insecure_tls: bool) -> None:
        self.base_url = base_url
        self.run_id = run_id
        self.insecure_tls = insecure_tls
        self.report: dict[str, Any] = {
            "phase": "web_first_registration_live_smoke",
            "status": "pending",
            "run_id": run_id,
            "base_url": base_url,
            "commit": _git_commit(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checks": {},
            "created": {},
        }
        self.seed: dict[str, str] = {}

    async def setup(self) -> None:
        await init_db(DATABASE_URL)
        self.seed = await _seed_reference_data(self.run_id)
        self.report["created"].update(self.seed)

    async def close(self) -> None:
        await shutdown_db()

    def run_http_flow(self) -> None:
        user_login = f"webfirst-user-{self.run_id}@example.test"
        password = f"Wf{uuid.uuid4().hex[:12]}!"
        user = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, cookies=True)
        anon = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, cookies=True)
        admin = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, token=self.seed["admin_token"])
        agent = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, token=self.seed["agent_token"])

        escalation = anon.request(
            "POST",
            "/api/web/session/register",
            payload={
                "login": f"webfirst-escalate-{self.run_id}",
                "password": password,
                "password_repeat": password,
                "actor_role": "admin",
            },
            expect_success=False,
        )
        if escalation["http_status"] == 403 and escalation["body"].get("error_code") == "SELF_REGISTRATION_DISABLED":
            raise SmokeFailure("WEB_SELF_REGISTRATION_ENABLED is not enabled on the target server")
        _require(escalation["http_status"] == 400, "self-registration accepted actor_role escalation payload")
        self.report["checks"]["role_escalation_rejected"] = escalation["body"].get("error_code")

        register = user.request(
            "POST",
            "/api/web/session/register",
            payload={"login": user_login, "password": password, "password_repeat": password},
            expect_success=False,
        )
        if register["http_status"] == 403 and register["body"].get("error_code") == "SELF_REGISTRATION_DISABLED":
            raise SmokeFailure("WEB_SELF_REGISTRATION_ENABLED is not enabled on the target server")
        _require(register["http_status"] == 201, f"registration failed: {sanitize_for_report(register['body'])}")
        data = register["body"].get("data") or {}
        _require(data.get("actor_role") == "user", "registered account role is not user")
        _require("Set-Cookie" not in register["headers"], "registration issued a web session cookie")
        self.report["checks"]["registered_role"] = data.get("actor_role")
        self.report["checks"]["register_set_cookie"] = False

        me_before_login = user.request("GET", "/api/web/session/me")
        _require(me_before_login["body"].get("data") is None, "registration auto-logged the new user in")
        self.report["checks"]["no_auto_login"] = True

        login = user.data("POST", "/api/web/session/login", payload={"login": user_login, "password": password})
        _require(login.get("actor_role") == "user", "login did not return user actor role")
        bootstrap_before = user.data("GET", "/api/web/requester/bootstrap")
        completion_before = bootstrap_before.get("profile_completion") or {}
        _require(completion_before.get("blocks", {}).get("ticket_create") is True, "incomplete profile did not block ticket create")
        _require(bool(completion_before.get("missing_fields")), "incomplete profile did not expose missing_fields")

        profile = user.data(
            "PUT",
            "/api/web/requester/profile",
            payload={
                "full_name": f"Web First User {self.run_id}",
                "department_id": self.seed["department_id"],
                "location_id": self.seed["location_id"],
                "phone": "1001",
                "position": "Requester",
                "workplace_label": "Live smoke workplace",
            },
        )
        completion_after = profile.get("profile_completion") or {}
        _require(completion_after.get("complete") is True, "profile completion did not become complete")

        pairing = agent.data("POST", "/api/registry/agent/browser-pairings", payload={"purpose": "registration"})
        pairing_id = str(pairing.get("pairing_id") or "")
        _require(pairing_id, "agent pairing did not return pairing_id")
        _require(bool(str(pairing.get("pairing_code") or "").strip()), "agent pairing did not return visible pairing code")
        claim = user.data("POST", f"/api/web/registry/browser-pairings/{pairing_id}/registration/confirm", payload={})
        claim_id = str(claim.get("claim_id") or "")
        _require(claim_id, "registration pairing did not create claim")
        agent_pickup = agent.data("GET", f"/api/registry/agent/browser-pairings/{pairing_id}")
        _require(agent_pickup.get("status") == "consumed", "agent did not observe consumed registration pairing")

        approved = admin.data("POST", f"/api/web/admin/registry/registrations/{claim_id}/approve", payload={})
        binding = approved.get("binding") or {}
        binding_id = str(binding.get("binding_id") or "")
        _require(binding_id, "admin approval did not create binding")
        state = agent.data("GET", "/api/registry/agent/account-state")
        accounts = state.get("accounts") or []
        _require(any(item.get("account_mode") == "confirmed_binding" for item in accounts), "agent does not see linked state")

        bootstrap_after = user.data("GET", "/api/web/requester/bootstrap")
        _require(any(item.get("device_id") == self.seed["device_id"] for item in bootstrap_after.get("devices") or []), "requester does not see linked device")
        ticket = user.data(
            "POST",
            "/api/web/requester/tickets",
            payload={
                "device_id": self.seed["device_id"],
                "title": f"Web-first live smoke {self.run_id}",
                "description": "Clean web-first registration smoke ticket",
            },
        )
        ticket_id = str(ticket.get("ticket_id") or "")
        _require(ticket_id, "requester ticket was not created")

        self.report["created"].update(
            {
                "user_login": user_login,
                "claim_id": claim_id,
                "binding_id": binding_id,
                "ticket_id": ticket_id,
            }
        )
        self.report["checks"].update(
            {
                "profile_blocks_before_completion": True,
                "profile_missing_fields_preserved": True,
                "profile_complete_after_update": True,
                "pairing_code_returned_to_agent": True,
                "admin_approval_created_binding": True,
                "agent_linked_state_seen": True,
                "ticket_created": True,
            }
        )

    async def run(self) -> dict[str, Any]:
        try:
            await self.setup()
            self.run_http_flow()
            self.report["status"] = "passed"
        except Exception as exc:
            self.report["status"] = "failed"
            self.report["error"] = str(exc)
            raise
        finally:
            await self.close()
        return self.report


def default_output(run_id: str) -> Path:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return REPO_ROOT / "artifacts" / "browser_live_validation" / f"web-first-registration-live-{day}" / f"{run_id}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a production-style web-first registration smoke.")
    parser.add_argument("--base-url", default="https://example.test:9443")
    parser.add_argument("--run-id", default=f"webfirst-{_now_slug()}-{uuid.uuid4().hex[:6]}")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--insecure-tls", action="store_true")
    return parser.parse_args()


async def amain() -> int:
    args = parse_args()
    output = args.output or default_output(args.run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    smoke = WebFirstRegistrationLiveSmoke(base_url=args.base_url, run_id=args.run_id, insecure_tls=args.insecure_tls)
    report: dict[str, Any]
    try:
        report = await smoke.run()
    except Exception:
        report = smoke.report
        output.write_text(json.dumps(sanitize_for_report(report), ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    output.write_text(json.dumps(sanitize_for_report(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"web-first registration live smoke: {report['status']} -> {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(amain()))
    except SmokeFailure as exc:
        print(f"web-first registration live smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
