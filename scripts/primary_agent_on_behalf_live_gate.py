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
from urllib import error, request
import uuid

from sqlalchemy import func, select

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for import_path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from app.db import get_session, init_db, shutdown_db
from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceUserBinding,
    Operation,
    Playbook,
    PlaybookRun,
    PlaybookVersion,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
    TicketEvent,
    UiUser,
)
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from auth.password_service import hash_password
from auth.service import AuthService
from config import DATABASE_URL
from registry.account_session_service import AccountSessionService
from registry.registration_service import RegistrationService
from tickets.create_flow import create_ticket_with_side_effects


REQUIRED_SCENARIOS = (
    "normal_ticket_targets_creator_primary_agent",
    "on_behalf_ticket_targets_affected_primary_agent",
    "affected_primary_agent_offline_skips_module_enqueue",
    "gui_login_bound_user_success",
    "gui_login_wrong_user_mismatch_no_rebind",
    "admin_transfer_device_b_to_c_future_targets",
)

SECRET_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "session_token",
    "token",
)


class LiveGateFailure(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LiveGateFailure(message)


def _now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _git_commit() -> str:
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
        return "unknown"
    return completed.stdout.strip() or "unknown"


def default_evidence_dir(*, commit: str, day: str) -> Path:
    short_commit = (commit or "unknown")[:8]
    return Path("artifacts") / "browser_live_validation" / f"primary-agent-on-behalf-{short_commit}-{day}"


def sanitize_for_report(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower().replace("-", "_")
            if any(part in lowered for part in SECRET_KEY_PARTS):
                sanitized[str(key)] = "<redacted>"
            else:
                sanitized[str(key)] = sanitize_for_report(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_report(item) for item in value]
    return value


def on_behalf_form_schema(*, template_code: str, version: str, playbook_key: str) -> dict[str, Any]:
    return {
        "pack_key": "request_forms",
        "version": version,
        "forms": [
            {
                "key": template_code,
                "request_template_key": template_code,
                "title": "PA release on-behalf incident",
                "request_kind": "incident",
                "ticket_type": "incident",
                "on_behalf_policy": {
                    "allowed": True,
                    "reason_required": True,
                    "affected_person_required": True,
                    "allowed_scope": "same_department_or_privileged",
                    "diagnostic_target": "affected_person_primary_agent",
                    "knowledge_visibility": "creator_only",
                    "support_visibility": "creator_and_affected",
                    "no_primary_agent_behavior": "allow_ticket_no_diagnostics",
                },
                "diagnostic_policy": {
                    "id": "pa_release_primary_agent",
                    "suggested_playbooks": [playbook_key],
                    "auto_run": {
                        "enabled": True,
                        "only_if_agent_online": True,
                        "only_for_priorities": ["P1", "P2"],
                    },
                    "consent": {"required_for_requester_device": True},
                },
                "fields": [
                    {"key": "summary", "label": "Summary", "type": "text", "required": False},
                ],
            }
        ],
    }


def _priority_payload() -> dict[str, Any]:
    return {
        "impact": True,
        "urgency": True,
        "importance": True,
        "legacy_priority": "high",
        "effective_priority": "P1",
        "priority_class": "P1",
        "computed_priority": "P1",
        "priority_source": "live_gate",
        "priority_reason": "PA release live gate",
        "urgency_reason": "PA release live gate",
        "importance_reason": "PA release live gate",
        "applied_modifiers": [],
        "priority_explanation": {},
    }


def _diagnostic_custom_fields(*, template_code: str, playbook_key: str) -> dict[str, Any]:
    form = on_behalf_form_schema(template_code=template_code, version="live", playbook_key=playbook_key)["forms"][0]
    return {
        "request_form_key": template_code,
        "request_form_title": form["title"],
        "request_template": {
            "key": template_code,
            "title": form["title"],
            "ticket_type": "incident",
            "diagnostic_policy": form["diagnostic_policy"],
            "on_behalf_policy": form["on_behalf_policy"],
        },
        "diagnostic_consent": {
            "required": True,
            "granted": True,
            "scope": "requester_device",
            "source": "pa_release_live_gate",
        },
    }


def _json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise LiveGateFailure(f"non-JSON response from {response.geturl()}: {text[:500]}") from exc


class ApiClient:
    def __init__(self, *, base_url: str, token: str, insecure_tls: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        handlers: list[Any] = []
        if self.base_url.startswith("https://"):
            context = ssl._create_unverified_context() if insecure_tls else ssl.create_default_context()
            handlers.append(request.HTTPSHandler(context=context))
        self.opener = request.build_opener(*handlers)

    def post(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        token: str | None = None,
        expect_success: bool = True,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token or self.token}",
            "Content-Type": "application/json",
        }
        data = json.dumps(payload or {}).encode("utf-8")
        req = request.Request(f"{self.base_url}{path}", data=data, headers=headers, method="POST")
        try:
            with self.opener.open(req, timeout=45) as response:
                body = _json_response(response)
                status = int(getattr(response, "status", 200))
        except error.HTTPError as exc:
            body = _json_response(exc)
            status = exc.code
            if expect_success:
                raise LiveGateFailure(f"POST {path} failed with HTTP {status}: {sanitize_for_report(body)}") from exc
        except error.URLError as exc:
            raise LiveGateFailure(f"POST {path} failed: {exc}") from exc
        if expect_success and body.get("status") != "success":
            raise LiveGateFailure(f"POST {path} returned non-success payload: {sanitize_for_report(body)}")
        return {"http_status": status, "body": body}


class GateState:
    def __init__(self, online_device_ids: set[str]) -> None:
        self.online_device_ids = online_device_ids
        self.ui_publisher = None
        self.device_dispatch_service = None

    def is_agent_online(self, device_id: str) -> bool:
        return str(device_id) in self.online_device_ids


class PrimaryAgentOnBehalfLiveGate:
    def __init__(
        self,
        *,
        base_url: str,
        run_id: str,
        commit: str,
        output_dir: Path,
        insecure_tls: bool,
    ) -> None:
        self.base_url = base_url
        self.run_id = run_id
        self.commit = commit
        self.output_dir = output_dir
        self.insecure_tls = insecure_tls
        self.template_code = f"pa_release_{run_id}".replace("-", "_")[:96]
        self.playbook_key = f"pa_release_diag_{run_id}".replace("-", "_")[:96]
        self.admin_token = ""
        self.agent_tokens: dict[str, str] = {}
        self.admin_api: ApiClient | None = None
        self.ids: dict[str, str] = {}
        self.passwords: dict[str, str] = {}
        self.report: dict[str, Any] = {
            "status": "pending",
            "run_id": run_id,
            "commit": commit,
            "base_url": base_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evidence_dir": str(output_dir),
            "required_scenarios": list(REQUIRED_SCENARIOS),
            "scenarios": {},
            "created": {},
            "commands": [],
        }

    @property
    def admin(self) -> ApiClient:
        _require(self.admin_api is not None, "admin API client is not initialized")
        return self.admin_api

    async def setup(self) -> None:
        await init_db(DATABASE_URL)
        auth = AuthService(SimpleNamespace(users={}))
        admin_login = f"pa-release-admin-{self.run_id}"
        self.admin_token = await auth.generate_ui_token(admin_login, "admin", expires_hours=4)

        device_ids = {
            "device_a": str(uuid.uuid4()),
            "device_b": str(uuid.uuid4()),
            "device_c": str(uuid.uuid4()),
        }
        for key, device_id in device_ids.items():
            self.agent_tokens[key] = await auth.generate_agent_token(
                device_id=device_id,
                expires_hours=4,
                replace_existing=True,
                max_active_tokens=20,
            )
        self.ids.update(device_ids)
        self.admin_api = ApiClient(base_url=self.base_url, token=self.admin_token, insecure_tls=self.insecure_tls)

        await self._seed_db(admin_login=admin_login)
        self.report["created"] = {
            key: value
            for key, value in self.ids.items()
            if key.startswith(("person_", "device_", "binding_", "ticket_", "playbook_"))
        }

    async def close(self) -> None:
        await shutdown_db()

    async def _seed_db(self, *, admin_login: str) -> None:
        now = datetime.now(timezone.utc)
        async with get_session() as session:
            department = RegistryDepartment(
                department_id=str(uuid.uuid4()),
                code=f"pa-release-{self.run_id}"[:64],
                name=f"PA release department {self.run_id}",
                status="active",
                source="pa_release_live_gate",
                metadata_json={},
            )
            location = RegistryLocation(
                location_id=str(uuid.uuid4()),
                building=f"PA release {self.run_id}",
                floor="1",
                room="101",
                display_name=f"PA release {self.run_id} / 101",
                status="active",
                source="pa_release_live_gate",
                metadata_json={},
            )
            session.add_all([department, location])
            await session.flush()
            self.ids.update(
                {
                    "department_shared": department.department_id,
                    "location": location.location_id,
                }
            )

            for label in ("a", "b", "c"):
                login = f"pa-release-user-{label}-{self.run_id}@example.test"
                password = f"PaRelease-{label}-{uuid.uuid4().hex[:12]}!"
                person = RegistryPerson(
                    person_id=str(uuid.uuid4()),
                    display_name=f"PA Release User {label.upper()} {self.run_id}",
                    full_name=f"PA Release User {label.upper()} {self.run_id}",
                    email=login,
                    phone=f"100{label}",
                    department_id=department.department_id,
                    location_id=location.location_id,
                    source="pa_release_live_gate",
                    status="active",
                    metadata_json={},
                )
                session.add(person)
                session.add(
                    RegistryPersonIdentity(
                        person_id=person.person_id,
                        provider="ui_login",
                        identifier=login,
                        normalized_identifier=login.lower(),
                        verified=True,
                        source="pa_release_live_gate",
                    )
                )
                session.add(
                    UiUser(
                        user_login=login,
                        password_hash=hash_password(password),
                        actor_role="user",
                        is_active=True,
                    )
                )
                self.ids[f"person_{label}"] = person.person_id
                self.ids[f"login_{label}"] = login
                self.passwords[f"user_{label}"] = password

            await session.flush()
            for label in ("a", "b", "c"):
                device = await session.get(Device, self.ids[f"device_{label}"])
                _require(device is not None, f"agent token did not create device {label}")
                device.protocol_version = "ws_ticket_v3"
                device.agent_version = "pa-release-live-gate"
                device.hostname = f"pa-release-{label}-{self.run_id}"
                device.os = "Windows 11 live gate"
                device.capabilities = {"protocol_v3": True, "pa_release_live_gate": True}
                device.device_metadata = {"pa_release_run_id": self.run_id, "label": label}
                device.last_seen_at = now
                device.last_handshake_at = now

            registration = RegistrationService(session)
            bind_a = await registration.bind_person_to_device(
                device_id=self.ids["device_a"],
                person_id=self.ids["person_a"],
                relationship_type="primary_user",
                reviewed_by=admin_login,
                reason=f"PA release live gate {self.run_id}: bind A",
            )
            bind_b = await registration.bind_person_to_device(
                device_id=self.ids["device_b"],
                person_id=self.ids["person_b"],
                relationship_type="primary_user",
                reviewed_by=admin_login,
                reason=f"PA release live gate {self.run_id}: bind B",
            )
            self.ids["binding_a"] = bind_a["binding"]["binding_id"]
            self.ids["binding_b"] = bind_b["binding"]["binding_id"]

            forms_repo = TicketFormPacksRepo(session)
            form_schema = on_behalf_form_schema(
                template_code=self.template_code,
                version=f"pa-release-{self.run_id}",
                playbook_key=self.playbook_key,
            )
            await forms_repo.upsert_pack(
                pack_key="request_forms",
                version=f"pa-release-{self.run_id}",
                schema_json=form_schema,
                created_by=admin_login,
            )
            await forms_repo.set_preferred(
                pack_key="request_forms",
                version=f"pa-release-{self.run_id}",
                updated_by=admin_login,
            )

            playbook = Playbook(
                key=self.playbook_key,
                name=f"PA release diagnostic {self.run_id}",
                domain="diagnostics",
                owner="pa_release_live_gate",
                archived=False,
            )
            session.add(playbook)
            await session.flush()
            version = PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={"purpose": "PA release live gate marker"},
                status="published",
                created_at=now,
                published_at=now,
            )
            session.add(version)
            await session.flush()
            self.ids["playbook_key"] = self.playbook_key
            self.ids["playbook_version_id"] = str(version.id)

            await session.commit()

    async def _create_ticket(
        self,
        *,
        creator_label: str,
        affected_person_id: str | None,
        title: str,
        state_online: set[str],
    ) -> Ticket:
        placeholder_device_id = str(uuid.uuid4())
        async with get_session() as session:
            result = await create_ticket_with_side_effects(
                session,
                device_id=placeholder_device_id,
                requester_id=self.ids[f"login_{creator_label}"],
                title=title,
                description=f"{title} ({self.run_id})",
                user_display_name=f"PA Release User {creator_label.upper()}",
                requester_profile={
                    "full_name": f"PA Release User {creator_label.upper()}",
                    "email": self.ids[f"login_{creator_label}"],
                    "phone": "1000",
                },
                normalized_priority=_priority_payload(),
                include_public_access=False,
                ticket_type="incident",
                extra_custom_fields=_diagnostic_custom_fields(
                    template_code=self.template_code,
                    playbook_key=self.playbook_key,
                ),
                requester_account={
                    "account_mode": "browser_no_device",
                    "person_id": self.ids[f"person_{creator_label}"],
                    "display_name": f"PA Release User {creator_label.upper()}",
                    "email": self.ids[f"login_{creator_label}"],
                    "validation": "web_requester_identity_resolved",
                },
                ticket_context={
                    "affected_person_id": affected_person_id,
                    "on_behalf_reason": "PA release live gate on-behalf check",
                }
                if affected_person_id
                else None,
                state=GateState(state_online),
            )
            await session.commit()
            ticket = await session.get(Ticket, result["ticket_id"])
            _require(ticket is not None, "ticket was not persisted")
            self.ids[f"ticket_{len([key for key in self.ids if key.startswith('ticket_')]) + 1}"] = ticket.ticket_id
            return ticket

    async def _ticket_facts(self, ticket_id: str) -> dict[str, Any]:
        async with get_session() as session:
            ticket = await session.get(Ticket, ticket_id)
            _require(ticket is not None, f"ticket missing: {ticket_id}")
            fields = ticket.custom_fields or {}
            events = (
                await session.execute(
                    select(TicketEvent)
                    .where(TicketEvent.ticket_id == ticket_id)
                    .order_by(TicketEvent.id.asc())
                )
            ).scalars().all()
            runs = (await session.execute(select(PlaybookRun))).scalars().all()
            matching_runs = [
                run
                for run in runs
                if ((run.context_json or {}).get("ticket") or {}).get("ticket_id") == ticket_id
            ]
            operations = []
            if matching_runs:
                run_ids = [run.id for run in matching_runs]
                operations = (
                    await session.execute(select(Operation).where(Operation.playbook_run_id.in_(run_ids)))
                ).scalars().all()
            return {
                "ticket_id": ticket.ticket_id,
                "requester_id": ticket.requester_id,
                "requester_person_id": ticket.requester_person_id,
                "target_device_id": fields.get("target_device_id"),
                "target_binding_id": fields.get("target_binding_id"),
                "target_agent_status": fields.get("target_agent_status"),
                "diagnostic_target_source": fields.get("diagnostic_target_source"),
                "created_on_behalf": fields.get("created_on_behalf"),
                "creator_person_id": fields.get("creator_person_id"),
                "affected_person_id": fields.get("affected_person_id"),
                "on_behalf_reason": fields.get("on_behalf_reason"),
                "diagnostics": fields.get("diagnostics"),
                "event_types": [event.event_type for event in events],
                "diagnostic_skip_events": [
                    event.payload
                    for event in events
                    if event.event_type == "diagnostic_autorun_skipped"
                ],
                "playbook_runs": [
                    {
                        "id": run.id,
                        "device_id": run.device_id,
                        "status": run.status,
                        "trigger_type": run.trigger_type,
                    }
                    for run in matching_runs
                ],
                "operation_count": len(operations),
            }

    async def scenario_normal_ticket(self) -> None:
        ticket = await self._create_ticket(
            creator_label="a",
            affected_person_id=None,
            title=f"PA release normal ticket {self.run_id}",
            state_online={self.ids["device_a"]},
        )
        facts = await self._ticket_facts(ticket.ticket_id)
        _require(facts["created_on_behalf"] is False, "normal ticket was marked on-behalf")
        _require(facts["creator_person_id"] == self.ids["person_a"], "normal ticket creator is not A")
        _require(facts["affected_person_id"] == self.ids["person_a"], "normal ticket affected person is not A")
        _require(facts["target_device_id"] == self.ids["device_a"], "normal ticket did not target A primary agent")
        _require(facts["diagnostic_target_source"] == "creator_primary_agent", "normal ticket target source mismatch")
        _require(facts["playbook_runs"] and facts["playbook_runs"][0]["device_id"] == self.ids["device_a"], "normal diagnostic auto-run did not target A")
        self.report["scenarios"][REQUIRED_SCENARIOS[0]] = {"status": "passed", **facts}

    async def scenario_on_behalf_ticket(self) -> None:
        ticket = await self._create_ticket(
            creator_label="a",
            affected_person_id=self.ids["person_b"],
            title=f"PA release on-behalf ticket {self.run_id}",
            state_online={self.ids["device_b"]},
        )
        facts = await self._ticket_facts(ticket.ticket_id)
        _require(facts["created_on_behalf"] is True, "on-behalf ticket flag missing")
        _require(facts["creator_person_id"] == self.ids["person_a"], "on-behalf creator is not A")
        _require(facts["affected_person_id"] == self.ids["person_b"], "on-behalf affected person is not B")
        _require(facts["target_device_id"] == self.ids["device_b"], "on-behalf ticket did not target B primary agent")
        _require(facts["diagnostic_target_source"] == "affected_user_primary_agent", "on-behalf target source mismatch")
        _require(all(run["device_id"] != self.ids["device_a"] for run in facts["playbook_runs"]), "diagnostic run targeted creator A device")
        _require(facts["playbook_runs"] and facts["playbook_runs"][0]["device_id"] == self.ids["device_b"], "on-behalf diagnostic auto-run did not target B")
        self.report["scenarios"][REQUIRED_SCENARIOS[1]] = {"status": "passed", **facts}

    async def scenario_offline_ticket(self) -> None:
        ticket = await self._create_ticket(
            creator_label="a",
            affected_person_id=self.ids["person_b"],
            title=f"PA release offline affected ticket {self.run_id}",
            state_online=set(),
        )
        facts = await self._ticket_facts(ticket.ticket_id)
        _require(facts["target_device_id"] == self.ids["device_b"], "offline ticket did not retain B target")
        _require(facts["target_agent_status"] == "offline", "offline target evidence was not stored")
        _require(facts["playbook_runs"] == [], "offline target still created a playbook run")
        _require(facts["operation_count"] == 0, "offline target still created operations")
        _require(facts["diagnostic_skip_events"], "offline target did not write skip event")
        _require(facts["diagnostic_skip_events"][0]["reason"] == "target_agent_offline", "offline skip reason mismatch")
        self.report["scenarios"][REQUIRED_SCENARIOS[2]] = {"status": "passed", **facts}

    async def scenario_gui_login(self) -> None:
        success = self.admin.post(
            "/api/registry/agent/account-sessions/login",
            token=self.agent_tokens["device_b"],
            payload={"login": self.ids["login_b"], "password": self.passwords["user_b"]},
        )
        body = success["body"]
        session_payload = (body.get("data") or {}).get("session") or {}
        session_id = str(session_payload.get("session_id") or "")
        _require(success["http_status"] == 200, "bound GUI login did not return HTTP 200")
        _require(session_payload.get("device_id") == self.ids["device_b"], "bound GUI session device mismatch")
        _require(session_payload.get("person_id") == self.ids["person_b"], "bound GUI session person mismatch")
        _require(session_payload.get("verification_method") == "gui_password", "bound GUI session method mismatch")
        self.ids["gui_bound_session_id"] = session_id
        self.report["scenarios"][REQUIRED_SCENARIOS[3]] = {
            "status": "passed",
            "http_status": success["http_status"],
            "session": sanitize_for_report(session_payload),
        }

        mismatch = self.admin.post(
            "/api/registry/agent/account-sessions/login",
            token=self.agent_tokens["device_b"],
            payload={"login": self.ids["login_a"], "password": self.passwords["user_a"]},
            expect_success=False,
        )
        mismatch_body = mismatch["body"]
        _require(mismatch["http_status"] == 403, "wrong-user GUI login did not return HTTP 403")
        _require(mismatch_body.get("error_code") == "ACCOUNT_SESSION_DEVICE_MISMATCH", "wrong-user GUI error code mismatch")
        async with get_session() as session:
            session_count = await session.scalar(
                select(func.count())
                .select_from(DeviceAccountSession)
                .where(
                    DeviceAccountSession.device_id == self.ids["device_b"],
                    DeviceAccountSession.person_id == self.ids["person_a"],
                )
            )
            binding_count = await session.scalar(
                select(func.count())
                .select_from(DeviceUserBinding)
                .where(
                    DeviceUserBinding.device_id == self.ids["device_b"],
                    DeviceUserBinding.person_id == self.ids["person_a"],
                    DeviceUserBinding.status == "active",
                )
            )
        _require(int(session_count or 0) == 0, "wrong-user GUI login created a session")
        _require(int(binding_count or 0) == 0, "wrong-user GUI login rebound device B to A")
        self.report["scenarios"][REQUIRED_SCENARIOS[4]] = {
            "status": "passed",
            "http_status": mismatch["http_status"],
            "error_code": mismatch_body.get("error_code"),
            "sessions_for_wrong_user_on_device_b": int(session_count or 0),
            "active_bindings_for_wrong_user_on_device_b": int(binding_count or 0),
        }

    async def scenario_admin_transfer(self) -> None:
        transferred = self.admin.post(
            f"/api/web/admin/registry/devices/{self.ids['device_b']}/transfer-owner",
            payload={
                "new_person_id": self.ids["person_c"],
                "old_binding_action": "transferred",
                "reason": f"PA release live gate {self.run_id}: transfer B device to C",
            },
        )
        transfer_data = transferred["body"].get("data") or {}
        new_binding = transfer_data.get("binding") or {}
        _require(new_binding.get("person_id") == self.ids["person_c"], "transfer did not create C primary binding")

        b_ticket = await self._create_ticket(
            creator_label="b",
            affected_person_id=None,
            title=f"PA release B future ticket after transfer {self.run_id}",
            state_online={self.ids["device_b"]},
        )
        c_ticket = await self._create_ticket(
            creator_label="c",
            affected_person_id=None,
            title=f"PA release C future ticket after transfer {self.run_id}",
            state_online={self.ids["device_b"]},
        )
        b_facts = await self._ticket_facts(b_ticket.ticket_id)
        c_facts = await self._ticket_facts(c_ticket.ticket_id)
        _require(b_facts["target_device_id"] != self.ids["device_b"], "B future ticket still targets transferred device")
        _require(c_facts["target_device_id"] == self.ids["device_b"], "C future ticket does not target transferred device")
        _require(c_facts["diagnostic_target_source"] == "creator_primary_agent", "C future target source mismatch")
        revoked_status = None
        if self.ids.get("gui_bound_session_id"):
            async with get_session() as session:
                row = await session.get(DeviceAccountSession, self.ids["gui_bound_session_id"])
                revoked_status = getattr(row, "verification_status", None)
        _require(revoked_status == "revoked", "transfer did not revoke previous B GUI session")
        self.report["scenarios"][REQUIRED_SCENARIOS[5]] = {
            "status": "passed",
            "transfer": sanitize_for_report(transfer_data),
            "b_future_ticket": b_facts,
            "c_future_ticket": c_facts,
            "previous_b_gui_session_status": revoked_status,
        }

    async def run(self) -> dict[str, Any]:
        await self.setup()
        try:
            await self.scenario_normal_ticket()
            await self.scenario_on_behalf_ticket()
            await self.scenario_offline_ticket()
            await self.scenario_gui_login()
            await self.scenario_admin_transfer()
            missing = [name for name in REQUIRED_SCENARIOS if self.report["scenarios"].get(name, {}).get("status") != "passed"]
            _require(not missing, f"missing required scenario results: {missing}")
            self.report["status"] = "passed"
            return self.report
        except Exception as exc:
            self.report["status"] = "failed"
            self.report["error"] = str(exc)
            raise
        finally:
            await self.close()

    def write_report(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.output_dir / "live_gate_report.json"
        report_path.write_text(
            json.dumps(sanitize_for_report(self.report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        lines = [
            "# Primary Agent On-Behalf Live Gate",
            "",
            f"- status: {self.report.get('status')}",
            f"- commit: {self.commit}",
            f"- run_id: {self.run_id}",
            f"- base_url: {self.base_url}",
            "",
            "## Scenarios",
        ]
        for name in REQUIRED_SCENARIOS:
            scenario = self.report["scenarios"].get(name) or {}
            lines.append(f"- {name}: {scenario.get('status', 'missing')}")
        lines.append("")
        lines.append("## Artifacts")
        lines.append("- live_gate_report.json")
        (self.output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    commit = _git_commit()
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    parser = argparse.ArgumentParser(description="Final PA-release live gate for primary-agent on-behalf behavior.")
    parser.add_argument("--base-url", default="https://example.test:9443")
    parser.add_argument("--run-id", default=f"pa-release-{_now_slug()}-{uuid.uuid4().hex[:6]}")
    parser.add_argument("--commit", default=commit)
    parser.add_argument("--output-dir", type=Path, default=default_evidence_dir(commit=commit, day=day))
    parser.add_argument("--insecure-tls", action="store_true")
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    gate = PrimaryAgentOnBehalfLiveGate(
        base_url=args.base_url,
        run_id=args.run_id,
        commit=args.commit,
        output_dir=output_dir,
        insecure_tls=args.insecure_tls,
    )
    try:
        await gate.run()
        return_code = 0
    except Exception as exc:
        print(f"primary-agent on-behalf live gate failed: {exc}", file=sys.stderr)
        return_code = 1
    finally:
        gate.write_report()
        print(f"primary-agent on-behalf live gate: {gate.report['status']} -> {output_dir}")
    return return_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
