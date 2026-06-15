from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (str(REPO_ROOT), str(SERVER_ROOT), str(SCRIPTS_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.db import get_session, init_db, shutdown_db
from app.db.models import Device, RegistryDepartment, RegistryLocation, RegistryPerson, RegistryPersonIdentity, UiUser
from auth.service import AuthService
from config import DATABASE_URL
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService
from web_first_registration_live_smoke import HttpClient, SmokeFailure, sanitize_for_report


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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


async def _seed_profile_context(session: Any, person: RegistryPerson, *, marker: str) -> None:
    suffix = uuid.uuid4().hex[:8]
    department_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    session.add_all(
        [
            RegistryDepartment(
                department_id=department_id,
                code=f"rollout-{marker[:14]}-{suffix}",
                name=f"Rollout Department {marker}",
                status="active",
                source="rollout_smoke",
                metadata_json={},
            ),
            RegistryLocation(
                location_id=location_id,
                building=f"Rollout Building {suffix}",
                floor="1",
                room="101",
                display_name=f"Rollout Building {suffix} / 101",
                status="active",
                source="rollout_smoke",
                metadata_json={},
            ),
        ]
    )
    person.department_id = department_id
    person.location_id = location_id
    person.phone = person.phone or "1001"


async def _approved_binding(session: Any, *, device_id: str, login: str) -> dict[str, Any]:
    service = RegistrationService(session)
    claim = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=login,
        display_name=f"Rollout Owner {login}",
        profile={"full_name": f"Rollout Owner {login}", "email": login, "login": login, "user_confirmed": True},
    )
    approved = await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="rollout-smoke")
    person = await session.get(RegistryPerson, approved["person"]["person_id"])
    _require(person is not None, "approved binding did not create person")
    await _seed_profile_context(session, person, marker=login.replace("@", "-")[:32])
    return approved


class WebFirstRegistrationRolloutSmoke:
    def __init__(self, *, base_url: str, run_id: str, insecure_tls: bool) -> None:
        self.base_url = base_url
        self.run_id = run_id
        self.insecure_tls = insecure_tls
        self.report: dict[str, Any] = {
            "phase": "web_first_registration_rollout_smoke",
            "status": "pending",
            "run_id": run_id,
            "base_url": base_url,
            "commit": _git_commit(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cases": {},
            "created": {},
        }
        self.ids: dict[str, str] = {}
        self.tokens: dict[str, str] = {}

    async def setup(self) -> None:
        await init_db(DATABASE_URL)
        auth = AuthService(SimpleNamespace(users={}))
        admin_login = f"rollout-admin-{self.run_id}"
        self.tokens["admin"] = await auth.generate_ui_token(admin_login, "admin", expires_hours=4)
        logins = {
            "no_profile": f"rollout-no-profile-{self.run_id}@example.test",
            "orphan_person": f"rollout-orphan-{self.run_id}@example.test",
            "active": f"rollout-active-{self.run_id}@example.test",
            "pending": f"rollout-pending-{self.run_id}@example.test",
            "other_owner": f"rollout-other-owner-{self.run_id}@example.test",
        }
        for key, login in logins.items():
            self.tokens[key] = await auth.generate_ui_token(login, "user", expires_hours=4)
            self.ids[f"{key}_login"] = login
        for key in ("active_device_id", "pending_device_id", "other_device_id"):
            self.ids[key] = str(uuid.uuid4())
        self.tokens["active_agent"] = await auth.generate_agent_token(
            self.ids["active_device_id"],
            expires_hours=4,
            replace_existing=True,
            max_active_tokens=20,
        )
        self.tokens["pending_agent"] = await auth.generate_agent_token(
            self.ids["pending_device_id"],
            expires_hours=4,
            replace_existing=True,
            max_active_tokens=20,
        )
        self.tokens["other_agent"] = await auth.generate_agent_token(
            self.ids["other_device_id"],
            expires_hours=4,
            replace_existing=True,
            max_active_tokens=20,
        )

        async with get_session() as session:
            session.add(UiUser(user_login=admin_login, password_hash="rollout-smoke", actor_role="admin", is_active=True))
            for login in logins.values():
                session.add(UiUser(user_login=login, password_hash="rollout-smoke", actor_role="user", is_active=True))

            orphan = RegistryPerson(
                person_id=str(uuid.uuid4()),
                full_name=f"Rollout Orphan {self.run_id}",
                display_name=f"Rollout Orphan {self.run_id}",
                email=logins["orphan_person"],
                status="active",
                source="rollout_smoke",
            )
            session.add(orphan)

            for key in ("active_device_id", "pending_device_id", "other_device_id"):
                device = await session.get(Device, self.ids[key])
                _require(device is not None, f"agent token placeholder was not created for {key}")
                device.protocol_version = "ws_ticket_v3"
                device.agent_version = "rollout-smoke"
                device.hostname = f"{key}-{self.run_id}"
                device.os = "Windows rollout smoke"
                device.capabilities = {"protocol_v3": True, "web_first_registration_rollout_smoke": True}
                device.device_metadata = {"web_first_registration_rollout_run_id": self.run_id}
                device.last_seen_at = datetime.now(timezone.utc)
                device.last_handshake_at = device.last_seen_at

            active = await _approved_binding(session, device_id=self.ids["active_device_id"], login=logins["active"])
            self.ids["active_binding_id"] = active["binding"]["binding_id"]

            pending_claim = await RegistrationService(session).submit_agent_profile_claim(
                device_id=self.ids["pending_device_id"],
                requester_id=logins["pending"],
                display_name="Rollout Pending User",
                profile={
                    "full_name": "Rollout Pending User",
                    "email": logins["pending"],
                    "login": logins["pending"],
                    "user_confirmed": True,
                },
            )
            self.ids["pending_claim_id"] = pending_claim["registration"]["claim_id"]

            other_binding = await _approved_binding(session, device_id=self.ids["other_device_id"], login=logins["other_owner"])
            self.ids["other_base_binding_id"] = other_binding["binding"]["binding_id"]
            other_request = await AccountSessionService(session).create_other_account_login_request(
                device_id=self.ids["other_device_id"],
                requested_account={
                    "full_name": "Rollout Other Account",
                    "display_name": "Rollout Other",
                    "login": f"rollout-other-{self.run_id}",
                    "email": f"rollout-other-{self.run_id}@example.test",
                    "phone": "1002",
                    "reason": "Rollout compatibility smoke",
                },
            )
            approved_other = await AccountSessionService(session).approve_login_request(
                other_request["request_id"],
                reviewed_by="rollout-smoke",
            )
            self.ids["other_session_id"] = approved_other["session"]["session_id"]
            await session.commit()
        self.report["created"].update(self.ids)

    async def close(self) -> None:
        await shutdown_db()

    def run_http_checks(self) -> None:
        admin = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, token=self.tokens["admin"])

        no_profile = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, token=self.tokens["no_profile"]).data(
            "GET",
            "/api/web/requester/bootstrap",
        )
        completion = no_profile.get("profile_completion") or {}
        _require(no_profile.get("profile") is None, "user without RegistryPerson unexpectedly resolved a profile")
        _require(bool(completion.get("missing_fields")), "user without RegistryPerson did not keep missing_fields")
        self.report["cases"]["user_without_registry_person"] = "passed"

        orphan = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, token=self.tokens["orphan_person"]).data(
            "GET",
            "/api/web/requester/bootstrap",
        )
        _require(orphan.get("profile") is None, "RegistryPerson without ui_login was incorrectly linked by email alone")
        self.report["cases"]["registry_person_without_ui_login"] = "passed"

        active_state = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, token=self.tokens["active_agent"]).data(
            "GET",
            "/api/registry/agent/account-state",
        )
        _require(
            any(item.get("binding_id") == self.ids["active_binding_id"] for item in active_state.get("accounts") or []),
            "active binding was not visible in agent account-state",
        )
        self.report["cases"]["active_binding"] = "passed"

        pending_bootstrap = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, token=self.tokens["pending"]).data(
            "GET",
            "/api/web/requester/bootstrap",
        )
        _require(
            any(item.get("claim_id") == self.ids["pending_claim_id"] for item in pending_bootstrap.get("pending_registration_claims") or []),
            "pending legacy claim was not visible to requester",
        )
        admin_registry = admin.data("GET", "/api/web/admin/registry")
        _require(
            any(item.get("claim_id") == self.ids["pending_claim_id"] for item in admin_registry.get("registration_claims") or []),
            "pending legacy claim was not visible to admin registry",
        )
        self.report["cases"]["pending_legacy_claim"] = "passed"

        other_state = HttpClient(base_url=self.base_url, insecure_tls=self.insecure_tls, token=self.tokens["other_agent"]).data(
            "GET",
            "/api/registry/agent/account-state",
        )
        _require(
            any(item.get("account_mode") == "verified_other_account" and item.get("session_id") == self.ids["other_session_id"] for item in other_state.get("accounts") or []),
            "verified other-account session was not visible in agent account-state",
        )
        self.report["cases"]["other_account_active_session"] = "passed"

    async def run(self) -> dict[str, Any]:
        try:
            await self.setup()
            self.run_http_checks()
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
    return REPO_ROOT / "artifacts" / "browser_live_validation" / f"web-first-registration-rollout-{day}" / f"{run_id}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run web-first registration rollout compatibility smoke against a DB copy.")
    parser.add_argument("--base-url", default="https://192.168.100.17:9443")
    parser.add_argument("--run-id", default=f"rollout-{_now_slug()}-{uuid.uuid4().hex[:6]}")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--insecure-tls", action="store_true")
    return parser.parse_args()


async def amain() -> int:
    args = parse_args()
    output = args.output or default_output(args.run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    smoke = WebFirstRegistrationRolloutSmoke(base_url=args.base_url, run_id=args.run_id, insecure_tls=args.insecure_tls)
    try:
        report = await smoke.run()
    except Exception:
        output.write_text(json.dumps(sanitize_for_report(smoke.report), ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    output.write_text(json.dumps(sanitize_for_report(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"web-first registration rollout smoke: {report['status']} -> {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(amain()))
    except SmokeFailure as exc:
        print(f"web-first registration rollout smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
