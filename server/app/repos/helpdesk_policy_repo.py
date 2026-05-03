"""Repository for standalone helpdesk request-template and policy registries."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any
import zoneinfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ApprovalPolicy,
    ClosurePolicy,
    DiagnosticPolicy,
    FormCondition,
    FormField,
    FormSchema,
    HelpdeskPolicyAudit,
    NotificationPolicy,
    OlaPolicy,
    PriorityPolicy,
    ReportingPolicy,
    RequestTemplate,
    RoutingPolicy,
    SlaPolicy,
    SmartView,
    TicketType,
    VisibilityPolicy,
)
from tickets.form_catalog import next_form_pack_version, validate_form_pack_schema
from utils.versioning import version_key


POLICY_MODELS = {
    "priority": PriorityPolicy,
    "sla": SlaPolicy,
    "ola": OlaPolicy,
    "routing": RoutingPolicy,
    "approval": ApprovalPolicy,
    "closure": ClosurePolicy,
    "diagnostic": DiagnosticPolicy,
    "notification": NotificationPolicy,
    "visibility": VisibilityPolicy,
    "reporting": ReportingPolicy,
}

POLICY_TABLE_NAMES = {
    "priority": "priority_policies",
    "sla": "sla_policies",
    "ola": "ola_policies",
    "routing": "routing_policies",
    "approval": "approval_policies",
    "closure": "closure_policies",
    "diagnostic": "diagnostic_policies",
    "notification": "notification_policies",
    "visibility": "visibility_policies",
    "reporting": "reporting_policies",
}

REQUEST_TEMPLATE_POLICY_CODE_FIELDS = {
    "priority": "priority_policy_code",
    "routing": "routing_policy_code",
    "sla": "sla_policy_code",
    "ola": "ola_policy_code",
    "approval": "approval_policy_code",
    "diagnostic": "diagnostic_policy_code",
    "closure": "closure_policy_code",
    "visibility": "visibility_policy_code",
    "notification": "notification_policy_code",
    "reporting": "reporting_policy_code",
}

SCOPE_RANK = {
    "system": 0,
    "ticket_type": 1,
    "category": 2,
    "request_template": 3,
}

_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$")
_APPROVAL_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)?\s*$", re.IGNORECASE)
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_APPROVAL_SOURCE_TYPES = {
    "explicit_user",
    "user",
    "specific_user",
    "explicit_users",
    "users",
    "group_members",
    "group",
    "approval_group",
    "security_role",
    "form_field",
    "requester_manager",
    "service_owner",
    "queue_lead",
}
_APPROVAL_MODES = {"any_one", "all", "sequential"}


def normalize_policy_kind(raw_kind: Any) -> str:
    kind = str(raw_kind or "").strip().lower()
    kind = kind.removesuffix("_policy").removesuffix("_policies")
    if kind not in POLICY_MODELS:
        raise ValueError(f"unknown policy kind: {raw_kind}")
    return kind


def normalize_template_code(raw_value: Any) -> str:
    code = str(raw_value or "").strip().lower().replace(" ", "_")
    cleaned = "".join(ch for ch in code if ch.isalnum() or ch in {"_", "-", "."})
    return cleaned.strip("_.-")


def _normalize_positive_int(raw_value: Any, *, field_name: str) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"routing policy {field_name} must be integer") from exc
    if value <= 0:
        raise ValueError(f"routing policy {field_name} must be positive integer")
    return value


def _normalize_non_negative_int(raw_value: Any, *, field_name: str) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"routing policy {field_name} must be integer") from exc
    if value < 0:
        raise ValueError(f"routing policy {field_name} must be non-negative integer")
    return value


def _validate_routing_action_targets(actions: Any, *, field_name: str) -> None:
    if actions in (None, ""):
        return
    if not isinstance(actions, dict):
        raise ValueError(f"routing policy {field_name} must be an object")
    for key in ("queue_id", "target_queue_id"):
        if key in actions:
            _normalize_positive_int(actions.get(key), field_name=f"{field_name}.{key}")


def _validate_routing_policy_config(config: dict[str, Any]) -> None:
    _normalize_positive_int(config.get("default_queue_id"), field_name="default_queue_id")
    _normalize_non_negative_int(config.get("max_auto_reroutes"), field_name="max_auto_reroutes")
    _validate_routing_action_targets(config.get("fallback"), field_name="fallback")

    rules = config.get("rules")
    if rules in (None, ""):
        return
    if not isinstance(rules, list):
        raise ValueError("routing policy rules must be an array")
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"routing policy rules[{index}] must be an object")
        actions = rule.get("then") if "then" in rule else rule
        _validate_routing_action_targets(actions, field_name=f"rules[{index}].then")


def _duration_to_minutes(raw_value: Any, *, policy_name: str, field_name: str, allow_zero: bool = False) -> float:
    if raw_value in (None, "") or isinstance(raw_value, bool):
        raise ValueError(f"{policy_name} {field_name} must be duration")
    if isinstance(raw_value, (int, float)):
        minutes = float(raw_value)
    else:
        match = _DURATION_RE.match(str(raw_value).strip())
        if not match:
            raise ValueError(f"{policy_name} {field_name} must be duration")
        amount = float(match.group(1))
        unit = match.group(2).strip().lower()
        if unit in {"", "m", "min", "mins", "minute", "minutes"}:
            multiplier = 1
        elif unit in {"h", "hr", "hour", "hours"}:
            multiplier = 60
        elif unit in {"d", "day", "days"}:
            multiplier = 24 * 60
        else:
            raise ValueError(f"{policy_name} {field_name} has unsupported duration unit")
        minutes = amount * multiplier
    if minutes < 0 or (minutes == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{policy_name} {field_name} must be {qualifier} duration")
    return minutes


def _validate_policy_duration_map(
    target_map: Any,
    *,
    policy_name: str,
    field_name: str,
    allow_zero: bool = False,
) -> None:
    if target_map in (None, ""):
        return
    if not isinstance(target_map, dict):
        raise ValueError(f"{policy_name} {field_name} must be an object")
    for priority, raw_duration in target_map.items():
        priority_key = str(priority or "").strip()
        if not priority_key:
            raise ValueError(f"{policy_name} {field_name} priority key is required")
        _duration_to_minutes(
            raw_duration,
            policy_name=policy_name,
            field_name=f"{field_name}.{priority_key}",
            allow_zero=allow_zero,
        )


def _parse_policy_time(raw_value: Any, *, policy_name: str, field_name: str) -> int:
    if not isinstance(raw_value, str) or not _TIME_RE.match(raw_value.strip()):
        raise ValueError(f"{policy_name} {field_name} must be HH:MM")
    hours, minutes = raw_value.strip().split(":", 1)
    return int(hours) * 60 + int(minutes)


def _validate_calendar_slots(slots: Any, *, policy_name: str, field_name: str) -> None:
    if slots in (None, ""):
        return
    if not isinstance(slots, list):
        raise ValueError(f"{policy_name} {field_name} must be an array")
    for index, slot in enumerate(slots):
        slot_name = f"{field_name}[{index}]"
        if not isinstance(slot, dict):
            raise ValueError(f"{policy_name} {slot_name} must be an object")
        day_raw = slot.get("day")
        if isinstance(day_raw, bool):
            raise ValueError(f"{policy_name} {slot_name}.day must be integer 0-6")
        try:
            day = int(day_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{policy_name} {slot_name}.day must be integer 0-6") from exc
        if day < 0 or day > 6:
            raise ValueError(f"{policy_name} {slot_name}.day must be integer 0-6")
        start_minutes = _parse_policy_time(slot.get("start"), policy_name=policy_name, field_name=f"{slot_name}.start")
        end_minutes = _parse_policy_time(slot.get("end"), policy_name=policy_name, field_name=f"{slot_name}.end")
        if start_minutes >= end_minutes:
            raise ValueError(f"{policy_name} {slot_name}.start must be before end")


def _validate_calendar_config(calendar: Any, *, policy_name: str, field_name: str = "calendar") -> None:
    if calendar in (None, ""):
        return
    if not isinstance(calendar, dict):
        raise ValueError(f"{policy_name} {field_name} must be an object")
    timezone_name = calendar.get("timezone")
    if timezone_name not in (None, ""):
        try:
            zoneinfo.ZoneInfo(str(timezone_name))
        except Exception as exc:
            raise ValueError(f"{policy_name} {field_name}.timezone is unknown") from exc
    _validate_calendar_slots(
        calendar.get("weekly_hours_json") if "weekly_hours_json" in calendar else calendar.get("weekly_hours"),
        policy_name=policy_name,
        field_name=f"{field_name}.weekly_hours_json",
    )
    holidays = calendar.get("holidays_json") if "holidays_json" in calendar else calendar.get("holidays")
    if holidays in (None, ""):
        return
    if not isinstance(holidays, list):
        raise ValueError(f"{policy_name} {field_name}.holidays_json must be an array")
    for index, item in enumerate(holidays):
        if not isinstance(item, str):
            raise ValueError(f"{policy_name} {field_name}.holidays_json[{index}] must be YYYY-MM-DD")
        try:
            datetime.strptime(item, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"{policy_name} {field_name}.holidays_json[{index}] must be YYYY-MM-DD") from exc


def _validate_sla_policy_config(config: dict[str, Any]) -> None:
    targets = config.get("targets")
    if targets not in (None, "") and not isinstance(targets, dict):
        raise ValueError("sla policy targets must be an object")
    target_source = targets if isinstance(targets, dict) else config
    for key in ("first_response", "first_response_targets", "resolution", "resolution_targets"):
        if key in target_source:
            _validate_policy_duration_map(
                target_source.get(key),
                policy_name="sla policy",
                field_name=f"targets.{key}",
            )

    _validate_calendar_config(config.get("calendar"), policy_name="sla policy")
    business_hours = config.get("business_hours_json") if "business_hours_json" in config else config.get("business_hours")
    if isinstance(business_hours, dict):
        _validate_calendar_config(business_hours, policy_name="sla policy", field_name="business_hours_json")
    else:
        _validate_calendar_slots(business_hours, policy_name="sla policy", field_name="business_hours_json")


def _validate_ola_policy_config(config: dict[str, Any]) -> None:
    targets = config.get("targets")
    if targets not in (None, "") and not isinstance(targets, dict):
        raise ValueError("ola policy targets must be an object")
    target_source = targets if isinstance(targets, dict) else config
    for key in ("ack", "processing"):
        if key in target_source:
            _validate_policy_duration_map(
                target_source.get(key),
                policy_name="ola policy",
                field_name=f"targets.{key}",
                allow_zero=True,
            )


def _validate_approval_duration(raw_value: Any, *, field_name: str) -> None:
    if raw_value in (None, ""):
        return
    if isinstance(raw_value, bool):
        raise ValueError(f"approval policy {field_name} must be non-negative duration")
    if isinstance(raw_value, (int, float)):
        if raw_value < 0:
            raise ValueError(f"approval policy {field_name} must be non-negative duration")
        return
    match = _APPROVAL_DURATION_RE.match(str(raw_value).strip())
    if not match:
        raise ValueError(f"approval policy {field_name} must be non-negative duration")


def _validate_approval_source(source: Any, *, field_name: str) -> None:
    if source in (None, ""):
        return
    if isinstance(source, str):
        source_type = source.strip()
        if source_type and source_type not in _APPROVAL_SOURCE_TYPES:
            raise ValueError(f"approval policy {field_name}.type is unsupported")
        return
    if not isinstance(source, dict):
        raise ValueError(f"approval policy {field_name} must be an object")
    source_type = str(source.get("type") or source.get("source") or "").strip()
    if not source_type:
        return
    if source_type not in _APPROVAL_SOURCE_TYPES:
        raise ValueError(f"approval policy {field_name}.type is unsupported")
    if source_type == "form_field" and not str(source.get("field") or source.get("field_key") or "").strip():
        raise ValueError(f"approval policy {field_name}.field is required")
    if source_type in {"group", "approval_group"} and not str(
        source.get("group_id") or source.get("id") or source.get("code") or ""
    ).strip():
        raise ValueError(f"approval policy {field_name}.group_id is required")
    if "fallback" in source:
        _validate_approval_source(source.get("fallback"), field_name=f"{field_name}.fallback")


def _validate_approval_policy_config(config: dict[str, Any]) -> None:
    mode = str(config.get("approval_mode") or config.get("mode") or "").strip().lower()
    if mode and mode not in _APPROVAL_MODES:
        raise ValueError("approval policy approval_mode is unsupported")
    _validate_approval_source(config.get("approver_source") or config.get("approvers"), field_name="approver_source")
    timeout = config.get("timeout")
    if timeout in (None, ""):
        return
    if not isinstance(timeout, dict):
        raise ValueError("approval policy timeout must be an object")
    for key in ("reminder_after", "escalate_after", "due_in"):
        _validate_approval_duration(timeout.get(key), field_name=f"timeout.{key}")


def _validate_visibility_path(raw_path: Any, *, policy_name: str, field_name: str) -> None:
    path = str(raw_path or "").strip()
    if not path:
        raise ValueError(f"{policy_name} {field_name} contains empty path")
    if path.startswith(".") or path.endswith(".") or ".." in path:
        raise ValueError(f"{policy_name} {field_name} contains invalid path")
    for part in path.split("."):
        if not part or not all(ch.isalnum() or ch in {"_", "-"} for ch in part):
            raise ValueError(f"{policy_name} {field_name} contains invalid path")


def _validate_visibility_path_list(value: Any, *, field_name: str) -> None:
    if value in (None, ""):
        return
    if not isinstance(value, list):
        raise ValueError(f"visibility policy {field_name} must be an array")
    for index, item in enumerate(value):
        _validate_visibility_path(item, policy_name="visibility policy", field_name=f"{field_name}[{index}]")


def _validate_visibility_mapping(value: Any, *, field_name: str) -> None:
    if value in (None, ""):
        return
    if not isinstance(value, dict):
        raise ValueError(f"visibility policy {field_name} must be an object")
    for status, entry in value.items():
        status_key = str(status or "").strip()
        if not status_key:
            raise ValueError(f"visibility policy {field_name} contains empty status")
        if isinstance(entry, dict):
            for key in ("status", "code", "label", "title"):
                if key in entry and entry.get(key) is not None and not str(entry.get(key)).strip():
                    raise ValueError(f"visibility policy {field_name}.{status_key}.{key} must be non-empty")
        elif entry is not None and not str(entry).strip():
            raise ValueError(f"visibility policy {field_name}.{status_key} must be non-empty")


def _validate_visibility_policy_config(config: dict[str, Any]) -> None:
    for key in ("hide_from_requester", "show_to_requester", "show_to_support", "support_fields"):
        _validate_visibility_path_list(config.get(key), field_name=key)
    _validate_visibility_mapping(config.get("public_status_mapping"), field_name="public_status_mapping")
    _validate_visibility_mapping(config.get("public_statuses"), field_name="public_statuses")


def _validate_policy_config(kind: str, config: dict[str, Any]) -> None:
    if kind == "routing":
        _validate_routing_policy_config(config)
    elif kind == "sla":
        _validate_sla_policy_config(config)
    elif kind == "ola":
        _validate_ola_policy_config(config)
    elif kind == "approval":
        _validate_approval_policy_config(config)
    elif kind == "visibility":
        _validate_visibility_policy_config(config)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _row_version(row: Any) -> str:
    return str(getattr(row, "version", "") or "")


def _latest_version(rows: list[Any]) -> str | None:
    if not rows:
        return None
    return max((_row_version(row) for row in rows), key=lambda value: version_key(value).key)


def _row_timestamp(row: Any) -> datetime:
    return (
        getattr(row, "published_at", None)
        or getattr(row, "updated_at", None)
        or getattr(row, "created_at", None)
        or datetime.min.replace(tzinfo=timezone.utc)
    )


def serialize_policy_row(kind: str, row: Any) -> dict[str, Any]:
    return {
        "kind": normalize_policy_kind(kind),
        "table": POLICY_TABLE_NAMES[normalize_policy_kind(kind)],
        "code": str(row.code),
        "version": str(row.version),
        "title": str(row.title),
        "description": row.description,
        "scope_level": str(row.scope_level or "system"),
        "scope_ref": row.scope_ref,
        "config": deepcopy(row.config_json or {}),
        "is_active": bool(row.is_active),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


def serialize_request_template(row: RequestTemplate) -> dict[str, Any]:
    return {
        "template_code": str(row.template_code),
        "version": str(row.version),
        "public_title": str(row.public_title),
        "internal_name": row.internal_name,
        "description": row.description,
        "ticket_type": str(row.ticket_type),
        "category_id": row.category_id,
        "service_id": row.service_id,
        "subcategory_id": row.subcategory_id,
        "form_schema_id": row.form_schema_id,
        "workflow_profile_id": row.workflow_profile_id,
        "priority_policy_code": row.priority_policy_code,
        "routing_policy_code": row.routing_policy_code,
        "sla_policy_id": row.sla_policy_id,
        "sla_policy_code": row.sla_policy_code,
        "ola_policy_code": row.ola_policy_code,
        "approval_policy_code": row.approval_policy_code,
        "diagnostic_policy_code": row.diagnostic_policy_code,
        "closure_policy_code": row.closure_policy_code,
        "visibility_policy_code": row.visibility_policy_code,
        "notification_policy_code": row.notification_policy_code,
        "reporting_policy_code": row.reporting_policy_code,
        "config": deepcopy(row.config_json or {}),
        "overrides": deepcopy(row.overrides_json or {}),
        "is_active": bool(row.is_active),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


def _ticket_type_feature_flags(row: TicketType) -> dict[str, bool]:
    return {
        "sla_required": bool(row.sla_required),
        "ola_required": bool(row.ola_required),
        "approval_allowed": bool(row.approval_allowed),
        "approval_required_by_default": bool(row.approval_required_by_default),
        "diagnostics_allowed": bool(row.diagnostics_allowed),
        "remediation_allowed": bool(row.remediation_allowed),
        "portal_visible": bool(row.portal_visible),
    }


def serialize_ticket_type(row: TicketType) -> dict[str, Any]:
    return {
        "code": str(row.code),
        "version": str(row.version),
        "title": str(row.title),
        "description": row.description,
        "default_workflow_profile_id": row.default_workflow_profile_id,
        "default_priority_policy_code": row.default_priority_policy_code,
        "default_routing_policy_code": row.default_routing_policy_code,
        "default_sla_policy_id": row.default_sla_policy_id,
        "default_sla_policy_code": row.default_sla_policy_code,
        "default_ola_policy_code": row.default_ola_policy_code,
        "default_approval_policy_code": row.default_approval_policy_code,
        "default_diagnostic_policy_code": row.default_diagnostic_policy_code,
        "default_closure_policy_code": row.default_closure_policy_code,
        "default_visibility_policy_code": row.default_visibility_policy_code,
        "default_notification_policy_code": row.default_notification_policy_code,
        "default_reporting_policy_code": row.default_reporting_policy_code,
        "feature_flags": _ticket_type_feature_flags(row),
        "config": deepcopy(row.config_json or {}),
        "is_active": bool(row.is_active),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


def serialize_form_field(row: FormField) -> dict[str, Any]:
    return {
        "key": str(row.key),
        "label": str(row.label),
        "type": str(row.field_type),
        "required": bool(row.required),
        "options": deepcopy(row.options_json or []),
        "validation": deepcopy(row.validation_json or {}),
        "process_mapping": deepcopy(row.process_mapping_json or {}),
        "visibility": deepcopy(row.visibility_json or {}),
        "sort_order": int(row.sort_order or 0),
    }


def serialize_form_condition(row: FormCondition) -> dict[str, Any]:
    return {
        "condition": deepcopy(row.condition_json or {}),
        "show_fields": deepcopy(row.show_fields_json or []),
        "require_fields": deepcopy(row.require_fields_json or []),
        "sort_order": int(row.sort_order or 0),
    }


def serialize_form_schema(
    row: FormSchema,
    *,
    fields: list[FormField] | None = None,
    conditions: list[FormCondition] | None = None,
) -> dict[str, Any]:
    return {
        "schema_id": str(row.schema_id),
        "version": str(row.version),
        "title": str(row.title),
        "description": row.description,
        "form_key": row.form_key,
        "request_template_code": row.request_template_code,
        "ticket_type": row.ticket_type,
        "fields": [serialize_form_field(field) for field in fields or []],
        "conditions": [serialize_form_condition(condition) for condition in conditions or []],
        "config": deepcopy(row.config_json or {}),
        "is_active": bool(row.is_active),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


def serialize_smart_view(row: SmartView) -> dict[str, Any]:
    return {
        "code": str(row.code),
        "version": str(row.version),
        "title": str(row.title),
        "description": row.description,
        "scope_level": str(row.scope_level or "system"),
        "scope_ref": row.scope_ref,
        "filter": deepcopy(row.filter_json or {}),
        "sort": deepcopy(row.sort_json or []),
        "columns": deepcopy(row.columns_json or []),
        "is_active": bool(row.is_active),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


def _json_diff(before: Any, after: Any, *, path: str) -> list[dict[str, Any]]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child_path = f"{path}.{key}" if path else str(key)
            changes.extend(_json_diff(before.get(key), after.get(key), path=child_path))
        return changes
    if before != after:
        return [{"path": path, "from": deepcopy(before), "to": deepcopy(after)}]
    return []


class HelpdeskPolicyRepo:
    """Data access for versioned request templates, policies and smart views."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _audit(
        self,
        *,
        entity_type: str,
        entity_code: str,
        version: str,
        action: str,
        actor_id: str | None,
        actor_role: str | None,
        before_json: dict[str, Any] | None,
        after_json: dict[str, Any] | None,
    ) -> None:
        self.session.add(
            HelpdeskPolicyAudit(
                entity_type=entity_type,
                entity_code=entity_code,
                version=version,
                action=action,
                actor_id=actor_id,
                actor_role=actor_role,
                before_json=before_json,
                after_json=after_json,
                created_at=datetime.now(timezone.utc),
            )
        )

    async def list_policies(self, kind: str | None = None, *, include_inactive: bool = True) -> dict[str, list[dict[str, Any]]]:
        kinds = [normalize_policy_kind(kind)] if kind else list(POLICY_MODELS)
        result: dict[str, list[dict[str, Any]]] = {}
        for item_kind in kinds:
            model = POLICY_MODELS[item_kind]
            stmt = select(model)
            if not include_inactive:
                stmt = stmt.where(model.is_active.is_(True))
            stmt = stmt.order_by(model.code.asc(), model.created_at.desc())
            rows = list((await self.session.execute(stmt)).scalars().all())
            result[item_kind] = [serialize_policy_row(item_kind, row) for row in rows]
        return result

    async def list_request_templates(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        stmt = select(RequestTemplate)
        if not include_inactive:
            stmt = stmt.where(RequestTemplate.is_active.is_(True))
        stmt = stmt.order_by(RequestTemplate.template_code.asc(), RequestTemplate.created_at.desc())
        rows = list((await self.session.execute(stmt)).scalars().all())
        return [serialize_request_template(row) for row in rows]

    async def list_ticket_types(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        stmt = select(TicketType)
        if not include_inactive:
            stmt = stmt.where(TicketType.is_active.is_(True))
        stmt = stmt.order_by(TicketType.code.asc(), TicketType.created_at.desc())
        rows = list((await self.session.execute(stmt)).scalars().all())
        return [serialize_ticket_type(row) for row in rows]

    async def list_form_schemas(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        stmt = select(FormSchema)
        if not include_inactive:
            stmt = stmt.where(FormSchema.is_active.is_(True))
        stmt = stmt.order_by(FormSchema.schema_id.asc(), FormSchema.created_at.desc())
        schemas = list((await self.session.execute(stmt)).scalars().all())
        result: list[dict[str, Any]] = []
        for schema in schemas:
            fields = list(
                (
                    await self.session.execute(
                        select(FormField)
                        .where(
                            FormField.schema_id == schema.schema_id,
                            FormField.schema_version == schema.version,
                        )
                        .order_by(FormField.sort_order.asc(), FormField.id.asc())
                    )
                ).scalars().all()
            )
            conditions = list(
                (
                    await self.session.execute(
                        select(FormCondition)
                        .where(
                            FormCondition.schema_id == schema.schema_id,
                            FormCondition.schema_version == schema.version,
                        )
                        .order_by(FormCondition.sort_order.asc(), FormCondition.id.asc())
                    )
                ).scalars().all()
            )
            result.append(serialize_form_schema(schema, fields=fields, conditions=conditions))
        return result

    async def publish_form_schema(
        self,
        *,
        schema_id: str,
        title: str,
        fields: list[dict[str, Any]],
        form_key: str | None = None,
        request_template_code: str | None = None,
        ticket_type: str | None = None,
        description: str | None = None,
        field_roles: dict[str, list[str]] | None = None,
        conditions: list[dict[str, Any]] | None = None,
        config: dict[str, Any] | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        requested_version: str | None = None,
    ) -> dict[str, Any]:
        normalized_schema_id = normalize_template_code(schema_id)
        if not normalized_schema_id:
            raise ValueError("form schema id is required")
        normalized_form_key = normalize_template_code(form_key or normalized_schema_id)
        normalized_template_code = normalize_template_code(request_template_code) if request_template_code else None
        if not isinstance(fields, list) or not fields:
            raise ValueError("form schema fields must be a non-empty list")

        raw_form = {
            "key": normalized_form_key,
            "request_kind": normalized_form_key,
            "request_template_key": normalized_template_code or normalized_form_key,
            "request_template_title": str(title or normalized_schema_id),
            "title": str(title or normalized_schema_id),
            "description": str(description or "").strip(),
            "ticket_type": normalize_template_code(ticket_type) if ticket_type else None,
            "field_roles": deepcopy(field_roles or {}),
            "priority_policy": deepcopy((config or {}).get("priority_policy") if isinstance((config or {}).get("priority_policy"), dict) else {}),
            "fields": deepcopy(fields),
        }
        normalized_pack = validate_form_pack_schema(
            {
                "pack_key": "form_schema_registry",
                "version": "1.0.1",
                "title": str(title or normalized_schema_id),
                "description": str(description or ""),
                "forms": [raw_form],
            }
        )
        normalized_form = deepcopy(normalized_pack["forms"][0])
        field_keys = {str(field.get("key") or "") for field in normalized_form.get("fields") or []}
        normalized_conditions: list[dict[str, Any]] = []
        for index, field in enumerate(normalized_form.get("fields") or []):
            visibility = field.get("visible_when") if isinstance(field.get("visible_when"), dict) else None
            if visibility:
                normalized_conditions.append(
                    {
                        "condition": deepcopy(visibility),
                        "show_fields": [field["key"]],
                        "require_fields": [field["key"]] if field.get("required") else [],
                        "sort_order": index,
                    }
                )
        for index, raw_condition in enumerate(conditions or [], start=len(normalized_conditions)):
            if not isinstance(raw_condition, dict):
                raise ValueError("form condition must be an object")
            condition = raw_condition.get("condition") or raw_condition.get("if")
            if not isinstance(condition, dict):
                raise ValueError("form condition requires condition")
            dependency_field = str(condition.get("field") or "").strip()
            if dependency_field and dependency_field not in field_keys:
                raise ValueError(f"form condition references unknown field {dependency_field!r}")
            show_fields = [str(item or "").strip() for item in raw_condition.get("show_fields") or [] if str(item or "").strip()]
            require_fields = [str(item or "").strip() for item in raw_condition.get("require_fields") or [] if str(item or "").strip()]
            missing = sorted({item for item in show_fields + require_fields if item not in field_keys})
            if missing:
                raise ValueError(f"form condition references unknown output fields: {', '.join(missing)}")
            normalized_conditions.append(
                {
                    "condition": deepcopy(condition),
                    "show_fields": show_fields,
                    "require_fields": require_fields,
                    "sort_order": int(raw_condition.get("sort_order") or index),
                }
            )

        existing_rows = list(
            (
                await self.session.execute(
                    select(FormSchema).where(FormSchema.schema_id == normalized_schema_id)
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = str(requested_version or next_form_pack_version(latest)).strip()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(FormSchema)
            .where(FormSchema.schema_id == normalized_schema_id, FormSchema.is_active.is_(True))
            .values(is_active=False, valid_to=now, updated_at=now, updated_by=actor_id)
        )
        schema = FormSchema(
            schema_id=normalized_schema_id,
            version=version,
            title=str(title or normalized_schema_id),
            description=description,
            form_key=normalized_form_key,
            request_template_code=normalized_template_code,
            ticket_type=normalize_template_code(ticket_type) if ticket_type else normalized_form.get("ticket_type"),
            config_json={
                **deepcopy(config or {}),
                "form": {
                    key: deepcopy(value)
                    for key, value in normalized_form.items()
                    if key not in {"fields"}
                },
            },
            is_active=True,
            valid_from=now,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(schema)
        await self.session.flush()
        field_rows: list[FormField] = []
        for index, field in enumerate(normalized_form.get("fields") or []):
            field_row = FormField(
                schema_id=normalized_schema_id,
                schema_version=version,
                key=str(field.get("key") or ""),
                label=str(field.get("label") or field.get("key") or ""),
                field_type=str(field.get("type") or "text"),
                required=bool(field.get("required")),
                options_json=deepcopy(field.get("options") or []),
                validation_json=deepcopy(field.get("validation") or {}),
                process_mapping_json=deepcopy(field.get("process_mapping") or {}),
                visibility_json=deepcopy(field.get("visible_when") or {}),
                sort_order=index,
                created_at=now,
            )
            self.session.add(field_row)
            field_rows.append(field_row)
        condition_rows: list[FormCondition] = []
        for index, condition in enumerate(normalized_conditions):
            condition_row = FormCondition(
                schema_id=normalized_schema_id,
                schema_version=version,
                condition_json=deepcopy(condition.get("condition") or {}),
                show_fields_json=deepcopy(condition.get("show_fields") or []),
                require_fields_json=deepcopy(condition.get("require_fields") or []),
                sort_order=int(condition.get("sort_order") or index),
                created_at=now,
            )
            self.session.add(condition_row)
            condition_rows.append(condition_row)
        await self.session.flush()
        serialized = serialize_form_schema(schema, fields=field_rows, conditions=condition_rows)
        await self._audit(
            entity_type="form_schemas",
            entity_code=normalized_schema_id,
            version=version,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=None,
            after_json=serialized,
        )
        return serialized

    async def list_smart_views(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        stmt = select(SmartView)
        if not include_inactive:
            stmt = stmt.where(SmartView.is_active.is_(True))
        stmt = stmt.order_by(SmartView.code.asc(), SmartView.created_at.desc())
        rows = list((await self.session.execute(stmt)).scalars().all())
        return [serialize_smart_view(row) for row in rows]

    async def publish_smart_view(
        self,
        *,
        code: str,
        title: str,
        filter_config: dict[str, Any],
        sort: list[dict[str, Any]] | None = None,
        columns: list[str] | None = None,
        description: str | None = None,
        scope_level: str = "system",
        scope_ref: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        requested_version: str | None = None,
    ) -> dict[str, Any]:
        normalized_code = normalize_template_code(code)
        if not normalized_code:
            raise ValueError("smart view code is required")
        if not isinstance(filter_config, dict):
            raise ValueError("smart view filter must be object")
        if sort is not None and not isinstance(sort, list):
            raise ValueError("smart view sort must be list")
        if columns is not None and not isinstance(columns, list):
            raise ValueError("smart view columns must be list")

        existing_rows = list(
            (
                await self.session.execute(
                    select(SmartView).where(SmartView.code == normalized_code)
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = str(requested_version or next_form_pack_version(latest)).strip()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(SmartView)
            .where(SmartView.code == normalized_code, SmartView.is_active.is_(True))
            .values(is_active=False, updated_at=now, updated_by=actor_id)
        )
        row = SmartView(
            code=normalized_code,
            version=version,
            title=str(title or normalized_code),
            description=description,
            scope_level=str(scope_level or "system"),
            scope_ref=str(scope_ref).strip() if scope_ref is not None and str(scope_ref).strip() else None,
            filter_json=deepcopy(filter_config),
            sort_json=deepcopy(sort or []),
            columns_json=[str(item) for item in (columns or []) if str(item).strip()],
            is_active=True,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        serialized = serialize_smart_view(row)
        await self._audit(
            entity_type="smart_views",
            entity_code=normalized_code,
            version=version,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=None,
            after_json=serialized,
        )
        return serialized

    async def publish_ticket_type(
        self,
        *,
        code: str,
        title: str,
        description: str | None = None,
        default_workflow_profile_id: str | None = None,
        default_priority_policy_code: str | None = None,
        default_routing_policy_code: str | None = None,
        default_sla_policy_id: int | None = None,
        default_sla_policy_code: str | None = None,
        default_ola_policy_code: str | None = None,
        default_approval_policy_code: str | None = None,
        default_diagnostic_policy_code: str | None = None,
        default_closure_policy_code: str | None = None,
        default_visibility_policy_code: str | None = None,
        default_notification_policy_code: str | None = None,
        default_reporting_policy_code: str | None = None,
        feature_flags: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        requested_version: str | None = None,
    ) -> dict[str, Any]:
        normalized_code = normalize_template_code(code)
        if not normalized_code:
            raise ValueError("ticket type code is required")
        flags = dict(feature_flags or {})
        existing_rows = list(
            (
                await self.session.execute(
                    select(TicketType).where(TicketType.code == normalized_code)
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = str(requested_version or next_form_pack_version(latest)).strip()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(TicketType)
            .where(TicketType.code == normalized_code, TicketType.is_active.is_(True))
            .values(is_active=False, valid_to=now, updated_at=now, updated_by=actor_id)
        )
        row = TicketType(
            code=normalized_code,
            version=version,
            title=str(title or normalized_code),
            description=description,
            default_workflow_profile_id=default_workflow_profile_id,
            default_priority_policy_code=default_priority_policy_code,
            default_routing_policy_code=default_routing_policy_code,
            default_sla_policy_id=default_sla_policy_id,
            default_sla_policy_code=default_sla_policy_code,
            default_ola_policy_code=default_ola_policy_code,
            default_approval_policy_code=default_approval_policy_code,
            default_diagnostic_policy_code=default_diagnostic_policy_code,
            default_closure_policy_code=default_closure_policy_code,
            default_visibility_policy_code=default_visibility_policy_code,
            default_notification_policy_code=default_notification_policy_code,
            default_reporting_policy_code=default_reporting_policy_code,
            sla_required=bool(flags.get("sla_required", False)),
            ola_required=bool(flags.get("ola_required", False)),
            approval_allowed=bool(flags.get("approval_allowed", False)),
            approval_required_by_default=bool(flags.get("approval_required_by_default", False)),
            diagnostics_allowed=bool(flags.get("diagnostics_allowed", False)),
            remediation_allowed=bool(flags.get("remediation_allowed", False)),
            portal_visible=bool(flags.get("portal_visible", True)),
            config_json=deepcopy(config or {}),
            is_active=True,
            valid_from=now,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        serialized = serialize_ticket_type(row)
        await self._audit(
            entity_type="ticket_types",
            entity_code=normalized_code,
            version=version,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=None,
            after_json=serialized,
        )
        return serialized

    async def resolve_ticket_type_defaults(self, code: str | None) -> dict[str, Any] | None:
        normalized_code = normalize_template_code(code)
        if not normalized_code:
            return None
        row = await self.session.scalar(
            select(TicketType)
            .where(TicketType.code == normalized_code, TicketType.is_active.is_(True))
            .order_by(TicketType.published_at.desc(), TicketType.created_at.desc())
        )
        if row is None:
            return None
        return serialize_ticket_type(row)

    async def _get_ticket_type_row(self, *, code: str, version: str) -> tuple[str, TicketType]:
        normalized_code = normalize_template_code(code)
        row = await self.session.scalar(
            select(TicketType).where(
                TicketType.code == normalized_code,
                TicketType.version == str(version),
            )
        )
        if row is None:
            raise ValueError(f"ticket type version not found: {normalized_code}/{version}")
        return normalized_code, row

    async def deactivate_ticket_type(
        self,
        *,
        code: str,
        version: str,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        normalized_code, row = await self._get_ticket_type_row(code=code, version=version)
        before = serialize_ticket_type(row)
        now = datetime.now(timezone.utc)
        row.is_active = False
        row.valid_to = now
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        after = serialize_ticket_type(row)
        await self._audit(
            entity_type="ticket_types",
            entity_code=normalized_code,
            version=str(version),
            action="deactivated",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=before,
            after_json=after,
        )
        return after

    async def rollback_ticket_type(
        self,
        *,
        code: str,
        target_version: str,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        normalized_code, target_row = await self._get_ticket_type_row(code=code, version=target_version)
        existing_rows = list(
            (
                await self.session.execute(
                    select(TicketType).where(TicketType.code == normalized_code)
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = next_form_pack_version(latest)
        now = datetime.now(timezone.utc)
        active_before = [serialize_ticket_type(row) for row in existing_rows if bool(row.is_active)]
        await self.session.execute(
            update(TicketType)
            .where(TicketType.code == normalized_code, TicketType.is_active.is_(True))
            .values(is_active=False, valid_to=now, updated_at=now, updated_by=actor_id)
        )
        row = TicketType(
            code=normalized_code,
            version=version,
            title=str(target_row.title),
            description=target_row.description,
            default_workflow_profile_id=target_row.default_workflow_profile_id,
            default_priority_policy_code=target_row.default_priority_policy_code,
            default_routing_policy_code=target_row.default_routing_policy_code,
            default_sla_policy_id=target_row.default_sla_policy_id,
            default_sla_policy_code=target_row.default_sla_policy_code,
            default_ola_policy_code=target_row.default_ola_policy_code,
            default_approval_policy_code=target_row.default_approval_policy_code,
            default_diagnostic_policy_code=target_row.default_diagnostic_policy_code,
            default_closure_policy_code=target_row.default_closure_policy_code,
            default_visibility_policy_code=target_row.default_visibility_policy_code,
            default_notification_policy_code=target_row.default_notification_policy_code,
            default_reporting_policy_code=target_row.default_reporting_policy_code,
            sla_required=bool(target_row.sla_required),
            ola_required=bool(target_row.ola_required),
            approval_allowed=bool(target_row.approval_allowed),
            approval_required_by_default=bool(target_row.approval_required_by_default),
            diagnostics_allowed=bool(target_row.diagnostics_allowed),
            remediation_allowed=bool(target_row.remediation_allowed),
            portal_visible=bool(target_row.portal_visible),
            config_json=deepcopy(target_row.config_json or {}),
            is_active=True,
            valid_from=now,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        serialized = serialize_ticket_type(row)
        await self._audit(
            entity_type="ticket_types",
            entity_code=normalized_code,
            version=version,
            action="rollback_published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json={
                "target_version": str(target_version),
                "active_versions": active_before,
            },
            after_json=serialized,
        )
        return serialized

    async def publish_policy(
        self,
        *,
        kind: str,
        code: str,
        title: str,
        config: dict[str, Any],
        description: str | None = None,
        scope_level: str = "system",
        scope_ref: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        requested_version: str | None = None,
    ) -> dict[str, Any]:
        normalized_kind = normalize_policy_kind(kind)
        model = POLICY_MODELS[normalized_kind]
        normalized_code = normalize_template_code(code)
        if not normalized_code:
            raise ValueError("policy code is required")
        if not isinstance(config, dict):
            raise ValueError("policy config must be object")
        _validate_policy_config(normalized_kind, config)

        existing_rows = list(
            (
                await self.session.execute(
                    select(model).where(model.code == normalized_code)
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = str(requested_version or next_form_pack_version(latest)).strip()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(model)
            .where(model.code == normalized_code, model.is_active.is_(True))
            .values(is_active=False, valid_to=now, updated_at=now, updated_by=actor_id)
        )
        row = model(
            code=normalized_code,
            version=version,
            title=str(title or normalized_code),
            description=description,
            scope_level=str(scope_level or "system"),
            scope_ref=str(scope_ref).strip() if scope_ref is not None and str(scope_ref).strip() else None,
            config_json=deepcopy(config),
            is_active=True,
            valid_from=now,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        serialized = serialize_policy_row(normalized_kind, row)
        await self._audit(
            entity_type=POLICY_TABLE_NAMES[normalized_kind],
            entity_code=normalized_code,
            version=version,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=None,
            after_json=serialized,
        )
        return serialized

    async def _get_policy_row(self, *, kind: str, code: str, version: str):
        normalized_kind = normalize_policy_kind(kind)
        normalized_code = normalize_template_code(code)
        row = await self.session.scalar(
            select(POLICY_MODELS[normalized_kind]).where(
                POLICY_MODELS[normalized_kind].code == normalized_code,
                POLICY_MODELS[normalized_kind].version == str(version),
            )
        )
        if row is None:
            raise ValueError(f"policy version not found: {normalized_kind}/{normalized_code}/{version}")
        return normalized_kind, normalized_code, row

    async def diff_policy_versions(
        self,
        *,
        kind: str,
        code: str,
        from_version: str,
        to_version: str,
    ) -> dict[str, Any]:
        normalized_kind, normalized_code, from_row = await self._get_policy_row(
            kind=kind,
            code=code,
            version=from_version,
        )
        _, _, to_row = await self._get_policy_row(
            kind=normalized_kind,
            code=normalized_code,
            version=to_version,
        )
        before = serialize_policy_row(normalized_kind, from_row)
        after = serialize_policy_row(normalized_kind, to_row)
        return {
            "kind": normalized_kind,
            "code": normalized_code,
            "from": before,
            "to": after,
            "changes": _json_diff(before.get("config") or {}, after.get("config") or {}, path="config"),
        }

    async def deactivate_policy(
        self,
        *,
        kind: str,
        code: str,
        version: str,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        normalized_kind, normalized_code, row = await self._get_policy_row(
            kind=kind,
            code=code,
            version=version,
        )
        before = serialize_policy_row(normalized_kind, row)
        now = datetime.now(timezone.utc)
        row.is_active = False
        row.valid_to = now
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        after = serialize_policy_row(normalized_kind, row)
        await self._audit(
            entity_type=POLICY_TABLE_NAMES[normalized_kind],
            entity_code=normalized_code,
            version=str(version),
            action="deactivated",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=before,
            after_json=after,
        )
        return after

    async def rollback_policy(
        self,
        *,
        kind: str,
        code: str,
        target_version: str,
        actor_id: str | None = None,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        normalized_kind, normalized_code, target_row = await self._get_policy_row(
            kind=kind,
            code=code,
            version=target_version,
        )
        existing_rows = list(
            (
                await self.session.execute(
                    select(POLICY_MODELS[normalized_kind]).where(
                        POLICY_MODELS[normalized_kind].code == normalized_code
                    )
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = next_form_pack_version(latest)
        now = datetime.now(timezone.utc)
        active_rows = [row for row in existing_rows if bool(row.is_active)]
        active_before = [serialize_policy_row(normalized_kind, row) for row in active_rows]
        await self.session.execute(
            update(POLICY_MODELS[normalized_kind])
            .where(
                POLICY_MODELS[normalized_kind].code == normalized_code,
                POLICY_MODELS[normalized_kind].is_active.is_(True),
            )
            .values(is_active=False, valid_to=now, updated_at=now, updated_by=actor_id)
        )
        row = POLICY_MODELS[normalized_kind](
            code=normalized_code,
            version=version,
            title=str(target_row.title),
            description=target_row.description,
            scope_level=str(target_row.scope_level or "system"),
            scope_ref=target_row.scope_ref,
            config_json=deepcopy(target_row.config_json or {}),
            is_active=True,
            valid_from=now,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        serialized = serialize_policy_row(normalized_kind, row)
        await self._audit(
            entity_type=POLICY_TABLE_NAMES[normalized_kind],
            entity_code=normalized_code,
            version=version,
            action="rollback_published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json={
                "target_version": str(target_version),
                "active_versions": active_before,
            },
            after_json=serialized,
        )
        return serialized

    async def publish_request_template(
        self,
        *,
        template_code: str,
        public_title: str,
        ticket_type: str,
        internal_name: str | None = None,
        description: str | None = None,
        category_id: int | None = None,
        service_id: int | None = None,
        subcategory_id: int | None = None,
        form_schema_id: str | None = None,
        workflow_profile_id: str | None = None,
        priority_policy_code: str | None = None,
        routing_policy_code: str | None = None,
        sla_policy_id: int | None = None,
        sla_policy_code: str | None = None,
        ola_policy_code: str | None = None,
        approval_policy_code: str | None = None,
        diagnostic_policy_code: str | None = None,
        closure_policy_code: str | None = None,
        visibility_policy_code: str | None = None,
        notification_policy_code: str | None = None,
        reporting_policy_code: str | None = None,
        config: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        requested_version: str | None = None,
    ) -> dict[str, Any]:
        code = normalize_template_code(template_code)
        if not code:
            raise ValueError("template code is required")
        ticket_type_code = normalize_template_code(ticket_type) or "incident"
        ticket_type_defaults = await self.resolve_ticket_type_defaults(ticket_type_code)
        if ticket_type_defaults:
            workflow_profile_id = workflow_profile_id or ticket_type_defaults.get("default_workflow_profile_id")
            priority_policy_code = priority_policy_code or ticket_type_defaults.get("default_priority_policy_code")
            routing_policy_code = routing_policy_code or ticket_type_defaults.get("default_routing_policy_code")
            sla_policy_id = sla_policy_id if sla_policy_id is not None else ticket_type_defaults.get("default_sla_policy_id")
            sla_policy_code = sla_policy_code or ticket_type_defaults.get("default_sla_policy_code")
            ola_policy_code = ola_policy_code or ticket_type_defaults.get("default_ola_policy_code")
            approval_policy_code = approval_policy_code or ticket_type_defaults.get("default_approval_policy_code")
            diagnostic_policy_code = diagnostic_policy_code or ticket_type_defaults.get("default_diagnostic_policy_code")
            closure_policy_code = closure_policy_code or ticket_type_defaults.get("default_closure_policy_code")
            visibility_policy_code = visibility_policy_code or ticket_type_defaults.get("default_visibility_policy_code")
            notification_policy_code = notification_policy_code or ticket_type_defaults.get("default_notification_policy_code")
            reporting_policy_code = reporting_policy_code or ticket_type_defaults.get("default_reporting_policy_code")
        config_json = deepcopy(config or {})
        if ticket_type_defaults:
            config_json.setdefault(
                "ticket_type_defaults",
                {
                    "code": ticket_type_defaults.get("code"),
                    "version": ticket_type_defaults.get("version"),
                    "title": ticket_type_defaults.get("title"),
                    "default_workflow_profile_id": ticket_type_defaults.get("default_workflow_profile_id"),
                    "default_priority_policy_code": ticket_type_defaults.get("default_priority_policy_code"),
                    "default_routing_policy_code": ticket_type_defaults.get("default_routing_policy_code"),
                    "default_sla_policy_id": ticket_type_defaults.get("default_sla_policy_id"),
                    "default_sla_policy_code": ticket_type_defaults.get("default_sla_policy_code"),
                    "default_ola_policy_code": ticket_type_defaults.get("default_ola_policy_code"),
                    "default_approval_policy_code": ticket_type_defaults.get("default_approval_policy_code"),
                    "default_diagnostic_policy_code": ticket_type_defaults.get("default_diagnostic_policy_code"),
                    "default_closure_policy_code": ticket_type_defaults.get("default_closure_policy_code"),
                    "default_visibility_policy_code": ticket_type_defaults.get("default_visibility_policy_code"),
                    "default_notification_policy_code": ticket_type_defaults.get("default_notification_policy_code"),
                    "default_reporting_policy_code": ticket_type_defaults.get("default_reporting_policy_code"),
                    "feature_flags": deepcopy(ticket_type_defaults.get("feature_flags") or {}),
                },
            )
        existing_rows = list(
            (
                await self.session.execute(
                    select(RequestTemplate).where(RequestTemplate.template_code == code)
                )
            ).scalars().all()
        )
        latest = _latest_version(existing_rows)
        version = str(requested_version or next_form_pack_version(latest)).strip()
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(RequestTemplate)
            .where(RequestTemplate.template_code == code, RequestTemplate.is_active.is_(True))
            .values(is_active=False, valid_to=now, updated_at=now, updated_by=actor_id)
        )
        row = RequestTemplate(
            template_code=code,
            version=version,
            public_title=str(public_title or code),
            internal_name=internal_name,
            description=description,
            ticket_type=ticket_type_code,
            category_id=category_id,
            service_id=service_id,
            subcategory_id=subcategory_id,
            form_schema_id=form_schema_id,
            workflow_profile_id=workflow_profile_id,
            priority_policy_code=priority_policy_code,
            routing_policy_code=routing_policy_code,
            sla_policy_id=sla_policy_id,
            sla_policy_code=sla_policy_code,
            ola_policy_code=ola_policy_code,
            approval_policy_code=approval_policy_code,
            diagnostic_policy_code=diagnostic_policy_code,
            closure_policy_code=closure_policy_code,
            visibility_policy_code=visibility_policy_code,
            notification_policy_code=notification_policy_code,
            reporting_policy_code=reporting_policy_code,
            config_json=config_json,
            overrides_json=deepcopy(overrides or {}),
            is_active=True,
            valid_from=now,
            published_at=now,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        serialized = serialize_request_template(row)
        await self._audit(
            entity_type="request_templates",
            entity_code=code,
            version=version,
            action="published",
            actor_id=actor_id,
            actor_role=actor_role,
            before_json=None,
            after_json=serialized,
        )
        return serialized

    async def resolve_effective_policy(
        self,
        *,
        kind: str,
        ticket_type: str | None = None,
        category_id: int | str | None = None,
        template_code: str | None = None,
    ) -> dict[str, Any]:
        normalized_kind = normalize_policy_kind(kind)
        model = POLICY_MODELS[normalized_kind]
        category_ref = str(category_id) if category_id is not None and str(category_id).strip() else None
        template_ref = normalize_template_code(template_code)
        matching_scopes: list[tuple[str, str | None]] = [("system", None)]
        if ticket_type:
            matching_scopes.append(("ticket_type", str(ticket_type)))
        if category_ref:
            matching_scopes.append(("category", category_ref))
        if template_ref:
            matching_scopes.append(("request_template", template_ref))

        rows = list(
            (
                await self.session.execute(
                    select(model).where(model.is_active.is_(True))
                )
            ).scalars().all()
        )
        selected = [
            row
            for row in rows
            if (
                str(row.scope_level or "system"),
                str(row.scope_ref) if row.scope_ref is not None else None,
            )
            in matching_scopes
        ]
        selected.sort(
            key=lambda row: (
                SCOPE_RANK.get(str(row.scope_level or "system"), 99),
                _row_timestamp(row),
                version_key(str(row.version)).key,
            )
        )
        effective: dict[str, Any] = {}
        sources: list[dict[str, Any]] = []
        for row in selected:
            effective = _deep_merge(effective, row.config_json or {})
            sources.append(
                {
                    "code": row.code,
                    "version": row.version,
                    "scope_level": row.scope_level,
                    "scope_ref": row.scope_ref,
                }
            )
        return {
            "kind": normalized_kind,
            "config": effective,
            "sources": sources,
        }

    async def resolve_policy_ref(
        self,
        *,
        kind: str,
        code: str | None,
        source: str = "policy_ref",
    ) -> dict[str, Any]:
        normalized_kind = normalize_policy_kind(kind)
        normalized_code = normalize_template_code(code)
        if not normalized_code:
            return {"kind": normalized_kind, "config": {}, "sources": []}
        model = POLICY_MODELS[normalized_kind]
        rows = list(
            (
                await self.session.execute(
                    select(model).where(
                        model.code == normalized_code,
                        model.is_active.is_(True),
                    )
                )
            ).scalars().all()
        )
        if not rows:
            return {"kind": normalized_kind, "config": {}, "sources": []}
        rows.sort(key=lambda row: (_row_timestamp(row), version_key(str(row.version)).key), reverse=True)
        row = rows[0]
        source_row = {
            "code": row.code,
            "version": row.version,
            "scope_level": "policy_ref",
            "scope_ref": normalized_code,
            "source": source,
            "policy_scope_level": row.scope_level,
            "policy_scope_ref": row.scope_ref,
        }
        return {
            "kind": normalized_kind,
            "config": deepcopy(row.config_json or {}),
            "sources": [source_row],
            "policy": serialize_policy_row(normalized_kind, row),
        }

    async def resolve_effective_request_template(
        self,
        *,
        template_code: str,
        ticket_type: str | None = None,
        category_id: int | str | None = None,
        raise_if_missing: bool = True,
    ) -> dict[str, Any]:
        code = normalize_template_code(template_code)
        row = (
            await self.session.execute(
                select(RequestTemplate).where(
                    RequestTemplate.template_code == code,
                    RequestTemplate.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            if raise_if_missing:
                raise ValueError(f"active request template {template_code!r} not found")
            return {}

        serialized = serialize_request_template(row)
        config_json = deepcopy(row.config_json or {})
        config_refs = config_json.get("policy_refs") if isinstance(config_json.get("policy_refs"), dict) else {}
        resolved_policies: dict[str, dict[str, Any]] = {}
        policy_sources: dict[str, list[dict[str, Any]]] = {}
        policy_refs: dict[str, dict[str, Any]] = {}
        policy_snapshots: dict[str, dict[str, Any]] = {}
        for kind, attr_name in REQUEST_TEMPLATE_POLICY_CODE_FIELDS.items():
            ref_code = str(getattr(row, attr_name, None) or "").strip()
            if not ref_code and isinstance(config_refs, dict):
                raw_config_ref = config_refs.get(kind) or config_refs.get(f"{kind}_policy")
                if isinstance(raw_config_ref, dict):
                    ref_code = str(raw_config_ref.get("code") or raw_config_ref.get("policy_code") or "").strip()
                else:
                    ref_code = str(raw_config_ref or "").strip()
            if ref_code:
                effective = await self.resolve_policy_ref(
                    kind=kind,
                    code=ref_code,
                    source=f"request_template.{attr_name}",
                )
            else:
                effective = await self.resolve_effective_policy(
                    kind=kind,
                    ticket_type=ticket_type or row.ticket_type,
                    category_id=category_id if category_id is not None else row.category_id,
                    template_code=row.template_code,
                )
            config = effective.get("config") if isinstance(effective, dict) else {}
            sources = effective.get("sources") if isinstance(effective, dict) else []
            if isinstance(config, dict) and config:
                resolved_policies[kind] = config
            if isinstance(sources, list) and sources:
                policy_sources[kind] = sources
                primary_source = sources[-1]
                policy_refs[kind] = {
                    "code": primary_source.get("code"),
                    "version": primary_source.get("version"),
                    "source": primary_source.get("source") or primary_source.get("scope_level"),
                }
                policy_snapshots[kind] = {
                    "code": primary_source.get("code"),
                    "version": primary_source.get("version"),
                    "source": primary_source.get("source") or primary_source.get("scope_level"),
                    "scope_level": primary_source.get("scope_level"),
                    "scope_ref": primary_source.get("scope_ref"),
                    "config": deepcopy(config),
                }

        return {
            "request_template": serialized,
            "policy_refs": policy_refs,
            "resolved_policies": resolved_policies,
            "policy_sources": policy_sources,
            "policy_snapshots": policy_snapshots,
        }
