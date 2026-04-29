"""Deterministic process priority calculation for tickets."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from tickets.statuses import PRIORITY_CLASS_TO_LEGACY_PRIORITY


PROCESS_PRIORITIES = ("P0", "P1", "P2", "P3")

_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

_IMPACT_ALIASES = {
    "minimal": 0,
    "question": 0,
    "consultation": 0,
    "no_work_disruption": 0,
    "low": 1,
    "only_me": 1,
    "one_user": 1,
    "single_user": 1,
    "medium": 2,
    "several_people": 2,
    "department": 2,
    "group": 2,
    "high": 3,
    "building_or_org": 3,
    "building": 3,
    "organization": 3,
    "critical_system": 3,
}

_URGENCY_ALIASES = {
    "minimal": 0,
    "inconvenience_only": 0,
    "consultation": 0,
    "low": 1,
    "workaround_available": 1,
    "has_workaround": 1,
    "medium": 2,
    "partial_work": 2,
    "strongly_degraded": 2,
    "high": 3,
    "work_stopped_no_workaround": 3,
    "work_stopped": 3,
    "no_workaround": 3,
}

_IMPORTANCE_ALIASES = {
    "normal": 1,
    "low": 1,
    "none": 1,
    "high": 2,
    "deadline": 2,
    "deadline_soon": 2,
    "critical": 3,
    "deadline_today": 3,
    "deadline_tomorrow": 3,
    "reporting_period": 3,
    "public_service": 3,
    "security": 3,
}

_BASE_MATRIX = {
    3: {3: "P0", 2: "P1", 1: "P2", 0: "P2"},
    2: {3: "P1", 2: "P1", 1: "P2", 0: "P3"},
    1: {3: "P2", 2: "P2", 1: "P3", 0: "P3"},
    0: {3: "P3", 2: "P3", 1: "P3", 0: "P3"},
}

_BOOST_MODIFIERS = {
    "critical_service",
    "deadline_today",
    "deadline_tomorrow",
    "reporting_period",
    "public_service",
    "citizen_reception",
    "confirmed_outage",
    "similar_tickets",
}


def _normalize_level(value: Any, aliases: Mapping[str, int], *, default: int, field_name: str) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return 3 if value else default
    if isinstance(value, int):
        if value in (0, 1, 2, 3):
            return value
        raise ValueError(f"{field_name} must be 0, 1, 2 or 3")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized.isdigit():
            return _normalize_level(int(normalized), aliases, default=default, field_name=field_name)
        if normalized in aliases:
            return aliases[normalized]
    raise ValueError(f"{field_name} has unsupported value: {value!r}")


def _priority_after_boost(priority: str, boost_count: int) -> str:
    rank = max(_PRIORITY_RANK.get(priority, _PRIORITY_RANK["P3"]) - max(boost_count, 0), 0)
    for item, item_rank in _PRIORITY_RANK.items():
        if item_rank == rank:
            return item
    return "P3"


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "critical", "high"}
    return bool(value)


def compute_priority_from_facts(
    *,
    impact: Any = None,
    urgency: Any = None,
    importance: Any = None,
    modifiers: Optional[Mapping[str, Any]] = None,
    manual_priority: Optional[str] = None,
    manual_reason: Optional[str] = None,
    source: str = "system",
) -> Dict[str, Any]:
    """Compute P0..P3 from impact, urgency, importance and deterministic modifiers."""
    impact_level = _normalize_level(impact, _IMPACT_ALIASES, default=1, field_name="impact")
    urgency_level = _normalize_level(urgency, _URGENCY_ALIASES, default=1, field_name="urgency")
    importance_level = _normalize_level(importance, _IMPORTANCE_ALIASES, default=1, field_name="importance")
    computed_priority = _BASE_MATRIX[impact_level][urgency_level]

    active_modifiers: list[str] = []
    for key, value in (modifiers or {}).items():
        if key in _BOOST_MODIFIERS and _is_truthy(value):
            active_modifiers.append(key)
    if importance_level >= 3:
        active_modifiers.append("high_importance")

    boost_count = len(active_modifiers)
    effective_priority = _priority_after_boost(computed_priority, boost_count)
    if (modifiers or {}).get("security") and _PRIORITY_RANK[effective_priority] > _PRIORITY_RANK["P1"]:
        active_modifiers.append("security")
        effective_priority = "P1"
    elif (modifiers or {}).get("security"):
        active_modifiers.append("security")

    priority_source = source
    if manual_priority:
        if manual_priority not in PROCESS_PRIORITIES:
            raise ValueError("manual_priority must be one of P0, P1, P2, P3")
        if not str(manual_reason or "").strip():
            raise ValueError("manual_reason is required for manual priority override")
        effective_priority = manual_priority
        priority_source = "support_override"

    reason_parts = [
        f"impact={impact_level}",
        f"urgency={urgency_level}",
        f"importance={importance_level}",
        f"computed={computed_priority}",
    ]
    if active_modifiers:
        reason_parts.append("modifiers=" + ",".join(active_modifiers))
    if manual_priority:
        reason_parts.append("manual_override=" + manual_priority)

    return {
        "impact": impact_level,
        "urgency": urgency_level,
        "importance": importance_level,
        "urgency_reason": f"urgency={urgency_level}",
        "importance_reason": f"importance={importance_level}",
        "computed_priority": computed_priority,
        "manual_priority": manual_priority,
        "effective_priority": effective_priority,
        "priority_class": effective_priority,
        "legacy_priority": PRIORITY_CLASS_TO_LEGACY_PRIORITY[effective_priority],
        "priority_source": priority_source,
        "priority_reason": "; ".join(reason_parts),
        "manual_priority_reason": str(manual_reason or "").strip() or None,
        "applied_modifiers": active_modifiers,
    }


def compute_priority_from_policy(
    *,
    priority_policy: Mapping[str, Any],
    submitted_values: Mapping[str, Any],
    fallback: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute priority using a request-template priority_policy and submitted form values."""
    fallback = fallback or {}
    impact_field = str(priority_policy.get("impact_field") or "").strip()
    urgency_field = str(priority_policy.get("urgency_field") or "").strip()
    importance_field = str(priority_policy.get("importance_field") or "").strip()
    modifier_fields = priority_policy.get("modifier_fields") or {}
    if modifier_fields and not isinstance(modifier_fields, dict):
        raise ValueError("priority_policy.modifier_fields must be object")

    modifiers: dict[str, Any] = {}
    for modifier_key, field_key in modifier_fields.items():
        modifiers[str(modifier_key)] = submitted_values.get(str(field_key))

    literal_modifiers = priority_policy.get("modifiers") or {}
    if isinstance(literal_modifiers, dict):
        modifiers.update(literal_modifiers)

    return compute_priority_from_facts(
        impact=submitted_values.get(impact_field, fallback.get("impact")) if impact_field else fallback.get("impact"),
        urgency=submitted_values.get(urgency_field, fallback.get("urgency")) if urgency_field else fallback.get("urgency"),
        importance=(
            submitted_values.get(importance_field, fallback.get("importance"))
            if importance_field
            else fallback.get("importance")
        ),
        modifiers=modifiers,
        source="system",
    )
