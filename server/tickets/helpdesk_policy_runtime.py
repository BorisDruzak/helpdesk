"""Runtime bridge from standalone helpdesk policy registry to ticket context."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.db.models import TicketSlaPolicy
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo


RUNTIME_POLICY_KINDS = (
    "priority",
    "sla",
    "ola",
    "routing",
    "approval",
    "closure",
    "diagnostic",
    "notification",
    "visibility",
)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def apply_effective_registry_policies(
    session: Any,
    validated_submission: dict[str, Any],
) -> dict[str, Any]:
    """Overlay effective registry policies onto a validated form submission.

    Existing form-pack metadata remains the fallback. Active standalone registry
    policies for system/ticket_type/category/request_template scopes override it
    before priority, routing, SLA/OLA and other runtime services read
    `custom_fields.request_template`.
    """
    template_context = deepcopy(validated_submission.get("template_context") or {})
    template_code = str(template_context.get("key") or validated_submission.get("form_key") or "").strip()
    ticket_type = str(template_context.get("ticket_type") or validated_submission.get("ticket_type") or "").strip()
    category_id = template_context.get("category_id")

    repo = HelpdeskPolicyRepo(session)
    sources: dict[str, list[dict[str, Any]]] = {}
    for kind in RUNTIME_POLICY_KINDS:
        effective = await repo.resolve_effective_policy(
            kind=kind,
            ticket_type=ticket_type or None,
            category_id=category_id,
            template_code=template_code or None,
        )
        config = effective.get("config") if isinstance(effective, dict) else {}
        if not isinstance(config, dict) or not config:
            continue
        field_name = f"{kind}_policy"
        existing = template_context.get(field_name) if isinstance(template_context.get(field_name), dict) else {}
        template_context[field_name] = _deep_merge(existing, config)
        source_rows = effective.get("sources") if isinstance(effective.get("sources"), list) else []
        if source_rows:
            sources[kind] = source_rows

    sla_policy = template_context.get("sla_policy")
    if isinstance(sla_policy, dict):
        sla_policy_id = _as_int(sla_policy.get("sla_policy_id") or sla_policy.get("legacy_sla_policy_id"))
        if sla_policy_id is not None and await session.get(TicketSlaPolicy, sla_policy_id) is not None:
            template_context["sla_policy_id"] = sla_policy_id

    if sources:
        template_context["effective_policy_sources"] = sources

    result = deepcopy(validated_submission)
    result["template_context"] = template_context
    return result
