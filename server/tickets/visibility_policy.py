"""Executable visibility policy helpers for request templates."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
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
    "custom_fields.request_template",
}

REQUESTER_SAFE_TICKET_FIELDS = {
    "ticket_id",
    "ticket_code",
    "title",
    "description",
    "status",
    "status_label",
    "requester_status",
    "requester_status_label",
    "public_status",
    "public_status_label",
    "next_action_owner",
    "next_action_due_at",
    "status_reason",
    "created_at",
    "updated_at",
    "queue_code",
    "ticket_type",
    "first_response_due_at",
    "resolution_due_at",
    "first_response_at",
    "resolution_at",
    "resolved_at",
    "closed_at",
    "canceled_at",
    "reopen_count",
    "requester_resolution_summary",
    "closure_feedback",
    "requester_profile",
    "requester_display_name",
    "requires_operator_action",
    "public_access_code_hint",
    "public_access_url",
    "public_ticket_unbound",
    "resolution_confirmation_pending",
    "tags",
    "visibility",
    "requester_visible_fields",
    "support_visible_fields",
    "chat_counters",
    "presence",
    "actor_role",
    "actions",
    "events",
    "history",
    "last_event_id",
    "relations",
}

REQUESTER_SAFE_CUSTOM_FIELD_KEYS = {
    "request_kind",
    "request_form_pack_key",
    "request_form_version",
    "request_form_key",
    "request_form_title",
    "request_form",
    "resolved_from",
    "resolved_pack_key",
    "resolved_pack_version",
    "resolved_template_key",
    "resolved_template_version",
    "resolved_form_schema_id",
    "resolved_form_schema_version",
    "request_form_data",
    "request_form_summary",
}

REQUESTER_FORBIDDEN_CUSTOM_FIELD_ROOTS = {
    "approval_runtime",
    "diagnostic_consent",
    "diagnostic_result",
    "diagnostics",
    "knowledge_attempts",
    "ola_runtime",
    "priority_decision",
    "public_access",
    "request_template",
    "requester_account_context",
    "resolution_confirmation_policy",
    "routing_decision",
    "ticket_context",
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


def _resolve_public_status_with_policy(ticket: Any, policy: dict[str, Any]) -> dict[str, str]:
    internal_status = str(getattr(ticket, "status", None) or "").strip()
    derived_requester_status = requester_status_for_internal(internal_status)
    stored_requester_status = str(getattr(ticket, "requester_status", None) or "").strip()
    if stored_requester_status and (stored_requester_status != "accepted" or derived_requester_status == "accepted"):
        requester_status = stored_requester_status
    else:
        requester_status = derived_requester_status
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


def resolve_public_status(ticket: Any) -> dict[str, str]:
    return _resolve_public_status_with_policy(ticket, get_template_visibility_policy(ticket))


def _build_visibility_metadata_with_policy(
    policy: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    hide = sorted(DEFAULT_HIDE_FROM_REQUESTER | set(_string_list(policy.get("hide_from_requester"))))
    show = _string_list(policy.get("show_to_requester"))
    support_fields = _string_list(policy.get("show_to_support") or policy.get("support_fields"))
    return {
        "source": source if policy else "default",
        "hidden_from_requester": hide,
        "requester_visible_fields": show,
        "support_visible_fields": support_fields,
    }


def _remove_path(payload: dict[str, Any], path: str) -> None:
    parts = [part for part in str(path or "").split(".") if part]
    if not parts:
        return
    current: Any = payload
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return
        current = current.get(part)
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _prune_requester_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return an explicit requester/public allowlist projection."""

    if "ticket_id" not in payload and "ticket_code" not in payload:
        return payload
    custom_fields = _requester_custom_fields_projection(payload)
    pruned = {key: value for key, value in payload.items() if key in REQUESTER_SAFE_TICKET_FIELDS}
    if custom_fields:
        pruned["custom_fields"] = custom_fields
    visibility = pruned.get("visibility")
    if isinstance(visibility, dict):
        pruned["visibility"] = {
            "source": visibility.get("source") or "default",
            "requester_safe": True,
        }
    return pruned


def _copy_nested_field(source: dict[str, Any], target: dict[str, Any], parts: list[str]) -> None:
    if not parts or parts[0] in REQUESTER_FORBIDDEN_CUSTOM_FIELD_ROOTS:
        return
    current: Any = source
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return
        current = current.get(part)
    cursor = target
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = deepcopy(current)


def _requester_custom_fields_projection(payload: dict[str, Any]) -> dict[str, Any]:
    custom_fields = payload.get("custom_fields")
    if not isinstance(custom_fields, dict):
        return {}

    result = {
        key: deepcopy(custom_fields[key])
        for key in REQUESTER_SAFE_CUSTOM_FIELD_KEYS
        if key in custom_fields
    }
    for field in _string_list(payload.get("requester_visible_fields")):
        parts = [part for part in field.split(".") if part]
        if len(parts) >= 2 and parts[0] == "custom_fields":
            _copy_nested_field(custom_fields, result, parts[1:])
    return result


def build_visibility_metadata(ticket: Any) -> dict[str, Any]:
    policy = get_template_visibility_policy(ticket)
    return _build_visibility_metadata_with_policy(
        policy,
        source="request_template.visibility_policy",
    )


def _apply_visibility_payload_with_policy(
    ticket: Any,
    payload: dict[str, Any],
    *,
    visibility: str,
    policy: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    result = deepcopy(payload)
    public_status = _resolve_public_status_with_policy(ticket, policy)
    metadata = _build_visibility_metadata_with_policy(policy, source=source)
    result.update(public_status)
    result["visibility"] = {
        "source": metadata["source"],
        "hidden_from_requester": metadata["hidden_from_requester"],
    }
    result["requester_visible_fields"] = metadata["requester_visible_fields"]
    result["support_visible_fields"] = metadata["support_visible_fields"]

    if str(visibility or "").lower() in {"requester", "public", "user"}:
        for key in metadata["hidden_from_requester"]:
            _remove_path(result, key)
        result = _prune_requester_payload(result)
    return result


def apply_ticket_visibility_payload(
    ticket: Any,
    payload: dict[str, Any],
    *,
    visibility: str,
) -> dict[str, Any]:
    return _apply_visibility_payload_with_policy(
        ticket,
        payload,
        visibility=visibility,
        policy=get_template_visibility_policy(ticket),
        source="request_template.visibility_policy",
    )


async def apply_ticket_visibility_payload_async(
    session: Any,
    ticket: Any,
    payload: dict[str, Any],
    *,
    visibility: str,
) -> dict[str, Any]:
    snapshot_policy = get_template_visibility_policy(ticket)
    policy = await resolve_effective_ticket_policy(session, ticket, "visibility")
    source = (
        "effective.visibility_policy"
        if policy and policy != snapshot_policy
        else "request_template.visibility_policy"
    )
    return _apply_visibility_payload_with_policy(
        ticket,
        payload,
        visibility=visibility,
        policy=policy,
        source=source,
    )
