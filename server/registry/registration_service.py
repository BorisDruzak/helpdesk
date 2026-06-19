from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import re
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceInventoryBinding,
    DeviceInventoryBindingHistory,
    DeviceRegistrationClaim,
    DeviceRegistrationEvent,
    RegistryAsset,
    RegistryPerson,
    Ticket,
)
from app.repos.registration_repo import RegistrationRepo, is_person_active, normalize_identifier
from app.repos.registry_repo import RegistryRepo
from registry.policy_service import RegistryPolicyService


REGISTRATION_POLICY = {
    "require_user_confirmation": True,
    "require_admin_confirmation": False,
    "auto_approve_first_binding": True,
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
        "department_id",
        "location_id",
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


def _raise_if_person_inactive(person: RegistryPerson | None) -> None:
    if not is_person_active(person):
        raise RegistrationValidationError("registry person is archived or inactive")


class RegistrationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RegistrationRepo(session)
        self.registry_repo = RegistryRepo(session)

    @staticmethod
    def _operation_status(items: list[dict[str, Any]]) -> str:
        failed = sum(1 for item in items if item.get("status") == "error")
        success = sum(1 for item in items if item.get("status") == "success")
        if failed and success:
            return "partial_success"
        if failed:
            return "error"
        return "success"

    @staticmethod
    def _operation_result(*, operation: str, items: list[dict[str, Any]], events: list[str], summary_extra: dict[str, int] | None = None) -> dict[str, Any]:
        summary = {
            "success": sum(1 for item in items if item.get("status") == "success"),
            "failed": sum(1 for item in items if item.get("status") == "error"),
            "warnings": 0,
        }
        if summary_extra:
            summary.update(summary_extra)
        return {
            "operation_id": _new_id(),
            "operation": operation,
            "status": RegistrationService._operation_status(items),
            "summary": summary,
            "items": items,
            "events": events,
            "report_url": None,
        }

    async def _registration_policy(self) -> dict[str, Any]:
        try:
            policies = await RegistryPolicyService(self.session).get_policies()
            return policies.get("registration") or REGISTRATION_POLICY
        except Exception:
            return REGISTRATION_POLICY

    async def _get_device(self, device_id: str) -> Device | None:
        return await self.session.get(Device, str(device_id))

    async def _require_device(self, device_id: str) -> Device:
        normalized = _validate_device_id(device_id)
        device = await self._get_device(normalized)
        if device is None:
            raise RegistrationValidationError("device not found")
        return device

    async def _ensure_asset_for_device(self, device: Device) -> RegistryAsset:
        asset = await self.registry_repo.get_asset_by_device_id(device.device_id)
        if asset is not None:
            return asset
        return await self.registry_repo.upsert_agent_asset(
            device_id=device.device_id,
            hostname=device.hostname,
            os_name=device.os,
            agent_version=device.agent_version,
            metadata={"source": "admin_registry_action"},
        )

    async def _resolve_registration_department(self, profile: dict[str, Any], policy: dict[str, Any]) -> str | None:
        mode = str(policy.get("department_mode") or "allow_pending_request").strip().lower()
        department_id = _clean(profile.get("department_id"), max_length=36)
        if department_id:
            department = await self.registry_repo.get_department(department_id)
            if department is None or str(department.status or "").lower() in {"archived", "merged", "inactive"}:
                raise RegistrationValidationError("department_id not found")
            return department.department_id
        if mode == "required_existing":
            raise RegistrationValidationError("department_id is required")
        if mode == "allow_pending_request":
            department = await self.registry_repo.get_or_create_department(
                name=profile.get("department"),
                source="agent_profile",
                status="pending",
            )
            return department.department_id if department else None
        return None

    async def _resolve_registration_location(self, profile: dict[str, Any], policy: dict[str, Any]) -> str | None:
        mode = str(policy.get("location_mode") or "allow_pending_request").strip().lower()
        location_id = _clean(profile.get("location_id"), max_length=36)
        if location_id:
            location = await self.registry_repo.get_location(location_id)
            if location is None or str(location.status or "").lower() in {"archived", "merged", "inactive"}:
                raise RegistrationValidationError("location_id not found")
            return location.location_id
        if mode == "required_existing":
            raise RegistrationValidationError("location_id is required")
        if mode == "allow_pending_request":
            location = await self.registry_repo.get_or_create_location(
                building=profile.get("building"),
                floor=profile.get("floor"),
                room=profile.get("room"),
                source="agent_profile",
                status="pending",
            )
            return location.location_id if location else None
        return None

    async def _apply_claim_profile_to_person(self, claim: DeviceRegistrationClaim) -> RegistryPerson | None:
        person = await self.registry_repo.get_person(claim.person_id)
        if person is None:
            return None
        profile = claim.profile_snapshot or {}
        changed = False

        department_id = _clean(profile.get("department_id"), max_length=36)
        if department_id:
            department = await self.registry_repo.get_department(department_id)
            if department is None or str(department.status or "").lower() in {"archived", "merged", "inactive"}:
                raise RegistrationValidationError("department_id not found")
            if person.department_id != department.department_id:
                person.department_id = department.department_id
                changed = True

        location_id = _clean(profile.get("location_id"), max_length=36)
        if location_id:
            location = await self.registry_repo.get_location(location_id)
            if location is None or str(location.status or "").lower() in {"archived", "merged", "inactive"}:
                raise RegistrationValidationError("location_id not found")
            if person.location_id != location.location_id:
                person.location_id = location.location_id
                changed = True

        if changed:
            person.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
        return person

    async def _mark_claim_resolved_by_admin_binding(
        self,
        claim: DeviceRegistrationClaim,
        binding: Any,
        *,
        reviewed_by: str | None,
        reason: str | None,
        matched: bool,
    ) -> None:
        now = datetime.now(timezone.utc)
        if claim.claim_id == binding.source_claim_id:
            return
        claim.status = "approved" if matched else "superseded"
        claim.reviewed_by = reviewed_by
        claim.reviewed_at = now
        claim.updated_at = now
        if not matched:
            claim.conflict_reason = "resolved_by_admin_binding"
        await self.repo.append_event(
            event_type="claim_satisfied_by_admin_binding" if matched else "claim_superseded_by_admin_binding",
            claim_id=claim.claim_id,
            binding_id=binding.binding_id,
            device_id=claim.device_id,
            person_id=claim.person_id,
            actor_id=reviewed_by,
            actor_role="admin",
            payload={"reason": reason, "matched": matched, "binding_person_id": binding.person_id},
        )

    async def _reconcile_open_agent_claims_for_binding(
        self,
        *,
        device_id: str,
        binding: Any,
        reviewed_by: str | None,
        reason: str | None,
    ) -> None:
        claims = await self.repo.list_claims(device_id=device_id, limit=100)
        for claim in claims:
            if claim.status not in PENDING_CLAIM_STATUSES or claim.source != "agent_profile":
                continue
            matched = claim.person_id == binding.person_id and claim.relationship_type == binding.relationship_type
            await self._mark_claim_resolved_by_admin_binding(
                claim,
                binding,
                reviewed_by=reviewed_by,
                reason=reason,
                matched=matched,
            )

    async def _revoke_account_sessions_for_binding(
        self,
        binding_id: str,
        *,
        revoked_by: str | None,
        reason: str,
    ) -> list[dict[str, Any]]:
        from registry.account_session_service import AccountSessionService

        return await AccountSessionService(self.session).revoke_sessions_for_binding(
            binding_id=binding_id,
            revoked_by=revoked_by,
            reason=reason,
        )

    async def _cancel_account_login_requests_for_binding(
        self,
        binding_id: str,
        *,
        canceled_by: str | None,
        reason: str,
    ) -> list[dict[str, Any]]:
        from registry.account_session_service import AccountSessionService

        return await AccountSessionService(self.session).cancel_pending_login_requests_for_binding(
            binding_id=binding_id,
            canceled_by=canceled_by,
            reason=reason,
        )

    async def _revoke_registration_pending_sessions_for_claim(
        self,
        claim_id: str,
        *,
        revoked_by: str | None,
        reason: str,
    ) -> list[dict[str, Any]]:
        from registry.account_session_service import AccountSessionService

        return await AccountSessionService(self.session).revoke_registration_pending_sessions_for_claim(
            claim_id=claim_id,
            revoked_by=revoked_by,
            reason=reason,
        )

    async def _create_admin_binding(
        self,
        *,
        device: Device,
        asset: RegistryAsset,
        person: RegistryPerson,
        relationship_type: str,
        reviewed_by: str | None,
        reason: str | None,
        source: str = "admin_manual",
        source_claim: DeviceRegistrationClaim | None = None,
    ) -> tuple[Any, Any]:
        now = datetime.now(timezone.utc)
        if source_claim is None:
            claim = await self.repo.create_claim(
                device_id=device.device_id,
                asset_id=asset.asset_id,
                person_id=person.person_id,
                claim_type="admin_created",
                status="approved",
                relationship_type=relationship_type,
                profile_snapshot={
                    "display_name": person.display_name,
                    "full_name": person.full_name,
                    "email": person.email,
                    "phone": person.phone,
                    "reason": _clean(reason, max_length=1000),
                },
                device_snapshot={
                    "hostname": device.hostname or asset.hostname,
                    "os": device.os,
                    "agent_version": device.agent_version,
                },
                confidence=Decimal("1.00"),
                source=source,
                source_ref=reviewed_by,
                submitted_at=now,
                user_confirmed_at=None,
                reviewed_by=reviewed_by,
                reviewed_at=now,
                metadata_json={"reason": _clean(reason, max_length=1000)},
            )
        else:
            claim = source_claim
            claim.status = "approved"
            claim.reviewed_by = reviewed_by
            claim.reviewed_at = now
            claim.updated_at = now
            claim.conflict_reason = None
            metadata = dict(claim.metadata_json or {})
            metadata["admin_binding_reason"] = _clean(reason, max_length=1000)
            claim.metadata_json = metadata
        binding = await self.repo.create_binding(
            device_id=device.device_id,
            asset_id=asset.asset_id,
            person_id=person.person_id,
            relationship_type=relationship_type,
            status="active",
            source_claim_id=claim.claim_id,
            source=source,
            confidence=Decimal("1.00"),
            valid_from=now,
            confirmed_by_admin=reviewed_by,
            confirmed_at=now,
            metadata_json={"reason": _clean(reason, max_length=1000), "admin_created": True},
        )
        await self.repo.append_event(
            event_type="admin_binding_created",
            claim_id=claim.claim_id,
            binding_id=binding.binding_id,
            device_id=device.device_id,
            person_id=person.person_id,
            actor_id=reviewed_by,
            actor_role="admin",
            payload={"relationship_type": relationship_type, "reason": reason},
        )
        await self.repo.append_event(
            event_type="binding_activated",
            claim_id=claim.claim_id,
            binding_id=binding.binding_id,
            device_id=device.device_id,
            person_id=person.person_id,
            actor_id=reviewed_by,
            actor_role="admin",
            payload={"relationship_type": relationship_type, "source": source},
        )
        return claim, binding

    async def _retire_binding(
        self,
        binding: Any,
        *,
        status: str,
        reviewed_by: str | None,
        reason: str | None,
        event_type: str,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        binding.status = status
        binding.valid_to = now
        binding.revoked_by = reviewed_by
        binding.revoked_at = now
        binding.revoke_reason = _clean(reason, max_length=1000)
        binding.updated_at = now
        await self.repo.append_event(
            event_type=event_type,
            binding_id=binding.binding_id,
            device_id=binding.device_id,
            person_id=binding.person_id,
            actor_id=reviewed_by,
            actor_role="admin",
            payload={"reason": reason, "status": status},
        )
        revoked_sessions = await self._revoke_account_sessions_for_binding(
            binding.binding_id,
            revoked_by=reviewed_by,
            reason=f"{event_type}: {reason or status}",
        )
        await self._cancel_account_login_requests_for_binding(
            binding.binding_id,
            canceled_by=reviewed_by,
            reason=f"base binding changed: {reason or status}",
        )
        if revoked_sessions:
            await self.repo.append_event(
                event_type="account_sessions_revoked_due_to_transfer"
                if status == "transferred"
                else "account_sessions_revoked_due_to_revoke",
                binding_id=binding.binding_id,
                device_id=binding.device_id,
                person_id=binding.person_id,
                actor_id=reviewed_by,
                actor_role="admin",
                payload={"revoked_session_ids": [row["session_id"] for row in revoked_sessions]},
            )
        return revoked_sessions

    async def bind_person_to_device(
        self,
        *,
        device_id: str,
        person_id: str,
        relationship_type: str,
        replace_existing: bool = False,
        reviewed_by: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        device = await self._require_device(device_id)
        person = await self.registry_repo.get_person(person_id)
        if person is None:
            raise RegistrationValidationError("person not found")
        if relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
            raise RegistrationValidationError("invalid relationship_type")
        policy = await self._registration_policy()
        if relationship_type == "shared_user" and not bool(policy.get("allow_shared_devices", True)):
            raise RegistrationConflictError("shared device bindings are disabled by policy")
        if relationship_type == "responsible" and not bool(policy.get("allow_responsible_binding", True)):
            raise RegistrationConflictError("responsible bindings are disabled by policy")
        asset = await self._ensure_asset_for_device(device)
        active_bindings = await self.repo.list_active_bindings_for_device(device.device_id)
        for existing in active_bindings:
            if existing.person_id == person.person_id and existing.relationship_type == relationship_type:
                await self._reconcile_open_agent_claims_for_binding(
                    device_id=device.device_id,
                    binding=existing,
                    reviewed_by=reviewed_by,
                    reason=reason,
                )
                await self.session.flush()
                return {
                    "binding": self._binding_payload(existing),
                    "asset": _asset_payload(asset),
                    "inventory_binding": self._inventory_registration_dict(
                        await self.session.get(DeviceInventoryBinding, device.device_id)
                    ),
                    "events": {"reused_existing_binding": True, "revoked_sessions": []},
                }

        active_primary = next((row for row in active_bindings if row.relationship_type == "primary_user"), None)
        active_responsible = next((row for row in active_bindings if row.relationship_type == "responsible"), None)
        if relationship_type == "primary_user" and active_primary and active_primary.person_id != person.person_id:
            if not replace_existing:
                raise RegistrationConflictError("active primary binding exists")
            await self._retire_binding(
                active_primary,
                status="transferred",
                reviewed_by=reviewed_by,
                reason=reason or "replaced by admin primary binding",
                event_type="binding_transferred",
            )
        if relationship_type == "responsible" and active_responsible and active_responsible.person_id != person.person_id:
            if not replace_existing:
                raise RegistrationConflictError("active responsible binding exists")
            await self._retire_binding(
                active_responsible,
                status="transferred",
                reviewed_by=reviewed_by,
                reason=reason or "responsible replaced by admin",
                event_type="binding_transferred",
            )

        pending_claim = await self.repo.find_pending_claim(
            device_id=device.device_id,
            person_id=person.person_id,
            source="agent_profile",
        )
        source_claim = pending_claim if pending_claim is not None and pending_claim.relationship_type == relationship_type else None

        _claim, binding = await self._create_admin_binding(
            device=device,
            asset=asset,
            person=person,
            relationship_type=relationship_type,
            reviewed_by=reviewed_by,
            reason=reason,
            source_claim=source_claim,
        )
        if relationship_type == "primary_user":
            await self.sync_asset_from_active_binding(binding)
            await self.sync_inventory_from_active_binding(
                binding,
                profile={"login": None, "department": None, "building": None, "floor": None, "room": None},
                reason="admin_binding_created",
            )
        await self._reconcile_open_agent_claims_for_binding(
            device_id=device.device_id,
            binding=binding,
            reviewed_by=reviewed_by,
            reason=reason,
        )
        await self.session.flush()
        return {
            "binding": self._binding_payload(binding),
            "asset": _asset_payload(await self.registry_repo.get_asset(asset.asset_id)),
            "inventory_binding": self._inventory_registration_dict(
                await self.session.get(DeviceInventoryBinding, device.device_id)
            ),
            "events": {
                "reused_existing_binding": False,
                **({"satisfied_pending_claim": source_claim.claim_id} if source_claim is not None else {}),
            },
        }

    async def transfer_owner(
        self,
        *,
        device_id: str,
        new_person_id: str,
        old_binding_action: str = "transferred",
        reviewed_by: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        if old_binding_action not in {"transferred", "revoked", "keep_as_shared"}:
            raise RegistrationValidationError("invalid old_binding_action")
        device = await self._require_device(device_id)
        person = await self.registry_repo.get_person(new_person_id)
        if person is None:
            raise RegistrationValidationError("person not found")
        asset = await self._ensure_asset_for_device(device)
        active_primary = await self.repo.get_active_primary_binding(device.device_id)
        if active_primary and active_primary.person_id == person.person_id:
            return {
                **self._operation_result(
                    operation="transfer_owner",
                    items=[{"id": active_primary.binding_id, "entity_type": "binding", "status": "success", "message": "already_active_primary"}],
                    events=[],
                    summary_extra={"reused": 1},
                ),
                "binding": self._binding_payload(active_primary),
                "asset": _asset_payload(asset),
                "legacy_events": {"reused_existing_binding": True, "revoked_sessions": []},
            }
        previous_primary_status = active_primary.status if active_primary else None
        if active_primary:
            if old_binding_action == "keep_as_shared":
                active_primary.relationship_type = "shared_user"
                active_primary.updated_at = datetime.now(timezone.utc)
                await self.repo.append_event(
                    event_type="binding_transferred",
                    binding_id=active_primary.binding_id,
                    device_id=active_primary.device_id,
                    person_id=active_primary.person_id,
                    actor_id=reviewed_by,
                    actor_role="admin",
                    payload={"old_binding_action": old_binding_action, "reason": reason},
                )
                revoked_sessions = await self._revoke_account_sessions_for_binding(
                    active_primary.binding_id,
                    revoked_by=reviewed_by,
                    reason=f"owner transfer: {reason or old_binding_action}",
                )
            else:
                revoked_sessions = await self._retire_binding(
                    active_primary,
                    status=old_binding_action,
                    reviewed_by=reviewed_by,
                    reason=reason or "owner transferred by admin",
                    event_type="binding_transferred" if old_binding_action == "transferred" else "binding_revoked",
                )
        else:
            revoked_sessions = []

        _claim, binding = await self._create_admin_binding(
            device=device,
            asset=asset,
            person=person,
            relationship_type="primary_user",
            reviewed_by=reviewed_by,
            reason=reason,
        )
        await self.sync_asset_from_active_binding(binding)
        await self.sync_inventory_from_active_binding(
            binding,
            profile={},
            reason="registration_transferred",
        )
        await self.repo.append_event(
            event_type="binding_transferred",
            binding_id=binding.binding_id,
            device_id=device.device_id,
            person_id=person.person_id,
            actor_id=reviewed_by,
            actor_role="admin",
            payload={
                "old_binding_id": active_primary.binding_id if active_primary else None,
                "old_binding_action": old_binding_action,
                "reason": reason,
                "revoked_session_ids": [row["session_id"] for row in revoked_sessions],
                "changes": [
                    {
                        "field": "primary_person_id",
                        "before": active_primary.person_id if active_primary else None,
                        "after": person.person_id,
                    },
                    {
                        "field": "old_binding_status",
                        "before": previous_primary_status,
                        "after": old_binding_action if active_primary and old_binding_action != "keep_as_shared" else None,
                    },
                    {
                        "field": "revoked_session_count",
                        "before": len(revoked_sessions),
                        "after": 0,
                    },
                ],
            },
        )
        await self.session.flush()
        operation_items = []
        if active_primary:
            operation_items.append(
                {
                    "id": active_primary.binding_id,
                    "entity_type": "binding",
                    "status": "success",
                    "message": old_binding_action,
                }
            )
        operation_items.extend(
            [
                {"id": binding.binding_id, "entity_type": "binding", "status": "success", "message": "new_primary"},
                {"id": asset.asset_id, "entity_type": "registry_asset", "status": "success"},
                {"id": device.device_id, "entity_type": "inventory_binding", "status": "success"},
            ]
        )
        operation_items.extend(
            {"id": row["session_id"], "entity_type": "account_session", "status": "success", "message": "revoked"}
            for row in revoked_sessions
        )
        return {
            **self._operation_result(
                operation="transfer_owner",
                items=operation_items,
                events=["binding_transferred"],
                summary_extra={"revoked_sessions": len(revoked_sessions)},
            ),
            "binding": self._binding_payload(binding),
            "asset": _asset_payload(await self.registry_repo.get_asset(asset.asset_id)),
            "inventory_binding": self._inventory_registration_dict(
                await self.session.get(DeviceInventoryBinding, device.device_id)
            ),
            "legacy_events": {"revoked_sessions": revoked_sessions},
        }

    async def preview_transfer_owner(
        self,
        *,
        device_id: str,
        new_person_id: str,
        old_binding_action: str = "transferred",
    ) -> dict[str, Any]:
        if old_binding_action not in {"transferred", "revoked", "keep_as_shared"}:
            raise RegistrationValidationError("invalid old_binding_action")
        device = await self._require_device(device_id)
        person = await self.registry_repo.get_person(new_person_id)
        if person is None:
            raise RegistrationValidationError("person not found")
        asset = await self.registry_repo.get_asset_by_device_id(device.device_id)
        active_primary = await self.repo.get_active_primary_binding(device.device_id)
        inventory = await self.session.get(DeviceInventoryBinding, device.device_id)

        changes: list[dict[str, Any]] = []
        warnings: list[str] = []
        sessions_to_revoke: list[Any] = []
        tickets_preserved = 0

        if active_primary and active_primary.person_id == person.person_id:
            warnings.append("new_person_already_active_primary")
        elif active_primary:
            after_status = "active" if old_binding_action == "keep_as_shared" else old_binding_action
            after_relationship = "shared_user" if old_binding_action == "keep_as_shared" else active_primary.relationship_type
            changes.append(
                {
                    "kind": "binding",
                    "action": "update",
                    "object_id": active_primary.binding_id,
                    "before": {
                        "person_id": active_primary.person_id,
                        "relationship_type": active_primary.relationship_type,
                        "status": active_primary.status,
                    },
                    "after": {
                        "person_id": active_primary.person_id,
                        "relationship_type": after_relationship,
                        "status": after_status,
                        "valid_to": None if old_binding_action == "keep_as_shared" else "now",
                    },
                    "severity": "destructive" if old_binding_action != "keep_as_shared" else "warning",
                }
            )
            session_rows = (
                await self.session.execute(
                    select(DeviceAccountSession).where(
                        or_(
                            DeviceAccountSession.binding_id == active_primary.binding_id,
                            DeviceAccountSession.base_binding_id == active_primary.binding_id,
                        ),
                        DeviceAccountSession.verification_status == "verified",
                    )
                )
            ).scalars().all()
            sessions_to_revoke = list({row.session_id: row for row in session_rows}.values())
            for row in sessions_to_revoke:
                changes.append(
                    {
                        "kind": "account_session",
                        "action": "revoke",
                        "object_id": row.session_id,
                        "before": {"verification_status": row.verification_status, "person_id": row.person_id},
                        "after": {"verification_status": "revoked", "revoked_at": "now"},
                        "severity": "destructive",
                    }
                )
            ticket_filters = [
                Ticket.requester_person_id == active_primary.person_id,
                Ticket.requester_binding_id == active_primary.binding_id,
            ]
            if sessions_to_revoke:
                ticket_filters.append(Ticket.requester_account_session_id.in_([row.session_id for row in sessions_to_revoke]))
            tickets_preserved = (
                await self.session.execute(select(Ticket).where(or_(*ticket_filters)))
            ).scalars().unique().all()
            tickets_preserved = len(tickets_preserved)

        if not (active_primary and active_primary.person_id == person.person_id):
            changes.append(
                {
                    "kind": "binding",
                    "action": "create",
                    "object_id": None,
                    "before": None,
                    "after": {
                        "device_id": device.device_id,
                        "person_id": person.person_id,
                        "relationship_type": "primary_user",
                        "status": "active",
                        "source": "admin_manual",
                    },
                    "severity": "info",
                }
            )
            changes.append(
                {
                    "kind": "registry_asset",
                    "action": "update" if asset else "create",
                    "object_id": asset.asset_id if asset else None,
                    "before": {"assigned_person_id": asset.assigned_person_id if asset else None},
                    "after": {"assigned_person_id": person.person_id},
                    "severity": "warning",
                }
            )
            changes.append(
                {
                    "kind": "inventory_binding",
                    "action": "update" if inventory else "create",
                    "object_id": device.device_id,
                    "before": {
                        "person_id": inventory.person_id if inventory else None,
                        "source_binding_id": inventory.source_binding_id if inventory else None,
                        "registration_status": inventory.registration_status if inventory else None,
                    },
                    "after": {
                        "person_id": person.person_id,
                        "source_binding_id": "new_binding",
                        "registration_status": "admin_confirmed",
                    },
                    "severity": "warning",
                }
            )

        return {
            "operation": "transfer_owner",
            "dry_run": True,
            "requires_confirmation": True,
            "device_id": device.device_id,
            "new_person_id": person.person_id,
            "old_binding_id": active_primary.binding_id if active_primary else None,
            "old_person_id": active_primary.person_id if active_primary else None,
            "old_binding_action": old_binding_action,
            "counts": {
                "bindings_to_update": 1 if active_primary and active_primary.person_id != person.person_id else 0,
                "bindings_to_create": 0 if active_primary and active_primary.person_id == person.person_id else 1,
                "sessions_to_revoke": len(sessions_to_revoke),
                "tickets_preserved": tickets_preserved,
            },
            "ticket_policy": {
                "requester_person_id": "preserve_existing_requester",
                "requester_binding_id": "preserve_existing_binding_reference",
                "requester_account_session_id": "preserve_existing_session_reference",
            },
            "changes": changes,
            "warnings": warnings,
            "blockers": [],
        }

    async def add_shared_user(
        self,
        *,
        device_id: str,
        person_id: str,
        reviewed_by: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return await self.bind_person_to_device(
            device_id=device_id,
            person_id=person_id,
            relationship_type="shared_user",
            replace_existing=False,
            reviewed_by=reviewed_by,
            reason=reason,
        )

    async def assign_responsible(
        self,
        *,
        device_id: str,
        person_id: str,
        replace_existing: bool = True,
        reviewed_by: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return await self.bind_person_to_device(
            device_id=device_id,
            person_id=person_id,
            relationship_type="responsible",
            replace_existing=replace_existing,
            reviewed_by=reviewed_by,
            reason=reason,
        )

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
                identity = await self.repo.find_identity(provider, str(identifier))
                person = await self.registry_repo.get_person(identity.person_id) if identity else None
                if person:
                    _raise_if_person_inactive(person)
                    if not identity.verified:
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
        person = await self.registry_repo.upsert_person_from_profile(
            profile_key=profile_key,
            display_name=display_name or full_name,
            full_name=full_name,
            phone=profile.get("phone"),
            email=profile.get("email"),
            department_id=department_id,
            location_id=location_id,
            metadata={"profile": profile},
        )
        _raise_if_person_inactive(person)
        return person

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
        if (
            str(actor_role or "").strip().lower() == "agent"
            and actor_id
            and bool((profile or {}).get("user_confirmed"))
        ):
            raise RegistrationValidationError("agent cannot assert user_confirmed")
        profile_snapshot = _sanitize_profile(profile)
        display_name = _clean(display_name, max_length=300) or profile_snapshot.get("display_name")
        relationship_type = str(profile_snapshot.get("relationship_type") or "primary_user").strip()
        if profile_snapshot.get("is_shared_device") and relationship_type == "primary_user":
            relationship_type = "shared_user"
        if relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
            raise ValueError("invalid relationship_type")
        policy = await self._registration_policy()

        department_id = await self._resolve_registration_department(profile_snapshot, policy)
        location_id = await self._resolve_registration_location(profile_snapshot, policy)
        person = await self._find_or_create_person(
            requester_id=requester_id,
            display_name=display_name,
            profile=profile_snapshot,
            department_id=department_id,
            location_id=location_id,
        )
        _raise_if_person_inactive(person)
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
        active_bindings = await self.repo.list_active_bindings_for_device(device_id)
        existing_binding = next(
            (
                row
                for row in active_bindings
                if row.person_id == person.person_id and row.relationship_type == relationship_type
            ),
            None,
        )
        if existing_binding is not None:
            await self._reconcile_open_agent_claims_for_binding(
                device_id=device_id,
                binding=existing_binding,
                reviewed_by=actor_id or requester_id,
                reason="agent profile matched existing binding",
            )
            source_claim = await self.repo.get_claim(existing_binding.source_claim_id) if existing_binding.source_claim_id else None
            if source_claim is None:
                source_claim = await self.repo.create_claim(
                    device_id=device_id,
                    asset_id=asset.asset_id,
                    person_id=person.person_id,
                    claim_type="self_reported",
                    status="approved",
                    relationship_type=relationship_type,
                    profile_snapshot=profile_snapshot,
                    device_snapshot={
                        "hostname": getattr(device, "hostname", None) if device else asset.hostname,
                        "os": getattr(device, "os", None) if device else profile_snapshot.get("os"),
                        "agent_version": getattr(device, "agent_version", None) if device else profile_snapshot.get("agent_version"),
                    },
                    confidence=Decimal("1.00"),
                    source="agent_profile",
                    source_ref=requester_id,
                    submitted_at=datetime.now(timezone.utc),
                    user_confirmed_at=datetime.now(timezone.utc),
                    reviewed_by=actor_id or requester_id,
                    reviewed_at=datetime.now(timezone.utc),
                    metadata_json={"reason": "matched_existing_binding"},
                )
            await self.session.flush()
            return await self._build_approved_payload(source_claim, existing_binding)
        confidence = _compute_confidence(profile_snapshot, requester_id)
        conflict_reason = await self.detect_conflicts(device_id, person.person_id, relationship_type)
        if device is not None and getattr(device, "deleted_at", None) is not None:
            conflict_reason = "device_archived"

        user_confirmed = bool(profile_snapshot.get("user_confirmed") or (profile or {}).get("user_confirmed"))
        if conflict_reason:
            status = "conflict"
        elif user_confirmed:
            status = "pending_admin_review" if policy["require_admin_confirmation"] else "user_confirmed"
        else:
            status = "pending_user_confirmation" if policy["require_user_confirmation"] else "pending_admin_review"

        claim = await self.repo.find_pending_claim(device_id=device_id, person_id=None, source="agent_profile")
        now = datetime.now(timezone.utc)
        if claim is not None and claim.person_id != person.person_id and not conflict_reason:
            conflict_reason = "open_claim_exists_for_device"
            status = "conflict"
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
            claim.source_ref = requester_id
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

        if (
            not conflict_reason
            and user_confirmed
            and policy["auto_approve_first_binding"]
            and not policy["require_admin_confirmation"]
        ):
            return await self.approve_claim(
                claim.claim_id,
                reviewed_by=actor_id or requester_id or "system",
                actor_role="system",
            )

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

    async def confirm_claim_by_user(
        self,
        claim_id: str,
        actor_id: str | None = None,
        actor_role: str | None = "user",
    ) -> dict[str, Any]:
        claim = await self.repo.get_claim(claim_id)
        if claim is None:
            raise ValueError("registration claim not found")
        person_for_claim = await self.registry_repo.get_person(claim.person_id)
        _raise_if_person_inactive(person_for_claim)
        if claim.status in {"approved", "rejected", "superseded"}:
            asset = await self.registry_repo.get_asset(claim.asset_id)
            return self._build_submit_payload(person=person_for_claim, asset=asset, claim=claim)
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
            actor_role=actor_role or "user",
            payload={"status": new_status},
        )
        await self.session.flush()
        asset = await self.registry_repo.get_asset(claim.asset_id)
        policy = await self._registration_policy()
        if not conflict_reason and policy["auto_approve_first_binding"] and not policy["require_admin_confirmation"]:
            return await self.approve_claim(claim.claim_id, reviewed_by=actor_id or "system", actor_role="system")
        return self._build_submit_payload(person=person_for_claim, asset=asset, claim=claim)

    def _normalized_actor_identities(self, actor_id: str | None) -> dict[str, set[str]]:
        raw = str(actor_id or "").strip()
        values: dict[str, set[str]] = {"ui_login": set(), "windows_login": set(), "email": set()}
        if not raw:
            return values
        for provider in values:
            normalized = normalize_identifier(provider, raw)
            if normalized:
                values[provider].add(normalized)
        if "\\" in raw:
            local = raw.split("\\", 1)[1]
            normalized = normalize_identifier("ui_login", local)
            if normalized:
                values["ui_login"].add(normalized)
        if "@" in raw:
            local = raw.split("@", 1)[0]
            normalized = normalize_identifier("ui_login", local)
            if normalized:
                values["ui_login"].add(normalized)
        return values

    def _identity_matches_actor(self, *, provider: str, identifier: str | None, actor_values: dict[str, set[str]]) -> bool:
        provider_key = str(provider or "").strip().lower()
        if provider_key in {"agent_profile", "manual"}:
            provider_key = "ui_login"
        if provider_key == "ad":
            provider_key = "windows_login"
        if provider_key == "phone":
            return False
        normalized = normalize_identifier(provider_key, identifier)
        if not normalized:
            return False
        if normalized in actor_values.get(provider_key, set()):
            return True
        if provider_key == "email":
            local = normalized.split("@", 1)[0]
            return local in actor_values.get("ui_login", set())
        return False

    async def can_confirm_claim_for_actor(self, claim: Any, auth_context: Any) -> bool:
        actor_role = str(getattr(auth_context, "actor_role", "") or "")
        actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
        if actor_role in {"admin", "support"}:
            return True
        if actor_role == "agent":
            return claim.device_id == actor_id
        if actor_role != "user" or not actor_id:
            return False

        actor_values = self._normalized_actor_identities(actor_id)
        profile = claim.profile_snapshot or {}
        claim_identity_candidates = [
            ("ui_login", claim.source_ref),
            ("ui_login", profile.get("requester_id")),
            ("ui_login", profile.get("login")),
            ("windows_login", profile.get("login")),
            ("windows_login", profile.get("current_user")),
            ("email", profile.get("email")),
        ]
        if any(
            self._identity_matches_actor(provider=provider, identifier=identifier, actor_values=actor_values)
            for provider, identifier in claim_identity_candidates
        ):
            return True

        for identity in await self.repo.list_identities_for_person(claim.person_id):
            if self._identity_matches_actor(
                provider=identity.provider,
                identifier=identity.normalized_identifier,
                actor_values=actor_values,
            ):
                return True
        return False

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
        person_for_claim = await self.registry_repo.get_person(claim.person_id)
        _raise_if_person_inactive(person_for_claim)
        existing_for_claim = None
        if claim.status == "approved":
            rows = await self.repo.list_active_bindings_for_device(claim.device_id)
            existing_for_claim = next((row for row in rows if row.source_claim_id == claim.claim_id), None)
            if existing_for_claim:
                await self._apply_claim_profile_to_person(claim)
                await self.sync_asset_from_active_binding(existing_for_claim)
                await self.sync_inventory_from_active_binding(existing_for_claim, profile=claim.profile_snapshot or {})
                await self._revoke_registration_pending_sessions_for_claim(
                    claim.claim_id,
                    revoked_by=reviewed_by,
                    reason="registration claim approved",
                )
                return await self._build_approved_payload(claim, existing_for_claim)
        if claim.status in {"rejected", "superseded", "expired"}:
            raise ValueError("claim cannot be approved")
        policy = await self._registration_policy()
        if (
            policy["require_user_confirmation"]
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
            await self._apply_claim_profile_to_person(claim)
            await self.sync_asset_from_active_binding(active_primary)
            await self.sync_inventory_from_active_binding(active_primary, profile=claim.profile_snapshot or {})
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
            await self._revoke_registration_pending_sessions_for_claim(
                claim.claim_id,
                revoked_by=reviewed_by,
                reason="registration claim approved",
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
        await self._apply_claim_profile_to_person(claim)
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
        await self._revoke_registration_pending_sessions_for_claim(
            claim.claim_id,
            revoked_by=reviewed_by,
            reason="registration claim approved",
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
        revoked_sessions = await self._revoke_account_sessions_for_binding(
            binding.binding_id,
            revoked_by=revoked_by,
            reason=f"binding revoked: {reason or 'admin revoke'}",
        )
        canceled_login_requests = await self._cancel_account_login_requests_for_binding(
            binding.binding_id,
            canceled_by=revoked_by,
            reason=f"base binding changed: {reason or 'admin revoke'}",
        )
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
            payload={
                "reason": reason,
                "revoked_session_ids": [row["session_id"] for row in revoked_sessions],
                "canceled_login_request_ids": [row["request_id"] for row in canceled_login_requests],
            },
        )
        if revoked_sessions:
            await self.repo.append_event(
                event_type="account_sessions_revoked_due_to_revoke",
                binding_id=binding.binding_id,
                device_id=binding.device_id,
                person_id=binding.person_id,
                actor_id=revoked_by,
                actor_role="admin",
                payload={"revoked_session_ids": [row["session_id"] for row in revoked_sessions]},
            )
        await self.session.flush()
        return {
            "binding": {"binding_id": binding.binding_id, "status": binding.status},
            "events": {"revoked_sessions": revoked_sessions, "canceled_login_requests": canceled_login_requests},
        }

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
        if person and not is_person_active(person):
            return "person_inactive"
        primary_count = sum(
            1
            for row in await self.repo.list_bindings_for_person(person_id, active_only=True)
            if row.relationship_type == "primary_user"
        )
        policy = await self._registration_policy()
        if relationship_type == "primary_user" and primary_count >= int(policy["max_primary_devices_per_person"]):
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
