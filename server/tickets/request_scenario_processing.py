"""Trusted scenario bindings resolve through the existing Helpdesk registry."""
from copy import deepcopy

from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from web_api.dto.request_scenario import ProcessBinding


async def apply_scenario_policy_refs(session, validated, references):
    if not references:
        return validated
    # Defensive validation for historical stored definitions; callers supply
    # references only from server-loaded scenario snapshots, never request JSON.
    refs = ProcessBinding(request_template_key="scenario", policy_refs=references).policy_refs
    result = deepcopy(validated)
    context = result.setdefault("template_context", {})
    repo = HelpdeskPolicyRepo(session)
    for kind, code in refs.items():
        effective = await repo.resolve_policy_ref(kind=kind, code=code, source=f"request_scenario.policy_refs.{kind}")
        policy = effective.get("policy") or {}
        config = effective.get("config")
        if not policy.get("is_active") or not policy.get("published_at") or not isinstance(config, dict) or not config:
            raise ValueError({"policy_refs." + kind: "Selected processing policy is not published or available"})
        context[kind + "_policy"] = deepcopy(config)
        context[kind + "_policy_code"] = code
        context.setdefault("policy_refs", {})[kind] = {"code": code, "version": policy["version"]}
        context.setdefault("effective_policy_sources", {})[kind] = deepcopy(effective.get("sources") or [])
        context.setdefault("effective_policy_snapshots", {})[kind] = deepcopy(policy)
        if kind == "sla":
            # Canonical registry overlay uses the same bridge for legacy SLA rows.
            from app.db.models import TicketSlaPolicy
            from tickets.helpdesk_policy_runtime import _as_int
            identifier = _as_int(config.get("sla_policy_id") or config.get("legacy_sla_policy_id"))
            if identifier is not None:
                legacy = await session.get(TicketSlaPolicy, identifier)
                if legacy is None or not legacy.is_active:
                    raise ValueError({"policy_refs.sla": "Selected SLA references an unavailable legacy policy"})
                context["sla_policy_id"] = identifier
            else:
                context.pop("sla_policy_id", None)
    return result
