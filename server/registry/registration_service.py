from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Device,
    DeviceInventoryBinding,
    DeviceInventoryBindingHistory,
    DeviceRegistrationEvent,
    RegistryAsset,
    RegistryPerson,
)
from app.repos.registration_repo import RegistrationRepo, normalize_identifier
from app.repos.registry_repo import RegistryRepo


REGISTRATION_POLICY = {
    "require_user_confirmation": True,
    "require_admin_confirmation": True,
    "auto_approve_first_binding": False,
    "allow_shared_devices": True,
    "max_primary_devices_per_person": 3,
    "stale_after_days": 90,
}

ALLOWED_RELATIONSHIP_TYPES = {"primary_user", "responsible", "owner", "shared_user", "temporary_user"}
PENDING_CLAIM_STATUSES = {
    "self_reported",
    "pending_user_confirmation",
    "user_confirmed",
    "pending_admin_review",
    "conflict",
}


class RegistrationConflictError(RuntimeError):
    def __init__(self, message: str, *, claim_id: str | None = None):
        super().__init__(message)
        self.claim_id = claim_id


class RegistrationValidationError(ValueError):
    pass


def _new_id() -> str:
    return str(uuid.uuid4())


def _validate_device_id(device_id: str) -> str:
    value = str(device_id or "").strip()
    if not value:
        raise RegistrationValidationError("device_id is required")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise RegistrationValidationError("device_id must be a valid UUID") from exc


def _clean(value: Any, *, max_length: int = 500) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return None
    if "<script" in text.lower() or "</" in text.lower():
        raise ValueError("profile field contains unsafe markup")
    return text[:max_length]


def _profile_value(profile: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _clean(profile.get(key), max_length=300)
        if value:
            return value
    return None


def _sanitize_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    profile = profile or {}
    allowed = {
        "full_name",
        "display_name",
        "login",
        "email",
        "phone",
        "department",
        "building",
        "floor",
        "room",
        "relationship_type",
        "is_shared_device",
        "current_user",
        "user_confirmed",
        "hostname",
        "os",
        "agent_version",
    }
    result: dict[str, Any] = {}
    for key in allowed:
        if key not in profile:
            continue
        if isinstance(profile[key], bool):
            result[key] = bool(profile[key])
        else:
            limit = 80 if key == "phone" else 300
            value = _clean(profile.get(key), max_length=limit)
            if value:
                result[key] = value
    email = result.get("email")
    if email and ("@" not in email or len(email) > 320):
        raise ValueError("invalid email")
    return result


def _compute_confidence(profile: dict[str, Any], requester_id: str | None) -> Decimal:
    score = Decimal("0.50")
    if profile.get("email") or profile.get("login") or requester_id:
        score += Decimal("0.15")
    if profile.get("department"):
        score += Decimal("0.10")
    if profile.get("building") or profile.get("room"):
        score += Decimal("0.10")
    current_user = normalize_identifier("windows_login", str(profile.get("current_user") or ""))
    login = normalize_identifier("windows_login", str(profile.get("login") or requester_id or ""))
    if current_user and login and current_user.endswith(login.split("\\")[-1]):
        score += Decimal("0.15")
    return min(score, Decimal("0.95"))


def _person_payload(person: RegistryPerson | None) -> dict[str, Any] | None:
    if not person:
        return None
    return {
        "person_id": person.person_id,
        "display_name": person.display_name,
        "full_name": person.full_name,
        "email": person.email,
        "phone": person.phone,
        "status": person.status,
        "department_id": person.department_id,
        "location_id": person.location_id,
    }


def _asset_payload(asset: RegistryAsset | None) -> dict[str, Any] | None:
    if not asset:
        return None
    return {
        "asset_id": asset.asset_id,
        "device_id": asset.device_id,
        "name": asset.name,
        "hostname": asset.hostname,
        "assigned_person_id": asset.assigned_person_id,
        "location_id": asset.location_id,
        "department_id": asset.department_id,
    }


class RegistrationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RegistrationRepo(session)
        self.registry_repo = RegistryRepo(session)

    async def _get_device(self, device_id: str) -> Device | None:
        return await self.session.get(Device, str(device_id))

    async def _require_device(self, device_id: str) -> Device:
        normalized = _validate_device_id(device_id)
        device = await self._get_device(normalized)
        if device is None:
            raise RegistrationValidationError("device not found")
        return device

    async def _find_or_create_person(
        self,
        *,
        requester_id: str | None,
        display_name: str | None,
        profile: dict[str, Any],
        department_id: str | None,
        location_id: str | None,
    ) -> RegistryPerson:
        identity_candidates = [
            ("email", profile.get("email")),
            ("windows_login", profile.get("login") or profile.get("current_user")),
            ("ui_login", requester_id),
            ("agent_profile", requester_id),
        ]
        for provider, identifier in identity_candidates:
            if identifier:
                person = await self.repo.find_person_by_identity(provider, str(identifier))
                if person:
                    person.display_name = display_name or person.display_name
                    person.full_name = profile.get("full_name") or person.full_name
                    person.phone = profile.get("phone") or person.phone
                    person.email = profile.get("email") or person.email
                    person.department_id = department_id or person.department_id
                    person.location_id = location_id or person.location_id
                    person.last_seen_at = datetime.now(timezone.utc)
                    await self.session.flush()
                    return person

        full_name = profile.get("full_name") or display_name or requester_id or "Unknown user"
        profile_key = (
            normalize_identifier("email", str(profile.get("email") or ""))
            or normalize_identifier("ui_login", str(requester_id or ""))
            or normalize_identifier("manual", str(display_name or full_name))
        )
        return await self.registry_repo.upsert_person_from_profile(
            profile_key=profile_key,
            display_name=display_name or full_name,
            full_name=full_name,
            phone=profile.get("phone"),
            email=profile.get("email"),
            department_id=department_id,
            location_id=location_id,
            metadata={"profile": profile},
        )

    async def _upsert_identities(self, person: RegistryPerson, *, requester_id: str | None, profile: dict[str, Any]) -> None:
        await self.repo.create_or_update_person_identity(
            person_id=person.person_id,
            provider="agent_profile",
            identifier=requester_id or person.profile_key,
            source="agent_profile",
        )
        await self.repo.create_or_update_person_identity(
            person_id=person.person_id,
            provider="ui_login",
            identifier=requester_id,
            source="agent_profile",
        )
        await self.repo.create_or_update_person_identity(
            person_id=person.person_id,
            provider="email",
            identifier=profile.get("email"),
            source="agent_profile",
        )
        await self.repo.create_or_update_person_identity(
            person_id=person.person_id,
            provider="phone",
            identifier=profile.get("phone"),
            source="agent_profile",
        )
        await self.repo.create_or_update_person_identity(
            person_id=person.person_id,
            provider="windows_login",
            identifier=profile.get("login") or profile.get("current_user"),
            source="agent_profile",
        )

    async def submit_agent_profile_claim(
        self,
        *,
        device_id: str,
        requester_id: str | None,
        display_name: str | None,
        profile: dict[str, Any],
        actor_id: str | None = None,
        actor_role: str | None = "agent",
    ) -> dict[str, Any]:
        device = await self._require_device(device_id)
        device_id = device.device_id
        profile_snapshot = _sanitize_profile(profile)
        display_name = _clean(display_name, max_length=300) or profile_snapshot.get("display_name")
        relationship_type = str(profile_snapshot.get("relationship_type") or "primary_user").strip()
        if profile_snapshot.get("is_shared_device") and relationship_type == "primary_user":
            relationship_type = "shared_user"
        if relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
            raise ValueError("invalid relationship_type")

        department = await self.registry_repo.get_or_create_department(
            name=profile_snapshot.get("department"),
            source="agent_profile",
            status="pending",
        )
        location = await self.registry_repo.get_or_create_location(
            building=profile_snapshot.get("building"),
            floor=profile_snapshot.get("floor"),
            room=profile_snapshot.get("room"),
            source="agent_profile",
            status="pending",
        )
        person = await self._find_or_create_person(
            requester_id=requester_id,
            display_name=display_name,
            profile=profile_snapshot,
            department_id=department.department_id if department else None,
            location_id=location.location_id if location else None,
        )
        await self._upsert_identities(person, requester_id=requester_id, profile=profile_snapshot)

        asset = await self.registry_repo.get_asset_by_device_id(device_id)
        if asset is None:
            asset = await self.registry_repo.upsert_agent_asset(
                device_id=device_id,
                hostname=profile_snapshot.get("hostname"),
                os_name=profile_snapshot.get("os"),
                agent_version=profile_snapshot.get("agent_version"),
                metadata={"source": "registration_claim"},
            )
        confidence = _compute_confidence(profile_snapshot, requester_id)
        conflict_reason = await self.detect_conflicts(device_id, person.person_id, relationship_type)
        if device is not None and getattr(device, "deleted_at", None) is not None:
            conflict_reason = "device_archived"

        user_confirmed = bool(profile_snapshot.get("user_confirmed") or (profile or {}).get("user_confirmed"))
        if conflict_reason:
            status = "conflict"
        elif user_confirmed:
            status = "pending_admin_review" if REGISTRATION_POLICY["require_admin_confirmation"] else "user_confirmed"
        else:
            status = "pending_user_confirmation" if REGISTRATION_POLICY["require_user_confirmation"] else "pending_admin_review"

        claim = await self.repo.find_pending_claim(device_id=device_id, person_id=person.person_id, source="agent_profile")
        now = datetime.now(timezone.utc)
        if claim is None:
            claim = await self.repo.create_claim(
                device_id=device_id,
                asset_id=asset.asset_id,
                person_id=person.person_id,
                claim_type="self_reported",
                status=status,
                relationship_type=relationship_type,
                profile_snapshot=profile_snapshot,
                device_snapshot={
                    "hostname": getattr(device, "hostname", None) if device else asset.hostname,
                    "os": getattr(device, "os", None) if device else profile_snapshot.get("os"),
                    "agent_version": getattr(device, "agent_version", None) if device else profile_snapshot.get("agent_version"),
                },
                confidence=confidence,
                source="agent_profile",
                source_ref=requester_id,
                submitted_at=now,
                user_confirmed_at=now if user_confirmed else None,
                conflict_reason=conflict_reason,
                metadata_json={},
            )
            await self.repo.append_event(
                event_type="claim_created",
                claim_id=claim.claim_id,
                device_id=device_id,
                person_id=person.person_id,
                actor_id=actor_id or requester_id,
                actor_role=actor_role,
                payload={"status": status, "relationship_type": relationship_type},
            )
        else:
            claim.asset_id = asset.asset_id
            claim.person_id = person.person_id
            claim.status = status if claim.status not in {"approved", "rejected", "superseded"} else claim.status
            claim.relationship_type = relationship_type
            claim.profile_snapshot = profile_snapshot
            claim.confidence = confidence
            claim.user_confirmed_at = claim.user_confirmed_at or (now if user_confirmed else None)
            claim.conflict_reason = conflict_reason
            claim.updated_at = now
            await self.repo.append_event(
                event_type="claim_updated",
                claim_id=claim.claim_id,
                device_id=device_id,
                person_id=person.person_id,
                actor_id=actor_id or requester_id,
                actor_role=actor_role,
                payload={"status": claim.status},
            )

        try:
            from inventory.service import DeviceInventoryService

            await DeviceInventoryService(self.session).create_or_update_binding_suggestion_from_profile(
                device_id=device_id,
                requester_id=requester_id,
                display_name=display_name or person.display_name,
                profile={**profile_snapshot, "full_name": person.full_name or person.display_name},
            )
        except Exception:
            pass

        return self._build_submit_payload(person=person, asset=asset, claim=claim)

    def _build_submit_payload(self, *, person: RegistryPerson, asset: RegistryAsset, claim: Any) -> dict[str, Any]:
        return {
            "person": _person_payload(person),
            "asset": _asset_payload(asset),
            "registration": {
                "claim_id": claim.claim_id,
                "status": claim.status,
                "requires_user_action": claim.status in {"self_reported", "pending_user_confirmation"},
                "requires_admin_action": claim.status in {"user_confirmed", "pending_admin_review", "conflict"},
                "conflict_reason": claim.conflict_reason,
            },
        }

    async def confirm_claim_by_user(self, claim_id: str, actor_id: str | None = None) -> dict[str, Any]:
        claim = await self.repo.get_claim(claim_id)
        if claim is None:
            raise ValueError("registration claim not found")
        if claim.status in {"approved", "rejected", "superseded"}:
            person = await self.registry_repo.get_person(claim.person_id)
            asset = await self.registry_repo.get_asset(claim.asset_id)
            return self._build_submit_payload(person=person, asset=asset, claim=claim)
        if claim.status not in {"pending_user_confirmation", "self_reported", "user_confirmed", "pending_admin_review", "conflict"}:
            raise ValueError("claim cannot be confirmed")
        conflict_reason = await self.detect_conflicts(claim.device_id, claim.person_id, claim.relationship_type)
        new_status = "conflict" if conflict_reason else "pending_admin_review"
        now = datetime.now(timezone.utc)
        claim.status = new_status
        claim.user_confirmed_at = claim.user_confirmed_at or now
        claim.conflict_reason = conflict_reason
        claim.updated_at = now
        await self.repo.append_event(
            event_type="user_confirmed",
            claim_id=claim.claim_id,
            device_id=claim.device_id,
            person_id=claim.person_id,
            actor_id=actor_id,
            actor_role="user",
            payload={"status": new_status},
        )
        await self.session.flush()
        person = await self.registry_repo.get_person(claim.person_id)
        asset = await self.registry_repo.get_asset(claim.asset_id)
        if not conflict_reason and REGISTRATION_POLICY["auto_approve_first_binding"] and not REGISTRATION_POLICY["require_admin_confirmation"]:
            return await self.approve_claim(claim.claim_id, reviewed_by=actor_id or "system", actor_role="system")
        return self._build_submit_payload(person=person, asset=asset, claim=claim)

    async def approve_claim(
        self,
        claim_id: str,
        reviewed_by: str | None,
        actor_role: str = "admin",
        fields: list[str] | None = None,
        replace_existing: bool = False,
        admin_override_user_confirmation: bool = False,
        override_reason: str | None = None,
    ) -> dict[str, Any]:
        claim = await self.repo.get_claim(claim_id)
        if claim is None:
            raise ValueError("registration claim not found")
        existing_for_claim = None
        if claim.status == "approved":
            rows = await self.repo.list_active_bindings_for_device(claim.device_id)
            existing_for_claim = next((row for row in rows if row.source_claim_id == claim.claim_id), None)
            if existing_for_claim:
                return await self._build_approved_payload(claim, existing_for_claim)
        if claim.status in {"rejected", "superseded", "expired"}:
            raise ValueError("claim cannot be approved")
        if (
            REGISTRATION_POLICY["require_user_confirmation"]
            and not claim.user_confirmed_at
            and not admin_override_user_confirmation
        ):
            claim.status = "pending_user_confirmation"
            claim.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
            raise RegistrationConflictError("user confirmation required before approval", claim_id=claim.claim_id)

        active_primary = await self.repo.get_active_primary_binding(claim.device_id)
        if active_primary and claim.relationship_type == "primary_user" and active_primary.person_id == claim.person_id:
            now = datetime.now(timezone.utc)
            claim.status = "approved"
            claim.reviewed_by = reviewed_by
            claim.reviewed_at = now
            claim.updated_at = now
            await self.repo.append_event(
                event_type="claim_approved_existing_binding",
                claim_id=claim.claim_id,
                binding_id=active_primary.binding_id,
                device_id=claim.device_id,
                person_id=claim.person_id,
                actor_id=reviewed_by,
                actor_role=actor_role,
                payload={"reason": "active primary binding already exists for same person"},
            )
            await self.session.flush()
            return await self._build_approved_payload(claim, active_primary)
        if (
            active_primary
            and claim.relationship_type == "primary_user"
            and active_primary.person_id != claim.person_id
            and not replace_existing
        ):
            claim.status = "conflict"
            claim.conflict_reason = "active_primary_user_exists"
            await self.repo.append_event(
                event_type="conflict_detected",
                claim_id=claim.claim_id,
                binding_id=active_primary.binding_id,
                device_id=claim.device_id,
                person_id=claim.person_id,
                actor_id=reviewed_by,
                actor_role=actor_role,
                payload={"reason": claim.conflict_reason},
            )
            await self.session.flush()
            raise RegistrationConflictError("active primary binding exists", claim_id=claim.claim_id)
        if active_primary and replace_existing and active_primary.person_id != claim.person_id:
            now = datetime.now(timezone.utc)
            active_primary.status = "transferred"
            active_primary.valid_to = now
            active_primary.revoked_by = reviewed_by
            active_primary.revoked_at = now
            active_primary.revoke_reason = "replaced by approved registration claim"
            await self.repo.append_event(
                event_type="binding_transferred",
                claim_id=claim.claim_id,
                binding_id=active_primary.binding_id,
                device_id=claim.device_id,
                person_id=active_primary.person_id,
                actor_id=reviewed_by,
                actor_role=actor_role,
                payload={"replacement_claim_id": claim.claim_id},
            )
            await self._record_inventory_registration_history(
                device_id=active_primary.device_id,
                changed_by=reviewed_by,
                reason="registration_transferred",
            )
            await self.session.flush()

        now = datetime.now(timezone.utc)
        binding = await self.repo.create_binding(
            device_id=claim.device_id,
            asset_id=claim.asset_id,
            person_id=claim.person_id,
            relationship_type=claim.relationship_type,
            status="active",
            source_claim_id=claim.claim_id,
            source="registration_claim",
            confidence=claim.confidence,
            valid_from=now,
            confirmed_by_user_at=claim.user_confirmed_at,
            confirmed_by_admin=reviewed_by,
            confirmed_at=now,
            metadata_json={"profile_snapshot": claim.profile_snapshot or {}},
        )
        claim.status = "approved"
        claim.reviewed_by = reviewed_by
        claim.reviewed_at = now
        claim.updated_at = now
        await self.sync_asset_from_active_binding(binding)
        await self.sync_inventory_from_active_binding(binding, profile=claim.profile_snapshot or {})
        await self.repo.append_event(
            event_type="admin_approved",
            claim_id=claim.claim_id,
            binding_id=binding.binding_id,
            device_id=claim.device_id,
            person_id=claim.person_id,
            actor_id=reviewed_by,
            actor_role=actor_role,
            payload={
                "admin_override_user_confirmation": bool(admin_override_user_confirmation),
                "override_reason": _clean(override_reason, max_length=1000),
            },
        )
        await self.repo.append_event(
            event_type="binding_activated",
            claim_id=claim.claim_id,
            binding_id=binding.binding_id,
            device_id=claim.device_id,
            person_id=claim.person_id,
            actor_id=reviewed_by,
            actor_role=actor_role,
            payload={"relationship_type": binding.relationship_type},
        )
        await self.session.flush()
        return await self._build_approved_payload(claim, binding)

    async def _build_approved_payload(self, claim: Any, binding: Any) -> dict[str, Any]:
        person = await self.registry_repo.get_person(binding.person_id)
        asset = await self.registry_repo.get_asset(binding.asset_id)
        payload = self._build_submit_payload(person=person, asset=asset, claim=claim)
        payload["binding"] = {
            "binding_id": binding.binding_id,
            "device_id": binding.device_id,
            "asset_id": binding.asset_id,
            "person_id": binding.person_id,
            "relationship_type": binding.relationship_type,
            "status": binding.status,
            "confirmed_at": binding.confirmed_at.isoformat() if binding.confirmed_at else None,
        }
        return payload

    async def reject_claim(self, claim_id: str, reviewed_by: str | None, reason: str) -> dict[str, Any]:
        claim = await self.repo.get_claim(claim_id)
        if claim is None:
            raise ValueError("registration claim not found")
        now = datetime.now(timezone.utc)
        claim.status = "rejected"
        claim.reviewed_by = reviewed_by
        claim.reviewed_at = now
        claim.rejection_reason = _clean(reason, max_length=1000) or "rejected"
        claim.updated_at = now
        await self.repo.append_event(
            event_type="admin_rejected",
            claim_id=claim.claim_id,
            device_id=claim.device_id,
            person_id=claim.person_id,
            actor_id=reviewed_by,
            actor_role="admin",
            payload={"reason": claim.rejection_reason},
        )
        await self.session.flush()
        person = await self.registry_repo.get_person(claim.person_id)
        asset = await self.registry_repo.get_asset(claim.asset_id)
        return self._build_submit_payload(person=person, asset=asset, claim=claim)

    async def revoke_binding(self, binding_id: str, *, revoked_by: str | None = None, reason: str | None = None) -> dict[str, Any]:
        binding = await self.repo.revoke_binding(binding_id, revoked_by=revoked_by, reason=reason)
        replacement = await self.repo.get_active_primary_binding(binding.device_id)
        if replacement:
            await self.sync_asset_from_active_binding(replacement)
            await self.sync_inventory_from_active_binding(
                replacement,
                profile=(replacement.metadata_json or {}).get("profile_snapshot") or {},
                reason="registration_revoked",
            )
        else:
            await self.clear_registration_assignment_for_binding(binding, changed_by=revoked_by)
        await self.repo.append_event(
            event_type="binding_revoked",
            binding_id=binding.binding_id,
            device_id=binding.device_id,
            person_id=binding.person_id,
            actor_id=revoked_by,
            actor_role="admin",
            payload={"reason": reason},
        )
        await self.session.flush()
        return {"binding": {"binding_id": binding.binding_id, "status": binding.status}}

    async def sync_asset_from_active_binding(self, binding: Any) -> None:
        asset = await self.registry_repo.get_asset(binding.asset_id)
        person = await self.registry_repo.get_person(binding.person_id)
        if not asset or not person:
            return
        asset.assigned_person_id = binding.person_id
        if person.location_id:
            asset.location_id = person.location_id
        if person.department_id:
            asset.department_id = person.department_id
        if asset.status in {"unverified", "pending"}:
            asset.status = "verified"
        asset.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

    def _inventory_registration_dict(self, row: DeviceInventoryBinding | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "person_id": row.person_id,
            "asset_id": row.asset_id,
            "source_binding_id": row.source_binding_id,
            "registration_status": row.registration_status,
            "responsible_user": row.responsible_user,
            "responsible_user_login": row.responsible_user_login,
            "building": row.building,
            "floor": row.floor,
            "room": row.room,
            "department": row.department,
            "inventory_number": row.inventory_number,
            "tags": list(row.tags or []),
            "notes": row.notes,
        }

    async def _record_inventory_registration_history(
        self,
        *,
        device_id: str,
        changed_by: str | None,
        reason: str,
        old_binding: dict[str, Any] | None = None,
        new_binding: dict[str, Any] | None = None,
    ) -> None:
        row = await self.session.get(DeviceInventoryBinding, device_id)
        old_payload = old_binding if old_binding is not None else self._inventory_registration_dict(row)
        new_payload = new_binding if new_binding is not None else self._inventory_registration_dict(row)
        if old_payload == new_payload:
            return
        changed_fields = sorted(
            key
            for key in set((old_payload or {}).keys()) | set((new_payload or {}).keys())
            if (old_payload or {}).get(key) != (new_payload or {}).get(key)
        )
        self.session.add(
            DeviceInventoryBindingHistory(
                id=_new_id(),
                device_id=device_id,
                changed_by=changed_by,
                changed_at=datetime.now(timezone.utc),
                old_binding=old_payload,
                new_binding=new_payload or {},
                changed_fields=changed_fields,
                reason=reason,
            )
        )

    async def sync_inventory_from_active_binding(
        self,
        binding: Any,
        *,
        profile: dict[str, Any],
        reason: str = "registration_approved",
    ) -> None:
        row = await self.session.get(DeviceInventoryBinding, binding.device_id)
        now = datetime.now(timezone.utc)
        old_payload = self._inventory_registration_dict(row)
        if row is None:
            row = DeviceInventoryBinding(device_id=binding.device_id, updated_at=now)
            self.session.add(row)
        person = await self.registry_repo.get_person(binding.person_id)
        row.person_id = binding.person_id
        row.asset_id = binding.asset_id
        row.source_binding_id = binding.binding_id
        row.registration_status = "admin_confirmed"
        row.responsible_user = row.responsible_user or (person.display_name if person else None)
        row.responsible_user_login = row.responsible_user_login or profile.get("login") or profile.get("email")
        for field_name in ("building", "floor", "room", "department"):
            value = profile.get(field_name)
            if value and not getattr(row, field_name):
                setattr(row, field_name, value)
        row.updated_by = binding.confirmed_by_admin
        row.updated_at = now
        await self.session.flush()
        await self._record_inventory_registration_history(
            device_id=binding.device_id,
            changed_by=binding.confirmed_by_admin,
            reason=reason,
            old_binding=old_payload,
            new_binding=self._inventory_registration_dict(row),
        )
        await self.session.flush()

    async def clear_registration_assignment_for_binding(self, binding: Any, *, changed_by: str | None = None) -> None:
        asset = await self.registry_repo.get_asset(binding.asset_id)
        if asset and asset.assigned_person_id == binding.person_id:
            asset.assigned_person_id = None
            asset.updated_at = datetime.now(timezone.utc)
        row = await self.session.get(DeviceInventoryBinding, binding.device_id)
        if row is not None:
            old_payload = self._inventory_registration_dict(row)
            if row.source_binding_id == binding.binding_id or row.person_id == binding.person_id:
                row.person_id = None
                row.source_binding_id = None
                row.registration_status = "revoked"
                row.updated_by = changed_by
                row.updated_at = datetime.now(timezone.utc)
                await self.session.flush()
                await self._record_inventory_registration_history(
                    device_id=binding.device_id,
                    changed_by=changed_by,
                    reason="registration_revoked",
                    old_binding=old_payload,
                    new_binding=self._inventory_registration_dict(row),
                )
        await self.session.flush()

    async def detect_conflicts(self, device_id: str, person_id: str | None, relationship_type: str) -> str | None:
        if not person_id:
            return None
        active_primary = await self.repo.get_active_primary_binding(device_id)
        if active_primary and relationship_type == "primary_user" and active_primary.person_id != person_id:
            return "active_primary_user_exists"
        person = await self.registry_repo.get_person(person_id)
        if person and str(person.status or "").lower() in {"inactive", "disabled"}:
            return "person_inactive"
        primary_count = sum(
            1
            for row in await self.repo.list_bindings_for_person(person_id, active_only=True)
            if row.relationship_type == "primary_user"
        )
        if relationship_type == "primary_user" and primary_count >= int(REGISTRATION_POLICY["max_primary_devices_per_person"]):
            return "person_primary_device_limit"
        device = await self._get_device(device_id)
        if device is not None and getattr(device, "deleted_at", None) is not None:
            return "device_archived"
        return None

    async def get_device_registration_status(self, device_id: str) -> dict[str, Any]:
        active = await self.repo.get_active_primary_binding(device_id)
        active_bindings = await self.repo.list_active_bindings_for_device(device_id)
        claims = await self.repo.list_claims(device_id=device_id, limit=50)
        latest_claim = claims[0] if claims else None
        if active:
            status = "admin_confirmed"
        elif active_bindings:
            status = "shared_device"
        elif latest_claim and latest_claim.status == "conflict":
            status = "conflict"
        elif latest_claim and latest_claim.status in {"pending_admin_review", "user_confirmed"}:
            status = "pending_admin_review"
        elif latest_claim and latest_claim.status in {"pending_user_confirmation", "self_reported"}:
            status = "self_reported"
        elif latest_claim and latest_claim.status == "rejected":
            status = "rejected"
        else:
            status = "unregistered"
        person = await self.registry_repo.get_person(active.person_id) if active else None
        pending_claim = next((claim for claim in claims if claim.status in PENDING_CLAIM_STATUSES), None)
        return {
            "device_id": device_id,
            "status": status,
            "active_binding": self._binding_payload(active) if active else None,
            "active_person": _person_payload(person),
            "pending_claim": self._claim_payload(pending_claim) if pending_claim else None,
            "claims_count": len(claims),
            "requires_user_action": bool(pending_claim and pending_claim.status in {"pending_user_confirmation", "self_reported"}),
            "requires_admin_action": bool(pending_claim and pending_claim.status in {"user_confirmed", "pending_admin_review", "conflict"}),
            "conflict_reason": pending_claim.conflict_reason if pending_claim else None,
        }

    def _binding_payload(self, binding: Any) -> dict[str, Any]:
        return {
            "binding_id": binding.binding_id,
            "device_id": binding.device_id,
            "asset_id": binding.asset_id,
            "person_id": binding.person_id,
            "relationship_type": binding.relationship_type,
            "status": binding.status,
            "confirmed_at": binding.confirmed_at.isoformat() if binding.confirmed_at else None,
            "confirmed_by_admin": binding.confirmed_by_admin,
        }

    def _claim_payload(self, claim: Any) -> dict[str, Any]:
        return {
            "claim_id": claim.claim_id,
            "device_id": claim.device_id,
            "asset_id": claim.asset_id,
            "person_id": claim.person_id,
            "status": claim.status,
            "claim_type": claim.claim_type,
            "relationship_type": claim.relationship_type,
            "confidence": float(claim.confidence) if claim.confidence is not None else None,
            "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
            "conflict_reason": claim.conflict_reason,
            "profile_snapshot": claim.profile_snapshot or {},
        }

    async def list_registration_claims(
        self,
        *,
        status: str | None = None,
        device_id: str | None = None,
        person_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        claims = await self.repo.list_claims(status=status, device_id=device_id, person_id=person_id, limit=limit)
        return [self._claim_payload(claim) for claim in claims]

    async def get_timeline(self, device_id: str) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(DeviceRegistrationEvent)
            .where(DeviceRegistrationEvent.device_id == str(device_id))
            .order_by(DeviceRegistrationEvent.event_at)
        )
        rows = list(result.scalars().all())
        return [
            {
                "event_id": row.event_id,
                "claim_id": row.claim_id,
                "binding_id": row.binding_id,
                "device_id": row.device_id,
                "person_id": row.person_id,
                "event_type": row.event_type,
                "actor_id": row.actor_id,
                "actor_role": row.actor_role,
                "event_at": row.event_at.isoformat() if row.event_at else None,
                "payload": row.payload or {},
            }
            for row in rows
        ]
