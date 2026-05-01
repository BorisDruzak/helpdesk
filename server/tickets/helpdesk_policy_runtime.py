"""Runtime bridge from standalone helpdesk policy registry to ticket context."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

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
    "reporting",
)

POLICY_SNAPSHOT_FIELDS = {
    "notification": ("notification_policy", "notifications"),
}


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


def _request_template_context_from_ticket(ticket: Any) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    return deepcopy(request_template) if isinstance(request_template, dict) else {}


def _snapshot_policy_from_ticket(
    ticket: Any,
    kind: str,
    *,
    snapshot_fields: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    request_template = _request_template_context_from_ticket(ticket)
    fields = snapshot_fields or POLICY_SNAPSHOT_FIELDS.get(kind, (f"{kind}_policy",))
    policy: dict[str, Any] = {}
    for field_name in fields:
        value = request_template.get(field_name)
        if isinstance(value, dict):
            policy = _deep_merge(policy, value)
    return policy


async def resolve_effective_ticket_policy(
    session: Any,
    ticket: Any,
    kind: str,
    *,
    snapshot_fields: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Resolve a policy for an existing ticket lifecycle action.

    The ticket snapshot remains the fallback for old tickets and already
    persisted forms. Active standalone registry policies override it so
    published policy changes affect transitions, notifications and other
    lifecycle runtime checks.
    """
    if ticket is None:
        return {}

    request_template = _request_template_context_from_ticket(ticket)
    policy = _snapshot_policy_from_ticket(ticket, kind, snapshot_fields=snapshot_fields)
    if not isinstance(session, AsyncSession):
        return policy

    template_code = str(
        request_template.get("key")
        or request_template.get("template_code")
        or request_template.get("request_kind")
        or request_template.get("form_key")
        or ""
    ).strip()
    ticket_type = str(
        request_template.get("ticket_type")
        or getattr(ticket, "ticket_type", None)
        or ""
    ).strip()
    category_id = request_template.get("category_id")
    if category_id is None:
        category_id = getattr(ticket, "category_id", None)

    policy_refs = request_template.get("policy_refs") if isinstance(request_template.get("policy_refs"), dict) else {}
    ref = policy_refs.get(kind) if isinstance(policy_refs, dict) else None
    ref_code = str(ref.get("code") if isinstance(ref, dict) else ref or "").strip()
    if ref_code:
        effective = await HelpdeskPolicyRepo(session).resolve_policy_ref(
            kind=kind,
            code=ref_code,
            source=f"ticket_snapshot.policy_refs.{kind}",
        )
        config = effective.get("config") if isinstance(effective, dict) else {}
        if isinstance(config, dict) and config:
            return config
        return policy

    effective = await HelpdeskPolicyRepo(session).resolve_effective_policy(
        kind=kind,
        ticket_type=ticket_type or None,
        category_id=category_id,
        template_code=template_code or None,
    )
    config = effective.get("config") if isinstance(effective, dict) else {}
    if isinstance(config, dict) and config:
        policy = _deep_merge(policy, config)
    return policy


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
    snapshots: dict[str, dict[str, Any]] = {}
    refs: dict[str, dict[str, Any]] = {}
    effective_template = await repo.resolve_effective_request_template(
        template_code=template_code,
        ticket_type=ticket_type or None,
        category_id=category_id,
        raise_if_missing=False,
    )
    if effective_template:
        request_template = effective_template.get("request_template") or {}
        if isinstance(request_template, dict):
            template_context.setdefault("request_template_version", request_template.get("version"))
            for key in (
                "form_schema_id",
                "workflow_profile_id",
                "priority_policy_code",
                "routing_policy_code",
                "sla_policy_id",
                "sla_policy_code",
                "ola_policy_code",
                "approval_policy_code",
                "diagnostic_policy_code",
                "closure_policy_code",
                "visibility_policy_code",
                "notification_policy_code",
                "reporting_policy_code",
            ):
                if request_template.get(key) is not None:
                    template_context[key] = deepcopy(request_template.get(key))
        resolved_policies = (
            effective_template.get("resolved_policies")
            if isinstance(effective_template.get("resolved_policies"), dict)
            else {}
        )
        for kind, config in resolved_policies.items():
            if not isinstance(config, dict) or not config:
                continue
            field_name = f"{kind}_policy"
            existing = template_context.get(field_name) if isinstance(template_context.get(field_name), dict) else {}
            template_context[field_name] = _deep_merge(existing, config)
        sources = (
            effective_template.get("policy_sources")
            if isinstance(effective_template.get("policy_sources"), dict)
            else {}
        )
        snapshots = (
            effective_template.get("policy_snapshots")
            if isinstance(effective_template.get("policy_snapshots"), dict)
            else {}
        )
        refs = (
            effective_template.get("policy_refs")
            if isinstance(effective_template.get("policy_refs"), dict)
            else {}
        )
    else:
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
    if snapshots:
        template_context["effective_policy_snapshots"] = snapshots
    if refs:
        template_context["policy_refs"] = refs

    result = deepcopy(validated_submission)
    result["template_context"] = template_context
    return result
