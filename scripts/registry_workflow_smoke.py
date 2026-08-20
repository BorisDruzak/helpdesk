from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import sys
from types import SimpleNamespace
from typing import Any
from urllib import error, parse, request
import uuid

from sqlalchemy import or_, select

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.db import get_session, init_db, shutdown_db
from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceInventoryBinding,
    DeviceRegistrationEvent,
    DeviceUserBinding,
    RegistryAdminEvent,
    RegistryAsset,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
)
from auth.service import AuthService
from config import DATABASE_URL
from registry.account_session_service import AccountSessionService
from tickets.account_access_service import TicketAccountAccessService
from tickets.create_flow import create_ticket_with_side_effects


class SmokeFailure(RuntimeError):
    pass


def _now_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    text = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"non-JSON response from {response.geturl()}: {text[:500]}") from exc
    return payload


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
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode({k: v for k, v in query.items() if v is not None})}"
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token or self.token}",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with self.opener.open(req, timeout=45) as response:
                body = _json_response(response)
        except error.HTTPError as exc:
            body = _json_response(exc)
            raise SmokeFailure(f"{method} {path} failed with HTTP {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise SmokeFailure(f"{method} {path} failed: {exc}") from exc
        if body.get("status") != "success":
            raise SmokeFailure(f"{method} {path} returned non-success payload: {body}")
        return body.get("data") or {}

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        return self.request("POST", path, payload=payload or {}, **kwargs)

    def patch(self, path: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        return self.request("PATCH", path, payload=payload or {}, **kwargs)


class RegistryWorkflowSmoke:
    def __init__(self, *, base_url: str, run_id: str, insecure_tls: bool) -> None:
        self.base_url = base_url
        self.run_id = run_id
        self.insecure_tls = insecure_tls
        self.reason = f"registry workflow smoke {run_id}"
        self.admin_token = ""
        self.agent_tokens: dict[str, str] = {}
        self.api: ApiClient | None = None
        self.created_sessions: list[str] = []
        self.results: dict[str, Any] = {"run_id": run_id, "scenarios": {}}

    @property
    def client(self) -> ApiClient:
        _require(self.api is not None, "api client is not initialized")
        return self.api

    async def setup(self, device_ids: list[str]) -> None:
        await init_db(DATABASE_URL)
        auth = AuthService(SimpleNamespace(users={}))
        self.admin_token = await auth.generate_ui_token(
            user_login=f"registry-smoke-{self.run_id}",
            actor_role="admin",
            expires_hours=2,
        )
        for device_id in device_ids:
            self.agent_tokens[device_id] = await auth.generate_agent_token(
                device_id=device_id,
                expires_hours=2,
                replace_existing=True,
                max_active_tokens=20,
            )
        async with get_session() as session:
            now = datetime.now(timezone.utc)
            for index, device_id in enumerate(device_ids, start=1):
                device = await session.get(Device, device_id)
                _require(device is not None, f"device stub was not created for {device_id}")
                device.protocol_version = "ws_ticket_v3"
                device.agent_version = "registry-smoke"
                device.hostname = f"rsmoke-{self.run_id}-{index}"
                device.os = "Windows 11 smoke"
                device.capabilities = {"protocol_v3": True, "registry_smoke": True}
                device.device_metadata = {"machine_id": device_id, "registry_smoke_run_id": self.run_id}
                device.last_seen_at = now
                device.last_handshake_at = now
            await session.commit()
        self.api = ApiClient(base_url=self.base_url, token=self.admin_token, insecure_tls=self.insecure_tls)

    async def cleanup(self) -> None:
        async with get_session() as session:
            service = AccountSessionService(session)
            for session_id in sorted(set(self.created_sessions)):
                row = await session.get(DeviceAccountSession, session_id)
                if row is not None and row.verification_status != "revoked":
                    await service.revoke_session(
                        session_id=session_id,
                        revoked_by=f"registry-smoke-{self.run_id}",
                        reason="registry workflow smoke cleanup",
                    )
            await session.commit()

    def create_location(self, label: str) -> dict[str, Any]:
        data = self.client.post(
            "/api/web/admin/registry/locations",
            {
                "building": f"RSMOKE-{self.run_id}-{label}",
                "floor": "2",
                "room": label,
                "display_name": f"Registry smoke {label}",
                "notes": self.reason,
                "reason": self.reason,
            },
        )
        return data["location"]

    def create_department(self, label: str) -> dict[str, Any]:
        data = self.client.post(
            "/api/web/admin/registry/departments",
            {
                "code": f"RSMOKE-{self.run_id}-{label}",
                "name": f"Registry smoke department {label}",
                "support_queue": "registry-smoke",
                "reason": self.reason,
            },
        )
        return data["department"]

    def create_person(self, label: str, *, location_id: str | None = None, department_id: str | None = None) -> dict[str, Any]:
        email = f"{label.lower()}-{self.run_id}@registry-smoke.test"
        data = self.client.post(
            "/api/web/admin/registry/people",
            {
                "display_name": f"Registry Smoke {label}",
                "full_name": f"Registry Smoke {label} Initial",
                "email": email,
                "phone": f"+7000{self.run_id[-6:]}",
                "location_id": location_id,
                "department_id": department_id,
                "reason": self.reason,
            },
        )
        return data["person"]

    def add_identity(self, person_id: str, provider: str, identifier: str, *, verified: bool = False) -> dict[str, Any]:
        data = self.client.post(
            f"/api/web/admin/registry/people/{person_id}/identities",
            {
                "provider": provider,
                "identifier": identifier,
                "verified": verified,
                "reason": self.reason,
            },
        )
        return data["identity"]

    def update_identity(self, identity_id: str, *, verified: bool) -> dict[str, Any]:
        data = self.client.patch(
            f"/api/web/admin/registry/identities/{identity_id}",
            {"verified": verified, "source": "registry_workflow_smoke"},
        )
        return data["identity"]

    async def scenario_a_person_identity(self, location: dict[str, Any], department: dict[str, Any]) -> dict[str, Any]:
        person = self.create_person("Master", location_id=location["location_id"], department_id=department["department_id"])
        email_identity = self.add_identity(
            person["person_id"],
            "email",
            f"master-{self.run_id}@registry-smoke.test",
            verified=False,
        )
        windows_identity = self.add_identity(
            person["person_id"],
            "windows_login",
            f"RSMOKE\\master-{self.run_id}",
            verified=False,
        )
        verified_identity = self.update_identity(email_identity["identity_id"], verified=True)
        updated = self.client.patch(
            f"/api/web/admin/registry/people/{person['person_id']}",
            {
                "full_name": f"Registry Smoke Master Updated {self.run_id}",
                "phone": f"+7999{self.run_id[-6:]}",
                "department_id": department["department_id"],
                "location_id": location["location_id"],
                "reason": self.reason,
            },
        )["person"]
        snapshot = self.client.get("/api/web/admin/registry")
        snapshot_person = next((row for row in snapshot.get("people", []) if row.get("person_id") == person["person_id"]), None)
        _require(snapshot_person is not None, "person is missing from registry snapshot")
        identities = snapshot_person.get("identities") or []
        _require(len(identities) >= 2, "person drawer/snapshot does not expose identities")
        _require(any(row.get("identity_id") == verified_identity["identity_id"] and row.get("verified") for row in identities), "verified identity is not visible")
        result = {"person_id": person["person_id"], "identity_count": len(identities)}
        self.results["scenarios"]["A"] = result
        return {**result, "person": updated, "email_identity": email_identity, "windows_identity": windows_identity}

    async def scenario_b_manual_bind(self, device_id: str, person_id: str) -> dict[str, Any]:
        data = self.client.post(
            f"/api/web/admin/registry/devices/{device_id}/bind-person",
            {
                "person_id": person_id,
                "relationship_type": "primary_user",
                "replace_existing": False,
                "reason": self.reason,
            },
        )
        binding = data["binding"]
        async with get_session() as session:
            binding_row = await session.get(DeviceUserBinding, binding["binding_id"])
            asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one_or_none()
            inventory = await session.get(DeviceInventoryBinding, device_id)
            event = (
                await session.execute(
                    select(DeviceRegistrationEvent)
                    .where(DeviceRegistrationEvent.binding_id == binding["binding_id"])
                    .order_by(DeviceRegistrationEvent.event_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            _require(binding_row is not None and binding_row.status == "active", "active binding was not created")
            _require(asset is not None and asset.assigned_person_id == person_id, "registry asset owner was not synced")
            _require(inventory is not None and inventory.person_id == person_id, "inventory person was not synced")
            _require(inventory.source_binding_id == binding["binding_id"], "inventory source binding was not synced")
            _require(inventory.registration_status == "admin_confirmed", "inventory registration status was not synced")
            _require(event is not None, "registration event was not written")
        account = self.client.post(
            "/api/registry/agent/account-sessions/confirmed-binding",
            {"binding_id": binding["binding_id"]},
            token=self.agent_tokens[device_id],
        )
        self.created_sessions.append(account["session"]["session_id"])
        result = {
            "device_id": device_id,
            "binding_id": binding["binding_id"],
            "session_id": account["session"]["session_id"],
        }
        self.results["scenarios"]["B"] = result
        return {**result, "session_token": account["session_token"]}

    async def scenario_c_shared_responsible(self, device_id: str, primary_person_id: str) -> dict[str, Any]:
        shared = self.create_person("Shared")
        responsible = self.create_person("Responsible")
        shared_binding = self.client.post(
            f"/api/web/admin/registry/devices/{device_id}/shared-users",
            {"person_id": shared["person_id"], "reason": self.reason},
        )["binding"]
        responsible_binding = self.client.post(
            f"/api/web/admin/registry/devices/{device_id}/responsible",
            {"person_id": responsible["person_id"], "replace_existing": True, "reason": self.reason},
        )["binding"]
        state = self.client.get("/api/registry/agent/account-state", token=self.agent_tokens[device_id])
        relationships = {
            account.get("relationship_type"): account.get("person_id")
            for account in state.get("accounts", [])
            if account.get("relationship_type")
        }
        _require(relationships.get("primary_user") == primary_person_id, "primary binding was changed by shared/responsible actions")
        _require(relationships.get("shared_user") == shared["person_id"], "shared user is missing from account state")
        _require(relationships.get("responsible") == responsible["person_id"], "responsible user is missing from account state")
        result = {
            "shared_binding_id": shared_binding["binding_id"],
            "responsible_binding_id": responsible_binding["binding_id"],
            "relationships": sorted(relationships),
        }
        self.results["scenarios"]["C"] = result
        return result

    async def scenario_d_transfer_owner(
        self,
        device_id: str,
        old_session_id: str,
        old_session_token: str,
        old_binding_id: str,
    ) -> dict[str, Any]:
        new_owner = self.create_person("Transfer")
        async with get_session() as session:
            ticket = await create_ticket_with_side_effects(
                session,
                device_id=device_id,
                requester_id=device_id,
                title=f"Registry smoke transfer ticket {self.run_id}",
                description="ticket created before owner transfer",
                user_display_name="Registry smoke transfer owner",
                requester_account={"session_id": old_session_id, "session_token": old_session_token},
            )
            await session.commit()
            ticket_id = ticket["ticket_id"]

        transferred = self.client.post(
            f"/api/web/admin/registry/devices/{device_id}/transfer-owner",
            {
                "new_person_id": new_owner["person_id"],
                "old_binding_action": "transferred",
                "reason": self.reason,
            },
        )
        new_binding = transferred["binding"]
        async with get_session() as session:
            old_binding = await session.get(DeviceUserBinding, old_binding_id)
            new_binding_row = await session.get(DeviceUserBinding, new_binding["binding_id"])
            asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one_or_none()
            inventory = await session.get(DeviceInventoryBinding, device_id)
            old_session = await session.get(DeviceAccountSession, old_session_id)
            validation = await AccountSessionService(session).validate_session(
                device_id=device_id,
                session_id=old_session_id,
                session_token=old_session_token,
            )
            ticket_row = await session.get(Ticket, ticket_id)
            access = False
            if validation.get("valid"):
                access = await TicketAccountAccessService(session).can_view_ticket(
                    ticket=ticket_row,
                    account_session=validation["session"],
                )
            _require(old_binding is not None and old_binding.status == "transferred", "old owner binding was not transferred")
            _require(new_binding_row is not None and new_binding_row.status == "active", "new primary binding is not active")
            _require(new_binding_row.relationship_type == "primary_user", "new binding is not primary")
            _require(asset is not None and asset.assigned_person_id == new_owner["person_id"], "asset owner was not transferred")
            _require(inventory is not None and inventory.person_id == new_owner["person_id"], "inventory owner was not transferred")
            _require(old_session is not None and old_session.verification_status == "revoked", "old account session was not revoked")
            _require(validation.get("error_code") == "ACCOUNT_SESSION_REVOKED", "old account session still validates")
            _require(access is False, "ticket access with old session is still allowed")
        result = {
            "new_person_id": new_owner["person_id"],
            "new_binding_id": new_binding["binding_id"],
            "ticket_id": ticket_id,
        }
        self.results["scenarios"]["D"] = result
        return result

    async def scenario_e_merge_people(self) -> dict[str, Any]:
        master = self.create_person("MergeMaster")
        duplicate = self.create_person("MergeDuplicate")
        duplicate_identity = self.add_identity(
            duplicate["person_id"],
            "email",
            f"merge-duplicate-{self.run_id}@registry-smoke.test",
            verified=True,
        )
        device_id = str(uuid.uuid4())
        token = await AuthService(SimpleNamespace(users={})).generate_agent_token(
            device_id=device_id,
            expires_hours=2,
            replace_existing=True,
            max_active_tokens=20,
        )
        self.agent_tokens[device_id] = token
        async with get_session() as session:
            device = await session.get(Device, device_id)
            _require(device is not None, "merge device was not created")
            device.protocol_version = "ws_ticket_v3"
            device.agent_version = "registry-smoke"
            device.hostname = f"rsmoke-{self.run_id}-merge"
            device.os = "Windows 11 smoke"
            await session.commit()
        bind = self.client.post(
            f"/api/web/admin/registry/devices/{device_id}/bind-person",
            {
                "person_id": duplicate["person_id"],
                "relationship_type": "primary_user",
                "replace_existing": False,
                "reason": self.reason,
            },
        )
        account = self.client.post(
            "/api/registry/agent/account-sessions/confirmed-binding",
            {"binding_id": bind["binding"]["binding_id"]},
            token=token,
        )
        self.created_sessions.append(account["session"]["session_id"])
        async with get_session() as session:
            ticket = await create_ticket_with_side_effects(
                session,
                device_id=device_id,
                requester_id=device_id,
                title=f"Registry smoke merge ticket {self.run_id}",
                description="ticket created for duplicate person before merge",
                user_display_name="Registry smoke duplicate",
                requester_account={
                    "session_id": account["session"]["session_id"],
                    "session_token": account["session_token"],
                },
            )
            await session.commit()
            ticket_id = ticket["ticket_id"]

        merged = self.client.post(
            "/api/web/admin/registry/people/merge",
            {
                "master_person_id": master["person_id"],
                "duplicate_person_id": duplicate["person_id"],
                "field_strategy": {"phone": "duplicate"},
                "reason": self.reason,
            },
        )
        async with get_session() as session:
            identity = await session.get(RegistryPersonIdentity, duplicate_identity["identity_id"])
            binding = await session.get(DeviceUserBinding, bind["binding"]["binding_id"])
            account_row = await session.get(DeviceAccountSession, account["session"]["session_id"])
            ticket_row = await session.get(Ticket, ticket_id)
            duplicate_row = await session.get(RegistryPerson, duplicate["person_id"])
            asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one_or_none()
            inventory = await session.get(DeviceInventoryBinding, device_id)
            event = (
                await session.execute(
                    select(RegistryAdminEvent)
                    .where(RegistryAdminEvent.event_type == "person_merged", RegistryAdminEvent.object_id == master["person_id"])
                    .limit(1)
                )
            ).scalar_one_or_none()
            _require(identity is not None and identity.person_id == master["person_id"], "duplicate identity was not moved")
            _require(binding is not None and binding.person_id == master["person_id"], "duplicate binding was not moved")
            _require(account_row is not None and account_row.person_id == master["person_id"], "duplicate account session was not moved")
            _require(ticket_row is not None and ticket_row.requester_person_id == master["person_id"], "ticket requester was not moved")
            _require(duplicate_row is not None and duplicate_row.status == "merged", "duplicate person was not marked merged")
            _require(asset is not None and asset.assigned_person_id == master["person_id"], "asset derived owner was not moved during people merge")
            _require(inventory is not None and inventory.person_id == master["person_id"], "inventory derived owner was not moved during people merge")
            _require(event is not None, "people merge audit event was not written")
        result = {
            "master_person_id": master["person_id"],
            "duplicate_person_id": duplicate["person_id"],
            "moved": merged["moved"],
        }
        self.results["scenarios"]["E"] = result
        return result

    async def scenario_f_locations_departments(self, person_id: str, device_id: str) -> dict[str, Any]:
        master_location = self.create_location("F-MASTER")
        duplicate_location = self.create_location("F-DUP")
        master_department = self.create_department("FMASTER")
        duplicate_department = self.create_department("FDUP")
        self.client.patch(
            f"/api/web/admin/registry/people/{person_id}",
            {
                "location_id": duplicate_location["location_id"],
                "department_id": duplicate_department["department_id"],
                "reason": self.reason,
            },
        )
        location_bulk = self.client.post(
            "/api/web/admin/registry/bulk/devices/assign-location",
            {
                "ids": [device_id],
                "payload": {"location_id": duplicate_location["location_id"]},
                "reason": self.reason,
            },
        )
        department_bulk = self.client.post(
            "/api/web/admin/registry/bulk/devices/assign-department",
            {
                "ids": [device_id],
                "payload": {"department_id": duplicate_department["department_id"]},
                "reason": self.reason,
            },
        )
        _require(location_bulk["results"][0]["success"], "bulk assign location failed")
        _require(department_bulk["results"][0]["success"], "bulk assign department failed")
        self.client.post(
            "/api/web/admin/registry/locations/merge",
            {
                "master_location_id": master_location["location_id"],
                "duplicate_location_id": duplicate_location["location_id"],
                "reason": self.reason,
            },
        )
        self.client.post(
            "/api/web/admin/registry/departments/merge",
            {
                "master_department_id": master_department["department_id"],
                "duplicate_department_id": duplicate_department["department_id"],
                "reason": self.reason,
            },
        )
        async with get_session() as session:
            person = await session.get(RegistryPerson, person_id)
            asset = (await session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one_or_none()
            inventory = await session.get(DeviceInventoryBinding, device_id)
            duplicate_location_row = await session.get(RegistryLocation, duplicate_location["location_id"])
            duplicate_department_row = await session.get(RegistryDepartment, duplicate_department["department_id"])
            _require(person is not None and person.location_id == master_location["location_id"], "person location was not merged")
            _require(person.department_id == master_department["department_id"], "person department was not merged")
            _require(asset is not None and asset.location_id == master_location["location_id"], "asset location was not merged")
            _require(asset.department_id == master_department["department_id"], "asset department was not merged")
            _require(inventory is not None and inventory.room == master_location["room"], "inventory location text was not merged")
            _require(inventory.department == master_department["name"], "inventory department text was not merged")
            _require(duplicate_location_row is not None and duplicate_location_row.status == "merged", "duplicate location was not marked merged")
            _require(duplicate_department_row is not None and duplicate_department_row.status == "merged", "duplicate department was not marked merged")
        result = {
            "location_id": master_location["location_id"],
            "department_id": master_department["department_id"],
        }
        self.results["scenarios"]["F"] = result
        return result

    async def run(self) -> dict[str, Any]:
        device_ids = [str(uuid.uuid4()) for _ in range(2)]
        await self.setup(device_ids)
        try:
            base_location = self.create_location("A")
            base_department = self.create_department("A")
            scenario_a = await self.scenario_a_person_identity(base_location, base_department)
            scenario_b = await self.scenario_b_manual_bind(device_ids[0], scenario_a["person"]["person_id"])
            await self.scenario_c_shared_responsible(device_ids[0], scenario_a["person"]["person_id"])
            await self.scenario_d_transfer_owner(
                device_ids[0],
                scenario_b["session_id"],
                scenario_b["session_token"],
                scenario_b["binding_id"],
            )
            await self.scenario_e_merge_people()
            await self.scenario_f_locations_departments(scenario_a["person"]["person_id"], device_ids[0])
            self.results["status"] = "passed"
            return self.results
        finally:
            await self.cleanup()
            await shutdown_db()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live Registry Management Center workflow smoke.")
    parser.add_argument("--base-url", default="https://example.test:9443")
    parser.add_argument("--run-id", default=f"{_now_id()}-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--insecure-tls", action="store_true", help="Disable TLS certificate verification for the smoke target.")
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    smoke = RegistryWorkflowSmoke(base_url=args.base_url, run_id=args.run_id, insecure_tls=args.insecure_tls)
    try:
        result = await smoke.run()
    except Exception as exc:
        print(json.dumps({"status": "failed", "run_id": args.run_id, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
