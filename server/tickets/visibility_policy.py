"""Executable visibility policy helpers for request templates."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tickets.statuses import requester_status_for_internal, requester_status_label_ru

DEFAULT_HIDE_FROM_REQUESTER = {
    "internal_notes",
    "internal_queue_comments",
    "latest_operations",
    "ola",
    "ola_details",
    "queue_members",
    "watchers",
    "assignable_users",
    "available_queues",
    "provisioning_summary",
    "raw_diagnostics",
    "root_cause",
    "update_summary",
    "worklog_totals",
    "worklogs",
}


def get_template_visibility_policy(ticket: Any) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    if not isinstance(request_template, dict):
        return {}
    policy = request_template.get("visibility_policy") or {}
    return policy if isinstance(policy, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _public_status_mapping(policy: dict[str, Any]) -> dict[str, Any]:
    mapping = policy.get("public_status_mapping") or policy.get("public_statuses") or {}
    return mapping if isinstance(mapping, dict) else {}


def _resolve_mapping_entry(entry: Any, requester_status: str) -> tuple[str, str] | None:
    if isinstance(entry, dict):
        public_status = str(entry.get("status") or entry.get("code") or requester_status).strip() or requester_status
        label = str(entry.get("label") or entry.get("title") or public_status).strip()
        return public_status, label
    if entry is not None:
        label = str(entry).strip()
        if label:
            return requester_status, label
    return None


def resolve_public_status(ticket: Any) -> dict[str, str]:
    internal_status = str(getattr(ticket, "status", None) or "").strip()
    derived_requester_status = requester_status_for_internal(internal_status)
    stored_requester_status = str(getattr(ticket, "requester_status", None) or "").strip()
    if stored_requester_status and (stored_requester_status != "accepted" or derived_requester_status == "accepted"):
        requester_status = stored_requester_status
    else:
        requester_status = derived_requester_status
    policy = get_template_visibility_policy(ticket)
    mapping = _public_status_mapping(policy)
    mapped = None
    if mapping:
        mapped = _resolve_mapping_entry(mapping.get(internal_status), requester_status)
        if mapped is None:
            mapped = _resolve_mapping_entry(mapping.get(requester_status), requester_status)
    if mapped is None:
        mapped = (requester_status, requester_status_label_ru(requester_status))
    return {
        "public_status": mapped[0],
        "public_status_label": mapped[1],
    }


def build_visibility_metadata(ticket: Any) -> dict[str, Any]:
    policy = get_template_visibility_policy(ticket)
    hide = sorted(DEFAULT_HIDE_FROM_REQUESTER | set(_string_list(policy.get("hide_from_requester"))))
    show = _string_list(policy.get("show_to_requester"))
    support_fields = _string_list(policy.get("show_to_support") or policy.get("support_fields"))
    return {
        "source": "request_template.visibility_policy" if policy else "default",
        "hidden_from_requester": hide,
        "requester_visible_fields": show,
        "support_visible_fields": support_fields,
    }


def apply_ticket_visibility_payload(
    ticket: Any,
    payload: dict[str, Any],
    *,
    visibility: str,
) -> dict[str, Any]:
    result = deepcopy(payload)
    public_status = resolve_public_status(ticket)
    metadata = build_visibility_metadata(ticket)
    result.update(public_status)
    result["visibility"] = {
        "source": metadata["source"],
        "hidden_from_requester": metadata["hidden_from_requester"],
    }
    result["requester_visible_fields"] = metadata["requester_visible_fields"]
    result["support_visible_fields"] = metadata["support_visible_fields"]

    if str(visibility or "").lower() in {"requester", "public", "user"}:
        for key in metadata["hidden_from_requester"]:
            result.pop(key, None)
    return result
