"""Side-effect-free process preview for request-form drafts."""

from __future__ import annotations

from typing import Any

from tickets.form_business_validation import (
    FormBusinessValidationContext,
    validate_form_pack_business,
)
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    build_form_custom_fields,
    validate_form_pack_schema,
    validate_form_submission,
)
from tickets.priority_policy import compute_priority_from_policy
from tickets.routing_service import (
    FALLBACK_QUEUE_CODE,
    build_form_routing_context,
    find_matching_routing_rule,
)
from tickets.sla_service import _build_standalone_targets
from tickets.ola_service import _targets_from_ola_policy


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "required", "on"}
    return bool(value)


def _queue_id(queue: Any) -> int | None:
    value = getattr(queue, "id", None)
    if value is None and isinstance(queue, dict):
        value = queue.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _queue_code(queue: Any) -> str:
    value = getattr(queue, "code", None)
    if value is None and isinstance(queue, dict):
        value = queue.get("code")
    return str(value or "").strip()


def _queue_name(queue: Any) -> str | None:
    value = getattr(queue, "name", None)
    if value is None and isinstance(queue, dict):
        value = queue.get("name")
    text = str(value or "").strip()
    return text or None


def _queue_maps(queues: list[Any]) -> tuple[dict[int, str], dict[str, int], dict[str, str]]:
    name_by_id: dict[int, str] = {}
    id_by_code: dict[str, int] = {}
    name_by_code: dict[str, str] = {}
    for queue in queues:
        queue_id = _queue_id(queue)
        code = _queue_code(queue)
        name = _queue_name(queue)
        if queue_id is not None and name:
            name_by_id[queue_id] = name
        if queue_id is not None and code:
            id_by_code[code] = queue_id
        if code and name:
            name_by_code[code] = name
    return name_by_id, id_by_code, name_by_code


def _lookup_context_value(context: dict[str, Any], field_path: str) -> Any:
    actual: Any = context
    for part in str(field_path).split("."):
        if isinstance(actual, dict):
            actual = actual.get(part)
        else:
            actual = getattr(actual, part, None)
        if actual is None:
            break
    return actual


def _condition_matches(condition: Any, context: dict[str, Any]) -> bool:
    if not condition:
        return True
    if not isinstance(condition, dict):
        return False
    if "and" in condition:
        return all(_condition_matches(item, context) for item in _as_list(condition.get("and")))
    if "or" in condition:
        return any(_condition_matches(item, context) for item in _as_list(condition.get("or")))
    field = condition.get("field")
    op = condition.get("op")
    value = condition.get("value")
    if field is None or op is None:
        return False
    actual = _lookup_context_value(context, str(field))
    if op == "eq":
        return actual == value
    if op == "ne":
        return actual != value
    if op == "in":
        return isinstance(value, list) and actual in value
    if op == "nin":
        return isinstance(value, list) and actual not in value
    if op == "contains":
        return isinstance(actual, str) and value is not None and str(value) in actual
    if op == "is_null":
        return (value is True and actual is None) or (value is False and actual is not None)
    return False


def _template_rule_condition(rule: dict[str, Any]) -> dict[str, Any] | None:
    condition = rule.get("when")
    if condition is None:
        condition = rule.get("condition")
    if condition is None:
        condition = rule.get("condition_json")
    return condition if isinstance(condition, dict) else None


def _template_rule_actions(rule: dict[str, Any]) -> dict[str, Any]:
    actions = rule.get("then")
    if isinstance(actions, dict):
        return dict(actions)
    inline: dict[str, Any] = {}
    for key in (
        "queue_id",
        "target_queue_id",
        "queue",
        "queue_code",
        "target_queue_code",
        "priority_boost",
        "minimum_priority",
        "sla_policy_id",
        "approval_policy",
        "suggested_playbook",
        "suggested_playbook_id",
    ):
        if key in rule:
            inline[key] = rule[key]
    return inline


def _queue_from_actions(actions: dict[str, Any], id_by_code: dict[str, int]) -> int | None:
    for key in ("queue_id", "target_queue_id"):
        if actions.get(key) not in (None, ""):
            try:
                return int(actions[key])
            except (TypeError, ValueError):
                return None
    queue_code = str(actions.get("queue_code") or actions.get("target_queue_code") or actions.get("queue") or "").strip()
    return id_by_code.get(queue_code) if queue_code else None


def _template_matched_rule(rule: dict[str, Any], priority_order: int, index: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "priority_order": priority_order,
        "index": index,
    }
    for key in ("id", "code", "name"):
        if rule.get(key) is not None:
            result[key] = rule[key]
    condition = _template_rule_condition(rule)
    if condition:
        result["when"] = condition
    return result


def _template_routing_decision(
    *,
    form: dict[str, Any],
    context: dict[str, Any],
    id_by_code: dict[str, int],
    name_by_id: dict[int, str],
) -> dict[str, Any] | None:
    policy = _as_dict(form.get("routing_policy"))
    rules = policy.get("rules")
    normalized_rules: list[tuple[int, int, dict[str, Any]]] = []
    for index, raw_rule in enumerate(_as_list(rules)):
        if not isinstance(raw_rule, dict):
            continue
        try:
            priority_order = int(raw_rule.get("priority_order", index))
        except (TypeError, ValueError):
            priority_order = index
        normalized_rules.append((priority_order, index, raw_rule))

    for priority_order, index, rule in sorted(normalized_rules, key=lambda item: (item[0], item[1])):
        if not _condition_matches(_template_rule_condition(rule), context):
            continue
        actions = _template_rule_actions(rule)
        queue_id = _queue_from_actions(actions, id_by_code)
        return {
            "source": "request_template.routing_policy",
            "target_queue_id": queue_id,
            "target_queue_name": name_by_id.get(queue_id) if queue_id is not None else None,
            "fallback_applied": False,
            "matched_rule": _template_matched_rule(rule, priority_order, index),
            "actions": actions,
        }

    fallback = _as_dict(policy.get("fallback"))
    fallback_queue_id = _queue_from_actions(fallback, id_by_code) if fallback else None
    if fallback_queue_id is not None:
        return {
            "source": "request_template.routing_policy.fallback",
            "target_queue_id": fallback_queue_id,
            "target_queue_name": name_by_id.get(fallback_queue_id),
            "fallback_applied": True,
            "matched_rule": None,
            "actions": fallback,
        }

    return None


def _global_routing_decision(
    *,
    routing_rules: list[Any],
    context: dict[str, Any],
    name_by_id: dict[int, str],
) -> dict[str, Any] | None:
    matched_rule = find_matching_routing_rule(routing_rules, context)
    if matched_rule is None:
        return None
    queue_id = getattr(matched_rule, "target_queue_id", None)
    try:
        queue_id = int(queue_id)
    except (TypeError, ValueError):
        queue_id = None
    return {
        "source": "ticket_routing_rule",
        "target_queue_id": queue_id,
        "target_queue_name": name_by_id.get(queue_id) if queue_id is not None else None,
        "fallback_applied": False,
        "matched_rule": {
            "id": getattr(matched_rule, "id", None),
            "priority_order": getattr(matched_rule, "priority_order", None),
            "target_queue_id": queue_id,
            "condition_json": getattr(matched_rule, "condition_json", None),
        },
        "actions": {"queue_id": queue_id},
    }


def _default_or_fallback_routing_decision(
    *,
    form: dict[str, Any],
    name_by_id: dict[int, str],
    id_by_code: dict[str, int],
) -> dict[str, Any]:
    queue_id = form.get("default_queue_id")
    source = "request_template.default_queue"
    fallback_applied = False
    try:
        queue_id = int(queue_id) if queue_id not in (None, "") else None
    except (TypeError, ValueError):
        queue_id = None
    if queue_id is None and form.get("default_queue_code"):
        queue_id = id_by_code.get(str(form.get("default_queue_code") or "").strip())
    if queue_id is None:
        queue_id = id_by_code.get(FALLBACK_QUEUE_CODE)
        source = "fallback_queue"
        fallback_applied = True
    return {
        "source": source,
        "target_queue_id": queue_id,
        "target_queue_name": name_by_id.get(queue_id) if queue_id is not None else None,
        "fallback_applied": fallback_applied,
        "matched_rule": None,
        "actions": {"queue_id": queue_id} if queue_id is not None else {},
    }


def _policy_ref(form: dict[str, Any], kind: str) -> str | None:
    for field in (f"{kind}_policy_ref", f"{kind}_policy_code"):
        value = str(form.get(field) or "").strip()
        if value:
            return value
    refs = _as_dict(form.get("policy_refs"))
    raw_ref = refs.get(kind)
    if isinstance(raw_ref, dict):
        value = str(raw_ref.get("code") or "").strip()
    else:
        value = str(raw_ref or "").strip()
    return value or None


def _first_policy_code(policy: dict[str, Any], fallback: str | None = None) -> str | None:
    for key in ("code", "policy_code", "id", "name"):
        value = str(policy.get(key) or "").strip()
        if value:
            return value
    return fallback


def _sla_preview(form: dict[str, Any], priority_class: str) -> dict[str, Any]:
    policy = _as_dict(form.get("sla_policy"))
    targets = _build_standalone_targets(policy)
    selected = next((item for item in targets if item.priority == priority_class), None)
    if selected is None and targets:
        selected = next((item for item in targets if item.priority == "P3"), targets[0])
    return {
        "policy_ref": _policy_ref(form, "sla"),
        "policy_id": form.get("sla_policy_id"),
        "policy_code": _first_policy_code(policy, _policy_ref(form, "sla")),
        "first_response_min": selected.first_response_min if selected is not None else None,
        "resolution_min": selected.resolution_min if selected is not None else None,
        "source": "request_template.sla_policy" if policy else ("policy_ref" if _policy_ref(form, "sla") else None),
    }


def _ola_preview(form: dict[str, Any], priority_class: str) -> dict[str, Any]:
    policy = _as_dict(form.get("ola_policy"))
    targets = _targets_from_ola_policy(policy, priority_class)
    ack_min, processing_min = targets if targets is not None else (None, None)
    return {
        "policy_ref": _policy_ref(form, "ola"),
        "policy_code": _first_policy_code(policy, _policy_ref(form, "ola")),
        "ack_min": ack_min,
        "processing_min": processing_min,
        "source": "request_template.ola_policy" if policy else ("policy_ref" if _policy_ref(form, "ola") else None),
    }


def _approval_preview(form: dict[str, Any]) -> dict[str, Any]:
    policy = _as_dict(form.get("approval_policy"))
    source = _as_dict(policy.get("approver_source"))
    return {
        "policy_ref": _policy_ref(form, "approval"),
        "required": _truthy(policy.get("required")),
        "source_type": str(source.get("type") or policy.get("approver_source") or "").strip() or None,
        "source_field": str(source.get("field") or policy.get("approver_field") or "").strip() or None,
        "mode": str(policy.get("approval_mode") or policy.get("mode") or "any_one"),
    }


def _playbooks_from_policy(policy: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in _as_list(policy.get("suggested_playbooks")):
        if isinstance(item, dict):
            key = str(item.get("playbook_key") or item.get("key") or item.get("id") or "").strip()
        else:
            key = str(item or "").strip()
        if key and key not in result:
            result.append(key)
    for key in ("suggested_playbook", "suggested_playbook_id"):
        value = str(policy.get(key) or "").strip()
        if value and value not in result:
            result.append(value)
    return result


def _diagnostics_preview(form: dict[str, Any], priority_class: str) -> dict[str, Any]:
    policy = _as_dict(form.get("diagnostic_policy"))
    auto_run = _as_dict(policy.get("auto_run"))
    only_for = [str(item or "").strip().upper() for item in _as_list(auto_run.get("only_for_priorities"))]
    consent = _as_dict(policy.get("consent"))
    suggested = _playbooks_from_policy(policy)
    for trigger in _as_list(form.get("playbook_triggers")):
        if not isinstance(trigger, dict) or not _truthy(trigger.get("enabled", True)):
            continue
        key = str(trigger.get("playbook_key") or "").strip()
        if key and key not in suggested:
            suggested.append(key)
    return {
        "policy_ref": _policy_ref(form, "diagnostic"),
        "suggested_playbooks": suggested,
        "auto_run_enabled": _truthy(auto_run.get("enabled")),
        "auto_run_allowed_for_priority": not only_for or priority_class in only_for,
        "consent_required": _truthy(policy.get("requires_user_consent")) or _truthy(consent.get("required_for_requester_device")),
        "high_risk_consent_required": _truthy(policy.get("requires_high_risk_tool_consent")) or _truthy(consent.get("required_for_high_risk_tools")),
        "attach_results": _as_dict(policy.get("attach_results")),
    }


def _closure_preview(form: dict[str, Any], priority_class: str) -> dict[str, Any]:
    policy = _as_dict(form.get("closure_policy"))
    before = _as_dict(policy.get("before_resolved"))
    evidence = _as_dict(policy.get("evidence"))
    confirmation = _as_dict(policy.get("requester_confirmation"))
    evidence_priorities = {str(item or "").strip().upper() for item in _as_list(evidence.get("require_evidence_for_priorities"))}
    return {
        "policy_ref": _policy_ref(form, "closure"),
        "requires_resolution_code": _truthy(before.get("require_resolution_code") or policy.get("require_resolution_code")),
        "requires_public_summary": _truthy(before.get("require_public_summary") or policy.get("require_public_summary")),
        "requires_internal_summary": _truthy(before.get("require_internal_summary") or policy.get("require_internal_summary")),
        "requires_worklog": _truthy(before.get("require_worklog") or policy.get("require_worklog")),
        "requires_evidence": priority_class in evidence_priorities or _truthy(evidence.get("required")) or _truthy(policy.get("require_evidence")),
        "requester_confirmation_required": _truthy(confirmation.get("required")),
        "auto_close_after_days": confirmation.get("auto_close_after_days") or policy.get("auto_close_after_days"),
    }


def _visibility_preview(form: dict[str, Any]) -> dict[str, Any]:
    policy = _as_dict(form.get("visibility_policy"))
    return {
        "policy_ref": _policy_ref(form, "visibility"),
        "public_status_mapping": _as_dict(policy.get("public_status_mapping")),
        "requester_hidden_fields": _as_list(policy.get("requester_hidden_fields")),
        "requester_visible_metadata": _as_list(policy.get("requester_visible_metadata")),
    }


def _notifications_preview(form: dict[str, Any]) -> dict[str, Any]:
    policy = _as_dict(form.get("notification_policy"))
    events: list[str] = []
    channels: set[str] = set()
    recipients: set[str] = set()
    for key, config in policy.items():
        if not str(key).startswith("on_") or not isinstance(config, dict):
            continue
        events.append(str(key))
        raw_channels = _as_dict(config.get("channels"))
        channels.update(str(channel) for channel, enabled in raw_channels.items() if _truthy(enabled))
        for recipient in ("requester", "assignee", "queue_lead", "watchers"):
            if _truthy(config.get(recipient)):
                recipients.add(recipient)
    return {
        "policy_ref": _policy_ref(form, "notification"),
        "events": events,
        "channels": sorted(channels),
        "recipients": sorted(recipients),
    }


async def build_form_process_preview(
    *,
    raw_form: dict[str, Any],
    form_payload: dict[str, Any],
    queues: list[Any] | None = None,
    routing_rules: list[Any] | None = None,
    business_context: FormBusinessValidationContext | None = None,
) -> dict[str, Any]:
    """Build a full admin process preview without creating or mutating a ticket."""
    preview_pack = validate_form_pack_schema(
        {
            "pack_key": DEFAULT_TICKET_FORM_PACK_KEY,
            "version": "preview",
            "title": "Preview",
            "description": "Preview",
            "forms": [raw_form],
        }
    )
    form = preview_pack["forms"][0]
    validated_submission = validate_form_submission(
        preview_pack,
        form_key=str(form.get("key") or "").strip(),
        raw_values=form_payload,
    )
    submitted_values = _as_dict(validated_submission.get("submitted_values"))
    custom_fields = build_form_custom_fields(validated_submission)
    template_context = _as_dict(validated_submission.get("template_context"))
    priority_policy = _as_dict(template_context.get("priority_policy"))
    priority = compute_priority_from_policy(
        priority_policy=priority_policy,
        submitted_values=submitted_values,
        fallback={},
    )
    priority_class = str(priority.get("priority_class") or priority.get("effective_priority") or "P3")

    routing_context = build_form_routing_context(
        ticket_type=str(validated_submission.get("ticket_type") or form.get("ticket_type") or ""),
        custom_fields=custom_fields,
    )
    routing_context["priority_class"] = priority_class
    routing_context["priority"] = priority.get("legacy_priority")

    queue_items = queues or []
    name_by_id, id_by_code, _name_by_code = _queue_maps(queue_items)
    routing = (
        _template_routing_decision(
            form=form,
            context=routing_context,
            id_by_code=id_by_code,
            name_by_id=name_by_id,
        )
        or _global_routing_decision(
            routing_rules=routing_rules or [],
            context=routing_context,
            name_by_id=name_by_id,
        )
        or _default_or_fallback_routing_decision(form=form, name_by_id=name_by_id, id_by_code=id_by_code)
    )

    validation_report = validate_form_pack_business(preview_pack, context=business_context)

    return {
        "ticket_type": str(validated_submission.get("ticket_type") or ""),
        "request_kind": str(validated_submission.get("request_kind") or ""),
        "priority": {
            "priority_class": priority_class,
            "legacy_priority": priority.get("legacy_priority"),
            "priority_source": priority.get("priority_source"),
            "priority_reason": priority.get("priority_reason"),
            "priority_explanation": priority.get("priority_explanation"),
            "applied_modifiers": priority.get("applied_modifiers") or [],
        },
        "routing": routing,
        "sla": _sla_preview(form, priority_class),
        "ola": _ola_preview(form, priority_class),
        "approval": _approval_preview(form),
        "diagnostics": _diagnostics_preview(form, priority_class),
        "closure": _closure_preview(form, priority_class),
        "visibility": _visibility_preview(form),
        "notifications": _notifications_preview(form),
        "summary_rows": list(validated_submission.get("summary_rows") or []),
        "validation_report": {
            "summary": dict(validation_report.summary),
            "errors": list(validation_report.errors),
            "warnings": list(validation_report.warnings),
        },
        "preview_metadata": {
            "source": "draft",
            "side_effects": [],
        },
    }
