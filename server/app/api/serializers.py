"""Helpers for serializing ticket-domain objects into API payloads."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from tickets.public_access import (
    build_public_access_url,
    is_public_unbound_ticket,
    public_access_code_hint,
)
from tickets.statuses import (
    compute_effective_priority,
    extract_priority_class,
    get_requester_display_name,
    get_requester_profile,
    requester_status_for_internal,
    requester_status_label_ru,
    requires_operator_action,
    status_label_ru,
)
from tickets.visibility_policy import apply_ticket_visibility_payload


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def serialize_datetime_recursive(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: serialize_datetime_recursive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serialize_datetime_recursive(item) for item in value]
    return value


def _queue_code_from_ticket(ticket: Any, queue_code: Optional[str] = None) -> Optional[str]:
    if queue_code:
        return queue_code
    queue_rel = getattr(ticket, "queue", None)
    if queue_rel is not None:
        code = getattr(queue_rel, "code", None)
        if code:
            return str(code)
    return None


def ticket_to_dict(
    ticket: Any,
    queue_code: Optional[str] = None,
    *,
    visibility: str = "support",
) -> Dict[str, Any]:
    priority_class = extract_priority_class(ticket)
    created_at = getattr(ticket, "created_at", None)
    custom_fields = serialize_datetime_recursive(getattr(ticket, "custom_fields", None) or {})
    base: Dict[str, Any] = {
        "ticket_id": getattr(ticket, "ticket_id", None),
        "ticket_code": getattr(ticket, "ticket_code", None),
        "device_id": getattr(ticket, "device_id", None),
        "title": getattr(ticket, "title", None),
        "description": getattr(ticket, "description", None),
        "status": getattr(ticket, "status", None),
        "status_label": status_label_ru(getattr(ticket, "status", None)),
        "requester_status": getattr(ticket, "requester_status", None)
        or requester_status_for_internal(getattr(ticket, "status", None)),
        "requester_status_label": requester_status_label_ru(
            getattr(ticket, "requester_status", None)
            or requester_status_for_internal(getattr(ticket, "status", None))
        ),
        "next_action_owner": getattr(ticket, "next_action_owner", None)
        or ("requester" if getattr(ticket, "status", None) == "waiting_on_user" else "support"),
        "next_action_due_at": _iso(getattr(ticket, "next_action_due_at", None)),
        "status_reason": getattr(ticket, "status_reason", None),
        "created_at": _iso(created_at),
        "updated_at": _iso(getattr(ticket, "updated_at", None)),
        "archived_at": _iso(getattr(ticket, "archived_at", None)),
        "queue_id": getattr(ticket, "queue_id", None),
        "queue_code": _queue_code_from_ticket(ticket, queue_code=queue_code),
        "assignee_id": getattr(ticket, "assignee_id", None),
        "requester_id": getattr(ticket, "requester_id", None),
        "ticket_type": getattr(ticket, "ticket_type", None),
        "priority": getattr(ticket, "priority", None),
        "priority_class": priority_class,
        "effective_priority": compute_effective_priority(priority_class, getattr(ticket, "status", None), created_at),
        "impact": getattr(ticket, "impact", None),
        "urgency": getattr(ticket, "urgency", None),
        "importance": getattr(ticket, "importance", None),
        "urgency_reason": getattr(ticket, "urgency_reason", None),
        "importance_reason": getattr(ticket, "importance_reason", None),
        "first_response_due_at": _iso(getattr(ticket, "first_response_due_at", None)),
        "resolution_due_at": _iso(getattr(ticket, "resolution_due_at", None)),
        "first_response_at": _iso(getattr(ticket, "first_response_at", None)),
        "resolution_at": _iso(getattr(ticket, "resolution_at", None)),
        "first_response_breached_at": _iso(getattr(ticket, "first_response_breached_at", None)),
        "resolution_breached_at": _iso(getattr(ticket, "resolution_breached_at", None)),
        "sla_paused_at": _iso(getattr(ticket, "sla_paused_at", None)),
        "sla_paused_seconds": getattr(ticket, "sla_paused_seconds", None),
        "resolved_at": _iso(getattr(ticket, "resolved_at", None)),
        "closed_at": _iso(getattr(ticket, "closed_at", None)),
        "canceled_at": _iso(getattr(ticket, "canceled_at", None)),
        "reopen_count": getattr(ticket, "reopen_count", None),
        "category_id": getattr(ticket, "category_id", None),
        "service_id": getattr(ticket, "service_id", None),
        "subcategory_id": getattr(ticket, "subcategory_id", None),
        "resolution_code": getattr(ticket, "resolution_code", None),
        "resolution_summary": getattr(ticket, "resolution_summary", None),
        "requester_resolution_summary": getattr(ticket, "requester_resolution_summary", None),
        "evidence_required": bool(getattr(ticket, "evidence_required", False)),
        "evidence_ref": getattr(ticket, "evidence_ref", None),
        "closure_feedback": serialize_datetime_recursive(getattr(ticket, "closure_feedback", None) or {}),
        "root_cause": getattr(ticket, "root_cause", None),
        "parent_ticket_id": getattr(ticket, "parent_ticket_id", None),
        "manual_rank": getattr(ticket, "manual_rank", None),
        "manual_rank_updated_at": _iso(getattr(ticket, "manual_rank_updated_at", None)),
        "manual_rank_updated_by": getattr(ticket, "manual_rank_updated_by", None),
        "custom_fields": custom_fields,
        "requester_profile": get_requester_profile(ticket),
        "requester_display_name": get_requester_display_name(ticket),
        "requires_operator_action": requires_operator_action(getattr(ticket, "status", None)),
        "public_access_code_hint": public_access_code_hint(ticket),
        "public_access_url": build_public_access_url(getattr(ticket, "ticket_id", None)),
        "public_ticket_unbound": is_public_unbound_ticket(ticket),
        "resolution_confirmation_pending": bool(custom_fields.get("resolution_confirmation_pending")),
        "tags": serialize_datetime_recursive(getattr(ticket, "tags", None) or []),
    }
    return apply_ticket_visibility_payload(ticket, base, visibility=visibility)
