from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RegistryAdminPolicy


REGISTRY_POLICY_KEY = "registry_management"

DEFAULT_REGISTRY_POLICIES: dict[str, dict[str, Any]] = {
    "registration": {
        "require_user_confirmation": True,
        "require_admin_confirmation": True,
        "auto_approve_first_binding": False,
        "allow_shared_devices": True,
        "allow_responsible_binding": True,
        "max_primary_devices_per_person": 3,
        "stale_after_days": 90,
        "department_mode": "allow_pending_request",
        "location_mode": "allow_pending_request",
    },
    "account_sessions": {
        "confirmed_binding_ttl_hours": None,
        "verified_other_account_ttl_hours": 24,
        "registration_pending_ttl_hours": 72,
        "allow_other_account_login": True,
        "other_account_requires_reason": True,
        "other_account_requires_admin_approval": True,
        "allow_other_account_on_shared_or_responsible": True,
    },
    "ticket_visibility": {
        "owner_can_see_historical_tickets": True,
        "other_account_only_own_session_tickets": True,
    },
    "diagnostic_target": {
        "allow_single_active_binding_fallback": False,
    },
}

REGISTRY_POLICY_VALIDATION: dict[str, dict[str, Any]] = {
    "registration.max_primary_devices_per_person": {"type": "integer", "minimum": 1, "maximum": 50, "nullable": False},
    "registration.stale_after_days": {"type": "integer", "minimum": 1, "maximum": 3650, "nullable": False},
    "registration.department_mode": {"type": "enum", "values": ["allow_pending_request", "optional", "required_existing"]},
    "registration.location_mode": {"type": "enum", "values": ["allow_pending_request", "optional", "required_existing"]},
    "account_sessions.confirmed_binding_ttl_hours": {"type": "integer", "minimum": 1, "maximum": 87600, "nullable": True},
    "account_sessions.verified_other_account_ttl_hours": {"type": "integer", "minimum": 1, "maximum": 8760, "nullable": False},
    "account_sessions.registration_pending_ttl_hours": {"type": "integer", "minimum": 1, "maximum": 8760, "nullable": False},
    "diagnostic_target.allow_single_active_binding_fallback": {"type": "boolean", "nullable": False},
}

REGISTRY_POLICY_REQUIRES_RESTART_FIELDS: set[str] = set()
REGISTRATION_ENTITY_MODES = {"optional", "required_existing", "allow_pending_request"}

DANGEROUS_POLICY_WARNINGS: dict[str, dict[str, str]] = {
    "registration.auto_approve_first_binding": {
        "severity": "warning",
        "message": "Это позволит автоматически подтверждать первую регистрацию устройства. Рекомендуется только для тестового стенда.",
    }
}


def _deep_merge_defaults(value: dict[str, Any] | None) -> dict[str, Any]:
    merged = {section: dict(defaults) for section, defaults in DEFAULT_REGISTRY_POLICIES.items()}
    for section, section_value in (value or {}).items():
        if section in merged and isinstance(section_value, dict):
            merged[section].update(section_value)
    return merged


def _validate_bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field} must be boolean")


def _validate_int(value: Any, *, field: str, minimum: int, maximum: int, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if number < minimum or number > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return number


def _validate_mode(value: Any, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if text not in REGISTRATION_ENTITY_MODES:
        raise ValueError(f"{field} must be one of {', '.join(sorted(REGISTRATION_ENTITY_MODES))}")
    return text


def validate_registry_policies(value: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge_defaults(value)
    registration = merged["registration"]
    account_sessions = merged["account_sessions"]
    ticket_visibility = merged["ticket_visibility"]
    diagnostic_target = merged["diagnostic_target"]

    for field in (
        "require_user_confirmation",
        "require_admin_confirmation",
        "auto_approve_first_binding",
        "allow_shared_devices",
        "allow_responsible_binding",
    ):
        registration[field] = _validate_bool(registration.get(field), field=f"registration.{field}")
    registration["max_primary_devices_per_person"] = _validate_int(
        registration.get("max_primary_devices_per_person"),
        field="registration.max_primary_devices_per_person",
        minimum=1,
        maximum=50,
    )
    registration["stale_after_days"] = _validate_int(
        registration.get("stale_after_days"),
        field="registration.stale_after_days",
        minimum=1,
        maximum=3650,
    )
    registration["department_mode"] = _validate_mode(
        registration.get("department_mode"),
        field="registration.department_mode",
    )
    registration["location_mode"] = _validate_mode(
        registration.get("location_mode"),
        field="registration.location_mode",
    )

    account_sessions["confirmed_binding_ttl_hours"] = _validate_int(
        account_sessions.get("confirmed_binding_ttl_hours"),
        field="account_sessions.confirmed_binding_ttl_hours",
        minimum=1,
        maximum=87600,
        nullable=True,
    )
    account_sessions["verified_other_account_ttl_hours"] = _validate_int(
        account_sessions.get("verified_other_account_ttl_hours"),
        field="account_sessions.verified_other_account_ttl_hours",
        minimum=1,
        maximum=8760,
    )
    account_sessions["registration_pending_ttl_hours"] = _validate_int(
        account_sessions.get("registration_pending_ttl_hours"),
        field="account_sessions.registration_pending_ttl_hours",
        minimum=1,
        maximum=8760,
    )
    for field in (
        "allow_other_account_login",
        "other_account_requires_reason",
        "other_account_requires_admin_approval",
        "allow_other_account_on_shared_or_responsible",
    ):
        account_sessions[field] = _validate_bool(account_sessions.get(field), field=f"account_sessions.{field}")

    for field in ("owner_can_see_historical_tickets", "other_account_only_own_session_tickets"):
        ticket_visibility[field] = _validate_bool(ticket_visibility.get(field), field=f"ticket_visibility.{field}")
    diagnostic_target["allow_single_active_binding_fallback"] = _validate_bool(
        diagnostic_target.get("allow_single_active_binding_fallback"),
        field="diagnostic_target.allow_single_active_binding_fallback",
    )
    return merged


def _iter_policy_paths(value: dict[str, Any]):
    for section, fields in value.items():
        if not isinstance(fields, dict):
            continue
        for field, field_value in fields.items():
            yield f"{section}.{field}", field_value


def _changed_from_defaults(effective: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changed: dict[str, dict[str, Any]] = {}
    defaults = {section: dict(fields) for section, fields in DEFAULT_REGISTRY_POLICIES.items()}
    for path, effective_value in _iter_policy_paths(effective):
        section, field = path.split(".", 1)
        default_value = defaults.get(section, {}).get(field)
        if effective_value != default_value:
            changed[path] = {"default": default_value, "effective": effective_value}
    return changed


def _policy_warnings(effective: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if effective["registration"]["auto_approve_first_binding"]:
        warning = DANGEROUS_POLICY_WARNINGS["registration.auto_approve_first_binding"]
        warnings.append(
            {
                "field": "registration.auto_approve_first_binding",
                "severity": warning["severity"],
                "message": warning["message"],
            }
        )
    return warnings


def build_registry_policy_response(value: dict[str, Any] | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    effective = validate_registry_policies(value or {})
    changed = _changed_from_defaults(effective)
    restart_fields = sorted(path for path in changed if path in REGISTRY_POLICY_REQUIRES_RESTART_FIELDS)
    return {
        "defaults": deepcopy(DEFAULT_REGISTRY_POLICIES),
        "effective": effective,
        "changed_from_defaults": changed,
        "warnings": _policy_warnings(effective),
        "validation": deepcopy(REGISTRY_POLICY_VALIDATION),
        "requires_restart": bool(restart_fields),
        "restart_required_fields": restart_fields,
        "dry_run": dry_run,
    }


class RegistryPolicyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_policies(self) -> dict[str, Any]:
        row = await self.session.get(RegistryAdminPolicy, REGISTRY_POLICY_KEY)
        return validate_registry_policies(row.config_json if row else {})

    async def update_policies(self, value: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        config = validate_registry_policies(value)
        row = await self.session.get(RegistryAdminPolicy, REGISTRY_POLICY_KEY)
        now = datetime.now(timezone.utc)
        if row is None:
            row = RegistryAdminPolicy(
                policy_key=REGISTRY_POLICY_KEY,
                config_json=config,
                updated_by=actor_id,
                updated_at=now,
            )
            self.session.add(row)
        else:
            row.config_json = config
            row.updated_by = actor_id
            row.updated_at = now
        await self.session.flush()
        return config

    async def reset_to_defaults(self, *, actor_id: str | None = None) -> dict[str, Any]:
        return await self.update_policies({}, actor_id=actor_id)
