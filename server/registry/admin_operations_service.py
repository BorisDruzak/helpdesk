from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import io
import re
import uuid
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Device,
    DeviceAccountEvent,
    DeviceAccountLoginRequest,
    DeviceAccountSession,
    DeviceInventoryBinding,
    DeviceRegistrationClaim,
    DeviceRegistrationEvent,
    DeviceUserBinding,
    RegistryAdminEvent,
    RegistryAsset,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    RegistryQualityIssueOverride,
    Ticket,
)
from app.repos.registration_repo import normalize_identifier
from registry.account_session_service import AccountSessionService
from registry.policy_service import RegistryPolicyService, build_registry_policy_response


BULK_LIMIT = 200
IMPORT_LIMIT = 1000
IMPORT_TEXT_LIMIT = 2 * 1024 * 1024
REGISTRY_IMPORT_TYPES = {"people", "locations", "departments", "device_inventory_mapping"}


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any, *, max_length: int = 500) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_length] if text else None


def _require_reason(reason: Any) -> str:
    value = _text(reason, max_length=1000)
    if not value:
        raise ValueError("reason is required")
    return value


def _location_display(building: str, floor: str | None, room: str | None, display_name: str | None = None) -> str:
    if display_name:
        return display_name
    parts = [building]
    if floor:
        parts.append(f"{floor} этаж")
    if room:
        parts.append(f"кабинет {room}")
    return ", ".join(parts)


def _department_code(value: Any) -> str | None:
    text = _text(value, max_length=100)
    return text.upper() if text else None


def _json_notes(metadata: dict[str, Any] | None) -> str | None:
    metadata = metadata or {}
    return _text(metadata.get("notes"), max_length=2000)


def _csv_safe(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.isoformat()
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _import_preview_id(import_type: str, csv_text: str) -> str:
    digest = hashlib.sha256()
    digest.update(str(import_type or "").strip().lower().replace("-", "_").encode("utf-8"))
    digest.update(b"\0")
    digest.update(csv_text.encode("utf-8"))
    return digest.hexdigest()


def _parse_quality_issue_key(issue_key: str) -> dict[str, str | None]:
    parts = [part.strip() for part in str(issue_key or "").split(":")]
    if len(parts) < 3 or not all(parts[:3]):
        raise ValueError("invalid quality issue key")
    return {
        "issue_kind": parts[0],
        "object_type": parts[1],
        "object_id": parts[2],
        "related_id": ":".join(parts[3:]) if len(parts) > 3 else None,
    }


TIMELINE_CANONICAL_EVENT_TYPES = {
    "admin_binding_created": "binding_created",
    "registry_policy_updated": "policy_changed",
    "person_merged": "people_merged",
    "bulk_device_location_assigned": "bulk_action_applied",
    "bulk_devices_department_assigned": "bulk_action_applied",
    "bulk_people_department_assigned": "bulk_action_applied",
    "bulk_account_session_revoked": "bulk_action_applied",
}


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


class RegistryAdminOperationsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def append_event(
        self,
        *,
        object_type: str,
        object_id: str,
        event_type: str,
        actor_id: str | None = None,
        actor_role: str | None = "admin",
        reason: str | None = None,
        related_device_id: str | None = None,
        related_person_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> RegistryAdminEvent:
        row = RegistryAdminEvent(
            event_id=_new_id(),
            object_type=object_type,
            object_id=str(object_id),
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            related_device_id=related_device_id,
            related_person_id=related_person_id,
            event_at=_now(),
            payload=payload or {},
        )
        self.session.add(row)
        await self.session.flush()
        return row

    @staticmethod
    def serialize_event(row: Any) -> dict[str, Any]:
        payload = getattr(row, "payload", None) or {}
        source = RegistryAdminOperationsService._event_source(row)
        related = RegistryAdminOperationsService._event_related(row, payload)
        event_type = str(getattr(row, "event_type", "") or "")
        canonical_event_type = RegistryAdminOperationsService._canonical_event_type(event_type, payload)
        reason = RegistryAdminOperationsService._event_reason(row, payload)
        item = {
            "event_id": row.event_id,
            "object_type": getattr(row, "object_type", None),
            "object_id": getattr(row, "object_id", None),
            "source": source,
            "event_type": event_type,
            "canonical_event_type": canonical_event_type,
            "summary": RegistryAdminOperationsService._event_summary(event_type, canonical_event_type, related, payload),
            "actor_id": getattr(row, "actor_id", None),
            "actor_role": getattr(row, "actor_role", None),
            "reason": reason,
            "related_device_id": getattr(row, "related_device_id", None),
            "related_person_id": getattr(row, "related_person_id", None),
            "device_id": getattr(row, "device_id", None),
            "person_id": getattr(row, "person_id", None),
            "binding_id": getattr(row, "binding_id", None),
            "claim_id": getattr(row, "claim_id", None),
            "session_id": getattr(row, "session_id", None),
            "request_id": getattr(row, "request_id", None),
            "ticket_id": getattr(row, "ticket_id", None),
            "event_at": _iso(getattr(row, "event_at", None)),
            "payload": payload,
            "related": related,
            "changes": RegistryAdminOperationsService._event_changes(row, payload),
        }
        return item

    @staticmethod
    def _event_source(row: Any) -> str:
        if isinstance(row, RegistryAdminEvent):
            return "registry_admin"
        if isinstance(row, DeviceRegistrationEvent):
            return "registration"
        if isinstance(row, DeviceAccountEvent):
            return "account"
        return "registry_admin"

    @staticmethod
    def _canonical_event_type(event_type: str, payload: dict[str, Any]) -> str:
        if event_type == "admin_binding_created":
            relationship_type = str(payload.get("relationship_type") or "")
            if relationship_type == "shared_user":
                return "shared_user_added"
            if relationship_type == "responsible":
                return "responsible_assigned"
        return TIMELINE_CANONICAL_EVENT_TYPES.get(event_type, event_type)

    @staticmethod
    def _event_related(row: Any, payload: dict[str, Any]) -> dict[str, Any]:
        related = {
            "object_type": getattr(row, "object_type", None),
            "object_id": getattr(row, "object_id", None),
            "device_id": getattr(row, "device_id", None) or getattr(row, "related_device_id", None) or payload.get("device_id"),
            "person_id": getattr(row, "person_id", None) or getattr(row, "related_person_id", None) or payload.get("person_id") or payload.get("matched_person_id"),
            "binding_id": getattr(row, "binding_id", None) or payload.get("binding_id") or payload.get("base_binding_id") or payload.get("old_binding_id"),
            "claim_id": getattr(row, "claim_id", None) or payload.get("claim_id") or payload.get("replacement_claim_id"),
            "session_id": getattr(row, "session_id", None) or payload.get("session_id"),
            "request_id": getattr(row, "request_id", None) or payload.get("request_id"),
            "ticket_id": getattr(row, "ticket_id", None) or payload.get("ticket_id"),
            "identity_id": payload.get("identity_id"),
            "location_id": payload.get("location_id") or payload.get("master_location_id"),
            "department_id": payload.get("department_id") or payload.get("master_department_id"),
        }
        return {key: value for key, value in related.items() if value is not None}

    @staticmethod
    def _event_reason(row: Any, payload: dict[str, Any]) -> str | None:
        return (
            getattr(row, "reason", None)
            or payload.get("reason")
            or payload.get("override_reason")
            or payload.get("rejection_reason")
            or payload.get("merge_reason")
        )

    @staticmethod
    def _event_changes(row: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
        changes = payload.get("changes")
        if isinstance(changes, list):
            return [change for change in changes if isinstance(change, dict)]
        before = payload.get("before")
        after = payload.get("after")
        if isinstance(before, dict) and isinstance(after, dict):
            fields = sorted(set(before.keys()) | set(after.keys()))
            return [
                {"field": field, "before": before.get(field), "after": after.get(field)}
                for field in fields
                if before.get(field) != after.get(field)
            ]
        if isinstance(before, dict) and after is None:
            return [{"field": field, "before": value, "after": None} for field, value in sorted(before.items())]
        if before is None and isinstance(after, dict):
            return [{"field": field, "before": None, "after": value} for field, value in sorted(after.items())]
        event_type = str(getattr(row, "event_type", "") or "")
        synthetic: list[dict[str, Any]] = []
        if "status" in payload:
            synthetic.append({"field": "status", "after": payload.get("status")})
        if "relationship_type" in payload:
            synthetic.append({"field": "relationship_type", "after": payload.get("relationship_type")})
        if event_type.startswith("account_session_") and payload.get("revoked_at"):
            synthetic.append({"field": "revoked_at", "after": payload.get("revoked_at")})
        return synthetic

    @staticmethod
    def _event_summary(event_type: str, canonical_event_type: str, related: dict[str, Any], payload: dict[str, Any]) -> str:
        if payload.get("summary"):
            return str(payload["summary"])
        labels = {
            "person_created": "Person created",
            "person_updated": "Person updated",
            "identity_added": "Identity added",
            "identity_verified": "Identity verified",
            "identity_deleted": "Identity deleted",
            "binding_created": "Binding created",
            "binding_revoked": "Binding revoked",
            "binding_transferred": "Binding transferred",
            "shared_user_added": "Shared user added",
            "responsible_assigned": "Responsible person assigned",
            "location_merged": "Location merged",
            "department_merged": "Department merged",
            "people_merged": "People merged",
            "bulk_action_applied": "Bulk action applied",
            "policy_changed": "Policy changed",
            "quality_issue_ignored": "Quality issue ignored",
            "quality_issue_snoozed": "Quality issue snoozed",
            "quality_issue_resolved": "Quality issue resolved",
        }
        label = labels.get(canonical_event_type) or labels.get(event_type) or event_type.replace("_", " ")
        target = related.get("object_id") or related.get("device_id") or related.get("person_id") or related.get("binding_id") or related.get("session_id")
        return f"{label}: {target}" if target else label

    def _location_payload(self, row: RegistryLocation, *, users_count: int = 0, devices_count: int = 0) -> dict[str, Any]:
        metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        return {
            "id": row.location_id,
            "location_id": row.location_id,
            "building": row.building,
            "floor": row.floor,
            "room": row.room,
            "display_name": row.display_name,
            "status": row.status,
            "source": row.source,
            "notes": _json_notes(metadata),
            "metadata_json": metadata,
            "users_count": users_count,
            "devices_count": devices_count,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _department_payload(self, row: RegistryDepartment, *, users_count: int = 0, devices_count: int = 0) -> dict[str, Any]:
        metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        return {
            "id": row.department_id,
            "department_id": row.department_id,
            "code": row.code,
            "name": row.name,
            "parent_id": row.parent_department_id,
            "manager_person_id": metadata.get("manager_person_id"),
            "support_queue": metadata.get("support_queue"),
            "status": row.status,
            "source": row.source,
            "notes": _json_notes(metadata),
            "metadata_json": metadata,
            "users_count": users_count,
            "devices_count": devices_count,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def _location_counts(self) -> tuple[dict[str, int], dict[str, int]]:
        people = await self.session.execute(
            select(RegistryPerson.location_id, func.count(RegistryPerson.person_id))
            .where(RegistryPerson.location_id.isnot(None))
            .group_by(RegistryPerson.location_id)
        )
        assets = await self.session.execute(
            select(RegistryAsset.location_id, func.count(RegistryAsset.asset_id))
            .where(RegistryAsset.location_id.isnot(None))
            .group_by(RegistryAsset.location_id)
        )
        return {str(k): int(v) for k, v in people.all()}, {str(k): int(v) for k, v in assets.all()}

    async def _department_counts(self) -> tuple[dict[str, int], dict[str, int]]:
        people = await self.session.execute(
            select(RegistryPerson.department_id, func.count(RegistryPerson.person_id))
            .where(RegistryPerson.department_id.isnot(None))
            .group_by(RegistryPerson.department_id)
        )
        assets = await self.session.execute(
            select(RegistryAsset.department_id, func.count(RegistryAsset.asset_id))
            .where(RegistryAsset.department_id.isnot(None))
            .group_by(RegistryAsset.department_id)
        )
        return {str(k): int(v) for k, v in people.all()}, {str(k): int(v) for k, v in assets.all()}

    async def list_locations(self) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(select(RegistryLocation).order_by(RegistryLocation.building, RegistryLocation.floor, RegistryLocation.room))
        ).scalars().all()
        users, devices = await self._location_counts()
        return [self._location_payload(row, users_count=users.get(row.location_id, 0), devices_count=devices.get(row.location_id, 0)) for row in rows]

    async def create_location(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        building = _text(data.get("building"), max_length=200) or "Не указано"
        floor = _text(data.get("floor"), max_length=50)
        room = _text(data.get("room"), max_length=100)
        display_name = _location_display(building, floor, room, _text(data.get("display_name"), max_length=300))
        duplicate = (
            await self.session.execute(
                select(RegistryLocation).where(
                    RegistryLocation.status == "active",
                    RegistryLocation.building == building,
                    RegistryLocation.floor.is_(None) if floor is None else RegistryLocation.floor == floor,
                    RegistryLocation.room.is_(None) if room is None else RegistryLocation.room == room,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            raise ValueError("active location already exists")
        row = RegistryLocation(
            location_id=_new_id(),
            building=building,
            floor=floor,
            room=room,
            display_name=display_name,
            source="manual",
            status=_text(data.get("status"), max_length=30) or "active",
            metadata_json={**(data.get("metadata_json") if isinstance(data.get("metadata_json"), dict) else {}), "notes": _text(data.get("notes"), max_length=2000)},
        )
        self.session.add(row)
        await self.append_event(object_type="location", object_id=row.location_id, event_type="location_created", actor_id=actor_id, reason=reason)
        await self.session.flush()
        return {"location": self._location_payload(row)}

    async def update_location(self, location_id: str, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        row = await self.session.get(RegistryLocation, str(location_id))
        if row is None:
            raise LookupError("location not found")
        before = self._location_payload(row)
        for field, limit in {"building": 200, "floor": 50, "room": 100, "display_name": 300, "status": 30}.items():
            if field in data:
                value = _text(data.get(field), max_length=limit)
                setattr(row, field, value if field != "building" else value or "Не указано")
        if not row.display_name:
            row.display_name = _location_display(row.building, row.floor, row.room)
        metadata = dict(row.metadata_json or {})
        if isinstance(data.get("metadata_json"), dict):
            metadata.update(data.get("metadata_json") or {})
        if "notes" in data:
            metadata["notes"] = _text(data.get("notes"), max_length=2000)
        row.metadata_json = metadata
        row.updated_at = _now()
        await self.append_event(
            object_type="location",
            object_id=row.location_id,
            event_type="location_updated",
            actor_id=actor_id,
            reason=reason,
            payload={"before": before, "after": self._location_payload(row)},
        )
        await self.session.flush()
        return {"location": self._location_payload(row)}

    async def archive_location(self, location_id: str, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        force = bool(data.get("force"))
        row = await self.session.get(RegistryLocation, str(location_id))
        if row is None:
            raise LookupError("location not found")
        users, devices = await self._location_counts()
        if not force and (users.get(row.location_id, 0) or devices.get(row.location_id, 0)):
            raise ValueError("location is not empty")
        row.status = "archived"
        row.updated_at = _now()
        row.metadata_json = {**(row.metadata_json or {}), "archived_reason": reason}
        await self.append_event(object_type="location", object_id=row.location_id, event_type="location_archived", actor_id=actor_id, reason=reason)
        await self.session.flush()
        return {"location": self._location_payload(row)}

    async def merge_locations(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        master_id = str(data.get("master_location_id") or "").strip()
        duplicate_id = str(data.get("duplicate_location_id") or "").strip()
        if not master_id or not duplicate_id or master_id == duplicate_id:
            raise ValueError("master_location_id and duplicate_location_id are required")
        master = await self.session.get(RegistryLocation, master_id)
        duplicate = await self.session.get(RegistryLocation, duplicate_id)
        if master is None or duplicate is None:
            raise LookupError("location not found")
        people = (await self.session.execute(select(RegistryPerson).where(RegistryPerson.location_id == duplicate_id))).scalars().all()
        assets = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.location_id == duplicate_id))).scalars().all()
        for person in people:
            person.location_id = master_id
            person.updated_at = _now()
        for asset in assets:
            asset.location_id = master_id
            asset.updated_at = _now()
            if asset.device_id:
                binding = await self.session.get(DeviceInventoryBinding, asset.device_id)
                if binding:
                    binding.building = master.building
                    binding.floor = master.floor
                    binding.room = master.room
                    binding.updated_by = actor_id
                    binding.updated_at = _now()
        duplicate.status = "merged"
        duplicate.metadata_json = {**(duplicate.metadata_json or {}), "merged_into": master_id, "merged_at": _now().isoformat(), "merge_reason": reason}
        await self.append_event(
            object_type="location",
            object_id=master_id,
            event_type="location_merged",
            actor_id=actor_id,
            reason=reason,
            payload={"duplicate_location_id": duplicate_id, "people_moved": len(people), "assets_moved": len(assets)},
        )
        await self.session.flush()
        return {"master": self._location_payload(master), "duplicate": self._location_payload(duplicate), "moved": {"people": len(people), "assets": len(assets)}}

    async def preview_merge_locations(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        master_id = str(data.get("master_location_id") or "").strip()
        duplicate_id = str(data.get("duplicate_location_id") or "").strip()
        if not master_id or not duplicate_id or master_id == duplicate_id:
            raise ValueError("master_location_id and duplicate_location_id are required")
        master = await self.session.get(RegistryLocation, master_id)
        duplicate = await self.session.get(RegistryLocation, duplicate_id)
        if master is None or duplicate is None:
            raise LookupError("location not found")
        people = (await self.session.execute(select(RegistryPerson).where(RegistryPerson.location_id == duplicate_id))).scalars().all()
        assets = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.location_id == duplicate_id))).scalars().all()
        inventory_updates = [
            row
            for row in (
                await self.session.execute(
                    select(DeviceInventoryBinding).where(
                        DeviceInventoryBinding.device_id.in_([asset.device_id for asset in assets if asset.device_id])
                    )
                )
            ).scalars().all()
        ] if assets else []
        changes = [
            {
                "kind": "person",
                "action": "update",
                "object_id": row.person_id,
                "before": {"location_id": duplicate_id},
                "after": {"location_id": master_id},
                "severity": "warning",
            }
            for row in people
        ]
        changes.extend(
            {
                "kind": "registry_asset",
                "action": "update",
                "object_id": row.asset_id,
                "before": {"location_id": duplicate_id},
                "after": {"location_id": master_id},
                "severity": "warning",
            }
            for row in assets
        )
        changes.extend(
            {
                "kind": "inventory_binding",
                "action": "update",
                "object_id": row.device_id,
                "before": {"building": row.building, "floor": row.floor, "room": row.room},
                "after": {"building": master.building, "floor": master.floor, "room": master.room},
                "severity": "warning",
            }
            for row in inventory_updates
        )
        changes.append(
            {
                "kind": "location",
                "action": "mark_merged",
                "object_id": duplicate_id,
                "before": {"status": duplicate.status},
                "after": {"status": "merged", "merged_into": master_id},
                "severity": "destructive",
            }
        )
        return {
            "operation": "location_merge",
            "dry_run": True,
            "requires_confirmation": True,
            "master": self._location_payload(master),
            "duplicate": self._location_payload(duplicate),
            "counts": {
                "people_to_move": len(people),
                "assets_to_move": len(assets),
                "inventory_bindings_to_update": len(inventory_updates),
            },
            "changes": changes,
            "warnings": [],
            "blockers": [],
        }

    async def list_departments(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(RegistryDepartment).order_by(RegistryDepartment.name))).scalars().all()
        users, devices = await self._department_counts()
        return [self._department_payload(row, users_count=users.get(row.department_id, 0), devices_count=devices.get(row.department_id, 0)) for row in rows]

    async def create_department(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        name = _text(data.get("name"), max_length=300)
        if not name:
            raise ValueError("name is required")
        code = _department_code(data.get("code"))
        if code:
            duplicate = (await self.session.execute(select(RegistryDepartment).where(RegistryDepartment.code == code, RegistryDepartment.status == "active"))).scalar_one_or_none()
            if duplicate:
                raise ValueError("active department code already exists")
        row = RegistryDepartment(
            department_id=_new_id(),
            code=code,
            name=name,
            parent_department_id=_text(data.get("parent_id"), max_length=36),
            source="manual",
            status=_text(data.get("status"), max_length=30) or "active",
            metadata_json={
                **(data.get("metadata_json") if isinstance(data.get("metadata_json"), dict) else {}),
                "manager_person_id": _text(data.get("manager_person_id"), max_length=36),
                "support_queue": _text(data.get("support_queue"), max_length=120),
                "notes": _text(data.get("notes"), max_length=2000),
            },
        )
        self.session.add(row)
        await self.append_event(object_type="department", object_id=row.department_id, event_type="department_created", actor_id=actor_id, reason=reason)
        await self.session.flush()
        return {"department": self._department_payload(row)}

    async def update_department(self, department_id: str, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        row = await self.session.get(RegistryDepartment, str(department_id))
        if row is None:
            raise LookupError("department not found")
        before = self._department_payload(row)
        if "code" in data:
            row.code = _department_code(data.get("code"))
        for field, limit in {"name": 300, "parent_department_id": 36, "status": 30}.items():
            payload_key = "parent_id" if field == "parent_department_id" else field
            if payload_key in data:
                setattr(row, field, _text(data.get(payload_key), max_length=limit))
        if not row.name:
            raise ValueError("name is required")
        metadata = dict(row.metadata_json or {})
        if isinstance(data.get("metadata_json"), dict):
            metadata.update(data.get("metadata_json") or {})
        for key, limit in {"manager_person_id": 36, "support_queue": 120, "notes": 2000}.items():
            if key in data:
                metadata[key] = _text(data.get(key), max_length=limit)
        row.metadata_json = metadata
        row.updated_at = _now()
        await self.append_event(
            object_type="department",
            object_id=row.department_id,
            event_type="department_updated",
            actor_id=actor_id,
            reason=reason,
            payload={"before": before, "after": self._department_payload(row)},
        )
        await self.session.flush()
        return {"department": self._department_payload(row)}

    async def archive_department(self, department_id: str, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        force = bool(data.get("force"))
        row = await self.session.get(RegistryDepartment, str(department_id))
        if row is None:
            raise LookupError("department not found")
        users, devices = await self._department_counts()
        if not force and (users.get(row.department_id, 0) or devices.get(row.department_id, 0)):
            raise ValueError("department is not empty")
        row.status = "archived"
        row.updated_at = _now()
        row.metadata_json = {**(row.metadata_json or {}), "archived_reason": reason}
        await self.append_event(object_type="department", object_id=row.department_id, event_type="department_archived", actor_id=actor_id, reason=reason)
        await self.session.flush()
        return {"department": self._department_payload(row)}

    async def merge_departments(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        master_id = str(data.get("master_department_id") or "").strip()
        duplicate_id = str(data.get("duplicate_department_id") or "").strip()
        if not master_id or not duplicate_id or master_id == duplicate_id:
            raise ValueError("master_department_id and duplicate_department_id are required")
        master = await self.session.get(RegistryDepartment, master_id)
        duplicate = await self.session.get(RegistryDepartment, duplicate_id)
        if master is None or duplicate is None:
            raise LookupError("department not found")
        people = (await self.session.execute(select(RegistryPerson).where(RegistryPerson.department_id == duplicate_id))).scalars().all()
        assets = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.department_id == duplicate_id))).scalars().all()
        for person in people:
            person.department_id = master_id
            person.updated_at = _now()
        for asset in assets:
            asset.department_id = master_id
            asset.updated_at = _now()
            if asset.device_id:
                binding = await self.session.get(DeviceInventoryBinding, asset.device_id)
                if binding:
                    binding.department = master.name
                    binding.updated_by = actor_id
                    binding.updated_at = _now()
        duplicate.status = "merged"
        duplicate.metadata_json = {**(duplicate.metadata_json or {}), "merged_into": master_id, "merged_at": _now().isoformat(), "merge_reason": reason}
        await self.append_event(
            object_type="department",
            object_id=master_id,
            event_type="department_merged",
            actor_id=actor_id,
            reason=reason,
            payload={"duplicate_department_id": duplicate_id, "people_moved": len(people), "assets_moved": len(assets)},
        )
        await self.session.flush()
        return {"master": self._department_payload(master), "duplicate": self._department_payload(duplicate), "moved": {"people": len(people), "assets": len(assets)}}

    async def preview_merge_departments(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        master_id = str(data.get("master_department_id") or "").strip()
        duplicate_id = str(data.get("duplicate_department_id") or "").strip()
        if not master_id or not duplicate_id or master_id == duplicate_id:
            raise ValueError("master_department_id and duplicate_department_id are required")
        master = await self.session.get(RegistryDepartment, master_id)
        duplicate = await self.session.get(RegistryDepartment, duplicate_id)
        if master is None or duplicate is None:
            raise LookupError("department not found")
        people = (await self.session.execute(select(RegistryPerson).where(RegistryPerson.department_id == duplicate_id))).scalars().all()
        assets = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.department_id == duplicate_id))).scalars().all()
        inventory_updates = [
            row
            for row in (
                await self.session.execute(
                    select(DeviceInventoryBinding).where(
                        DeviceInventoryBinding.device_id.in_([asset.device_id for asset in assets if asset.device_id])
                    )
                )
            ).scalars().all()
        ] if assets else []
        changes = [
            {
                "kind": "person",
                "action": "update",
                "object_id": row.person_id,
                "before": {"department_id": duplicate_id},
                "after": {"department_id": master_id},
                "severity": "warning",
            }
            for row in people
        ]
        changes.extend(
            {
                "kind": "registry_asset",
                "action": "update",
                "object_id": row.asset_id,
                "before": {"department_id": duplicate_id},
                "after": {"department_id": master_id},
                "severity": "warning",
            }
            for row in assets
        )
        changes.extend(
            {
                "kind": "inventory_binding",
                "action": "update",
                "object_id": row.device_id,
                "before": {"department": row.department},
                "after": {"department": master.name},
                "severity": "warning",
            }
            for row in inventory_updates
        )
        changes.append(
            {
                "kind": "department",
                "action": "mark_merged",
                "object_id": duplicate_id,
                "before": {"status": duplicate.status},
                "after": {"status": "merged", "merged_into": master_id},
                "severity": "destructive",
            }
        )
        return {
            "operation": "department_merge",
            "dry_run": True,
            "requires_confirmation": True,
            "master": self._department_payload(master),
            "duplicate": self._department_payload(duplicate),
            "counts": {
                "people_to_move": len(people),
                "assets_to_move": len(assets),
                "inventory_bindings_to_update": len(inventory_updates),
            },
            "changes": changes,
            "warnings": [],
            "blockers": [],
        }

    async def get_policies(self) -> dict[str, Any]:
        effective = await RegistryPolicyService(self.session).get_policies()
        return build_registry_policy_response(effective)

    async def preview_policies(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        config = data.get("policies") if isinstance(data.get("policies"), dict) else data
        return build_registry_policy_response(config, dry_run=True)

    async def update_policies(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        config = data.get("policies") if isinstance(data.get("policies"), dict) else data
        effective = await RegistryPolicyService(self.session).update_policies(config, actor_id=actor_id)
        response = build_registry_policy_response(effective)
        await self.append_event(
            object_type="policy",
            object_id="registry_management",
            event_type="policy_changed",
            actor_id=actor_id,
            reason=reason,
            payload={
                "effective": effective,
                "changed_from_defaults": response["changed_from_defaults"],
                "warnings": response["warnings"],
                "requires_restart": response["requires_restart"],
            },
        )
        return response

    async def reset_policies(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        effective = await RegistryPolicyService(self.session).reset_to_defaults(actor_id=actor_id)
        response = build_registry_policy_response(effective)
        await self.append_event(
            object_type="policy",
            object_id="registry_management",
            event_type="policy_changed",
            actor_id=actor_id,
            reason=reason,
            payload={"effective": effective, "reset_to_defaults": True},
        )
        return response

    def _quality_override_payload(self, row: RegistryQualityIssueOverride) -> dict[str, Any]:
        return {
            "issue_key": row.issue_key,
            "issue_kind": row.issue_kind,
            "object_type": row.object_type,
            "object_id": row.object_id,
            "related_id": row.related_id,
            "status": row.status,
            "snoozed_until": _iso(row.snoozed_until),
            "reason": row.reason,
            "actor_id": row.actor_id,
            "updated_at": _iso(row.updated_at),
        }

    async def set_quality_issue_state(
        self,
        issue_key: str,
        *,
        status: str,
        reason: str,
        actor_id: str | None = None,
        days: int | None = None,
    ) -> dict[str, Any]:
        if status not in {"ignored", "snoozed", "resolved"}:
            raise ValueError("invalid quality issue status")
        reason = _require_reason(reason)
        info = _parse_quality_issue_key(issue_key)
        now = _now()
        snoozed_until = None
        if status == "snoozed":
            days = int(days or 7)
            if days < 1 or days > 365:
                raise ValueError("snooze days must be between 1 and 365")
            snoozed_until = now + timedelta(days=days)
        row = await self.session.get(RegistryQualityIssueOverride, issue_key)
        if row is None:
            row = RegistryQualityIssueOverride(
                issue_key=issue_key,
                issue_kind=str(info["issue_kind"]),
                object_type=str(info["object_type"]),
                object_id=str(info["object_id"]),
                related_id=info["related_id"],
                status=status,
                created_at=now,
                updated_at=now,
            )
            self.session.add(row)
        row.status = status
        row.reason = reason
        row.actor_id = actor_id
        row.snoozed_until = snoozed_until
        row.updated_at = now
        event_type = {
            "ignored": "quality_issue_ignored",
            "snoozed": "quality_issue_snoozed",
            "resolved": "quality_issue_resolved",
        }[status]
        await self.append_event(
            object_type="quality_issue",
            object_id=issue_key,
            event_type=event_type,
            actor_id=actor_id,
            reason=reason,
            payload={**info, "status": status, "snoozed_until": _iso(snoozed_until)},
        )
        await self.session.flush()
        return {"override": self._quality_override_payload(row)}

    async def merge_people(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        master_id = str(data.get("master_person_id") or "").strip()
        duplicate_id = str(data.get("duplicate_person_id") or "").strip()
        if not master_id or not duplicate_id or master_id == duplicate_id:
            raise ValueError("master_person_id and duplicate_person_id are required")
        master = await self.session.get(RegistryPerson, master_id)
        duplicate = await self.session.get(RegistryPerson, duplicate_id)
        if master is None or duplicate is None:
            raise LookupError("person not found")

        field_strategy = data.get("field_strategy") if isinstance(data.get("field_strategy"), dict) else {}
        for field in ("full_name", "display_name", "email", "phone", "department_id", "location_id"):
            if field_strategy.get(field) == "duplicate":
                setattr(master, field, getattr(duplicate, field))

        moved_identities = 0
        conflicted_identities = 0
        master_identities = (
            await self.session.execute(select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == master_id))
        ).scalars().all()
        master_keys = {(row.provider, row.normalized_identifier) for row in master_identities}
        duplicate_identities = (
            await self.session.execute(select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == duplicate_id))
        ).scalars().all()
        for identity in duplicate_identities:
            key = (identity.provider, identity.normalized_identifier)
            if key in master_keys:
                identity.metadata_json = {**(identity.metadata_json or {}), "merge_conflict": True, "merged_into_person_id": master_id}
                conflicted_identities += 1
                continue
            identity.person_id = master_id
            identity.metadata_json = {**(identity.metadata_json or {}), "merged_from_person_id": duplicate_id}
            moved_identities += 1

        bindings = (await self.session.execute(select(DeviceUserBinding).where(DeviceUserBinding.person_id == duplicate_id))).scalars().all()
        for row in bindings:
            row.person_id = master_id
            row.updated_at = _now()
        sessions = (
            await self.session.execute(
                select(DeviceAccountSession).where(
                    or_(DeviceAccountSession.person_id == duplicate_id, DeviceAccountSession.base_person_id == duplicate_id)
                )
            )
        ).scalars().all()
        for row in sessions:
            if row.person_id == duplicate_id:
                row.person_id = master_id
            if row.base_person_id == duplicate_id:
                row.base_person_id = master_id
        login_requests = (
            await self.session.execute(
                select(DeviceAccountLoginRequest).where(
                    or_(
                        DeviceAccountLoginRequest.matched_person_id == duplicate_id,
                        DeviceAccountLoginRequest.base_person_id == duplicate_id,
                    )
                )
            )
        ).scalars().all()
        for row in login_requests:
            if row.matched_person_id == duplicate_id:
                row.matched_person_id = master_id
            if row.base_person_id == duplicate_id:
                row.base_person_id = master_id
        claims = (await self.session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.person_id == duplicate_id))).scalars().all()
        for row in claims:
            row.person_id = master_id
            row.updated_at = _now()
        tickets = (await self.session.execute(select(Ticket).where(Ticket.requester_person_id == duplicate_id))).scalars().all()
        for row in tickets:
            row.requester_person_id = master_id
        assets = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.assigned_person_id == duplicate_id))).scalars().all()
        for row in assets:
            row.assigned_person_id = master_id
            row.updated_at = _now()
        moved_binding_ids = [row.binding_id for row in bindings]
        moved_asset_device_ids = [row.device_id for row in assets if row.device_id]
        inventory_filters = [DeviceInventoryBinding.person_id == duplicate_id]
        if moved_binding_ids:
            inventory_filters.append(DeviceInventoryBinding.source_binding_id.in_(moved_binding_ids))
        if moved_asset_device_ids:
            inventory_filters.append(DeviceInventoryBinding.device_id.in_(moved_asset_device_ids))
        inventory_bindings = (
            await self.session.execute(select(DeviceInventoryBinding).where(or_(*inventory_filters)))
        ).scalars().all()
        for row in inventory_bindings:
            row.person_id = master_id
            row.updated_by = actor_id
            row.updated_at = _now()

        duplicate.status = "merged"
        duplicate.metadata_json = {
            **(duplicate.metadata_json or {}),
            "merged_into": master_id,
            "merged_at": _now().isoformat(),
            "merge_reason": reason,
        }
        master.updated_at = _now()
        await self.append_event(
            object_type="person",
            object_id=master_id,
            event_type="person_merged",
            actor_id=actor_id,
            reason=reason,
            related_person_id=duplicate_id,
            payload={
                "duplicate_person_id": duplicate_id,
                "identities_moved": moved_identities,
                "identity_conflicts": conflicted_identities,
                "bindings_moved": len(bindings),
                "sessions_moved": len(sessions),
                "login_requests_moved": len(login_requests),
                "claims_moved": len(claims),
                "tickets_moved": len(tickets),
                "assets_moved": len(assets),
                "inventory_bindings_moved": len(inventory_bindings),
            },
        )
        await self.session.flush()
        return {
            "master_person_id": master_id,
            "duplicate_person_id": duplicate_id,
            "moved": {
                "identities": moved_identities,
                "identity_conflicts": conflicted_identities,
                "bindings": len(bindings),
                "sessions": len(sessions),
                "login_requests": len(login_requests),
                "claims": len(claims),
                "tickets": len(tickets),
                "assets": len(assets),
                "inventory_bindings": len(inventory_bindings),
            },
        }

    async def preview_merge_people(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        master_id = str(data.get("master_person_id") or "").strip()
        duplicate_id = str(data.get("duplicate_person_id") or "").strip()
        if not master_id or not duplicate_id or master_id == duplicate_id:
            raise ValueError("master_person_id and duplicate_person_id are required")
        master = await self.session.get(RegistryPerson, master_id)
        duplicate = await self.session.get(RegistryPerson, duplicate_id)
        if master is None or duplicate is None:
            raise LookupError("person not found")

        field_strategy = data.get("field_strategy") if isinstance(data.get("field_strategy"), dict) else {}
        master_identities = (
            await self.session.execute(select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == master_id))
        ).scalars().all()
        master_keys = {(row.provider, row.normalized_identifier) for row in master_identities}
        duplicate_identities = (
            await self.session.execute(select(RegistryPersonIdentity).where(RegistryPersonIdentity.person_id == duplicate_id))
        ).scalars().all()
        identity_conflicts = [
            row for row in duplicate_identities if (row.provider, row.normalized_identifier) in master_keys
        ]
        identities_to_move = [row for row in duplicate_identities if row not in identity_conflicts]
        bindings = (await self.session.execute(select(DeviceUserBinding).where(DeviceUserBinding.person_id == duplicate_id))).scalars().all()
        sessions = (
            await self.session.execute(
                select(DeviceAccountSession).where(
                    or_(DeviceAccountSession.person_id == duplicate_id, DeviceAccountSession.base_person_id == duplicate_id)
                )
            )
        ).scalars().all()
        login_requests = (
            await self.session.execute(
                select(DeviceAccountLoginRequest).where(
                    or_(
                        DeviceAccountLoginRequest.matched_person_id == duplicate_id,
                        DeviceAccountLoginRequest.base_person_id == duplicate_id,
                    )
                )
            )
        ).scalars().all()
        claims = (await self.session.execute(select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.person_id == duplicate_id))).scalars().all()
        tickets = (await self.session.execute(select(Ticket).where(Ticket.requester_person_id == duplicate_id))).scalars().all()
        assets = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.assigned_person_id == duplicate_id))).scalars().all()
        moved_binding_ids = [row.binding_id for row in bindings]
        moved_asset_device_ids = [row.device_id for row in assets if row.device_id]
        inventory_filters = [DeviceInventoryBinding.person_id == duplicate_id]
        if moved_binding_ids:
            inventory_filters.append(DeviceInventoryBinding.source_binding_id.in_(moved_binding_ids))
        if moved_asset_device_ids:
            inventory_filters.append(DeviceInventoryBinding.device_id.in_(moved_asset_device_ids))
        inventory_bindings = (
            await self.session.execute(select(DeviceInventoryBinding).where(or_(*inventory_filters)))
        ).scalars().all()

        field_changes = {
            field: {"before": getattr(master, field), "after": getattr(duplicate, field)}
            for field in ("full_name", "display_name", "email", "phone", "department_id", "location_id")
            if field_strategy.get(field) == "duplicate" and getattr(master, field) != getattr(duplicate, field)
        }
        changes: list[dict[str, Any]] = [
            {
                "kind": "person",
                "action": "update_fields",
                "object_id": master_id,
                "before": {field: change["before"] for field, change in field_changes.items()},
                "after": {field: change["after"] for field, change in field_changes.items()},
                "severity": "warning",
            }
        ] if field_changes else []
        changes.extend(
            {
                "kind": "identity",
                "action": "move",
                "object_id": row.identity_id,
                "before": {"person_id": duplicate_id},
                "after": {"person_id": master_id},
                "severity": "warning",
            }
            for row in identities_to_move
        )
        changes.extend(
            {
                "kind": "identity",
                "action": "mark_conflict",
                "object_id": row.identity_id,
                "before": {"person_id": duplicate_id},
                "after": {"person_id": duplicate_id, "merge_conflict": True, "merged_into_person_id": master_id},
                "severity": "warning",
            }
            for row in identity_conflicts
        )
        for kind, rows, object_attr in (
            ("binding", bindings, "binding_id"),
            ("account_session", sessions, "session_id"),
            ("account_login_request", login_requests, "request_id"),
            ("registration_claim", claims, "claim_id"),
            ("ticket", tickets, "ticket_id"),
            ("registry_asset", assets, "asset_id"),
            ("inventory_binding", inventory_bindings, "device_id"),
        ):
            changes.extend(
                {
                    "kind": kind,
                    "action": "move_to_master_person",
                    "object_id": getattr(row, object_attr),
                    "before": {"person_id": duplicate_id},
                    "after": {"person_id": master_id},
                    "severity": "warning",
                }
                for row in rows
            )
        changes.append(
            {
                "kind": "person",
                "action": "mark_merged",
                "object_id": duplicate_id,
                "before": {"status": duplicate.status},
                "after": {"status": "merged", "merged_into": master_id},
                "severity": "destructive",
            }
        )
        return {
            "operation": "people_merge",
            "dry_run": True,
            "requires_confirmation": True,
            "master_person_id": master_id,
            "duplicate_person_id": duplicate_id,
            "field_changes": field_changes,
            "counts": {
                "identities_to_move": len(identities_to_move),
                "identity_conflicts": len(identity_conflicts),
                "bindings_to_move": len(bindings),
                "sessions_to_move": len(sessions),
                "login_requests_to_move": len(login_requests),
                "claims_to_move": len(claims),
                "tickets_to_move": len(tickets),
                "assets_to_move": len(assets),
                "inventory_bindings_to_move": len(inventory_bindings),
            },
            "changes": changes,
            "warnings": ["verified_identity_conflict"] if identity_conflicts else [],
            "blockers": [],
        }

    def _validate_bulk_ids(self, data: dict[str, Any]) -> list[str]:
        ids = [str(item).strip() for item in data.get("ids") or [] if str(item).strip()]
        if not ids:
            raise ValueError("ids are required")
        if len(ids) > BULK_LIMIT:
            raise ValueError(f"batch limit is {BULK_LIMIT}")
        return ids

    @staticmethod
    def _bulk_item(result: dict[str, Any]) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": result.get("id"),
            "status": "success" if result.get("success") else "error",
        }
        for key in ("error_code", "error", "affected_sessions"):
            if key in result:
                item[key] = result.get(key)
        return item

    def _bulk_response(self, *, operation: str, selected_ids: list[str], results: list[dict[str, Any]]) -> dict[str, Any]:
        items = [self._bulk_item(result) for result in results]
        success_count = sum(1 for item in items if item["status"] == "success")
        failed_count = sum(1 for item in items if item["status"] == "error")
        return {
            "bulk_operation_id": _new_id(),
            "operation": operation,
            "summary": {"selected": len(selected_ids), "success": success_count, "failed": failed_count},
            "items": items,
            "results": results,
        }

    async def bulk_assign_location(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        ids = self._validate_bulk_ids(data)
        location_id = str((data.get("payload") or {}).get("location_id") or data.get("location_id") or "").strip()
        location = await self.session.get(RegistryLocation, location_id)
        if location is None:
            raise LookupError("location not found")
        results = []
        for device_id in ids:
            asset = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one_or_none()
            if asset is None:
                results.append({"id": device_id, "success": False, "error_code": "NOT_FOUND"})
                continue
            asset.location_id = location.location_id
            asset.updated_at = _now()
            binding = await self.session.get(DeviceInventoryBinding, device_id)
            if binding:
                binding.building = location.building
                binding.floor = location.floor
                binding.room = location.room
                binding.updated_by = actor_id
                binding.updated_at = _now()
            await self.append_event(
                object_type="asset",
                object_id=asset.asset_id,
                event_type="bulk_device_location_assigned",
                actor_id=actor_id,
                reason=reason,
                related_device_id=device_id,
                payload={"location_id": location.location_id},
            )
            results.append({"id": device_id, "success": True})
        await self.session.flush()
        return self._bulk_response(operation="devices.assign_location", selected_ids=ids, results=results)

    async def bulk_assign_department(self, data: dict[str, Any], *, actor_id: str | None = None, target: str = "devices") -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        ids = self._validate_bulk_ids(data)
        department_id = str((data.get("payload") or {}).get("department_id") or data.get("department_id") or "").strip()
        department = await self.session.get(RegistryDepartment, department_id)
        if department is None:
            raise LookupError("department not found")
        results = []
        for item_id in ids:
            if target == "people":
                row = await self.session.get(RegistryPerson, item_id)
                if row is None:
                    results.append({"id": item_id, "success": False, "error_code": "NOT_FOUND"})
                    continue
                row.department_id = department.department_id
                row.updated_at = _now()
                object_type = "person"
                object_id = row.person_id
                device_id = None
            else:
                row = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.device_id == item_id))).scalar_one_or_none()
                if row is None:
                    results.append({"id": item_id, "success": False, "error_code": "NOT_FOUND"})
                    continue
                row.department_id = department.department_id
                row.updated_at = _now()
                binding = await self.session.get(DeviceInventoryBinding, item_id)
                if binding:
                    binding.department = department.name
                    binding.updated_by = actor_id
                    binding.updated_at = _now()
                object_type = "asset"
                object_id = row.asset_id
                device_id = item_id
            await self.append_event(
                object_type=object_type,
                object_id=object_id,
                event_type=f"bulk_{target}_department_assigned",
                actor_id=actor_id,
                reason=reason,
                related_device_id=device_id,
                related_person_id=item_id if target == "people" else None,
                payload={"department_id": department.department_id},
            )
            results.append({"id": item_id, "success": True})
        await self.session.flush()
        return self._bulk_response(operation=f"{target}.assign_department", selected_ids=ids, results=results)

    async def bulk_revoke_sessions(self, data: dict[str, Any], *, actor_id: str | None = None, by_device: bool = False) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        ids = self._validate_bulk_ids(data)
        account_service = AccountSessionService(self.session)
        results = []
        session_ids: list[str] = []
        if by_device:
            rows = (
                await self.session.execute(
                    select(DeviceAccountSession).where(
                        DeviceAccountSession.device_id.in_(ids),
                        DeviceAccountSession.verification_status.in_(["verified", "pending_verification"]),
                    )
                )
            ).scalars().all()
            existing_devices = {
                str(device_id)
                for device_id in (
                    await self.session.execute(select(Device.device_id).where(Device.device_id.in_(ids)))
                ).scalars().all()
            }
            for device_id in ids:
                if device_id not in existing_devices:
                    results.append({"id": device_id, "success": False, "error_code": "NOT_FOUND"})
                    continue
                device_rows = [row for row in rows if row.device_id == device_id]
                revoked_count = 0
                for row in device_rows:
                    try:
                        session = await account_service.revoke_session(session_id=row.session_id, revoked_by=actor_id or "admin", reason=reason)
                        await self.append_event(
                            object_type="account_session",
                            object_id=row.session_id,
                            event_type="bulk_account_session_revoked",
                            actor_id=actor_id,
                            reason=reason,
                            related_device_id=session.get("device_id"),
                            related_person_id=session.get("person_id"),
                        )
                        revoked_count += 1
                    except ValueError as exc:
                        results.append({"id": device_id, "success": False, "error_code": "SESSION_REVOKE_FAILED", "error": str(exc)})
                        break
                else:
                    results.append({"id": device_id, "success": True, "affected_sessions": revoked_count})
        else:
            session_ids = ids
            for session_id in session_ids:
                try:
                    session = await account_service.revoke_session(session_id=session_id, revoked_by=actor_id or "admin", reason=reason)
                    await self.append_event(
                        object_type="account_session",
                        object_id=session_id,
                        event_type="bulk_account_session_revoked",
                        actor_id=actor_id,
                        reason=reason,
                        related_device_id=session.get("device_id"),
                        related_person_id=session.get("person_id"),
                    )
                    results.append({"id": session_id, "success": True})
                except ValueError as exc:
                    results.append({"id": session_id, "success": False, "error_code": "NOT_FOUND", "error": str(exc)})
        await self.session.flush()
        return self._bulk_response(
            operation="devices.revoke_account_sessions" if by_device else "account_sessions.revoke",
            selected_ids=ids,
            results=results,
        )

    async def preview_bulk(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        operation = str(data.get("operation") or "").strip()
        ids = self._validate_bulk_ids(data)
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        results: list[dict[str, Any]] = []
        changes: list[dict[str, Any]] = []
        warnings: list[str] = []

        if operation == "devices.assign_location":
            location_id = str(payload.get("location_id") or data.get("location_id") or "").strip()
            location = await self.session.get(RegistryLocation, location_id)
            if location is None:
                raise LookupError("location not found")
            for device_id in ids:
                asset = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device_id))).scalar_one_or_none()
                if asset is None:
                    results.append({"id": device_id, "success": False, "error_code": "NOT_FOUND"})
                    continue
                results.append({"id": device_id, "success": True})
                changes.append(
                    {
                        "kind": "registry_asset",
                        "action": "update",
                        "object_id": asset.asset_id,
                        "before": {"location_id": asset.location_id},
                        "after": {"location_id": location.location_id},
                        "severity": "warning",
                    }
                )
                if await self.session.get(DeviceInventoryBinding, device_id):
                    changes.append(
                        {
                            "kind": "inventory_binding",
                            "action": "update",
                            "object_id": device_id,
                            "before": "current_location_fields",
                            "after": {"building": location.building, "floor": location.floor, "room": location.room},
                            "severity": "warning",
                        }
                    )
        elif operation == "devices.assign_department":
            await self._preview_bulk_assign_department(ids, payload, results, changes, target="devices")
        elif operation == "people.assign_department":
            await self._preview_bulk_assign_department(ids, payload, results, changes, target="people")
        elif operation == "devices.revoke_account_sessions":
            rows = (
                await self.session.execute(
                    select(DeviceAccountSession).where(
                        DeviceAccountSession.device_id.in_(ids),
                        DeviceAccountSession.verification_status.in_(["verified", "pending_verification"]),
                    )
                )
            ).scalars().all()
            for device_id in ids:
                device_rows = [row for row in rows if row.device_id == device_id]
                results.append({"id": device_id, "success": True, "affected_sessions": len(device_rows)})
                changes.extend(
                    {
                        "kind": "account_session",
                        "action": "revoke",
                        "object_id": row.session_id,
                        "before": {"verification_status": row.verification_status},
                        "after": {"verification_status": "revoked", "revoked_at": "now"},
                        "severity": "destructive",
                    }
                    for row in device_rows
                )
        elif operation == "account_sessions.revoke":
            for session_id in ids:
                row = await self.session.get(DeviceAccountSession, session_id)
                if row is None:
                    results.append({"id": session_id, "success": False, "error_code": "NOT_FOUND"})
                    continue
                results.append({"id": session_id, "success": True})
                changes.append(
                    {
                        "kind": "account_session",
                        "action": "revoke",
                        "object_id": row.session_id,
                        "before": {"verification_status": row.verification_status},
                        "after": {"verification_status": "revoked", "revoked_at": "now"},
                        "severity": "destructive",
                    }
                )
        else:
            raise ValueError("unsupported bulk preview operation")

        return {
            "operation": operation,
            "dry_run": True,
            "requires_confirmation": True,
            "counts": {
                "requested": len(ids),
                "successful": sum(1 for row in results if row.get("success")),
                "failed": sum(1 for row in results if not row.get("success")),
                "changes": len(changes),
            },
            "results": results,
            "changes": changes,
            "warnings": warnings,
            "blockers": [],
        }

    async def _preview_bulk_assign_department(
        self,
        ids: list[str],
        payload: dict[str, Any],
        results: list[dict[str, Any]],
        changes: list[dict[str, Any]],
        *,
        target: str,
    ) -> None:
        department_id = str(payload.get("department_id") or "").strip()
        department = await self.session.get(RegistryDepartment, department_id)
        if department is None:
            raise LookupError("department not found")
        for item_id in ids:
            if target == "people":
                person = await self.session.get(RegistryPerson, item_id)
                if person is None:
                    results.append({"id": item_id, "success": False, "error_code": "NOT_FOUND"})
                    continue
                results.append({"id": item_id, "success": True})
                changes.append(
                    {
                        "kind": "person",
                        "action": "update",
                        "object_id": person.person_id,
                        "before": {"department_id": person.department_id},
                        "after": {"department_id": department.department_id},
                        "severity": "warning",
                    }
                )
            else:
                asset = (await self.session.execute(select(RegistryAsset).where(RegistryAsset.device_id == item_id))).scalar_one_or_none()
                if asset is None:
                    results.append({"id": item_id, "success": False, "error_code": "NOT_FOUND"})
                    continue
                results.append({"id": item_id, "success": True})
                changes.append(
                    {
                        "kind": "registry_asset",
                        "action": "update",
                        "object_id": asset.asset_id,
                        "before": {"department_id": asset.department_id},
                        "after": {"department_id": department.department_id},
                        "severity": "warning",
                    }
                )
                if await self.session.get(DeviceInventoryBinding, item_id):
                    changes.append(
                        {
                            "kind": "inventory_binding",
                            "action": "update",
                            "object_id": item_id,
                            "before": "current_department",
                            "after": {"department": department.name},
                            "severity": "warning",
                        }
                    )

    async def export_csv(self, export_type: str) -> str:
        registry = await self._build_export_rows(export_type)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=registry["columns"], lineterminator="\n")
        writer.writeheader()
        for row in registry["rows"]:
            writer.writerow({column: _csv_safe(row.get(column)) for column in registry["columns"]})
        return output.getvalue()

    async def preview_import_csv(self, import_type: str, csv_text: str) -> dict[str, Any]:
        import_type = self._normalize_import_type(import_type)
        rows = self._parse_import_csv(csv_text)
        if import_type == "people":
            payload = await self._preview_import_people(rows)
        elif import_type == "locations":
            payload = await self._preview_import_locations(rows)
        elif import_type == "departments":
            payload = await self._preview_import_departments(rows)
        elif import_type == "device_inventory_mapping":
            payload = await self._preview_import_device_inventory_mapping(rows)
        else:
            raise ValueError("unsupported registry import type")
        blockers = payload["row_errors"] + payload["duplicate_keys"]
        payload["preview_id"] = _import_preview_id(import_type, csv_text)
        payload["can_apply"] = not blockers
        payload["blocking_errors"] = blockers
        payload["warnings"] = []
        return payload

    async def apply_import_csv(
        self,
        import_type: str,
        csv_text: str,
        *,
        preview_id: str | None = None,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        reason = _require_reason(reason)
        normalized_import_type = self._normalize_import_type(import_type)
        expected_preview_id = _import_preview_id(normalized_import_type, csv_text)
        if not preview_id:
            raise ValueError("preview_id is required before import apply")
        if str(preview_id) != expected_preview_id:
            raise ValueError("preview_id does not match import payload")
        preview = await self.preview_import_csv(import_type, csv_text)
        if preview["row_errors"] or preview["duplicate_keys"]:
            raise ValueError("import has validation errors or duplicates")
        import_type = preview["import_type"]
        operation_id = _new_id()
        if import_type == "people":
            await self._apply_import_people(preview["changes"])
        elif import_type == "locations":
            await self._apply_import_locations(preview["changes"])
        elif import_type == "departments":
            await self._apply_import_departments(preview["changes"])
        elif import_type == "device_inventory_mapping":
            await self._apply_import_device_inventory_mapping(preview["changes"], actor_id=actor_id)
        else:
            raise ValueError("unsupported registry import type")
        await self.append_event(
            object_type="registry_import",
            object_id=operation_id,
            event_type="registry_import_applied",
            actor_id=actor_id,
            reason=reason,
            payload={
                "operation_id": operation_id,
                "import_type": import_type,
                "counts": preview["counts"],
                "changes": preview["changes"][:50],
                "rows_total": preview["rows_total"],
            },
        )
        await self.session.flush()
        items = [
            {
                "row": change.get("row"),
                "id": change.get("object_id"),
                "entity_type": change.get("kind"),
                "status": "success",
                "error_code": None,
                "message": None,
            }
            for change in preview["changes"]
        ]
        return {
            **preview,
            "operation_id": operation_id,
            "status": "success",
            "summary": {"success": len(items), "failed": 0, "warnings": 0},
            "items": items,
            "events": ["registry_import_applied"],
            "dry_run": False,
            "applied": True,
        }

    def _normalize_import_type(self, import_type: str) -> str:
        value = str(import_type or "").strip().lower().replace("-", "_")
        aliases = {
            "device_inventory": "device_inventory_mapping",
            "inventory_mapping": "device_inventory_mapping",
            "devices_inventory_mapping": "device_inventory_mapping",
        }
        value = aliases.get(value, value)
        if value not in REGISTRY_IMPORT_TYPES:
            raise ValueError("unsupported registry import type")
        return value

    def _parse_import_csv(self, csv_text: str) -> list[tuple[int, dict[str, str]]]:
        if not isinstance(csv_text, str) or not csv_text.strip():
            raise ValueError("csv_text is required")
        if len(csv_text.encode("utf-8")) > IMPORT_TEXT_LIMIT:
            raise ValueError("CSV import is too large")
        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            raise ValueError("CSV header is required")
        rows: list[tuple[int, dict[str, str]]] = []
        for row_number, row in enumerate(reader, start=2):
            if len(rows) >= IMPORT_LIMIT:
                raise ValueError(f"CSV import row limit is {IMPORT_LIMIT}")
            rows.append(
                (
                    row_number,
                    {
                        str(key or "").strip(): str(value or "").strip()
                        for key, value in row.items()
                        if key is not None
                    },
                )
            )
        return rows

    def _import_preview_payload(
        self,
        import_type: str,
        rows: list[tuple[int, dict[str, str]]],
        changes: list[dict[str, Any]],
        row_errors: list[dict[str, Any]],
        duplicate_keys: list[dict[str, Any]],
    ) -> dict[str, Any]:
        creates = sum(1 for change in changes if change.get("action") == "create")
        updates = sum(1 for change in changes if change.get("action") == "update")
        skips = sum(1 for change in changes if change.get("action") == "skip")
        return {
            "operation": "registry_import",
            "import_type": import_type,
            "dry_run": True,
            "requires_confirmation": True,
            "rows_total": len(rows),
            "counts": {
                "rows_total": len(rows),
                "creates": creates,
                "updates": updates,
                "skips": skips,
                "duplicates": len(duplicate_keys),
                "errors": len(row_errors),
                "changes": creates + updates,
            },
            "changes": [change for change in changes if change.get("action") != "skip"],
            "row_errors": row_errors,
            "duplicate_keys": duplicate_keys,
            "blockers": row_errors + duplicate_keys,
        }

    @staticmethod
    def _row_error(row_number: int, field: str, message: str) -> dict[str, Any]:
        return {"row": row_number, "field": field, "message": message}

    @staticmethod
    def _duplicate_key(row_number: int, key: str, value: str, message: str) -> dict[str, Any]:
        return {"row": row_number, "key": key, "value": value, "message": message}

    @staticmethod
    def _normalize_email(value: Any) -> str | None:
        text = _text(value, max_length=320)
        return text.lower() if text else None

    @staticmethod
    def _split_tags(value: Any) -> list[str]:
        text = _text(value, max_length=1000)
        if not text:
            return []
        return [part.strip() for part in re.split(r"[;,]", text) if part.strip()]

    async def _preview_import_people(self, rows: list[tuple[int, dict[str, str]]]) -> dict[str, Any]:
        import_type = "people"
        emails = [self._normalize_email(row.get("email")) for _, row in rows]
        email_counts = Counter(email for email in emails if email)
        existing_by_email: dict[str, RegistryPerson] = {}
        if email_counts:
            result = await self.session.execute(
                select(RegistryPerson).where(func.lower(RegistryPerson.email).in_(list(email_counts.keys())))
            )
            existing_by_email = {str(person.email).lower(): person for person in result.scalars().all() if person.email}
        changes: list[dict[str, Any]] = []
        row_errors: list[dict[str, Any]] = []
        duplicate_keys: list[dict[str, Any]] = []
        for row_number, row in rows:
            person_id = _text(row.get("person_id"), max_length=36)
            existing = await self.session.get(RegistryPerson, person_id) if person_id else None
            display_name = _text(row.get("display_name"), max_length=300)
            email = self._normalize_email(row.get("email"))
            errors: list[dict[str, Any]] = []
            if person_id and existing is None:
                errors.append(self._row_error(row_number, "person_id", "person_id not found"))
            if not display_name:
                errors.append(self._row_error(row_number, "display_name", "display_name is required"))
            department_id = _text(row.get("department_id"), max_length=36)
            location_id = _text(row.get("location_id"), max_length=36)
            if department_id and await self.session.get(RegistryDepartment, department_id) is None:
                errors.append(self._row_error(row_number, "department_id", "department_id not found"))
            if location_id and await self.session.get(RegistryLocation, location_id) is None:
                errors.append(self._row_error(row_number, "location_id", "location_id not found"))
            if errors:
                row_errors.extend(errors)
                continue
            if email and email_counts[email] > 1:
                duplicate_keys.append(self._duplicate_key(row_number, "email", email, "email appears more than once in this file"))
                continue
            duplicate = existing_by_email.get(email or "")
            if duplicate is not None and (existing is None or duplicate.person_id != existing.person_id):
                duplicate_keys.append(self._duplicate_key(row_number, "email", email or "", "email already belongs to another person"))
                continue
            after = {
                "display_name": display_name,
                "full_name": _text(row.get("full_name"), max_length=300),
                "email": email,
                "phone": _text(row.get("phone"), max_length=80),
                "department_id": department_id,
                "location_id": location_id,
                "status": _text(row.get("status"), max_length=30) or (existing.status if existing else "active"),
            }
            before = self._person_import_snapshot(existing) if existing else None
            if before == after:
                changes.append({"row": row_number, "kind": "person", "action": "skip", "object_id": person_id, "after": after})
            else:
                changes.append({"row": row_number, "kind": "person", "action": "update" if existing else "create", "object_id": person_id, "before": before, "after": after})
        return self._import_preview_payload(import_type, rows, changes, row_errors, duplicate_keys)

    @staticmethod
    def _person_import_snapshot(person: RegistryPerson | None) -> dict[str, Any] | None:
        if person is None:
            return None
        return {
            "display_name": person.display_name,
            "full_name": person.full_name,
            "email": person.email,
            "phone": person.phone,
            "department_id": person.department_id,
            "location_id": person.location_id,
            "status": person.status,
        }

    async def _apply_import_people(self, changes: list[dict[str, Any]]) -> None:
        for change in changes:
            after = change["after"]
            if change["action"] == "create":
                person = RegistryPerson(
                    person_id=_new_id(),
                    display_name=after["display_name"],
                    full_name=after.get("full_name"),
                    email=after.get("email"),
                    phone=after.get("phone"),
                    department_id=after.get("department_id"),
                    location_id=after.get("location_id"),
                    source="csv_import",
                    status=after.get("status") or "active",
                )
                self.session.add(person)
            elif change["action"] == "update":
                person = await self.session.get(RegistryPerson, change["object_id"])
                if person is None:
                    raise ValueError("person disappeared before apply")
                for field, value in after.items():
                    setattr(person, field, value)
                person.updated_at = _now()

    async def _preview_import_locations(self, rows: list[tuple[int, dict[str, str]]]) -> dict[str, Any]:
        import_type = "locations"
        keys = [(self._location_import_key(row), row_number) for row_number, row in rows]
        key_counts = Counter(key for key, _ in keys if key)
        existing_locations = (await self.session.execute(select(RegistryLocation))).scalars().all()
        existing_by_key = {
            (location.building.strip().casefold(), (location.floor or "").strip().casefold(), (location.room or "").strip().casefold()): location
            for location in existing_locations
        }
        changes: list[dict[str, Any]] = []
        row_errors: list[dict[str, Any]] = []
        duplicate_keys: list[dict[str, Any]] = []
        for row_number, row in rows:
            building = _text(row.get("building"), max_length=200)
            floor = _text(row.get("floor"), max_length=50)
            room = _text(row.get("room"), max_length=100)
            location_id = _text(row.get("location_id"), max_length=36)
            existing = await self.session.get(RegistryLocation, location_id) if location_id else None
            if location_id and existing is None:
                row_errors.append(self._row_error(row_number, "location_id", "location_id not found"))
                continue
            if not building:
                row_errors.append(self._row_error(row_number, "building", "building is required"))
                continue
            key = self._location_import_key(row)
            if key and key_counts[key] > 1:
                duplicate_keys.append(self._duplicate_key(row_number, "location", "|".join(key), "location appears more than once in this file"))
                continue
            duplicate = existing_by_key.get(key)
            if duplicate is not None and (existing is None or duplicate.location_id != existing.location_id):
                duplicate_keys.append(self._duplicate_key(row_number, "location", "|".join(key), "location already exists"))
                continue
            display_name = _location_display(building, floor, room, _text(row.get("display_name"), max_length=300))
            metadata = dict(existing.metadata_json or {}) if existing else {}
            metadata["notes"] = _text(row.get("notes"), max_length=2000)
            after = {
                "building": building,
                "floor": floor,
                "room": room,
                "display_name": display_name,
                "status": _text(row.get("status"), max_length=30) or (existing.status if existing else "active"),
                "metadata_json": metadata,
            }
            before = self._location_payload(existing) if existing else None
            changes.append({"row": row_number, "kind": "location", "action": "update" if existing else "create", "object_id": location_id, "before": before, "after": after})
        return self._import_preview_payload(import_type, rows, changes, row_errors, duplicate_keys)

    @staticmethod
    def _location_import_key(row: dict[str, str]) -> tuple[str, str, str] | None:
        building = _text(row.get("building"), max_length=200)
        if not building:
            return None
        return (
            building.casefold(),
            (_text(row.get("floor"), max_length=50) or "").casefold(),
            (_text(row.get("room"), max_length=100) or "").casefold(),
        )

    async def _apply_import_locations(self, changes: list[dict[str, Any]]) -> None:
        for change in changes:
            after = change["after"]
            if change["action"] == "create":
                self.session.add(RegistryLocation(location_id=_new_id(), source="csv_import", **after))
            elif change["action"] == "update":
                location = await self.session.get(RegistryLocation, change["object_id"])
                if location is None:
                    raise ValueError("location disappeared before apply")
                for field, value in after.items():
                    setattr(location, field, value)
                location.updated_at = _now()

    async def _preview_import_departments(self, rows: list[tuple[int, dict[str, str]]]) -> dict[str, Any]:
        import_type = "departments"
        codes = [_department_code(row.get("code")) for _, row in rows]
        code_counts = Counter(code for code in codes if code)
        existing_departments = (await self.session.execute(select(RegistryDepartment))).scalars().all()
        existing_by_code = {department.code: department for department in existing_departments if department.code}
        changes: list[dict[str, Any]] = []
        row_errors: list[dict[str, Any]] = []
        duplicate_keys: list[dict[str, Any]] = []
        for row_number, row in rows:
            department_id = _text(row.get("department_id"), max_length=36)
            existing = await self.session.get(RegistryDepartment, department_id) if department_id else None
            name = _text(row.get("name"), max_length=300)
            code = _department_code(row.get("code"))
            if department_id and existing is None:
                row_errors.append(self._row_error(row_number, "department_id", "department_id not found"))
                continue
            if not name:
                row_errors.append(self._row_error(row_number, "name", "name is required"))
                continue
            parent_department_id = _text(row.get("parent_id") or row.get("parent_department_id"), max_length=36)
            if parent_department_id and await self.session.get(RegistryDepartment, parent_department_id) is None:
                row_errors.append(self._row_error(row_number, "parent_id", "parent department not found"))
                continue
            if code and code_counts[code] > 1:
                duplicate_keys.append(self._duplicate_key(row_number, "code", code, "department code appears more than once in this file"))
                continue
            duplicate = existing_by_code.get(code or "")
            if duplicate is not None and (existing is None or duplicate.department_id != existing.department_id):
                duplicate_keys.append(self._duplicate_key(row_number, "code", code or "", "department code already exists"))
                continue
            metadata = dict(existing.metadata_json or {}) if existing else {}
            metadata.update(
                {
                    "manager_person_id": _text(row.get("manager_person_id"), max_length=36),
                    "support_queue": _text(row.get("support_queue"), max_length=120),
                    "notes": _text(row.get("notes"), max_length=2000),
                }
            )
            after = {
                "code": code,
                "name": name,
                "parent_department_id": parent_department_id,
                "status": _text(row.get("status"), max_length=30) or (existing.status if existing else "active"),
                "metadata_json": metadata,
            }
            before = self._department_payload(existing) if existing else None
            changes.append({"row": row_number, "kind": "department", "action": "update" if existing else "create", "object_id": department_id, "before": before, "after": after})
        return self._import_preview_payload(import_type, rows, changes, row_errors, duplicate_keys)

    async def _apply_import_departments(self, changes: list[dict[str, Any]]) -> None:
        for change in changes:
            after = change["after"]
            if change["action"] == "create":
                self.session.add(RegistryDepartment(department_id=_new_id(), source="csv_import", **after))
            elif change["action"] == "update":
                department = await self.session.get(RegistryDepartment, change["object_id"])
                if department is None:
                    raise ValueError("department disappeared before apply")
                for field, value in after.items():
                    setattr(department, field, value)
                department.updated_at = _now()

    async def _preview_import_device_inventory_mapping(self, rows: list[tuple[int, dict[str, str]]]) -> dict[str, Any]:
        import_type = "device_inventory_mapping"
        device_keys = [self._device_import_key(row) for _, row in rows]
        device_key_counts = Counter(key for key in device_keys if key)
        changes: list[dict[str, Any]] = []
        row_errors: list[dict[str, Any]] = []
        duplicate_keys: list[dict[str, Any]] = []
        for row_number, row in rows:
            device, error = await self._resolve_import_device(row)
            if error:
                row_errors.append(self._row_error(row_number, "device_id", error))
                continue
            assert device is not None
            device_key = self._device_import_key(row)
            if device_key and device_key_counts[device_key] > 1:
                duplicate_keys.append(self._duplicate_key(row_number, "device", device_key, "device appears more than once in this file"))
                continue
            location_id = _text(row.get("location_id"), max_length=36)
            department_id = _text(row.get("department_id"), max_length=36)
            if location_id and await self.session.get(RegistryLocation, location_id) is None:
                row_errors.append(self._row_error(row_number, "location_id", "location_id not found"))
                continue
            if department_id and await self.session.get(RegistryDepartment, department_id) is None:
                row_errors.append(self._row_error(row_number, "department_id", "department_id not found"))
                continue
            asset = (
                await self.session.execute(select(RegistryAsset).where(RegistryAsset.device_id == device.device_id).limit(1))
            ).scalar_one_or_none()
            binding = await self.session.get(DeviceInventoryBinding, device.device_id)
            after = {
                "device_id": device.device_id,
                "asset_id": asset.asset_id if asset else None,
                "asset_location_id": location_id,
                "asset_department_id": department_id,
                "binding": {
                    "building": _text(row.get("building"), max_length=120),
                    "floor": _text(row.get("floor"), max_length=64),
                    "room": _text(row.get("room"), max_length=120),
                    "department": _text(row.get("department"), max_length=160),
                    "responsible_user": _text(row.get("responsible_user"), max_length=160),
                    "responsible_user_login": _text(row.get("responsible_user_login"), max_length=160),
                    "inventory_number": _text(row.get("inventory_number"), max_length=120),
                    "status": _text(row.get("status"), max_length=32),
                    "tags": self._split_tags(row.get("tags")),
                    "notes": _text(row.get("notes"), max_length=2000),
                },
            }
            before = {
                "asset": {"location_id": asset.location_id, "department_id": asset.department_id} if asset else None,
                "binding": self._inventory_binding_snapshot(binding),
            }
            changes.append({"row": row_number, "kind": "device_inventory_mapping", "action": "update", "object_id": device.device_id, "before": before, "after": after})
        return self._import_preview_payload(import_type, rows, changes, row_errors, duplicate_keys)

    @staticmethod
    def _device_import_key(row: dict[str, str]) -> str | None:
        device_id = _text(row.get("device_id"), max_length=36)
        if device_id:
            return f"id:{device_id}"
        hostname = _text(row.get("hostname"), max_length=255)
        return f"host:{hostname.casefold()}" if hostname else None

    async def _resolve_import_device(self, row: dict[str, str]) -> tuple[Device | None, str | None]:
        device_id = _text(row.get("device_id"), max_length=36)
        hostname = _text(row.get("hostname"), max_length=255)
        if device_id:
            device = await self.session.get(Device, device_id)
            return (device, None) if device else (None, "device_id not found")
        if not hostname:
            return None, "device_id or hostname is required"
        devices = (await self.session.execute(select(Device).where(func.lower(Device.hostname) == hostname.lower()))).scalars().all()
        if not devices:
            return None, "hostname not found"
        if len(devices) > 1:
            return None, "hostname is not unique"
        return devices[0], None

    @staticmethod
    def _inventory_binding_snapshot(binding: DeviceInventoryBinding | None) -> dict[str, Any] | None:
        if binding is None:
            return None
        return {
            "asset_id": binding.asset_id,
            "building": binding.building,
            "floor": binding.floor,
            "room": binding.room,
            "department": binding.department,
            "responsible_user": binding.responsible_user,
            "responsible_user_login": binding.responsible_user_login,
            "inventory_number": binding.inventory_number,
            "status": binding.status,
            "tags": binding.tags or [],
            "notes": binding.notes,
        }

    async def _apply_import_device_inventory_mapping(self, changes: list[dict[str, Any]], *, actor_id: str | None = None) -> None:
        for change in changes:
            after = change["after"]
            device_id = after["device_id"]
            if after.get("asset_id"):
                asset = await self.session.get(RegistryAsset, after["asset_id"])
                if asset is not None:
                    asset.location_id = after.get("asset_location_id")
                    asset.department_id = after.get("asset_department_id")
                    asset.updated_at = _now()
            binding = await self.session.get(DeviceInventoryBinding, device_id)
            if binding is None:
                binding = DeviceInventoryBinding(device_id=device_id, asset_id=after.get("asset_id"), tags=[])
                self.session.add(binding)
            binding.asset_id = after.get("asset_id") or binding.asset_id
            for field, value in after["binding"].items():
                setattr(binding, field, value)
            binding.updated_by = actor_id
            binding.updated_at = _now()

    async def _build_export_rows(self, export_type: str) -> dict[str, Any]:
        export_type = str(export_type or "").strip().lower()
        if export_type == "locations":
            rows = await self.list_locations()
            columns = ["location_id", "display_name", "building", "floor", "room", "users_count", "devices_count", "status", "updated_at"]
        elif export_type == "departments":
            rows = await self.list_departments()
            columns = ["department_id", "code", "name", "manager_person_id", "support_queue", "users_count", "devices_count", "status", "updated_at"]
        else:
            from registry.service import RegistrySnapshotService

            snapshot = await RegistrySnapshotService(self.session).build_snapshot()
            if export_type == "devices":
                rows = snapshot.get("assets") or []
                columns = ["device_id", "hostname", "active_person_name", "binding_type", "location_name", "department_name", "registration_status", "agent_version", "last_seen_at"]
            elif export_type == "people":
                rows = snapshot.get("people") or []
                columns = ["person_id", "full_name", "display_name", "login", "email", "phone", "department_name", "location_name", "status"]
            elif export_type == "bindings":
                rows = snapshot.get("bindings") or []
                columns = ["binding_id", "device_id", "person_id", "relationship_type", "status", "confirmed_at", "valid_from", "valid_to"]
            elif export_type == "sessions":
                rows = snapshot.get("account_sessions") or []
                columns = ["session_id", "device_id", "person_id", "account_mode", "verification_status", "verification_method", "base_binding_id", "created_at", "expires_at", "revoked_at"]
            elif export_type == "quality":
                rows = snapshot.get("data_quality") or []
                columns = ["kind", "severity", "object_type", "object_id", "device_id", "person_id", "binding_id", "claim_id", "title", "description"]
            else:
                raise ValueError("unsupported export type")
        return {"columns": columns, "rows": rows}

    async def list_timeline(
        self,
        *,
        object_type: str,
        object_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 100), 200))
        items: list[dict[str, Any]] = []
        admin_stmt = select(RegistryAdminEvent).where(RegistryAdminEvent.object_type == object_type, RegistryAdminEvent.object_id == object_id)
        if object_type == "device":
            admin_stmt = select(RegistryAdminEvent).where(
                or_(
                    and_(RegistryAdminEvent.object_type == "device", RegistryAdminEvent.object_id == object_id),
                    RegistryAdminEvent.related_device_id == object_id,
                )
            )
            registration_rows = (
                await self.session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.device_id == object_id).order_by(desc(DeviceRegistrationEvent.event_at)).limit(limit)
                )
            ).scalars().all()
            account_rows = (
                await self.session.execute(
                    select(DeviceAccountEvent)
                    .where(DeviceAccountEvent.device_id == object_id)
                    .order_by(desc(DeviceAccountEvent.event_at))
                    .limit(limit)
                )
            ).scalars().all()
            items.extend(self.serialize_event(row) for row in registration_rows)
            items.extend(self.serialize_event(row) for row in account_rows)
        elif object_type == "person":
            admin_stmt = select(RegistryAdminEvent).where(or_(RegistryAdminEvent.object_id == object_id, RegistryAdminEvent.related_person_id == object_id))
            registration_rows = (
                await self.session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.person_id == object_id).order_by(desc(DeviceRegistrationEvent.event_at)).limit(limit)
                )
            ).scalars().all()
            items.extend(self.serialize_event(row) for row in registration_rows)
            session_rows = (
                await self.session.execute(
                    select(DeviceAccountSession)
                    .where(or_(DeviceAccountSession.person_id == object_id, DeviceAccountSession.base_person_id == object_id))
                    .limit(limit)
                )
            ).scalars().all()
            session_ids = [row.session_id for row in session_rows]
            if session_ids:
                account_rows = (
                    await self.session.execute(
                        select(DeviceAccountEvent)
                        .where(DeviceAccountEvent.session_id.in_(session_ids))
                        .order_by(desc(DeviceAccountEvent.event_at))
                        .limit(limit)
                    )
                ).scalars().all()
                items.extend(self.serialize_event(row) for row in account_rows)
        elif object_type == "binding":
            registration_rows = (
                await self.session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.binding_id == object_id).order_by(desc(DeviceRegistrationEvent.event_at)).limit(limit)
                )
            ).scalars().all()
            items.extend(self.serialize_event(row) for row in registration_rows)
            session_rows = (
                await self.session.execute(
                    select(DeviceAccountSession)
                    .where(or_(DeviceAccountSession.binding_id == object_id, DeviceAccountSession.base_binding_id == object_id))
                    .limit(limit)
                )
            ).scalars().all()
            session_ids = [row.session_id for row in session_rows]
            if session_ids:
                account_rows = (
                    await self.session.execute(
                        select(DeviceAccountEvent)
                        .where(DeviceAccountEvent.session_id.in_(session_ids))
                        .order_by(desc(DeviceAccountEvent.event_at))
                        .limit(limit)
                    )
                ).scalars().all()
                items.extend(self.serialize_event(row) for row in account_rows)
        elif object_type == "account_session":
            rows = (
                await self.session.execute(
                    select(DeviceAccountEvent)
                    .where(DeviceAccountEvent.session_id == object_id)
                    .order_by(desc(DeviceAccountEvent.event_at))
                    .limit(limit)
                )
            ).scalars().all()
            items.extend(self.serialize_event(row) for row in rows)
        elif object_type == "claim":
            registration_rows = (
                await self.session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.claim_id == object_id).order_by(desc(DeviceRegistrationEvent.event_at)).limit(limit)
                )
            ).scalars().all()
            items.extend(self.serialize_event(row) for row in registration_rows)

        admin_rows = (await self.session.execute(admin_stmt.order_by(desc(RegistryAdminEvent.event_at)).limit(limit))).scalars().all()
        items.extend(self.serialize_event(row) for row in admin_rows)
        items.sort(key=lambda item: item.get("event_at") or "", reverse=True)
        return items[:limit]
