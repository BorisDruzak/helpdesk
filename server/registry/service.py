from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DevicePresenceSnapshot,
    KnowledgeAudienceRule,
    KnowledgeItem,
    KnowledgeSpace,
    RegistryAudienceGroup,
    RegistryPersonIdentity,
    RegistryQualityIssueOverride,
    UiUser,
)
from app.repos.registry_repo import RegistryRepo
from app.repos.registration_repo import normalize_identifier
from registry.account_session_service import AccountSessionService
from registry.audience_group_service import RegistryAudienceService
from registry.profile_schema_service import RequesterProfileSchemaService


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _metadata_value(metadata: Any, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    return _clean(metadata.get(key))


def _presence_identity_match(current_user: str | None, identities: list[RegistryPersonIdentity]) -> bool | None:
    user = str(current_user or "").strip()
    if not user or not identities:
        return None
    current_values = {
        normalize_identifier("windows_login", user),
        normalize_identifier("ui_login", user),
    }
    if "\\" in user:
        current_values.add(normalize_identifier("ui_login", user.split("\\", 1)[1]))
    current_values = {value for value in current_values if value}
    if not current_values:
        return None

    comparable_seen = False
    for identity in identities:
        provider = str(identity.provider or "").strip().lower()
        normalized = str(identity.normalized_identifier or "").strip().lower()
        if not normalized:
            continue
        if provider in {"windows_login", "ui_login", "ad"}:
            comparable_seen = True
            if normalized in current_values:
                return True
            if "\\" in normalized and normalized.split("\\", 1)[1] in current_values:
                return True
        elif provider == "email":
            local_part = normalized.split("@", 1)[0]
            if local_part:
                comparable_seen = True
                if local_part in current_values:
                    return True
                if any(value.endswith(f"\\{local_part}") for value in current_values):
                    return True
    return False if comparable_seen else None


def _asset_registration_status(
    device_id: str | None,
    active_primary_by_device: dict[str, Any],
    active_shared_by_device: dict[str, list[Any]],
    pending_by_device: dict[str, list[Any]],
) -> str:
    key = str(device_id or "")
    pending_claims = pending_by_device.get(key, [])
    if active_primary_by_device.get(key):
        return "admin_confirmed"
    if active_shared_by_device.get(key):
        return "shared_device"
    if any(claim.status == "conflict" for claim in pending_claims):
        return "conflict"
    if pending_claims:
        return "pending"
    return "unregistered"


def _quality_issue_key(issue: dict[str, Any]) -> str:
    object_type = str(issue.get("object_type") or "object").strip() or "object"
    object_id = str(issue.get("object_id") or "").strip()
    related = (
        issue.get("binding_id")
        or issue.get("claim_id")
        or ",".join(str(item) for item in issue.get("duplicate_person_ids") or [])
        or None
    )
    parts = [str(issue.get("kind") or "issue").strip(), object_type, object_id]
    if related and str(related) != object_id:
        parts.append(str(related))
    return ":".join(part.replace(":", "_") for part in parts if part)


REQUESTER_VISIBLE_KNOWLEDGE_VISIBILITIES = {"public", "requester", "agent_requester_safe"}


def _is_active_person(person: Any) -> bool:
    return str(getattr(person, "status", "") or "active") not in {"inactive", "merged", "archived"}


def _department_tree_ids(department_id: str, children_by_parent: dict[str | None, list[str]]) -> set[str]:
    pending = [department_id]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(children_by_parent.get(current, []))
    return seen


@dataclass(frozen=True)
class RegistryProfileIngestResult:
    person_id: str
    asset_id: str | None
    location_id: str | None
    department_id: str | None
    registration: dict[str, Any] = field(default_factory=dict)


class RegistryIngestionService:
    """Converts discovered/self-reported agent data into registry records."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RegistryRepo(session)

    async def ingest_agent_handshake(
        self,
        *,
        device_id: str,
        hostname: str | None,
        os_name: str | None,
        agent_version: str | None,
        metadata: dict[str, Any] | None = None,
    ):
        return await self.repo.upsert_agent_asset(
            device_id=device_id,
            hostname=_clean(hostname),
            os_name=_clean(os_name),
            agent_version=_clean(agent_version),
            metadata=metadata or {},
        )

    async def ingest_requester_profile(
        self,
        *,
        device_id: str | None,
        requester_id: str | None,
        display_name: str | None,
        profile: dict[str, Any] | None,
    ) -> RegistryProfileIngestResult:
        from registry.registration_service import RegistrationService

        profile = profile or {}
        full_name = _clean(profile.get("full_name")) or _clean(display_name) or _clean(requester_id) or "Unknown user"
        person_display_name = _clean(display_name) or full_name
        result = await RegistrationService(self.session).submit_agent_profile_claim(
            device_id=device_id or "",
            requester_id=requester_id,
            display_name=person_display_name,
            profile={**profile, "full_name": full_name},
            actor_id=requester_id,
            actor_role="agent",
        )
        registration = result.get("registration") if isinstance(result.get("registration"), dict) else {}
        person_payload = result.get("person") if isinstance(result.get("person"), dict) else {}
        asset_payload = result.get("asset") if isinstance(result.get("asset"), dict) else {}
        person = await self.repo.get_person(person_payload.get("person_id"))
        asset = await self.repo.get_asset(asset_payload.get("asset_id"))
        location = await self.repo.get_location(person.location_id if person else None)
        department = await self.repo.get_department(person.department_id if person else None)

        return RegistryProfileIngestResult(
            person_id=person.person_id if person else "",
            asset_id=asset.asset_id if asset else None,
            location_id=location.location_id if location else None,
            department_id=department.department_id if department else None,
            registration=registration,
        )


class RegistrySnapshotService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RegistryRepo(session)

    async def build_snapshot(self) -> dict[str, Any]:
        from registry.registration_service import RegistrationService

        registration_service = RegistrationService(self.session)
        assets = await self.repo.list_assets()
        people = await self.repo.list_people()
        locations = await self.repo.list_locations()
        departments = await self.repo.list_departments()
        services = await self.repo.list_services()
        vendors = await self.repo.list_vendors()
        claims = await registration_service.repo.list_claims(limit=300)
        bindings = []
        for asset in assets:
            if asset.device_id:
                bindings.extend(await registration_service.repo.list_bindings_for_device(asset.device_id))
        account_service = AccountSessionService(self.session)
        account_sessions = await account_service.list_sessions_admin(limit=500)
        account_login_requests = await account_service.list_login_requests(limit=300)
        ui_users = list(
            (
                await self.session.execute(
                    select(UiUser).order_by(UiUser.user_login).limit(500)
                )
            ).scalars().all()
        )
        all_audience_groups = list(
            (
                await self.session.execute(
                    select(RegistryAudienceGroup)
                    .order_by(RegistryAudienceGroup.code.asc())
                    .limit(500)
                )
            ).scalars().all()
        )
        audience_groups = [group for group in all_audience_groups if group.status == "active"]
        knowledge_rules = list(
            (
                await self.session.execute(
                    select(KnowledgeAudienceRule)
                    .where(KnowledgeAudienceRule.status == "active")
                    .order_by(KnowledgeAudienceRule.subject_type.asc(), KnowledgeAudienceRule.subject_id.asc(), KnowledgeAudienceRule.priority.asc())
                    .limit(1000)
                )
            ).scalars().all()
        )
        knowledge_items = list(
            (
                await self.session.execute(
                    select(KnowledgeItem)
                    .where(KnowledgeItem.status == "published")
                    .order_by(KnowledgeItem.updated_at.desc())
                    .limit(1000)
                )
            ).scalars().all()
        )
        knowledge_spaces = list(
            (
                await self.session.execute(
                    select(KnowledgeSpace)
                    .order_by(KnowledgeSpace.code.asc())
                    .limit(500)
                )
            ).scalars().all()
        )

        people_by_id = {person.person_id: person for person in people}
        locations_by_id = {location.location_id: location for location in locations}
        departments_by_id = {department.department_id: department for department in departments}
        audience_groups_by_id = {group.audience_group_id: group for group in all_audience_groups}
        knowledge_items_by_id = {item.item_id: item for item in knowledge_items}
        knowledge_spaces_by_id = {space.space_id: space for space in knowledge_spaces}
        department_children_by_parent: dict[str | None, list[str]] = {}
        for department in departments:
            department_children_by_parent.setdefault(department.parent_department_id, []).append(department.department_id)
        location_user_counts = {
            location.location_id: sum(1 for person in people if person.location_id == location.location_id)
            for location in locations
        }
        location_device_counts = {
            location.location_id: sum(1 for asset in assets if asset.location_id == location.location_id)
            for location in locations
        }
        department_user_counts = {
            department.department_id: sum(1 for person in people if person.department_id == department.department_id)
            for department in departments
        }
        department_device_counts = {
            department.department_id: sum(1 for asset in assets if asset.department_id == department.department_id)
            for department in departments
        }
        active_primary_by_device = {
            binding.device_id: binding
            for binding in bindings
            if binding.status == "active" and binding.relationship_type == "primary_user"
        }
        active_owner_by_device = {
            binding.device_id: binding
            for binding in bindings
            if binding.status == "active" and binding.relationship_type == "owner"
        }
        active_shared_by_device: dict[str, list[Any]] = {}
        active_responsible_by_device: dict[str, Any] = {}
        active_any_by_device: dict[str, Any] = {}
        bindings_by_device: dict[str, list[Any]] = {}
        bindings_by_person: dict[str, list[Any]] = {}
        for binding in bindings:
            bindings_by_device.setdefault(binding.device_id, []).append(binding)
            bindings_by_person.setdefault(binding.person_id, []).append(binding)
            if binding.status != "active":
                continue
            active_any_by_device.setdefault(binding.device_id, binding)
            if binding.relationship_type == "shared_user":
                active_shared_by_device.setdefault(binding.device_id, []).append(binding)
            if binding.relationship_type == "responsible":
                active_responsible_by_device.setdefault(binding.device_id, binding)
        identities_by_person: dict[str, list[RegistryPersonIdentity]] = {}
        person_ids = [person.person_id for person in people]
        if person_ids:
            identity_rows = (
                await self.session.execute(
                    select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id.in_(person_ids))
                )
            ).scalars().all()
            for identity in identity_rows:
                identities_by_person.setdefault(identity.person_id, []).append(identity)
        ui_login_identity_by_normalized = {
            identity.normalized_identifier: identity
            for identities in identities_by_person.values()
            for identity in identities
            if identity.provider == "ui_login" and identity.normalized_identifier
        }
        latest_presence_by_device: dict[str, DevicePresenceSnapshot] = {}
        device_ids = [asset.device_id for asset in assets if asset.device_id]
        if device_ids:
            presence_rows = (
                await self.session.execute(
                    select(DevicePresenceSnapshot)
                    .where(DevicePresenceSnapshot.device_id.in_(device_ids))
                    .order_by(DevicePresenceSnapshot.device_id, desc(DevicePresenceSnapshot.collected_at))
                )
            ).scalars().all()
            for row in presence_rows:
                latest_presence_by_device.setdefault(row.device_id, row)
        pending_by_device: dict[str, list[Any]] = {}
        for claim in claims:
            if claim.status in {"self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review", "conflict"}:
                pending_by_device.setdefault(claim.device_id, []).append(claim)
        ticket_counts = await self.repo.count_tickets_by_device_ids([asset.device_id for asset in assets if asset.device_id])
        active_sessions_by_device: dict[str, list[dict[str, Any]]] = {}
        active_sessions_by_person: dict[str, list[dict[str, Any]]] = {}
        sessions_by_binding: dict[str, list[dict[str, Any]]] = {}
        for account_session in account_sessions:
            if account_session.get("verification_status") == "verified" and not account_session.get("revoked_at"):
                active_sessions_by_device.setdefault(account_session.get("device_id") or "", []).append(account_session)
                if account_session.get("person_id"):
                    active_sessions_by_person.setdefault(account_session.get("person_id") or "", []).append(account_session)
                if account_session.get("binding_id"):
                    sessions_by_binding.setdefault(account_session.get("binding_id") or "", []).append(account_session)
                if account_session.get("base_binding_id"):
                    sessions_by_binding.setdefault(account_session.get("base_binding_id") or "", []).append(account_session)

        data_quality = []
        for asset in assets:
            active_binding = active_any_by_device.get(asset.device_id or "")
            active_owner_binding = (
                active_primary_by_device.get(asset.device_id or "")
                or active_owner_by_device.get(asset.device_id or "")
            )
            active_responsible_binding = active_responsible_by_device.get(asset.device_id or "")
            pending_claims = pending_by_device.get(asset.device_id or "", [])
            if asset.asset_type == "pc" and not asset.location_id:
                data_quality.append({
                    "kind": "asset_missing_location",
                    "severity": "warning",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "device_id": asset.device_id,
                    "title": "PC without location",
                    "description": asset.name,
                    "details": asset.name,
                })
            if asset.asset_type == "pc" and not active_binding:
                data_quality.append({
                    "kind": "asset_missing_confirmed_user",
                    "severity": "warning",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "device_id": asset.device_id,
                    "title": "PC without confirmed user",
                    "description": asset.name,
                    "details": asset.name,
                })
            if asset.asset_type == "pc" and not (active_owner_binding or active_responsible_binding or asset.assigned_person_id):
                data_quality.append({
                    "kind": "asset_missing_owner_or_responsible",
                    "severity": "warning",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "device_id": asset.device_id,
                    "title": "PC without owner or responsible person",
                    "description": asset.name,
                    "details": asset.name,
                })
            if any(claim.status in {"pending_user_confirmation", "self_reported", "user_confirmed", "pending_admin_review"} for claim in pending_claims):
                data_quality.append({
                    "kind": "registration_pending_confirmation",
                    "severity": "info",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "device_id": asset.device_id,
                    "claim_id": pending_claims[0].claim_id if pending_claims else None,
                    "title": "Registration pending",
                    "description": asset.name,
                    "details": asset.name,
                })
            conflict = next((claim for claim in pending_claims if claim.status == "conflict"), None)
            if conflict:
                data_quality.append({
                    "kind": "registration_conflict",
                    "severity": "danger",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "device_id": asset.device_id,
                    "claim_id": conflict.claim_id,
                    "title": "Registration conflict",
                    "description": conflict.conflict_reason or asset.name,
                    "details": conflict.conflict_reason or asset.name,
                })
        for binding in bindings:
            if binding.status == "stale":
                data_quality.append({
                    "kind": "binding_stale",
                    "severity": "warning",
                    "object_type": "binding",
                    "object_id": binding.binding_id,
                    "binding_id": binding.binding_id,
                    "device_id": binding.device_id,
                    "person_id": binding.person_id,
                    "title": "Registration binding is stale",
                    "description": binding.device_id,
                    "details": binding.device_id,
                })
            if binding.status == "active":
                person = people_by_id.get(binding.person_id)
                if person is None or not _is_active_person(person):
                    data_quality.append({
                        "kind": "binding_inactive_person",
                        "severity": "danger",
                        "object_type": "binding",
                        "object_id": binding.binding_id,
                        "binding_id": binding.binding_id,
                        "device_id": binding.device_id,
                        "person_id": binding.person_id,
                        "title": "Active binding points to inactive person",
                        "description": binding.device_id,
                        "details": binding.person_id,
                    })
        for asset in assets:
            active_binding = active_primary_by_device.get(asset.device_id or "") or active_any_by_device.get(asset.device_id or "")
            presence = latest_presence_by_device.get(asset.device_id or "")
            current_user = (presence.current_user if presence else None) or ""
            identities = identities_by_person.get(active_binding.person_id if active_binding else "", [])
            presence_match = _presence_identity_match(current_user, identities)
            if active_binding and presence_match is False:
                data_quality.append({
                    "kind": "presence_user_mismatch",
                    "severity": "warning",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "device_id": asset.device_id,
                    "person_id": active_binding.person_id,
                    "title": "Presence user differs from active binding",
                    "description": asset.name,
                    "details": asset.name,
                })
        for location in locations:
            if location.status == "pending":
                data_quality.append({
                    "kind": "location_pending_confirmation",
                    "severity": "info",
                    "object_type": "location",
                    "object_id": location.location_id,
                    "title": "Location pending confirmation",
                    "description": location.display_name,
                    "details": location.display_name,
                })
        for department in departments:
            if department.status == "pending":
                data_quality.append({
                    "kind": "department_pending_confirmation",
                    "severity": "info",
                    "object_type": "department",
                    "object_id": department.department_id,
                    "department_id": department.department_id,
                    "title": "Department pending confirmation",
                    "description": department.name,
                    "details": department.name,
                })
        for person in people:
            if not _is_active_person(person):
                continue
            if not person.department_id:
                data_quality.append({
                    "kind": "person_missing_department",
                    "severity": "warning",
                    "object_type": "person",
                    "object_id": person.person_id,
                    "person_id": person.person_id,
                    "title": "Person without department",
                    "description": person.display_name,
                    "details": person.display_name,
                })
            if not person.location_id:
                data_quality.append({
                    "kind": "person_missing_location",
                    "severity": "warning",
                    "object_type": "person",
                    "object_id": person.person_id,
                    "person_id": person.person_id,
                    "title": "Person without location",
                    "description": person.display_name,
                    "details": person.display_name,
                })
            if person.department_id:
                department = departments_by_id.get(person.department_id)
                if department is not None and department.status == "archived":
                    data_quality.append({
                        "kind": "person_archived_department",
                        "severity": "warning",
                        "object_type": "person",
                        "object_id": person.person_id,
                        "person_id": person.person_id,
                        "department_id": person.department_id,
                        "title": "Person uses archived department",
                        "description": person.display_name,
                        "details": department.name,
                    })
            if person.location_id:
                location = locations_by_id.get(person.location_id)
                if location is not None and location.status == "archived":
                    data_quality.append({
                        "kind": "person_archived_location",
                        "severity": "warning",
                        "object_type": "person",
                        "object_id": person.person_id,
                        "person_id": person.person_id,
                        "location_id": person.location_id,
                        "title": "Person uses archived location",
                        "description": person.display_name,
                        "details": location.display_name,
                    })
        for user in ui_users:
            if not user.is_active:
                continue
            normalized_login = normalize_identifier("ui_login", user.user_login)
            if ui_login_identity_by_normalized.get(normalized_login):
                continue
            data_quality.append({
                "kind": "ui_user_unlinked_registry_person",
                "severity": "warning",
                "object_type": "ui_user",
                "object_id": user.user_login,
                "user_login": user.user_login,
                "title": "UI user is not linked to Registry person",
                "description": user.user_login,
                "details": user.actor_role,
            })
        people_by_identity_key: dict[tuple[str, str], list[Any]] = {}
        for person_id, identities in identities_by_person.items():
            for identity in identities:
                people_by_identity_key.setdefault((identity.provider, identity.normalized_identifier), []).append(identity)
            if not identities and people_by_id.get(person_id) and people_by_id[person_id].status not in {"merged", "inactive"}:
                data_quality.append({
                    "kind": "missing_identity",
                    "severity": "warning",
                    "object_type": "person",
                    "object_id": person_id,
                    "person_id": person_id,
                    "title": "Person has no identity",
                    "description": people_by_id[person_id].display_name,
                    "details": people_by_id[person_id].display_name,
                })
        seen_duplicate_people: set[tuple[str, str]] = set()
        for (provider, normalized), rows in people_by_identity_key.items():
            person_ids_for_identity = sorted({row.person_id for row in rows})
            if len(person_ids_for_identity) > 1:
                key = (provider, normalized)
                if key in seen_duplicate_people:
                    continue
                seen_duplicate_people.add(key)
                data_quality.append({
                    "kind": "duplicate_person",
                    "severity": "warning",
                    "object_type": "person",
                    "object_id": person_ids_for_identity[0],
                    "person_id": person_ids_for_identity[0],
                    "duplicate_person_ids": person_ids_for_identity[1:],
                    "title": "Possible duplicate people",
                    "description": f"{provider}: {normalized}",
                    "details": f"{provider}: {normalized}",
                })

        audience_service = RegistryAudienceService(self.session)
        audience_group_previews: dict[str, dict[str, Any]] = {}
        for group in audience_groups:
            preview = await audience_service.preview_members(group.audience_group_id)
            audience_group_previews[group.audience_group_id] = preview
            if int(preview.get("person_count") or 0) > 0:
                continue
            data_quality.append({
                "kind": "audience_group_empty",
                "severity": "warning",
                "object_type": "audience_group",
                "object_id": group.audience_group_id,
                "audience_group_id": group.audience_group_id,
                "title": "Audience group has no effective members",
                "description": group.code,
                "details": group.name,
                "member_count": int(preview.get("member_count") or 0),
                "person_count": int(preview.get("person_count") or 0),
                "warning_codes": [str(item.get("code") or "") for item in preview.get("warnings") or [] if isinstance(item, dict)],
            })

        async def knowledge_rule_target_count(rule: KnowledgeAudienceRule) -> int | None:
            target_type = str(rule.target_type or "")
            target_id = str(rule.target_id or "").strip()
            if not target_id:
                return 0
            active_people = [person for person in people if _is_active_person(person)]
            if target_type == "person":
                person = people_by_id.get(target_id)
                return 1 if person is not None and _is_active_person(person) else 0
            if target_type == "department":
                department = departments_by_id.get(target_id)
                if department is None or department.status == "archived":
                    return 0
                return sum(1 for person in active_people if person.department_id == target_id)
            if target_type == "department_tree":
                department = departments_by_id.get(target_id)
                if department is None or department.status == "archived":
                    return 0
                department_ids = _department_tree_ids(target_id, department_children_by_parent)
                return sum(1 for person in active_people if person.department_id in department_ids)
            if target_type == "location":
                location = locations_by_id.get(target_id)
                if location is None or location.status == "archived":
                    return 0
                return sum(1 for person in active_people if person.location_id == target_id)
            if target_type == "audience_group":
                group = audience_groups_by_id.get(target_id)
                if group is None or group.status != "active":
                    return 0
                preview = audience_group_previews.get(target_id)
                if preview is None:
                    preview = await audience_service.preview_members(target_id)
                    audience_group_previews[target_id] = preview
                return int(preview.get("person_count") or 0)
            return None

        knowledge_rules_by_item: dict[str, list[KnowledgeAudienceRule]] = {}
        knowledge_rules_by_space: dict[str, list[KnowledgeAudienceRule]] = {}
        for rule in knowledge_rules:
            if rule.subject_type == "item":
                knowledge_rules_by_item.setdefault(rule.subject_id, []).append(rule)
            elif rule.subject_type == "space":
                knowledge_rules_by_space.setdefault(rule.subject_id, []).append(rule)

            target_type = str(rule.target_type or "")
            target_id = str(rule.target_id or "").strip()
            invalid_target = False
            if target_type == "person":
                person = people_by_id.get(target_id)
                invalid_target = person is None or not _is_active_person(person)
            elif target_type in {"department", "department_tree"}:
                department = departments_by_id.get(target_id)
                invalid_target = department is None or department.status == "archived"
            elif target_type == "location":
                location = locations_by_id.get(target_id)
                invalid_target = location is None or location.status == "archived"
            elif target_type == "audience_group":
                group = audience_groups_by_id.get(target_id)
                invalid_target = group is None or group.status != "active"
            if invalid_target:
                data_quality.append({
                    "kind": "knowledge_audience_rule_invalid_target",
                    "severity": "danger",
                    "object_type": "knowledge_audience_rule",
                    "object_id": rule.rule_id,
                    "knowledge_rule_id": rule.rule_id,
                    "title": "Knowledge audience rule has invalid target",
                    "description": f"{target_type}: {target_id}",
                    "details": f"{rule.subject_type}:{rule.subject_id}",
                    "subject_type": rule.subject_type,
                    "subject_id": rule.subject_id,
                    "target_type": target_type,
                    "target_id": target_id,
                })

        for item in knowledge_items:
            if item.visibility not in REQUESTER_VISIBLE_KNOWLEDGE_VISIBILITIES:
                continue
            space = knowledge_spaces_by_id.get(item.space_id)
            if space is not None and space.visibility not in REQUESTER_VISIBLE_KNOWLEDGE_VISIBILITIES:
                continue
            rules = [*knowledge_rules_by_space.get(item.space_id, []), *knowledge_rules_by_item.get(item.item_id, [])]
            if not rules:
                continue
            counts: list[int] = []
            has_unknown_scope = False
            for rule in rules:
                count = await knowledge_rule_target_count(rule)
                if count is None:
                    has_unknown_scope = True
                    break
                counts.append(count)
            if has_unknown_scope or sum(counts) > 0:
                continue
            data_quality.append({
                "kind": "knowledge_audience_zero_users",
                "severity": "warning",
                "object_type": "knowledge_item",
                "object_id": item.item_id,
                "knowledge_item_id": item.item_id,
                "title": "Knowledge item audience resolves to zero users",
                "description": item.slug,
                "details": item.title,
                "space_id": item.space_id,
                "rule_count": len(rules),
            })

        data_quality = await self._apply_quality_issue_overrides(data_quality)

        suggestions = []
        for asset in assets:
            active_binding = active_primary_by_device.get(asset.device_id or "") or active_any_by_device.get(asset.device_id or "")
            person = people_by_id.get(active_binding.person_id if active_binding else asset.assigned_person_id or "")
            if asset.hostname and person:
                suggestions.append({
                    "kind": "hostname_person_link",
                    "asset_id": asset.asset_id,
                    "person_id": person.person_id,
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "PC and user link exists",
                    "description": f"{asset.hostname} -> {person.display_name}",
                    "details": f"{asset.hostname} -> {person.display_name}",
                    "confidence": 0.95,
                })

        profile_schema_service = RequesterProfileSchemaService(self.session)
        profile_schema = await profile_schema_service.get_schema()

        def person_profile_completion_payload(person: Any) -> dict[str, Any]:
            missing = profile_schema_service.completion_missing_fields(person, profile_schema)
            required_fields = [
                {"key": field["key"], "label": field["label"]}
                for field in profile_schema.get("fields", [])
                if isinstance(field, dict) and field.get("visible", True) and field.get("required")
            ]
            complete = not missing
            return {
                "complete": complete,
                "status": "complete" if complete else "required",
                "required_fields": required_fields,
                "missing_fields": missing,
                "setup_path": "/app/requester/profile/setup",
                "blocks": {
                    "ticket_create": not complete,
                    "ticket_preview": not complete,
                    "knowledge_requester_actions": not complete,
                    "device_binding_confirmation": not complete,
                },
            }

        def person_context_payload(person: Any) -> dict[str, Any]:
            metadata = person.metadata_json if isinstance(person.metadata_json, dict) else {}
            manager_person_id = _metadata_value(metadata, "manager_person_id") or _metadata_value(metadata, "manager_id")
            manager = people_by_id.get(manager_person_id or "")
            department = departments_by_id.get(person.department_id or "")
            location = locations_by_id.get(person.location_id or "")
            return {
                "position": _metadata_value(metadata, "position"),
                "workplace_label": _metadata_value(metadata, "workplace_label"),
                "internal_extension": _metadata_value(metadata, "internal_extension") or _metadata_value(metadata, "extension"),
                "manager_person_id": manager_person_id,
                "manager_name": manager.display_name if manager else None,
                "department_id": person.department_id,
                "department_name": department.name if department else None,
                "location_id": person.location_id,
                "location_name": location.display_name if location else None,
            }

        def department_manager_name(department: Any) -> str | None:
            manager_person_id = _metadata_value(department.metadata_json, "manager_person_id")
            manager = people_by_id.get(manager_person_id or "")
            return manager.display_name if manager else None

        def asset_responsible_binding(asset: Any) -> Any | None:
            return active_responsible_by_device.get(asset.device_id or "")

        def service_payload(service: Any) -> dict[str, Any]:
            metadata = service.metadata_json if isinstance(service.metadata_json, dict) else {}
            owner_person_id = _metadata_value(metadata, "owner_person_id")
            owner = people_by_id.get(owner_person_id or "")
            return {
                "id": service.service_id,
                "service_id": service.service_id,
                "code": service.code,
                "name": service.name,
                "owner_queue_id": service.owner_queue_id,
                "owner_person_id": owner_person_id,
                "owner_person_name": owner.display_name if owner else None,
                "support_queue": str(service.owner_queue_id) if service.owner_queue_id else None,
                "criticality": _metadata_value(metadata, "criticality"),
                "audience": _metadata_value(metadata, "audience"),
                "audience_group_id": _metadata_value(metadata, "audience_group_id"),
                "vendor_id": service.vendor_id,
                "source": service.source,
                "status": service.status,
                "updated_at": service.updated_at.isoformat() if service.updated_at else None,
            }

        def person_payload(person: Any) -> dict[str, Any]:
            context = person_context_payload(person)
            return {
                "id": person.person_id,
                "person_id": person.person_id,
                "display_name": person.display_name,
                "full_name": person.full_name,
                "phone": person.phone,
                "email": person.email,
                "position": context["position"],
                "workplace_label": context["workplace_label"],
                "internal_extension": context["internal_extension"],
                "manager_person_id": context["manager_person_id"],
                "manager_name": context["manager_name"],
                "production_context": context,
                "profile_completion": person_profile_completion_payload(person),
                "status": person.status,
                "source": person.source,
                "department_id": person.department_id,
                "department_name": context["department_name"],
                "location_id": person.location_id,
                "location_display_name": context["location_name"],
                "location_name": context["location_name"],
                "login": next((identity.identifier for identity in identities_by_person.get(person.person_id, []) if identity.provider in {"windows_login", "ui_login", "ad"}), None),
                "identities": [identity_payload(identity) for identity in identities_by_person.get(person.person_id, [])],
                "identity_count": len(identities_by_person.get(person.person_id, [])),
                "verified_identity_count": sum(1 for identity in identities_by_person.get(person.person_id, []) if identity.verified),
                "primary_device_count": sum(1 for row in bindings_by_person.get(person.person_id, []) if row.status == "active" and row.relationship_type == "primary_user"),
                "shared_device_count": sum(1 for row in bindings_by_person.get(person.person_id, []) if row.status == "active" and row.relationship_type == "shared_user"),
                "responsible_device_count": sum(1 for row in bindings_by_person.get(person.person_id, []) if row.status == "active" and row.relationship_type == "responsible"),
                "active_ticket_count": 0,
                "active_session_count": len(active_sessions_by_person.get(person.person_id, [])),
                "last_seen_at": person.last_seen_at.isoformat() if person.last_seen_at else None,
                "updated_at": person.updated_at.isoformat() if person.updated_at else None,
            }

        def claim_payload(claim: Any) -> dict[str, Any]:
            person = people_by_id.get(claim.person_id or "")
            return {
                "claim_id": claim.claim_id,
                "device_id": claim.device_id,
                "asset_id": claim.asset_id,
                "person_id": claim.person_id,
                "person_name": person.display_name if person else None,
                "status": claim.status,
                "claim_type": claim.claim_type,
                "relationship_type": claim.relationship_type,
                "confidence": float(claim.confidence) if claim.confidence is not None else None,
                "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
                "user_confirmed_at": claim.user_confirmed_at.isoformat() if claim.user_confirmed_at else None,
                "conflict_reason": claim.conflict_reason,
                "profile_snapshot": claim.profile_snapshot or {},
            }

        def binding_payload(binding: Any) -> dict[str, Any]:
            person = people_by_id.get(binding.person_id or "")
            asset = next((item for item in assets if item.device_id == binding.device_id), None)
            return {
                "binding_id": binding.binding_id,
                "device_id": binding.device_id,
                "hostname": asset.hostname if asset else None,
                "asset_id": binding.asset_id,
                "person_id": binding.person_id,
                "person_name": person.display_name if person else None,
                "relationship_type": binding.relationship_type,
                "status": binding.status,
                "source": binding.source,
                "source_claim_id": binding.source_claim_id,
                "confirmed_at": binding.confirmed_at.isoformat() if binding.confirmed_at else None,
                "confirmed_by_admin": binding.confirmed_by_admin,
                "valid_from": binding.valid_from.isoformat() if binding.valid_from else None,
                "valid_to": binding.valid_to.isoformat() if binding.valid_to else None,
                "last_seen_at": binding.last_seen_at.isoformat() if binding.last_seen_at else None,
                "revoked_at": binding.revoked_at.isoformat() if binding.revoked_at else None,
                "revoked_by": binding.revoked_by,
                "revoke_reason": binding.revoke_reason,
                "active_sessions_count": len(sessions_by_binding.get(binding.binding_id, [])),
            }

        def identity_payload(identity: RegistryPersonIdentity) -> dict[str, Any]:
            return {
                "identity_id": identity.identity_id,
                "person_id": identity.person_id,
                "provider": identity.provider,
                "identifier": identity.identifier,
                "normalized_identifier": identity.normalized_identifier,
                "verified": bool(identity.verified),
                "source": identity.source,
                "last_seen_at": identity.last_seen_at.isoformat() if identity.last_seen_at else None,
            }

        def ui_user_payload(user: UiUser) -> dict[str, Any]:
            normalized_login = normalize_identifier("ui_login", user.user_login)
            identity = ui_login_identity_by_normalized.get(normalized_login)
            person = people_by_id.get(identity.person_id if identity else "")
            return {
                "user_login": user.user_login,
                "actor_role": user.actor_role,
                "is_active": bool(user.is_active),
                "failed_attempts": int(user.failed_attempts or 0),
                "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "linked_person_id": identity.person_id if identity else None,
                "linked_person_name": person.display_name if person else None,
                "linked_identity_id": identity.identity_id if identity else None,
                "linked_identity_verified": bool(identity.verified) if identity else False,
            }

        return {
            "summary": {
                "assets_count": len(assets),
                "assets": len(assets),
                "people_count": len(people),
                "people": len(people),
                "locations_count": len(locations),
                "locations": len(locations),
                "departments_count": len(departments),
                "departments": len(departments),
                "services_count": len(services),
                "services": len(services),
                "vendors_count": len(vendors),
                "vendors": len(vendors),
                "registrations_pending": sum(1 for claim in claims if claim.status in {"self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review"}),
                "registrations_conflicts": sum(1 for claim in claims if claim.status == "conflict"),
                "unregistered_devices": sum(1 for asset in assets if asset.asset_type == "pc" and not active_any_by_device.get(asset.device_id or "")),
                "active_bindings": sum(1 for binding in bindings if binding.status == "active"),
                "bindings_active": sum(1 for binding in bindings if binding.status == "active"),
                "stale_bindings": sum(1 for binding in bindings if binding.status == "stale"),
                "devices_total": sum(1 for asset in assets if asset.asset_type == "pc"),
                "devices_registered": sum(1 for asset in assets if asset.asset_type == "pc" and active_any_by_device.get(asset.device_id or "")),
                "devices_unregistered": sum(1 for asset in assets if asset.asset_type == "pc" and not active_any_by_device.get(asset.device_id or "")),
                "people_total": len(people),
                "shared_devices": len(active_shared_by_device),
                "sessions_active": sum(1 for row in account_sessions if row.get("verification_status") == "verified" and not row.get("revoked_at")),
                "sessions_other_account": sum(1 for row in account_sessions if row.get("account_mode") == "verified_other_account" and row.get("verification_status") == "verified" and not row.get("revoked_at")),
                "other_account_requests": sum(1 for row in account_login_requests if row.get("status") == "pending_verification"),
                "ui_users": len(ui_users),
                "ui_users_linked": sum(1 for user in ui_users if ui_login_identity_by_normalized.get(normalize_identifier("ui_login", user.user_login))),
                "ui_users_unlinked": sum(1 for user in ui_users if not ui_login_identity_by_normalized.get(normalize_identifier("ui_login", user.user_login))),
                "claims_pending": sum(1 for claim in claims if claim.status in {"self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review"}),
                "claims_conflict": sum(1 for claim in claims if claim.status == "conflict"),
                "quality_issues": len(data_quality),
                "data_quality_issue_count": len(data_quality),
                "data_quality_issues": len(data_quality),
                "suggestions_count": len(suggestions),
                "suggestions": len(suggestions),
            },
            "assets": [
                {
                    "id": asset.asset_id,
                    "asset_id": asset.asset_id,
                    "asset_type": asset.asset_type,
                    "name": asset.name,
                    "hostname": asset.hostname,
                    "device_id": asset.device_id,
                    "inventory_number": asset.inventory_number,
                    "serial_number": asset.serial_number,
                    "status": asset.status,
                    "source": asset.source,
                    "location_id": asset.location_id,
                    "location_name": locations_by_id.get(asset.location_id or "").display_name
                    if asset.location_id in locations_by_id
                    else None,
                    "location_display_name": locations_by_id.get(asset.location_id or "").display_name
                    if asset.location_id in locations_by_id
                    else None,
                    "assigned_person_id": asset.assigned_person_id,
                    "owner_name": people_by_id.get(asset.assigned_person_id or "").display_name
                    if asset.assigned_person_id in people_by_id
                    else None,
                    "assigned_person_display_name": people_by_id.get(asset.assigned_person_id or "").display_name
                    if asset.assigned_person_id in people_by_id
                    else None,
                    "department_id": asset.department_id,
                    "department_name": departments_by_id.get(asset.department_id or "").name
                    if asset.department_id in departments_by_id
                    else None,
                    "service_id": asset.service_id,
                    "service_name": None,
                    "vendor_id": asset.vendor_id,
                    "vendor_name": None,
                    "registration_status": _asset_registration_status(
                        asset.device_id,
                        active_primary_by_device,
                        active_shared_by_device,
                        pending_by_device,
                    ),
                    "active_binding_id": (
                        active_primary_by_device.get(asset.device_id or "")
                        or active_any_by_device.get(asset.device_id or "")
                    ).binding_id
                    if (active_primary_by_device.get(asset.device_id or "") or active_any_by_device.get(asset.device_id or ""))
                    else None,
                    "active_person_id": (
                        active_primary_by_device.get(asset.device_id or "")
                        or active_any_by_device.get(asset.device_id or "")
                    ).person_id
                    if (active_primary_by_device.get(asset.device_id or "") or active_any_by_device.get(asset.device_id or ""))
                    else None,
                    "active_person_name": people_by_id.get(
                        (active_primary_by_device.get(asset.device_id or "") or active_any_by_device.get(asset.device_id or "")).person_id
                    ).display_name
                    if (
                        (active_primary_by_device.get(asset.device_id or "") or active_any_by_device.get(asset.device_id or ""))
                        and (active_primary_by_device.get(asset.device_id or "") or active_any_by_device.get(asset.device_id or "")).person_id in people_by_id
                    )
                    else None,
                    "responsible_person_id": asset_responsible_binding(asset).person_id
                    if asset_responsible_binding(asset)
                    else None,
                    "responsible_person_name": people_by_id.get(asset_responsible_binding(asset).person_id).display_name
                    if asset_responsible_binding(asset) and asset_responsible_binding(asset).person_id in people_by_id
                    else None,
                    "pending_claim_count": len(pending_by_device.get(asset.device_id or "", [])),
                    "last_claim_at": max(
                        (claim.submitted_at for claim in pending_by_device.get(asset.device_id or "", []) if claim.submitted_at),
                        default=None,
                    ).isoformat()
                    if pending_by_device.get(asset.device_id or "")
                    else None,
                    "current_os_user": latest_presence_by_device.get(asset.device_id or "").current_user
                    if asset.device_id in latest_presence_by_device
                    else None,
                    "latest_presence_user": latest_presence_by_device.get(asset.device_id or "").current_user
                    if asset.device_id in latest_presence_by_device
                    else None,
                    "latest_presence_at": latest_presence_by_device.get(asset.device_id or "").collected_at.isoformat()
                    if asset.device_id in latest_presence_by_device
                    else None,
                    "os": (asset.discovery_payload or {}).get("os"),
                    "agent_version": (asset.discovery_payload or {}).get("agent_version"),
                    "binding_type": (
                        active_primary_by_device.get(asset.device_id or "")
                        or active_responsible_by_device.get(asset.device_id or "")
                        or active_any_by_device.get(asset.device_id or "")
                    ).relationship_type
                    if (
                        active_primary_by_device.get(asset.device_id or "")
                        or active_responsible_by_device.get(asset.device_id or "")
                        or active_any_by_device.get(asset.device_id or "")
                    )
                    else None,
                    "active_bindings": [
                        binding_payload(binding)
                        for binding in bindings_by_device.get(asset.device_id or "", [])
                        if binding.status == "active"
                    ],
                    "active_sessions_count": len(active_sessions_by_device.get(asset.device_id or "", [])),
                    "active_tickets_count": ticket_counts.get(asset.device_id or "", 0),
                    "can_bind": bool(asset.device_id),
                    "can_transfer": bool(asset.device_id),
                    "can_revoke": bool(asset.device_id and active_any_by_device.get(asset.device_id or "")),
                    "last_seen_at": asset.last_seen_at.isoformat() if asset.last_seen_at else None,
                    "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
                    "ticket_count": ticket_counts.get(asset.device_id or "", 0),
                }
                for asset in assets
            ],
            "people": [person_payload(person) for person in people],
            "locations": [
                {
                    "id": location.location_id,
                    "location_id": location.location_id,
                    "building": location.building,
                    "floor": location.floor,
                    "room": location.room,
                    "display_name": location.display_name,
                    "status": location.status,
                    "source": location.source,
                    "notes": (location.metadata_json or {}).get("notes"),
                    "metadata_json": location.metadata_json or {},
                    "users_count": location_user_counts.get(location.location_id, 0),
                    "devices_count": location_device_counts.get(location.location_id, 0),
                    "updated_at": location.updated_at.isoformat() if location.updated_at else None,
                }
                for location in locations
            ],
            "departments": [
                {
                    "id": department.department_id,
                    "department_id": department.department_id,
                    "code": department.code,
                    "name": department.name,
                    "status": department.status,
                    "source": department.source,
                    "parent_id": department.parent_department_id,
                    "manager_person_id": (department.metadata_json or {}).get("manager_person_id"),
                    "manager_name": department_manager_name(department),
                    "support_queue": (department.metadata_json or {}).get("support_queue"),
                    "notes": (department.metadata_json or {}).get("notes"),
                    "metadata_json": department.metadata_json or {},
                    "users_count": department_user_counts.get(department.department_id, 0),
                    "devices_count": department_device_counts.get(department.department_id, 0),
                    "updated_at": department.updated_at.isoformat() if department.updated_at else None,
                }
                for department in departments
            ],
            "services": [service_payload(service) for service in services],
            "vendors": [
                {
                    "id": vendor.vendor_id,
                    "vendor_id": vendor.vendor_id,
                    "code": None,
                    "name": vendor.name,
                    "contact_name": vendor.contact_name,
                    "phone": vendor.contact_phone,
                    "email": vendor.contact_email,
                    "contact_phone": vendor.contact_phone,
                    "contact_email": vendor.contact_email,
                    "source": vendor.source,
                    "status": vendor.status,
                    "updated_at": vendor.updated_at.isoformat() if vendor.updated_at else None,
                }
                for vendor in vendors
            ],
            "registration_claims": [claim_payload(claim) for claim in claims],
            "active_bindings": [binding_payload(binding) for binding in bindings if binding.status == "active"],
            "bindings": [binding_payload(binding) for binding in bindings],
            "account_sessions": account_sessions,
            "account_login_requests": account_login_requests,
            "ui_users": [ui_user_payload(user) for user in ui_users],
            "data_quality": data_quality,
            "suggestions": suggestions,
        }

    async def _apply_quality_issue_overrides(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not issues:
            return issues
        for issue in issues:
            issue["issue_key"] = _quality_issue_key(issue)
        issue_keys = [issue["issue_key"] for issue in issues]
        rows = (
            await self.session.execute(
                select(RegistryQualityIssueOverride).where(RegistryQualityIssueOverride.issue_key.in_(issue_keys))
            )
        ).scalars().all()
        overrides = {row.issue_key: row for row in rows}
        now = datetime.now(timezone.utc)
        active_issues: list[dict[str, Any]] = []
        for issue in issues:
            override = overrides.get(issue["issue_key"])
            if override is None:
                active_issues.append(issue)
                continue
            issue["issue_state"] = override.status
            issue["issue_state_reason"] = override.reason
            if override.status in {"ignored", "resolved"}:
                continue
            if override.status == "snoozed" and override.snoozed_until and override.snoozed_until > now:
                continue
            active_issues.append(issue)
        return active_issues
