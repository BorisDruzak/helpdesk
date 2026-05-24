from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
import re
import uuid
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
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
    Ticket,
)
from app.repos.registration_repo import normalize_identifier
from registry.account_session_service import AccountSessionService
from registry.policy_service import DEFAULT_REGISTRY_POLICIES, RegistryPolicyService


BULK_LIMIT = 200


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
        return {
            "event_id": row.event_id,
            "object_type": getattr(row, "object_type", None),
            "object_id": getattr(row, "object_id", None),
            "event_type": row.event_type,
            "actor_id": getattr(row, "actor_id", None),
            "actor_role": getattr(row, "actor_role", None),
            "reason": getattr(row, "reason", None),
            "related_device_id": getattr(row, "related_device_id", None),
            "related_person_id": getattr(row, "related_person_id", None),
            "device_id": getattr(row, "device_id", None),
            "person_id": getattr(row, "person_id", None),
            "binding_id": getattr(row, "binding_id", None),
            "claim_id": getattr(row, "claim_id", None),
            "session_id": getattr(row, "session_id", None),
            "request_id": getattr(row, "request_id", None),
            "ticket_id": getattr(row, "ticket_id", None),
            "event_at": row.event_at.isoformat() if getattr(row, "event_at", None) else None,
            "payload": getattr(row, "payload", None) or {},
        }

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

    async def get_policies(self) -> dict[str, Any]:
        effective = await RegistryPolicyService(self.session).get_policies()
        return {"defaults": DEFAULT_REGISTRY_POLICIES, "effective": effective}

    async def update_policies(self, data: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _require_reason(data.get("reason"))
        config = data.get("policies") if isinstance(data.get("policies"), dict) else data
        effective = await RegistryPolicyService(self.session).update_policies(config, actor_id=actor_id)
        await self.append_event(
            object_type="policy",
            object_id="registry_management",
            event_type="registry_policy_updated",
            actor_id=actor_id,
            reason=reason,
            payload={"effective": effective},
        )
        return {"defaults": DEFAULT_REGISTRY_POLICIES, "effective": effective}

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
                "claims": len(claims),
                "tickets": len(tickets),
                "assets": len(assets),
                "inventory_bindings": len(inventory_bindings),
            },
        }

    def _validate_bulk_ids(self, data: dict[str, Any]) -> list[str]:
        ids = [str(item).strip() for item in data.get("ids") or [] if str(item).strip()]
        if not ids:
            raise ValueError("ids are required")
        if len(ids) > BULK_LIMIT:
            raise ValueError(f"batch limit is {BULK_LIMIT}")
        return ids

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
        return {"results": results}

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
        return {"results": results}

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
            session_ids = [row.session_id for row in rows]
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
        return {"results": results}

    async def export_csv(self, export_type: str) -> str:
        registry = await self._build_export_rows(export_type)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=registry["columns"], lineterminator="\n")
        writer.writeheader()
        for row in registry["rows"]:
            writer.writerow({column: _csv_safe(row.get(column)) for column in registry["columns"]})
        return output.getvalue()

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
            admin_stmt = select(RegistryAdminEvent).where(RegistryAdminEvent.related_device_id == object_id)
            registration_rows = (
                await self.session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.device_id == object_id).order_by(desc(DeviceRegistrationEvent.event_at)).limit(limit)
                )
            ).scalars().all()
            account_rows = (
                await self.session.execute(
                    select(DeviceAccountSession)
                    .where(DeviceAccountSession.device_id == object_id)
                    .order_by(desc(DeviceAccountSession.created_at))
                    .limit(limit)
                )
            ).scalars().all()
            items.extend(self.serialize_event(row) for row in registration_rows)
            items.extend(
                {
                    "event_id": f"session:{row.session_id}",
                    "event_type": f"account_session_{row.verification_status}",
                    "device_id": row.device_id,
                    "session_id": row.session_id,
                    "person_id": row.person_id,
                    "event_at": row.created_at.isoformat() if row.created_at else None,
                    "payload": {"account_mode": row.account_mode, "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None},
                }
                for row in account_rows
            )
        elif object_type == "person":
            admin_stmt = select(RegistryAdminEvent).where(or_(RegistryAdminEvent.object_id == object_id, RegistryAdminEvent.related_person_id == object_id))
            registration_rows = (
                await self.session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.person_id == object_id).order_by(desc(DeviceRegistrationEvent.event_at)).limit(limit)
                )
            ).scalars().all()
            items.extend(self.serialize_event(row) for row in registration_rows)
        elif object_type == "binding":
            registration_rows = (
                await self.session.execute(
                    select(DeviceRegistrationEvent).where(DeviceRegistrationEvent.binding_id == object_id).order_by(desc(DeviceRegistrationEvent.event_at)).limit(limit)
                )
            ).scalars().all()
            items.extend(self.serialize_event(row) for row in registration_rows)
        elif object_type == "account_session":
            account_rows = await AccountSessionService(self.session).list_events_for_session_admin(object_id, limit=limit)
            items.extend(account_rows)

        admin_rows = (await self.session.execute(admin_stmt.order_by(desc(RegistryAdminEvent.event_at)).limit(limit))).scalars().all()
        items.extend(self.serialize_event(row) for row in admin_rows)
        items.sort(key=lambda item: item.get("event_at") or "", reverse=True)
        return items[:limit]
