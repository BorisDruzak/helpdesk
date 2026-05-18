from __future__ import annotations

from typing import Any

CHANGE_TYPES = {"standard", "normal", "emergency"}
CHANGE_STATUSES = {
    "draft",
    "submitted",
    "assessing",
    "awaiting_approval",
    "approved",
    "scheduled",
    "implementation_in_progress",
    "implemented",
    "pir_required",
    "closed",
    "rejected",
    "canceled",
    "failed",
    "rolled_back",
}
CHANGE_TRANSITIONS = {
    "draft": {"submitted", "canceled"},
    "submitted": {"assessing", "rejected", "canceled"},
    "assessing": {"awaiting_approval", "rejected", "canceled"},
    "awaiting_approval": {"approved", "rejected", "canceled"},
    "approved": {"scheduled", "implementation_in_progress", "canceled"},
    "scheduled": {"implementation_in_progress", "canceled"},
    "implementation_in_progress": {"implemented", "failed", "rolled_back"},
    "implemented": {"pir_required", "closed"},
    "pir_required": {"closed", "failed"},
    "closed": set(),
    "rejected": set(),
    "canceled": set(),
    "failed": set(),
    "rolled_back": set(),
}
CHANGE_LEVELS = {"low", "medium", "high", "critical"}
CHANGE_CATEGORIES = {"infrastructure", "application", "network", "security", "access", "service_catalog", "knowledge", "process", "other"}
CHANGE_SOURCE_KINDS = {"manual", "problem", "improvement_action", "quality_review", "service_catalog", "security", "api"}


def clean_text(value: Any, *, max_length: int | None = None) -> str | None:
    result = str(value or "").strip()
    if not result:
        return None
    return result[:max_length] if max_length else result


def validate_choice(value: Any, allowed: set[str], field: str, *, default: str | None = None) -> str:
    raw = str(value or default or "").strip().lower()
    if raw not in allowed:
        raise ValueError(f"{field} is invalid")
    return raw


def normalize_change_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status not in CHANGE_STATUSES:
        raise ValueError("status is invalid")
    return status


def can_transition_change(current_status: str, new_status: str) -> bool:
    current = normalize_change_status(current_status)
    new = normalize_change_status(new_status)
    return new in CHANGE_TRANSITIONS.get(current, set())


def validate_change_approval_payload(
    *,
    change_type: str,
    emergency_justification: str | None,
    has_risk: bool,
    has_plan: bool,
    has_rollback: bool,
    approvals_satisfied: bool,
) -> None:
    if change_type in {"normal", "emergency"} and not has_risk:
        raise ValueError("risk assessment is required before approval")
    if change_type in {"normal", "emergency"} and not has_plan:
        raise ValueError("implementation plan is required before approval")
    if change_type in {"normal", "emergency"} and not has_rollback:
        raise ValueError("rollback plan is required before approval")
    if change_type == "emergency" and not clean_text(emergency_justification):
        raise ValueError("emergency justification is required before approval")
    if not approvals_satisfied:
        raise ValueError("approvals are not satisfied")

