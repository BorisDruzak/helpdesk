from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
from urllib import error, parse, request
import uuid

from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.db import get_session, init_db, shutdown_db
from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceUserBinding,
    KnowledgeAudienceRule,
    RegistryDepartment,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
    TicketQueue,
    TicketQueueMember,
    UiUser,
)
from app.repos.knowledge_repo import KnowledgeRepo
from auth.service import AuthService
from config import DATABASE_URL
from knowledge.ask_service import KnowledgeAskService
from knowledge.search_service import KnowledgeSearchService
from knowledge.suggestion_service import KnowledgeSuggestionService
from registry.account_session_service import AccountSessionService
from registry.effective_identity_service import EffectiveIdentityService
from registry.registration_service import RegistrationService


class SmokeFailure(RuntimeError):
    pass


SECRET_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "pairing_code",
    "manual_code",
    "access_code",
)


def _now_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"non-JSON response from {response.geturl()}: {text[:500]}") from exc


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


def sanitize_for_report(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower().replace("-", "_")
            if any(part in lowered for part in SECRET_KEY_PARTS):
                sanitized[key_text] = "<redacted>"
            else:
                sanitized[key_text] = sanitize_for_report(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_report(item) for item in value]
    return value


def default_output_path(*, run_id: str, today: str | None = None) -> Path:
    day = today or _today()
    return REPO_ROOT / "artifacts" / f"registry-visibility-foundation-{day}" / f"registry-visibility-live-smoke-{run_id}.json"


def build_initial_report(*, run_id: str, base_url: str, commit: str | None) -> dict[str, Any]:
    return {
        "phase": "phase7_registry_visibility",
        "status": "pending",
        "run_id": run_id,
        "base_url": base_url,
        "commit": commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "marker": f"phase7 registry visibility {run_id}",
        "evidence": {
            "http_db_smoke": {"status": "pending"},
            "real_agent_gui": {
                "status": "not_collected",
                "required_for_phase7_exit": True,
            },
            "browser_support_ui": {"status": "not_collected"},
        },
        "scenarios": {
            "registered_owner": {"status": "pending"},
            "verified_other_account": {"status": "pending"},
            "registration_pending": {"status": "pending"},
            "revoked_session": {"status": "pending"},
        },
        "limitations": [
            "This HTTP/DB smoke does not replace real-agent UIA/browser evidence required by Phase 7 exit criteria.",
        ],
        "created": {},
        "checks": {},
    }


def person_id_from_effective_identity(identity: Any) -> str | None:
    person = getattr(identity, "person", None)
    if isinstance(person, dict):
        value = str(person.get("person_id") or "").strip()
        return value or None
    if isinstance(identity, dict):
        person = identity.get("person")
        if isinstance(person, dict):
            value = str(person.get("person_id") or "").strip()
            return value or None
    value = str(getattr(identity, "person_id", "") or "").strip()
    return value or None


class ApiClient:
    def __init__(self, *, base_url: str, token: str, insecure_tls: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        context = ssl._create_unverified_context() if insecure_tls else ssl.create_default_context()
        self.opener = request.build_opener(request.HTTPSHandler(context=context))

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expect_success: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode({k: v for k, v in query.items() if v is not None})}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token or self.token}",
            **(headers or {}),
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with self.opener.open(req, timeout=45) as response:
                body = _json_response(response)
                status = int(getattr(response, "status", 200))
        except error.HTTPError as exc:
            body = _json_response(exc)
            status = exc.code
            if expect_success:
                raise SmokeFailure(f"{method} {path} failed with HTTP {status}: {sanitize_for_report(body)}") from exc
        except error.URLError as exc:
            raise SmokeFailure(f"{method} {path} failed: {exc}") from exc
        if expect_success and body.get("status") not in {"success", "ok"}:
            raise SmokeFailure(f"{method} {path} returned non-success payload: {sanitize_for_report(body)}")
        return {"http_status": status, "body": body}

    def data(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        body = self.request(method, path, **kwargs)["body"]
        return body.get("data") or {key: value for key, value in body.items() if key != "status"}

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.data("GET", path, **kwargs)

    def post(self, path: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        return self.data("POST", path, payload=payload or {}, **kwargs)


class RegistryVisibilityLiveSmoke:
    def __init__(self, *, base_url: str, run_id: str, insecure_tls: bool) -> None:
        self.base_url = base_url
        self.run_id = run_id
        self.insecure_tls = insecure_tls
        self.reason = f"registry visibility live smoke {run_id}"
        self.report = build_initial_report(run_id=run_id, base_url=base_url, commit=_git_commit())
        self.tokens: dict[str, str] = {}
        self.agent_tokens: dict[str, str] = {}
        self.ids: dict[str, str] = {}
        self.admin_api: ApiClient | None = None

    @property
    def api(self) -> ApiClient:
        _require(self.admin_api is not None, "admin api is not initialized")
        return self.admin_api

    async def setup(self) -> None:
        await init_db(DATABASE_URL)
        auth = AuthService(SimpleNamespace(users={}))
        logins = {
            "admin": f"phase7-admin-{self.run_id}",
            "support": f"phase7-support-{self.run_id}",
            "owner": f"phase7-owner-{self.run_id}",
            "other": f"phase7-other-{self.run_id}",
            "pending": f"phase7-pending-{self.run_id}",
        }
        self.tokens = {
            key: await auth.generate_ui_token(login, "admin" if key == "admin" else "support" if key == "support" else "user", expires_hours=2)
            for key, login in logins.items()
        }
        self.ids.update({f"{key}_login": login for key, login in logins.items()})
        device_ids = {
            "owner_device_id": str(uuid.uuid4()),
            "pending_device_id": str(uuid.uuid4()),
        }
        for key, device_id in device_ids.items():
            self.agent_tokens[key] = await auth.generate_agent_token(
                device_id=device_id,
                expires_hours=2,
                replace_existing=True,
                max_active_tokens=20,
            )
        self.ids.update(device_ids)
        await self._seed_devices()
        self.admin_api = ApiClient(base_url=self.base_url, token=self.tokens["admin"], insecure_tls=self.insecure_tls)
        await self._seed_identity_and_knowledge()

    async def close(self) -> None:
        await shutdown_db()

    async def _seed_devices(self) -> None:
        async with get_session() as session:
            now = datetime.now(timezone.utc)
            for key in ("owner_device_id", "pending_device_id"):
                device = await session.get(Device, self.ids[key])
                _require(device is not None, f"device stub missing for {key}")
                device.protocol_version = "ws_ticket_v3"
                device.agent_version = "registry-visibility-smoke"
                device.hostname = f"phase7-{key}-{self.run_id}"
                device.os = "Windows 11 smoke"
                device.capabilities = {"protocol_v3": True, "registry_visibility_smoke": True}
                device.device_metadata = {"registry_visibility_run_id": self.run_id}
                device.last_seen_at = now
                device.last_handshake_at = now
            await session.commit()

    async def _seed_identity_and_knowledge(self) -> None:
        async with get_session() as session:
            for key, role in (("admin", "admin"), ("support", "support"), ("owner", "user"), ("other", "user"), ("pending", "user")):
                session.add(UiUser(user_login=self.ids[f"{key}_login"], password_hash="live-smoke", actor_role=role, is_active=True))
            it_department = RegistryDepartment(
                department_id=str(uuid.uuid4()),
                code=f"phase7-it-{self.run_id}",
                name=f"Phase 7 IT {self.run_id}",
                status="active",
                source="live_smoke",
            )
            finance_department = RegistryDepartment(
                department_id=str(uuid.uuid4()),
                code=f"phase7-finance-{self.run_id}",
                name=f"Phase 7 Finance {self.run_id}",
                status="active",
                source="live_smoke",
            )
            owner = RegistryPerson(
                person_id=str(uuid.uuid4()),
                display_name=f"Phase 7 IT Owner {self.run_id}",
                email=f"{self.ids['owner_login']}@live-smoke.test",
                department_id=it_department.department_id,
                source="live_smoke",
                status="active",
            )
            other = RegistryPerson(
                person_id=str(uuid.uuid4()),
                display_name=f"Phase 7 Finance Other {self.run_id}",
                email=f"{self.ids['other_login']}@live-smoke.test",
                department_id=finance_department.department_id,
                source="live_smoke",
                status="active",
            )
            pending = RegistryPerson(
                person_id=str(uuid.uuid4()),
                display_name=f"Phase 7 Pending {self.run_id}",
                email=f"{self.ids['pending_login']}@live-smoke.test",
                department_id=it_department.department_id,
                source="live_smoke",
                status="active",
            )
            session.add_all([it_department, finance_department, owner, other, pending])
            for key, person in (("owner", owner), ("other", other), ("pending", pending)):
                session.add(
                    RegistryPersonIdentity(
                        person_id=person.person_id,
                        provider="ui_login",
                        identifier=self.ids[f"{key}_login"],
                        normalized_identifier=self.ids[f"{key}_login"],
                        verified=True,
                        source="live_smoke",
                    )
                )
                session.add(
                    RegistryPersonIdentity(
                        person_id=person.person_id,
                        provider="email",
                        identifier=person.email,
                        normalized_identifier=str(person.email or "").lower(),
                        verified=True,
                        source="live_smoke",
                    )
                )
            queue = TicketQueue(code=f"phase7-visibility-{self.run_id}", name=f"Phase 7 Visibility {self.run_id}", is_active=True)
            session.add(queue)
            await session.flush()
            session.add(TicketQueueMember(queue_id=queue.id, actor_id=self.ids["support_login"], role_in_queue="operator"))
            repo = KnowledgeRepo(session)
            space_code = f"phase7-visibility-{self.run_id}"
            await repo.upsert_space(
                {"code": space_code, "title": f"Phase 7 Visibility {self.run_id}", "visibility": "requester", "lifecycle_status": "active"},
                actor_id=self.ids["admin_login"],
            )
            public_item = await self._published_item(repo, space_code, "public", "public visible", "public body", "requester")
            it_item = await self._published_item(repo, space_code, "it", "IT scoped", "IT body", "requester")
            finance_item = await self._published_item(repo, space_code, "finance", "Finance scoped", "finance hidden body", "requester")
            internal_item = await self._published_item(repo, space_code, "internal", "support internal runbook", "internal body", "support_internal", item_type="runbook")
            session.add_all(
                [
                    KnowledgeAudienceRule(
                        rule_id=str(uuid.uuid4()),
                        subject_type="item",
                        subject_id=it_item["item_id"],
                        target_type="department",
                        target_id=it_department.department_id,
                        effect="allow",
                        status="active",
                    ),
                    KnowledgeAudienceRule(
                        rule_id=str(uuid.uuid4()),
                        subject_type="item",
                        subject_id=finance_item["item_id"],
                        target_type="department",
                        target_id=finance_department.department_id,
                        effect="allow",
                        status="active",
                    ),
                ]
            )
            await session.commit()
            self.ids.update(
                {
                    "it_department_id": it_department.department_id,
                    "finance_department_id": finance_department.department_id,
                    "owner_person_id": owner.person_id,
                    "other_person_id": other.person_id,
                    "pending_person_id": pending.person_id,
                    "queue_id": str(queue.id),
                    "public_slug": public_item["slug"],
                    "it_slug": it_item["slug"],
                    "finance_slug": finance_item["slug"],
                    "internal_slug": internal_item["slug"],
                    "finance_item_id": finance_item["item_id"],
                }
            )

    async def _published_item(
        self,
        repo: KnowledgeRepo,
        space_code: str,
        label: str,
        title_label: str,
        body_label: str,
        visibility: str,
        *,
        item_type: str = "article",
    ) -> dict[str, Any]:
        title = f"{self.report['marker']} {title_label}"
        item = await repo.create_item_draft(
            {
                "space_code": space_code,
                "slug": f"phase7-{label}-{self.run_id}",
                "item_type": item_type,
                "title": title,
                "summary": title,
                "visibility": visibility,
                "owner_actor_id": self.ids["admin_login"],
                "reviewer_actor_id": self.ids["admin_login"],
            },
            actor_id=self.ids["admin_login"],
            actor_role="admin",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": title, "body_format": "markdown", "body": f"{self.report['marker']} {body_label}"},
            actor_id=self.ids["admin_login"],
            actor_role="admin",
        )
        return await repo.publish_item(item["item_id"], version["version_id"], actor_id=self.ids["admin_login"], actor_role="admin")

    def _agent_token(self, key: str = "owner_device_id") -> str:
        return self.agent_tokens[key]

    async def run(self) -> dict[str, Any]:
        await self.setup()
        try:
            owner_session = await self._scenario_registered_owner()
            other_session = await self._scenario_verified_other_account(owner_session)
            await self._scenario_registration_pending()
            await self._scenario_revoked_session(other_session)
            self.report["status"] = "passed"
            self.report["evidence"]["http_db_smoke"]["status"] = "passed"
            self.report["created"] = {
                key: self.ids[key]
                for key in sorted(self.ids)
                if key.endswith("_slug") or key in {"owner_ticket_id", "other_ticket_id"}
            }
            return sanitize_for_report(self.report)
        except Exception as exc:
            self.report["status"] = "failed"
            self.report["error"] = str(exc)
            return sanitize_for_report(self.report)
        finally:
            await self.close()

    async def _scenario_registered_owner(self) -> dict[str, str]:
        binding = self.api.post(
            f"/api/web/admin/registry/devices/{self.ids['owner_device_id']}/bind-person",
            {
                "person_id": self.ids["owner_person_id"],
                "relationship_type": "primary_user",
                "replace_existing": False,
                "reason": self.reason,
            },
        )["binding"]
        account = self.api.post(
            "/api/registry/agent/account-sessions/confirmed-binding",
            {"binding_id": binding["binding_id"]},
            token=self._agent_token(),
        )
        session_id = account["session"]["session_id"]
        session_token = account["session_token"]
        validation = self.api.post(
            f"/api/registry/agent/account-sessions/{session_id}/validate",
            {"session_token": session_token},
            token=self._agent_token(),
        )
        _require(validation.get("valid") is True, "confirmed owner account session did not validate")
        ticket = self._create_agent_ticket(
            title=f"{self.report['marker']} owner ticket",
            description=f"{self.report['marker']} owner ticket needs IT knowledge",
            session_id=session_id,
            session_token=session_token,
        )
        self.ids["owner_ticket_id"] = ticket["ticket"]["ticket_id"]
        await self._assign_ticket_to_support(self.ids["owner_ticket_id"])
        agent_list = self.api.get(
            "/api/tickets",
            token=self._agent_token(),
            query={"account_session_id": session_id},
            headers={"X-Account-Session-Token": session_token},
        )
        listed_ids = {str(item.get("ticket", {}).get("ticket_id") or "") for item in agent_list.get("tickets") or []}
        _require(self.ids["owner_ticket_id"] in listed_ids, "confirmed owner agent ticket list missing own ticket")
        service_check = await self._check_service_knowledge_for_session(
            session_id=session_id,
            session_token=session_token,
            expected_slug=self.ids["it_slug"],
            hidden_slug=self.ids["finance_slug"],
        )
        support_check = self._check_support_suggestions(self.ids["owner_ticket_id"], expected_slug=self.ids["it_slug"], hidden_slug=self.ids["finance_slug"])
        self.report["scenarios"]["registered_owner"] = {
            "status": "passed",
            "account_mode": account["session"]["account_mode"],
            "ticket_id": self.ids["owner_ticket_id"],
            "service_knowledge": service_check,
            "support_suggestions": support_check,
        }
        return {"session_id": session_id, "session_token": session_token, "binding_id": binding["binding_id"]}

    async def _scenario_verified_other_account(self, owner_session: dict[str, str]) -> dict[str, str]:
        request_payload = self.api.post(
            "/api/registry/agent/account-login-requests",
            {
                "login": self.ids["other_login"],
                "email": f"{self.ids['other_login']}@live-smoke.test",
                "full_name": f"Phase 7 Finance Other {self.run_id}",
                "phone": "+70000000000",
                "reason": self.reason,
            },
            token=self._agent_token(),
        )
        request_id = request_payload["request_id"]
        approved = self.api.post(f"/api/web/admin/registry/account-login-requests/{request_id}/approve", {"reason": self.reason})
        _require(approved["request"]["status"] == "approved", "other-account login request was not approved")
        pickup = self.api.get(f"/api/registry/agent/account-login-requests/{request_id}", token=self._agent_token())
        session = pickup.get("session") or {}
        session_id = session.get("session_id")
        session_token = pickup.get("session_token")
        _require(session.get("account_mode") == "verified_other_account", "approved request did not create verified_other_account session")
        _require(bool(session_token), "approved other-account session token was not returned on pickup")
        other_ticket = self._create_agent_ticket(
            title=f"{self.report['marker']} other-account ticket",
            description=f"{self.report['marker']} other-account ticket needs Finance knowledge",
            session_id=session_id,
            session_token=session_token,
        )
        self.ids["other_ticket_id"] = other_ticket["ticket"]["ticket_id"]
        await self._assign_ticket_to_support(self.ids["other_ticket_id"])
        agent_list = self.api.get(
            "/api/tickets",
            token=self._agent_token(),
            query={"account_session_id": session_id},
            headers={"X-Account-Session-Token": session_token},
        )
        listed_ids = {str(item.get("ticket", {}).get("ticket_id") or "") for item in agent_list.get("tickets") or []}
        _require(self.ids["other_ticket_id"] in listed_ids, "verified other-account list missing its own ticket")
        _require(self.ids["owner_ticket_id"] not in listed_ids, "verified other-account list leaked owner ticket")
        owner_detail = self.api.request(
            "GET",
            f"/api/tickets/{self.ids['owner_ticket_id']}",
            token=self._agent_token(),
            query={"account_session_id": session_id},
            headers={"X-Account-Session-Token": session_token},
            expect_success=False,
        )
        _require(owner_detail["http_status"] == 403, "verified other-account could open owner ticket")
        async with get_session() as db_session:
            row = await db_session.get(Ticket, self.ids["other_ticket_id"])
            _require(row is not None, "other-account ticket missing in DB")
            _require(row.requester_account_session_id == session_id, "other-account ticket session id not stored")
            _require(row.requester_account_mode == "verified_other_account", "other-account ticket mode not stored")
            _require(row.requester_account_warning == "ticket_created_from_other_account_on_registered_device", "other-account warning not stored")
            binding = await db_session.get(DeviceUserBinding, owner_session["binding_id"])
            _require(binding is not None and binding.person_id == self.ids["owner_person_id"] and binding.status == "active", "other-account mutated owner binding")
        service_check = await self._check_service_knowledge_for_session(
            session_id=session_id,
            session_token=session_token,
            expected_slug=self.ids["finance_slug"],
            hidden_slug=self.ids["it_slug"],
        )
        support_check = self._check_support_suggestions(self.ids["other_ticket_id"], expected_slug=self.ids["finance_slug"], hidden_slug=self.ids["it_slug"])
        self.report["scenarios"]["verified_other_account"] = {
            "status": "passed",
            "account_mode": session.get("account_mode"),
            "ticket_id": self.ids["other_ticket_id"],
            "owner_ticket_hidden": True,
            "warning_stored": True,
            "service_knowledge": service_check,
            "support_suggestions": support_check,
        }
        return {"session_id": session_id, "session_token": session_token}

    async def _scenario_registration_pending(self) -> None:
        async with get_session() as session:
            registration = await RegistrationService(session).submit_agent_profile_claim(
                device_id=self.ids["pending_device_id"],
                requester_id=self.ids["pending_login"],
                display_name=f"Phase 7 Pending {self.run_id}",
                profile={"full_name": f"Phase 7 Pending {self.run_id}", "email": f"{self.ids['pending_login']}@live-smoke.test"},
            )
            claim_id = registration["registration"]["claim_id"]
            await session.commit()
        pending = self.api.post(
            "/api/registry/agent/account-sessions/registration-pending",
            {"claim_id": claim_id},
            token=self._agent_token("pending_device_id"),
        )
        session_id = pending["session"]["session_id"]
        session_token = pending["session_token"]
        create_denied = self.api.request(
            "POST",
            "/api/tickets/create",
            token=self._agent_token("pending_device_id"),
            payload={
                "device_id": self.ids["pending_device_id"],
                "title": f"{self.report['marker']} pending denied",
                "description": "pending registration must not create normal ticket",
                "user_display_name": "Phase 7 Pending",
                "requester_account": {"session_id": session_id, "session_token": session_token},
            },
            expect_success=False,
        )
        _require(create_denied["http_status"] == 403, "registration_pending session created a normal ticket")
        state = self.api.get("/api/registry/agent/account-state", token=self._agent_token("pending_device_id"))
        accounts = state.get("accounts") or []
        _require(any(account.get("account_mode") == "registration_pending" for account in accounts), "account-state missing registration_pending session")
        self.report["scenarios"]["registration_pending"] = {
            "status": "passed",
            "claim_id": claim_id,
            "normal_ticket_blocked": True,
        }

    async def _scenario_revoked_session(self, other_session: dict[str, str]) -> None:
        revoked = self.api.post(
            f"/api/web/admin/registry/account-sessions/{other_session['session_id']}/revoke",
            {"reason": self.reason},
        )
        _require((revoked.get("session") or {}).get("verification_status") == "revoked", "admin revoke did not revoke session")
        validation = self.api.request(
            "POST",
            f"/api/registry/agent/account-sessions/{other_session['session_id']}/validate",
            token=self._agent_token(),
            payload={"session_token": other_session["session_token"]},
            expect_success=False,
        )
        _require(validation["http_status"] == 403, "revoked session still validates")
        list_denied = self.api.request(
            "GET",
            "/api/tickets",
            token=self._agent_token(),
            query={"account_session_id": other_session["session_id"]},
            headers={"X-Account-Session-Token": other_session["session_token"]},
            expect_success=False,
        )
        _require(list_denied["http_status"] == 403, "revoked session still lists tickets")
        self.report["scenarios"]["revoked_session"] = {
            "status": "passed",
            "account_session_id": other_session["session_id"],
            "validation_denied": True,
            "ticket_list_denied": True,
        }

    def _create_agent_ticket(self, *, title: str, description: str, session_id: str, session_token: str) -> dict[str, Any]:
        created = self.api.post(
            "/api/tickets/create",
            {
                "device_id": self.ids["owner_device_id"],
                "title": title,
                "description": description,
                "user_display_name": "Phase 7 Agent User",
                "requester_account": {"session_id": session_id, "session_token": session_token},
            },
            token=self._agent_token(),
        )
        _require(bool((created.get("ticket") or {}).get("ticket_id")), "agent ticket create did not return ticket_id")
        return created

    async def _assign_ticket_to_support(self, ticket_id: str) -> None:
        async with get_session() as session:
            ticket = await session.get(Ticket, ticket_id)
            _require(ticket is not None, f"ticket {ticket_id} missing before support assignment")
            ticket.queue_id = int(self.ids["queue_id"])
            ticket.assignee_id = self.ids["support_login"]
            await session.commit()

    async def _check_service_knowledge_for_session(self, *, session_id: str, session_token: str, expected_slug: str, hidden_slug: str) -> dict[str, Any]:
        async with get_session() as session:
            identity = await EffectiveIdentityService(session).resolve_account_session_identity(
                device_id=self.ids["owner_device_id"],
                session_id=session_id,
                session_token=session_token,
            )
            person_id = person_id_from_effective_identity(identity)
            _require(person_id is not None, "account session did not resolve to requester person")
            audience = await EffectiveIdentityService(session).resolve_person_audience(
                person_id=person_id,
                actor_id=identity.actor_id,
                actor_role="requester",
            )
            search_results = await KnowledgeSearchService(session).search(
                query=str(self.report["marker"]),
                actor_role="requester",
                limit=10,
                surface="phase7_live_smoke",
                effective_audience=audience,
            )
            suggest = await KnowledgeSuggestionService(session).suggest(
                {"query": str(self.report["marker"]), "limit": 10, "surface": "phase7_live_smoke"},
                actor_role="requester",
                effective_audience=audience,
            )
            ask = await KnowledgeAskService(session).ask(
                query=str(self.report["marker"]),
                actor_role="requester",
                effective_audience=audience,
            )
        search_slugs = {str(item.get("slug") or "") for item in search_results if isinstance(item, dict)}
        suggest_slugs = {str(item.get("slug") or "") for item in suggest.get("suggestions") or [] if isinstance(item, dict)}
        ask_slugs = {
            str(((item.get("item") or {}) if isinstance(item, dict) else {}).get("slug") or "")
            for item in ask.get("retrieval_results") or []
            if isinstance(item, dict)
        }
        for label, slugs in (("search", search_slugs), ("suggest", suggest_slugs), ("ask", ask_slugs)):
            _require(expected_slug in slugs, f"{label} missing expected scoped article {expected_slug}")
            _require(hidden_slug not in slugs, f"{label} leaked hidden article {hidden_slug}")
        rendered = json.dumps({"search": search_results, "suggest": suggest, "ask": ask}, ensure_ascii=False, sort_keys=True)
        _require(hidden_slug not in rendered, "hidden slug leaked into service knowledge payload")
        return {
            "status": "passed",
            "person_id": audience.person_id,
            "search_slugs": sorted(search_slugs),
            "suggest_slugs": sorted(suggest_slugs),
            "ask_slugs": sorted(ask_slugs),
        }

    def _check_support_suggestions(self, ticket_id: str, *, expected_slug: str, hidden_slug: str) -> dict[str, Any]:
        response = self.api.get(
            f"/api/web/support/tickets/{ticket_id}/knowledge-suggestions",
            token=self.tokens["support"],
        )
        article_ids = {str(item.get("id") or "") for item in response.get("articles") or [] if isinstance(item, dict)}
        _require(expected_slug in article_ids, f"support suggestions missing expected requester article {expected_slug}")
        _require(hidden_slug not in article_ids, f"support suggestions leaked hidden article {hidden_slug}")
        rendered = json.dumps(response, ensure_ascii=False, sort_keys=True)
        _require(hidden_slug not in rendered, "hidden slug leaked into support suggestions payload")
        return {"status": "passed", "article_ids": sorted(article_ids)}


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sanitize_for_report(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def async_main(args: argparse.Namespace) -> int:
    smoke = RegistryVisibilityLiveSmoke(base_url=args.base_url, run_id=args.run_id, insecure_tls=args.insecure_tls)
    report = await smoke.run()
    output = Path(args.output) if args.output else default_output_path(run_id=args.run_id)
    write_report(report, output)
    print(json.dumps(sanitize_for_report({**report, "output": str(output)}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") == "passed" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live Phase 7 Registry Visibility Foundation HTTP/DB smoke.")
    parser.add_argument("--base-url", default="https://192.168.100.17:9443")
    parser.add_argument("--run-id", default=_now_id())
    parser.add_argument("--output", default="")
    parser.add_argument("--insecure-tls", action="store_true")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(async_main(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
