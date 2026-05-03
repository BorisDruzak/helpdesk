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
    "company": 3,
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
    "blocked": 3,
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

_IMPACT_BANDS = {
    0: "low_impact",
    1: "low_impact",
    2: "medium_impact",
    3: "high_impact",
}

_URGENCY_BANDS = {
    0: "low_urgency",
    1: "low_urgency",
    2: "medium_urgency",
    3: "high_urgency",
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


def _priority_after_delta(priority: str, delta: int) -> str:
    rank = min(max(_PRIORITY_RANK.get(priority, _PRIORITY_RANK["P3"]) + delta, 0), _PRIORITY_RANK["P3"])
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


def _normalize_priority(value: Any, *, field_name: str = "priority") -> str:
    priority = str(value or "").strip().upper()
    if priority not in PROCESS_PRIORITIES:
        raise ValueError(f"{field_name} must be one of P0, P1, P2, P3")
    return priority


def _matrix_priority(matrix: Any, impact_level: int, urgency_level: int, *, impact_raw: Any, urgency_raw: Any) -> str | None:
    if not isinstance(matrix, Mapping) or not matrix:
        return None
    impact_candidates = [
        str(impact_raw or "").strip(),
        str(impact_raw or "").strip().lower(),
        _IMPACT_BANDS.get(impact_level, "low_impact"),
        str(impact_level),
    ]
    urgency_candidates = [
        str(urgency_raw or "").strip(),
        str(urgency_raw or "").strip().lower(),
        _URGENCY_BANDS.get(urgency_level, "low_urgency"),
        str(urgency_level),
    ]
    for impact_key in impact_candidates:
        if not impact_key:
            continue
        row = matrix.get(impact_key)
        if not isinstance(row, Mapping):
            continue
        for urgency_key in urgency_candidates:
            if urgency_key and row.get(urgency_key):
                return _normalize_priority(row.get(urgency_key), field_name="matrix priority")
    return None


def _condition_matches(condition: Any, values: Mapping[str, Any]) -> bool:
    if not isinstance(condition, Mapping):
        return False
    for key, expected in condition.items():
        actual = values.get(str(key))
        if isinstance(expected, list):
            if actual not in expected and str(actual) not in {str(item) for item in expected}:
                return False
            continue
        if isinstance(expected, bool):
            if _is_truthy(actual) != expected:
                return False
            continue
        if str(actual).strip().lower() != str(expected).strip().lower():
            return False
    return True


def _apply_modifier_rule(priority: str, action: Mapping[str, Any]) -> str:
    result = priority
    if action.get("increase_priority_by") is not None:
        result = _priority_after_delta(result, -int(action.get("increase_priority_by") or 0))
    if action.get("decrease_priority_by") is not None:
        result = _priority_after_delta(result, int(action.get("decrease_priority_by") or 0))
    if action.get("minimum_priority") is not None:
        minimum = _normalize_priority(action.get("minimum_priority"), field_name="minimum_priority")
        if _PRIORITY_RANK[result] > _PRIORITY_RANK[minimum]:
            result = minimum
    if action.get("maximum_priority") is not None:
        maximum = _normalize_priority(action.get("maximum_priority"), field_name="maximum_priority")
        if _PRIORITY_RANK[result] < _PRIORITY_RANK[maximum]:
            result = maximum
    return result


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
    manual_override_event = None
    if manual_priority:
        manual_priority = _normalize_priority(manual_priority, field_name="manual_priority")
        if not str(manual_reason or "").strip():
            raise ValueError("manual_reason is required for manual priority override")
        old_effective_priority = effective_priority
        effective_priority = manual_priority
        priority_source = "support_override"
        manual_override_event = {
            "old_effective_priority": old_effective_priority,
            "new_effective_priority": effective_priority,
            "reason": str(manual_reason or "").strip(),
        }

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
        "manual_override_event": manual_override_event,
        "priority_explanation": {
            "summary": "Приоритет рассчитан по влиянию, срочности и признакам обращения.",
            "matched_modifiers": active_modifiers,
        },
    }


def compute_priority_from_policy(
    *,
    priority_policy: Mapping[str, Any],
    submitted_values: Mapping[str, Any],
    fallback: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute priority using a request-template priority_policy and submitted form values."""
    fallback = fallback or {}
    input_fields = priority_policy.get("input_fields") if isinstance(priority_policy.get("input_fields"), Mapping) else {}
    impact_field = str(priority_policy.get("impact_field") or input_fields.get("impact_field") or "").strip()
    urgency_field = str(priority_policy.get("urgency_field") or input_fields.get("urgency_field") or "").strip()
    importance_field = str(priority_policy.get("importance_field") or input_fields.get("importance_field") or "").strip()
    modifier_fields = priority_policy.get("modifier_fields") or {}
    if modifier_fields and not isinstance(modifier_fields, dict):
        raise ValueError("priority_policy.modifier_fields must be object")

    impact_value = submitted_values.get(impact_field, fallback.get("impact")) if impact_field else fallback.get("impact")
    urgency_value = submitted_values.get(urgency_field, fallback.get("urgency")) if urgency_field else fallback.get("urgency")
    importance_value = (
        submitted_values.get(importance_field, fallback.get("importance"))
        if importance_field
        else fallback.get("importance")
    )
    modifiers: dict[str, Any] = {}
    for modifier_key, field_key in modifier_fields.items():
        modifiers[str(modifier_key)] = submitted_values.get(str(field_key))

    literal_modifiers = priority_policy.get("modifiers") or {}
    if isinstance(literal_modifiers, dict):
        modifiers.update(literal_modifiers)

    source = "priority_policy" if isinstance(priority_policy.get("matrix"), Mapping) or isinstance(literal_modifiers, list) else "system"
    result = compute_priority_from_facts(
        impact=impact_value,
        urgency=urgency_value,
        importance=importance_value,
        modifiers=modifiers,
        source=source,
    )

    matrix_priority = _matrix_priority(
        priority_policy.get("matrix"),
        int(result["impact"]),
        int(result["urgency"]),
        impact_raw=impact_value,
        urgency_raw=urgency_value,
    )
    if matrix_priority:
        result["computed_priority"] = matrix_priority
        result["effective_priority"] = matrix_priority
        result["priority_class"] = matrix_priority
        result["legacy_priority"] = PRIORITY_CLASS_TO_LEGACY_PRIORITY[matrix_priority]
        result["priority_source"] = "priority_policy"

    applied_rule_labels: list[str] = []
    if isinstance(literal_modifiers, list):
        values = dict(submitted_values)
        if impact_field:
            values.setdefault(impact_field, impact_value)
        if urgency_field:
            values.setdefault(urgency_field, urgency_value)
        if importance_field:
            values.setdefault(importance_field, importance_value)
        for index, raw_rule in enumerate(literal_modifiers):
            if not isinstance(raw_rule, Mapping):
                continue
            if not _condition_matches(raw_rule.get("condition") or raw_rule.get("when"), values):
                continue
            action = raw_rule.get("action") if isinstance(raw_rule.get("action"), Mapping) else raw_rule
            before = result["effective_priority"]
            result["effective_priority"] = _apply_modifier_rule(str(result["effective_priority"]), action)
            result["priority_class"] = result["effective_priority"]
            result["legacy_priority"] = PRIORITY_CLASS_TO_LEGACY_PRIORITY[result["effective_priority"]]
            label = str(raw_rule.get("label") or raw_rule.get("name") or raw_rule.get("code") or f"modifier_{index + 1}")
            if before != result["effective_priority"] or label:
                applied_rule_labels.append(label)

    if applied_rule_labels:
        result["applied_modifiers"] = applied_rule_labels

    manual_priority = fallback.get("manual_priority")
    manual_reason = fallback.get("manual_reason") or fallback.get("manual_priority_reason")
    if manual_priority:
        manual_override = priority_policy.get("manual_override") if isinstance(priority_policy.get("manual_override"), Mapping) else {}
        actor_role = str(fallback.get("manual_actor_role") or fallback.get("actor_role") or "").strip()
        allowed_roles = manual_override.get("allowed_roles") if isinstance(manual_override.get("allowed_roles"), list) else []
        if allowed_roles and actor_role not in {str(item) for item in allowed_roles}:
            raise ValueError("manual priority override is not allowed for this role")
        if bool(manual_override.get("require_reason", True)) and not str(manual_reason or "").strip():
            raise ValueError("manual_reason is required for manual priority override")
        old_effective = str(result["effective_priority"])
        manual_priority = _normalize_priority(manual_priority, field_name="manual_priority")
        result["manual_priority"] = manual_priority
        result["manual_priority_reason"] = str(manual_reason or "").strip() or None
        result["effective_priority"] = manual_priority
        result["priority_class"] = manual_priority
        result["legacy_priority"] = PRIORITY_CLASS_TO_LEGACY_PRIORITY[manual_priority]
        result["priority_source"] = "support_override"
        if manual_override.get("log_event", True):
            result["manual_override_event"] = {
                "old_effective_priority": old_effective,
                "new_effective_priority": manual_priority,
                "actor_role": actor_role,
                "reason": str(manual_reason or "").strip(),
            }

    result["priority_reason"] = (
        f"impact={result['impact']}; urgency={result['urgency']}; importance={result['importance']}; "
        f"computed={result['computed_priority']}"
    )
    if result.get("applied_modifiers"):
        result["priority_reason"] += "; modifiers=" + ",".join(str(item) for item in result["applied_modifiers"])
    if result.get("manual_priority"):
        result["priority_reason"] += "; manual_override=" + str(result["manual_priority"])
    result["priority_explanation"] = {
        "summary": (
            "Приоритет рассчитан по матрице влияния и срочности."
            if matrix_priority
            else "Приоритет рассчитан по влиянию, срочности и признакам обращения."
        ),
        "matched_modifiers": result.get("applied_modifiers") or [],
        "source": result.get("priority_source"),
    }
    return result
