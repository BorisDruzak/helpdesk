from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
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
    DeviceUserBinding,
    RegistryAsset,
    RegistryAudienceGroup,
    RegistryAudienceGroupMember,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    UiUser,
)
from app.repos.registration_repo import normalize_identifier
from auth.service import AuthService
from config import DATABASE_URL
from scripts.registry_visibility_live_smoke import (
    ApiClient,
    SmokeFailure,
    _git_commit,
    _now_id,
    _require,
    _today,
    sanitize_for_report,
)


def default_output_path(*, run_id: str, today: str | None = None) -> Path:
    day = today or _today()
    return REPO_ROOT / "artifacts" / f"registry-visibility-foundation-{day}" / f"registry-visibility-phase8-live-signoff-{run_id}.json"


def build_initial_report(*, run_id: str, base_url: str, commit: str | None) -> dict[str, Any]:
    return {
        "phase": "phase8_registry_operability",
        "status": "pending",
        "run_id": run_id,
        "base_url": base_url,
        "commit": commit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "marker": f"phase8 registry operability {run_id}",
        "created": {},
        "checks": {
            "quality_before": {"status": "pending"},
            "quality_override": {"status": "pending"},
            "export": {"status": "pending"},
            "import_preview_apply": {"status": "pending"},
            "timeline_events": {"status": "pending"},
        },
        "evidence": {
            "browser_quality_tab": {
                "status": "not_collected",
                "required": True,
                "note": "Collect with browser workflow after this API/DB signoff run.",
            },
        },
    }


def _csv_sample(csv_text: str, *, marker: str, limit: int = 6) -> list[str]:
    lines = csv_text.splitlines()
    matched = [line for line in lines if marker in line]
    sample = [*lines[:2], *matched[: max(0, limit - 2)]]
    deduped: list[str] = []
    for line in sample:
        if line not in deduped:
            deduped.append(line)
    return deduped[:limit]


def _assert_no_raw_secret(report: dict[str, Any]) -> None:
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in ("bearer ", "authorization", "cookie", "session_token", "account_session_token", "token_hash"):
        _require(forbidden not in rendered, f"sanitized report contains forbidden secret marker: {forbidden}")


class Phase8LiveSignoff:
    def __init__(self, *, base_url: str, run_id: str, insecure_tls: bool) -> None:
        self.base_url = base_url
        self.run_id = run_id
        self.insecure_tls = insecure_tls
        self.reason = f"phase8 registry operability live signoff {run_id}"
        self.report = build_initial_report(run_id=run_id, base_url=base_url, commit=_git_commit())
        self.ids: dict[str, str] = {}
        self.admin_token = ""
        self.admin_api: ApiClient | None = None

    @property
    def api(self) -> ApiClient:
        _require(self.admin_api is not None, "admin API is not initialized")
        return self.admin_api

    async def setup(self) -> None:
        await init_db(DATABASE_URL)
        auth = AuthService(SimpleNamespace(users={}))
        admin_login = f"phase8-admin-{self.run_id}"
        self.admin_token = await auth.generate_ui_token(admin_login, "admin", expires_hours=2)
        self.admin_api = ApiClient(base_url=self.base_url, token=self.admin_token, insecure_tls=self.insecure_tls)
        self.ids["admin_login"] = admin_login
        await self._seed_invalid_states()

    async def close(self) -> None:
        await shutdown_db()

    async def _seed_invalid_states(self) -> None:
        async with get_session() as session:
            now = datetime.now(timezone.utc)
            archived_department = RegistryDepartment(
                department_id=str(uuid.uuid4()),
                code=f"phase8_archived_{self.run_id}",
                name=f"Phase 8 Archived Department {self.run_id}",
                status="archived",
                source="live_smoke",
            )
            archived_location = RegistryLocation(
                location_id=str(uuid.uuid4()),
                building=f"Phase8-{self.run_id}",
                floor="1",
                room="101",
                display_name=f"Phase 8 Archived Location {self.run_id}",
                status="archived",
                source="live_smoke",
            )
            person = RegistryPerson(
                person_id=str(uuid.uuid4()),
                display_name=f"Phase 8 Archived Context {self.run_id}",
                email=f"phase8-person-{self.run_id}@live-smoke.test",
                department_id=archived_department.department_id,
                location_id=archived_location.location_id,
                source="live_smoke",
                status="active",
            )
            inactive_person = RegistryPerson(
                person_id=str(uuid.uuid4()),
                display_name=f"Phase 8 Inactive Binding Person {self.run_id}",
                source="live_smoke",
                status="inactive",
            )
            unlinked_login = f"phase8-unlinked-{self.run_id}@live-smoke.test"
            device = Device(
                device_id=str(uuid.uuid4()),
                protocol_version="ws_ticket_v3",
                agent_version="phase8-operability-smoke",
                hostname=f"phase8-binding-{self.run_id}",
                os="Windows 11 smoke",
                capabilities={"phase8_registry_operability": True},
                device_metadata={"phase8_registry_operability_run_id": self.run_id},
                first_seen_at=now,
                last_seen_at=now,
                last_handshake_at=now,
            )
            asset = RegistryAsset(
                asset_id=str(uuid.uuid4()),
                asset_type="pc",
                name=f"phase8-binding-{self.run_id}",
                hostname=f"phase8-binding-{self.run_id}",
                device_id=device.device_id,
                source="live_smoke",
                status="active",
                discovery_payload={"phase8_registry_operability_run_id": self.run_id},
            )
            binding = DeviceUserBinding(
                binding_id=str(uuid.uuid4()),
                device_id=device.device_id,
                person_id=inactive_person.person_id,
                relationship_type="primary_user",
                status="active",
                source="live_smoke",
                confidence=1,
            )
            audience_group = RegistryAudienceGroup(
                audience_group_id=str(uuid.uuid4()),
                code=f"phase8_empty_{self.run_id}",
                name=f"=Phase 8 Formula Group {self.run_id}",
                description=f"+Phase 8 Formula Description {self.run_id}",
                source="manual",
                status="active",
                created_by=self.ids["admin_login"],
                updated_by=self.ids["admin_login"],
            )
            missing_department_id = str(uuid.uuid4())
            audience_member = RegistryAudienceGroupMember(
                membership_id=str(uuid.uuid4()),
                audience_group_id=audience_group.audience_group_id,
                member_type="department",
                member_id=missing_department_id,
                include_children=False,
                source="manual",
                created_by=self.ids["admin_login"],
                updated_by=self.ids["admin_login"],
            )
            session.add_all(
                [
                    archived_department,
                    archived_location,
                    person,
                    inactive_person,
                    UiUser(user_login=unlinked_login, password_hash="live-smoke", actor_role="user", is_active=True),
                    device,
                    asset,
                    audience_group,
                ]
            )
            await session.flush()
            session.add_all(
                [
                    RegistryPersonIdentity(
                        person_id=person.person_id,
                        provider="ui_login",
                        identifier=f"phase8-linked-{self.run_id}",
                        normalized_identifier=normalize_identifier("ui_login", f"phase8-linked-{self.run_id}"),
                        verified=True,
                        source="live_smoke",
                    ),
                    binding,
                    audience_member,
                ]
            )
            await session.commit()
            self.ids.update(
                {
                    "archived_department_id": archived_department.department_id,
                    "archived_location_id": archived_location.location_id,
                    "person_id": person.person_id,
                    "inactive_person_id": inactive_person.person_id,
                    "ui_user_login": unlinked_login,
                    "device_id": device.device_id,
                    "asset_id": asset.asset_id,
                    "binding_id": binding.binding_id,
                    "audience_group_id": audience_group.audience_group_id,
                    "audience_group_code": audience_group.code,
                    "audience_member_id": audience_member.membership_id,
                    "missing_department_id": missing_department_id,
                }
            )
            self.report["created"] = {
                key: self.ids[key]
                for key in (
                    "ui_user_login",
                    "person_id",
                    "binding_id",
                    "audience_group_id",
                )
            }

    def _export_csv(self, export_type: str) -> str:
        url = f"{self.api.base_url}/api/web/admin/registry/export?{parse.urlencode({'type': export_type, 'format': 'csv'})}"
        req = request.Request(
            url,
            headers={
                "Accept": "text/csv",
                "Authorization": f"Bearer {self.api.token}",
            },
            method="GET",
        )
        try:
            with self.api.opener.open(req, timeout=45) as response:
                return response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise SmokeFailure(f"GET export {export_type} failed with HTTP {exc.code}: {body[:500]}") from exc
        except error.URLError as exc:
            raise SmokeFailure(f"GET export {export_type} failed: {exc}") from exc

    def _find_issue(self, payload: dict[str, Any], *, kind: str, object_id: str) -> dict[str, Any]:
        for issue in payload.get("data_quality") or []:
            if issue.get("kind") == kind and str(issue.get("object_id") or "") == object_id:
                return issue
        raise SmokeFailure(f"quality issue {kind} for {object_id} not found")

    def _require_timeline_event(self, *, object_type: str, object_id: str, event_type: str) -> None:
        timeline = self.api.get(
            f"/api/web/admin/registry/timeline/{parse.quote(object_type, safe='')}/{parse.quote(object_id, safe='')}"
        )
        events = [str(item.get("event_type") or "") for item in timeline.get("items") or []]
        _require(event_type in events, f"timeline missing {event_type} for {object_type}:{object_id}")

    async def run(self) -> dict[str, Any]:
        await self.setup()
        try:
            registry_before = self.api.get("/api/web/admin/registry")
            expected = {
                "ui_user_unlinked_registry_person": self.ids["ui_user_login"],
                "person_archived_department": self.ids["person_id"],
                "person_archived_location": self.ids["person_id"],
                "binding_inactive_person": self.ids["binding_id"],
                "audience_group_empty": self.ids["audience_group_id"],
            }
            issues = {
                kind: self._find_issue(registry_before, kind=kind, object_id=object_id)
                for kind, object_id in expected.items()
            }
            self.report["checks"]["quality_before"] = {
                "status": "passed",
                "issue_count": len(registry_before.get("data_quality") or []),
                "expected_issue_keys": {kind: issue.get("issue_key") for kind, issue in issues.items()},
                "audience_group_warnings": issues["audience_group_empty"].get("warning_codes") or [],
            }

            groups_csv = self._export_csv("audience_groups")
            members_csv = self._export_csv("audience_group_members")
            _require(self.ids["audience_group_code"] in groups_csv, "audience group export missing seeded group")
            _require("'=Phase 8 Formula Group" in groups_csv, "audience group export did not escape formula-leading name")
            _require("'+Phase 8 Formula Description" in groups_csv, "audience group export did not escape formula-leading description")
            _require(self.ids["missing_department_id"] in members_csv, "audience member export missing seeded missing department member")
            self.report["checks"]["export"] = {
                "status": "passed",
                "audience_groups_sample": _csv_sample(groups_csv, marker=self.ids["audience_group_code"]),
                "audience_group_members_sample": _csv_sample(members_csv, marker=self.ids["missing_department_id"]),
            }

            duplicate_csv = (
                "code,name,description,source,status\n"
                f"{self.ids['audience_group_code']},Duplicate,{self.reason},import,active\n"
            )
            duplicate_preview = self.api.post(
                "/api/web/admin/registry/import/preview",
                {"type": "audience_groups", "format": "csv", "csv_text": duplicate_csv},
            )
            _require(duplicate_preview.get("duplicate_keys"), "audience group import preview did not detect duplicate code")

            import_group_code = f"phase8_import_{self.run_id}"
            import_group_csv = (
                "code,name,description,source,status\n"
                f"{import_group_code},Phase 8 Imported Group {self.run_id},Imported by live signoff,import,active\n"
            )
            preview = self.api.post(
                "/api/web/admin/registry/import/preview",
                {"type": "audience_groups", "format": "csv", "csv_text": import_group_csv},
            )
            _require(preview.get("can_apply") is True, "audience group import preview is not applyable")
            apply = self.api.post(
                "/api/web/admin/registry/import/apply",
                {
                    "type": "audience_groups",
                    "format": "csv",
                    "csv_text": import_group_csv,
                    "preview_id": preview["preview_id"],
                    "reason": self.reason,
                },
            )
            _require(apply.get("status") == "success", "audience group import apply did not succeed")
            operation_id = str(apply.get("operation_id") or "")
            _require(bool(operation_id), "audience group import apply did not return operation_id")
            async with get_session() as session:
                imported_group = (
                    await session.execute(select(RegistryAudienceGroup).where(RegistryAudienceGroup.code == import_group_code))
                ).scalar_one_or_none()
                _require(imported_group is not None, "imported audience group not found in DB")
                imported_group_id = imported_group.audience_group_id

            import_member_csv = (
                "group_code,member_type,member_id,include_children,source\n"
                f"{import_group_code},department,{self.ids['archived_department_id']},false,import\n"
            )
            member_preview = self.api.post(
                "/api/web/admin/registry/import/preview",
                {"type": "audience_group_members", "format": "csv", "csv_text": import_member_csv},
            )
            _require(member_preview.get("can_apply") is True, "audience group member import preview is not applyable")
            member_apply = self.api.post(
                "/api/web/admin/registry/import/apply",
                {
                    "type": "audience_group_members",
                    "format": "csv",
                    "csv_text": import_member_csv,
                    "preview_id": member_preview["preview_id"],
                    "reason": self.reason,
                },
            )
            _require(member_apply.get("status") == "success", "audience group member import apply did not succeed")
            member_operation_id = str(member_apply.get("operation_id") or "")
            _require(bool(member_operation_id), "audience group member import apply did not return operation_id")
            self.ids["imported_audience_group_id"] = imported_group_id
            self.ids["import_operation_id"] = operation_id
            self.ids["member_import_operation_id"] = member_operation_id
            self.report["checks"]["import_preview_apply"] = {
                "status": "passed",
                "duplicate_preview_detected": True,
                "audience_groups": {
                    "preview_id": preview["preview_id"],
                    "operation_id": operation_id,
                    "imported_group_id": imported_group_id,
                    "summary": apply.get("summary"),
                },
                "audience_group_members": {
                    "preview_id": member_preview["preview_id"],
                    "operation_id": member_operation_id,
                    "summary": member_apply.get("summary"),
                },
            }

            snoozed_issue_key = str(issues["audience_group_empty"].get("issue_key") or "")
            snooze = self.api.post(
                f"/api/web/admin/registry/quality/{parse.quote(snoozed_issue_key, safe='')}/snooze",
                {"reason": self.reason, "days": 7},
            )
            _require((snooze.get("override") or {}).get("status") == "snoozed", "quality issue snooze did not persist override")
            registry_after = self.api.get("/api/web/admin/registry")
            _require(
                not any(issue.get("issue_key") == snoozed_issue_key for issue in registry_after.get("data_quality") or []),
                "snoozed quality issue remained visible in registry snapshot",
            )
            self.report["checks"]["quality_override"] = {
                "status": "passed",
                "snoozed_issue_key": snoozed_issue_key,
                "hidden_after_snooze": True,
            }

            self._require_timeline_event(object_type="registry_import", object_id=operation_id, event_type="registry_import_applied")
            self._require_timeline_event(object_type="registry_import", object_id=member_operation_id, event_type="registry_import_applied")
            self._require_timeline_event(object_type="quality_issue", object_id=snoozed_issue_key, event_type="quality_issue_snoozed")
            self.report["checks"]["timeline_events"] = {
                "status": "passed",
                "events": ["registry_import_applied", "registry_import_applied", "quality_issue_snoozed"],
            }

            self.report["status"] = "passed"
            sanitized = sanitize_for_report(self.report)
            _assert_no_raw_secret(sanitized)
            return sanitized
        except Exception as exc:
            self.report["status"] = "failed"
            self.report["error"] = str(exc)
            return sanitize_for_report(self.report)
        finally:
            await self.close()


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sanitize_for_report(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def async_main(args: argparse.Namespace) -> int:
    signoff = Phase8LiveSignoff(base_url=args.base_url, run_id=args.run_id, insecure_tls=args.insecure_tls)
    report = await signoff.run()
    output = Path(args.output) if args.output else default_output_path(run_id=args.run_id)
    write_report(report, output)
    print(json.dumps(sanitize_for_report({**report, "output": str(output)}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("status") == "passed" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live Phase 8 Registry operability quality/import-export signoff.")
    parser.add_argument("--base-url", default="https://example.test:9443")
    parser.add_argument("--run-id", default=_now_id())
    parser.add_argument("--output", default="")
    parser.add_argument("--insecure-tls", action="store_true")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(async_main(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
