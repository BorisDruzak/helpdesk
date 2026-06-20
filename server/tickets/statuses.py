"""Canonical ticket statuses and common ticket-domain helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


CANONICAL_STATUSES = (
    "new",
    "queued",
    "assigned",
    "in_progress",
    "waiting_on_user",
    "waiting_on_internal_team",
    "waiting_on_vendor",
    "waiting_on_approval",
    "scheduled",
    "resolved",
    "closed",
    "canceled",
)

WAITING_STATUSES = {
    "waiting_on_user",
    "waiting_on_internal_team",
    "waiting_on_vendor",
    "waiting_on_approval",
}
TERMINAL_STATUSES = {"resolved", "closed", "canceled"}
ACTIVE_OPERATOR_STATUSES = {"assigned", "in_progress"}
ACTION_REQUIRED_STATUSES = {"new", "queued", "assigned", "in_progress"}
PUBLIC_VISIBLE_STATUSES = CANONICAL_STATUSES

STATUS_LABELS_RU = {
    "new": "Новая",
    "queued": "В очереди",
    "assigned": "Назначена",
    "in_progress": "В работе",
    "waiting_on_user": "Ожидает пользователя",
    "waiting_on_internal_team": "Ожидает внутреннюю группу",
    "waiting_on_vendor": "Ожидает внешнюю сторону",
    "waiting_on_approval": "Ожидает согласование",
    "scheduled": "Запланирована",
    "resolved": "Решена",
    "closed": "Закрыта",
    "canceled": "Отменена",
}

REQUESTER_STATUS_LABELS_RU = {
    "accepted": "Обращение принято",
    "in_work": "Обращение в работе",
    "needs_requester": "Нужен ваш ответ",
    "review_solution": "Проверьте решение",
    "closed": "Закрыто",
    "canceled": "Отменено",
}

LEGACY_STATUS_ALIASES = {
    "new ticket": "new",
    "new_request": "new",
    "newrequest": "new",
    "triaged": "queued",
    "queue": "queued",
    "in progress": "in_progress",
    "in-progress": "in_progress",
    "open": "in_progress",
    "waiting on user": "waiting_on_user",
    "waiting-for-user": "waiting_on_user",
    "waiting_user": "waiting_on_user",
    "waiting on internal team": "waiting_on_internal_team",
    "waiting_internal": "waiting_on_internal_team",
    "waiting on vendor": "waiting_on_vendor",
    "waiting_vendor": "waiting_on_vendor",
    "waiting on approval": "waiting_on_approval",
    "waiting_approval": "waiting_on_approval",
    "cancelled": "canceled",
}
_NORMALIZE_MAP = {status: status for status in CANONICAL_STATUSES}
_NORMALIZE_MAP.update(LEGACY_STATUS_ALIASES)

WAIT_STATUS_TO_TYPE = {
    "waiting_on_user": "user",
    "waiting_on_internal_team": "internal_team",
    "waiting_on_vendor": "vendor",
    "waiting_on_approval": "approval",
}

PRIORITY_CLASS_TO_LEGACY_PRIORITY = {
    "P0": "P1",
    "P1": "P2",
    "P2": "P3",
    "P3": "P4",
}

PRIORITY_CLASS_TO_FLAGS: dict[str, tuple[bool, bool]] = {
    "P0": (True, True),
    "P1": (True, False),
    "P2": (False, True),
    "P3": (False, False),
}

PRIORITY_CLASS_BASE_SCORE = {
    "P0": 4_000_000,
    "P1": 3_000_000,
    "P2": 2_000_000,
    "P3": 1_000_000,
}

WAITING_STATUS_PENALTY = 500_000

REQUESTER_PROFILE_FIELDS = ("full_name", "building", "room", "phone")


def normalize_status_for_input(raw_status: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normalize boundary input and report whether it used a legacy alias."""

    raw_value = raw_status if isinstance(raw_status, str) else None
    canonical, was_legacy = normalize_status(raw_status)
    if canonical is None:
        raise ValueError(f"invalid ticket status: {raw_status!r}")
    return {
        "status": canonical,
        "canonical_value": canonical,
        "raw_value": raw_value,
        "was_legacy": was_legacy,
        "context": context or {},
    }


def assert_canonical_status(status: str) -> str:
    if status not in CANONICAL_STATUSES:
        raise ValueError(f"{status!r} is not a canonical ticket status")
    return status


def normalize_status(raw: str) -> Tuple[Optional[str], bool]:
    if not raw or not isinstance(raw, str):
        return None, False
    s = raw.strip()
    if not s:
        return None, False
    if s in CANONICAL_STATUSES:
        return s, False
    key = s.lower()
    canonical = _NORMALIZE_MAP.get(key)
    if canonical is not None:
        return canonical, canonical != s
    return None, False


def is_valid_canonical_status(status: str) -> bool:
    return status in CANONICAL_STATUSES


def resolve_status(raw: str, fsm_mode: str = "soft") -> Tuple[Optional[str], bool]:
    if not raw or not isinstance(raw, str):
        return None, False
    s = raw.strip()
    if not s:
        return None, False
    if fsm_mode == "strict":
        if s in CANONICAL_STATUSES:
            return s, False
        return None, False
    return normalize_status(raw)


def is_waiting_status(status: Optional[str]) -> bool:
    return (status or "") in WAITING_STATUSES


def is_terminal_status(status: Optional[str]) -> bool:
    return (status or "") in TERMINAL_STATUSES


def is_active_operator_status(status: Optional[str]) -> bool:
    return (status or "") in ACTIVE_OPERATOR_STATUSES


def requires_operator_action(status: Optional[str]) -> bool:
    return (status or "") in ACTION_REQUIRED_STATUSES


def requester_status_for_internal(status: Optional[str]) -> str:
    if status in {"new", "queued", "assigned"}:
        return "accepted"
    if status == "waiting_on_user":
        return "needs_requester"
    if status == "resolved":
        return "review_solution"
    if status == "closed":
        return "closed"
    if status == "canceled":
        return "canceled"
    return "in_work"


def requester_status_label_ru(requester_status: Optional[str]) -> str:
    if not requester_status:
        return "Не указан"
    return REQUESTER_STATUS_LABELS_RU.get(requester_status, requester_status)


def requester_status_label_for_internal(status: Optional[str]) -> str:
    return requester_status_label_ru(requester_status_for_internal(status))


def next_action_owner_for_status(status: Optional[str]) -> str:
    if status == "waiting_on_user":
        return "requester"
    if status == "waiting_on_internal_team":
        return "internal_team"
    if status == "waiting_on_vendor":
        return "vendor"
    if status == "waiting_on_approval":
        return "approver"
    if status == "resolved":
        return "requester"
    if status in {"closed", "canceled"}:
        return "system"
    return "support"


def wait_type_for_status(status: Optional[str]) -> Optional[str]:
    return WAIT_STATUS_TO_TYPE.get(status or "")


def status_label_ru(status: Optional[str]) -> str:
    if not status:
        return "Не указан"
    canonical, _ = normalize_status(status)
    if canonical:
        return STATUS_LABELS_RU.get(canonical, canonical)
    return STATUS_LABELS_RU.get(status, status)


def normalize_boolish(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "urgent", "important"}:
            return True
        if normalized in {"false", "0", "no", "n", "not_urgent", "not_important"}:
            return False
    raise ValueError(f"{field_name} must be boolean")


def priority_class_from_flags(urgency: bool, importance: bool) -> str:
    if urgency and importance:
        return "P0"
    if urgency and not importance:
        return "P1"
    if not urgency and importance:
        return "P2"
    return "P3"


def normalize_ticket_priority_inputs(
    urgency: Any,
    importance: Any,
    urgency_reason: Any = None,
    importance_reason: Any = None,
) -> Dict[str, Any]:
    urgency_bool = normalize_boolish(urgency, "urgency")
    importance_bool = normalize_boolish(importance, "importance")
    urgency_reason_clean = str(urgency_reason or "").strip()
    importance_reason_clean = str(importance_reason or "").strip()
    if not urgency_reason_clean:
        raise ValueError("urgency_reason is required")
    if not importance_reason_clean:
        raise ValueError("importance_reason is required")
    if len(urgency_reason_clean) > 500:
        raise ValueError("urgency_reason must be at most 500 characters")
    if len(importance_reason_clean) > 500:
        raise ValueError("importance_reason must be at most 500 characters")
    priority_class = priority_class_from_flags(urgency_bool, importance_bool)
    return {
        "urgency": 1 if urgency_bool else 0,
        "importance": 1 if importance_bool else 0,
        "urgency_reason": urgency_reason_clean,
        "importance_reason": importance_reason_clean,
        "priority_class": priority_class,
        "legacy_priority": PRIORITY_CLASS_TO_LEGACY_PRIORITY[priority_class],
    }


def default_create_priority_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    urgency = data.get("urgency")
    importance = data.get("importance")
    urgency_reason = str(data.get("urgency_reason") or "").strip()
    importance_reason = str(data.get("importance_reason") or "").strip()
    if urgency is None or importance is None:
        urgency = False
        importance = False
    if not urgency_reason:
        urgency_reason = "Not specified during ticket create"
    if not importance_reason:
        importance_reason = "Not specified during ticket create"
    return normalize_ticket_priority_inputs(urgency, importance, urgency_reason, importance_reason)


def extract_priority_class(ticket: Any) -> str:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if isinstance(custom_fields, dict):
        priority_class = custom_fields.get("priority_class")
        if priority_class in PRIORITY_CLASS_BASE_SCORE:
            return priority_class
    priority = getattr(ticket, "priority", None)
    reverse_map = {v: k for k, v in PRIORITY_CLASS_TO_LEGACY_PRIORITY.items()}
    return reverse_map.get(priority, "P3")


def compute_effective_priority(priority_class: str, status: Optional[str], created_at: Optional[datetime]) -> int:
    score = PRIORITY_CLASS_BASE_SCORE.get(priority_class, PRIORITY_CLASS_BASE_SCORE["P3"])
    if is_waiting_status(status):
        score -= WAITING_STATUS_PENALTY
    if created_at:
        age_seconds = max(int((datetime.now(timezone.utc) - created_at).total_seconds()), 0)
        score += min(age_seconds // 3600, 499_999)
    return score


def normalize_requester_profile(raw_profile: Any) -> Dict[str, Optional[str]]:
    if raw_profile is None:
        return {field: None for field in REQUESTER_PROFILE_FIELDS}
    if not isinstance(raw_profile, dict):
        raise ValueError("requester_profile must be an object")
    profile: Dict[str, Optional[str]] = {}
    for field in REQUESTER_PROFILE_FIELDS:
        value = raw_profile.get(field)
        if value is None:
            profile[field] = None
            continue
        if not isinstance(value, str):
            raise ValueError(f"requester_profile.{field} must be string")
        cleaned = value.strip()
        profile[field] = cleaned or None
    return profile


def merge_requester_custom_fields(
    current_custom_fields: Any,
    *,
    user_display_name: Optional[str] = None,
    requester_profile: Optional[Dict[str, Optional[str]]] = None,
    priority_class: Optional[str] = None,
) -> Dict[str, Any]:
    merged = dict(current_custom_fields or {})
    if user_display_name is not None:
        merged["user_display_name"] = user_display_name.strip() or None
    if requester_profile is not None:
        merged["requester_profile"] = requester_profile
    if priority_class is not None:
        merged["priority_class"] = priority_class
    return merged


def get_requester_profile(ticket: Any) -> Dict[str, Optional[str]]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    raw_profile = custom_fields.get("requester_profile") if isinstance(custom_fields, dict) else None
    try:
        return normalize_requester_profile(raw_profile)
    except ValueError:
        return {field: None for field in REQUESTER_PROFILE_FIELDS}


def get_requester_display_name(ticket: Any) -> Optional[str]:
    profile = get_requester_profile(ticket)
    if profile.get("full_name"):
        return profile["full_name"]
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if isinstance(custom_fields, dict):
        user_display_name = str(custom_fields.get("user_display_name") or "").strip()
        if user_display_name:
            return user_display_name
    requester_id = str(getattr(ticket, "requester_id", "") or "").strip()
    return requester_id or None


REQUESTER_MESSAGE_ROLES = {"user", "agent", "requester", "device"}


def enrich_chat_payload_with_requester_name(ticket: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    sender_role = str(
        payload.get("from_role")
        or payload.get("sender_role")
        or payload.get("from")
        or payload.get("actor_role")
        or payload.get("role")
        or ""
    ).strip().lower()
    if sender_role not in REQUESTER_MESSAGE_ROLES:
        return payload
    requester_name = get_requester_display_name(ticket)
    if not requester_name:
        return payload
    enriched = dict(payload)
    enriched.setdefault("sender_display_name", requester_name)
    enriched.setdefault("requester_display_name", requester_name)
    return enriched
