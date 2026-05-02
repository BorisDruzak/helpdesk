"""Executable diagnostic policy helpers for request templates."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import select

from app.db.models import Operation, TicketEvidenceItem
from tickets.statuses import extract_priority_class

TERMINAL_OPERATION_STATUSES = {"succeeded", "failed", "denied", "timed_out", "canceled"}
ROUTING_DECISION_KEY = "routing_decision"
ROUTING_LOCK_KEY = "routing_lock"
HIGH_RISK_TOOL_LEVELS = {"high", "dangerous", "system_write", "code_exec"}

_RESULT_CLASS_KEYS = (
    "diagnostic_result",
    "diagnostic_result_class",
    "result_classification",
    "classification",
    "result_code",
    "error_code",
    "code",
)


def normalize_diagnostic_consent_payload(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    scope = str(raw.get("scope") or "requester_device").strip() or "requester_device"
    source = str(raw.get("source") or "pc_agent_create").strip() or "pc_agent_create"
    result: dict[str, Any] = {
        "required": bool(raw.get("required")),
        "granted": bool(raw.get("granted")),
        "scope": scope,
        "source": source,
    }
    if "high_risk_tools_granted" in raw:
        result["high_risk_tools_granted"] = bool(raw.get("high_risk_tools_granted"))
    grants = raw.get("grants")
    if isinstance(grants, dict):
        result["grants"] = {
            str(key): bool(value)
            for key, value in grants.items()
            if str(key or "").strip()
        }
    request_template_key = str(raw.get("request_template_key") or "").strip()
    if request_template_key:
        result["request_template_key"] = request_template_key
    return result


def get_template_diagnostic_policy(ticket: Any) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    if not isinstance(request_template, dict):
        return {}

    policy = request_template.get("diagnostic_policy") or request_template.get("diagnostics") or {}
    return policy if isinstance(policy, dict) else {}


def should_materialize_diagnostic_evidence(ticket: Any) -> bool:
    policy = get_template_diagnostic_policy(ticket)
    if not policy:
        return False

    attach_results = policy.get("attach_results")
    if isinstance(attach_results, dict):
        to_passport = attach_results.get("to_passport", True)
        return bool(attach_results.get("as_evidence")) and to_passport is not False

    return bool(policy.get("attach_as_evidence") or policy.get("attach_to_passport_as_evidence"))


def _bool_from_policy(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _diagnostic_policy_auto_run(policy: dict[str, Any]) -> dict[str, Any]:
    auto_run = policy.get("auto_run")
    if isinstance(auto_run, dict):
        return auto_run
    if auto_run is True:
        return {"enabled": True}
    return {}


def _diagnostic_policy_playbooks(policy: dict[str, Any]) -> list[str]:
    raw_playbooks = policy.get("suggested_playbooks")
    items = raw_playbooks if isinstance(raw_playbooks, list) else []
    for legacy_key in ("suggested_playbook_id", "suggested_playbook"):
        value = policy.get(legacy_key)
        if value:
            items.append(value)

    playbooks: list[str] = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("playbook_key") or item.get("key") or item.get("id")
        else:
            value = item
        playbook_key = str(value or "").strip()
        if playbook_key and playbook_key not in playbooks:
            playbooks.append(playbook_key)
    return playbooks


def _policy_requires_requester_device_consent(policy: dict[str, Any]) -> bool:
    consent = policy.get("consent") if isinstance(policy.get("consent"), dict) else {}
    return bool(policy.get("requires_user_consent") or consent.get("required_for_requester_device"))


def policy_requires_high_risk_tool_consent(policy: dict[str, Any]) -> bool:
    consent = policy.get("consent") if isinstance(policy.get("consent"), dict) else {}
    return bool(consent.get("required_for_high_risk_tools") or policy.get("requires_high_risk_tool_consent"))


def _has_granted_requester_device_consent(custom_fields: dict[str, Any]) -> bool:
    consent = custom_fields.get("diagnostic_consent")
    if not isinstance(consent, dict):
        return False
    scope = str(consent.get("scope") or "requester_device").strip() or "requester_device"
    return scope == "requester_device" and bool(consent.get("granted"))


def has_granted_high_risk_tool_consent(custom_fields: dict[str, Any]) -> bool:
    consent = custom_fields.get("diagnostic_consent")
    if not isinstance(consent, dict):
        return False
    if bool(consent.get("high_risk_tools_granted")):
        return True
    grants = consent.get("grants")
    if isinstance(grants, dict) and bool(grants.get("high_risk_tools")):
        return True
    scopes = consent.get("scopes")
    if isinstance(scopes, list) and "high_risk_tools" in {str(item).strip() for item in scopes}:
        return bool(consent.get("granted"))
    scope = str(consent.get("scope") or "").strip()
    return scope in {"high_risk_tools", "all_diagnostics"} and bool(consent.get("granted"))


def _state_reports_agent_online(state: Any | None, device_id: str) -> bool:
    if state is None or not device_id:
        return False
    checker = getattr(state, "is_agent_online", None)
    if callable(checker):
        try:
            return bool(checker(device_id))
        except Exception:
            return False
    connected_agents = getattr(state, "connected_agents", None)
    return isinstance(connected_agents, dict) and device_id in connected_agents


def _normalize_priority_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    priorities: list[str] = []
    for item in items:
        value = str(item or "").strip().upper()
        if value and value not in priorities:
            priorities.append(value)
    return priorities


def collect_diagnostic_policy_auto_run_triggers(
    *,
    ticket: Any,
    custom_fields: dict[str, Any] | None,
    state: Any | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return safe diagnostic policy auto-run triggers and explain skipped playbooks."""
    if ticket is None:
        return [], []
    fields = custom_fields if isinstance(custom_fields, dict) else {}
    policy = get_template_diagnostic_policy(ticket)
    if not policy:
        request_template = fields.get("request_template")
        if isinstance(request_template, dict):
            raw_policy = request_template.get("diagnostic_policy") or request_template.get("diagnostics")
            policy = raw_policy if isinstance(raw_policy, dict) else {}
    if not policy:
        return [], []

    auto_run = _diagnostic_policy_auto_run(policy)
    if not _bool_from_policy(auto_run.get("enabled"), default=False):
        return [], []

    playbooks = _diagnostic_policy_playbooks(policy)
    if not playbooks:
        return [], []

    device_id = str(getattr(ticket, "device_id", "") or "")
    priority_class = extract_priority_class(ticket)
    allowed_priorities = _normalize_priority_list(auto_run.get("only_for_priorities"))
    consent_required = _policy_requires_requester_device_consent(policy)
    high_risk_consent_required = policy_requires_high_risk_tool_consent(policy)
    consent_granted = _has_granted_requester_device_consent(fields)
    online_required = _bool_from_policy(auto_run.get("only_if_agent_online"), default=False)
    agent_online = _state_reports_agent_online(state, device_id)

    triggers: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []
    for playbook_key in playbooks:
        reason: str | None = None
        if allowed_priorities and priority_class not in allowed_priorities:
            reason = "priority_not_allowed"
        elif online_required and not agent_online:
            reason = "agent_offline"
        elif consent_required and not consent_granted:
            reason = "consent_required"

        if reason:
            skips.append(
                {
                    "playbook_key": playbook_key,
                    "reason": reason,
                    "priority_class": priority_class,
                    "agent_online": agent_online,
                    "consent_required": consent_required,
                    "consent_granted": consent_granted,
                    "source": "diagnostic_policy",
                }
            )
            continue

        triggers.append(
            {
                "event": "ticket_created",
                "playbook_key": playbook_key,
                "module_kind": "diagnostic",
                "enabled": True,
                "source": "diagnostic_policy",
                "trigger_type": "diagnostic_policy_auto_run",
                "auto_run": dict(auto_run),
                "diagnostic_policy": {
                    "id": policy.get("id"),
                    "policy_id": policy.get("policy_id"),
                    "auto_run": dict(auto_run),
                    "consent": dict(policy.get("consent")) if isinstance(policy.get("consent"), dict) else {},
                    "consent_required": consent_required,
                    "high_risk_consent_required": high_risk_consent_required,
                },
            }
        )
    return triggers, skips


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_result_class(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    return normalized or None


def _search_result_class(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    for key in _RESULT_CLASS_KEYS:
        result_class = _normalize_result_class(payload.get(key))
        if result_class:
            return result_class

    for nested_key in ("result", "data", "observations", "error"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            result_class = _search_result_class(nested)
            if result_class:
                return result_class

    http_status = payload.get("http_status") or payload.get("status_code")
    http_status_int = _as_int(http_status)
    if http_status_int and http_status_int >= 400:
        return f"HTTP_{http_status_int}"

    return None


def extract_diagnostic_result_class(operation: Operation, result_payload: dict[str, Any] | None = None) -> str | None:
    """Extract a stable diagnostic result class from terminal operation/result payloads."""
    result_class = _search_result_class(result_payload or {})
    if result_class:
        return result_class
    return _normalize_result_class(getattr(operation, "error_code", None))


def _get_reroute_target(policy: dict[str, Any], result_class: str) -> Any:
    reroute_by_result = policy.get("reroute_by_result")
    if not isinstance(reroute_by_result, dict):
        return None
    for key, target in reroute_by_result.items():
        if _normalize_result_class(key) == result_class:
            return target
    return None


async def _queue_id_from_reroute_target(ticket_repo: Any, target: Any) -> int | None:
    if isinstance(target, dict):
        queue_id = _as_int(target.get("queue_id") or target.get("target_queue_id"))
        if queue_id is not None:
            return queue_id
        queue_code = str(target.get("queue_code") or target.get("queue") or "").strip()
    else:
        queue_id = _as_int(target)
        if queue_id is not None:
            return queue_id
        queue_code = str(target or "").strip()

    if queue_code:
        queue = await ticket_repo.get_queue_by_code(queue_code)
        if queue is not None:
            return int(queue.id)
    return None


def _routing_count(custom_fields: dict[str, Any]) -> int:
    decision = custom_fields.get(ROUTING_DECISION_KEY)
    if not isinstance(decision, dict):
        return 0
    return _as_int(decision.get("auto_reroute_count")) or 0


def _operation_summary(operation: Operation) -> str | None:
    summary = operation.result_summary or operation.error_message or operation.status
    return str(summary).strip() if summary else None


def _operation_title(operation: Operation) -> str:
    return str(operation.tool_name or operation.command_name or operation.kind or operation.operation_id)


def _diagnostics_state(
    *,
    diagnostics: Any,
    operation: Operation,
    result_class: str,
) -> dict[str, Any]:
    state = dict(diagnostics) if isinstance(diagnostics, dict) else {}
    applied_ids = [
        str(item)
        for item in state.get("applied_operation_ids", [])
        if str(item or "").strip()
    ] if isinstance(state.get("applied_operation_ids"), list) else []
    operation_id = str(operation.operation_id)
    if operation_id not in applied_ids:
        applied_ids.append(operation_id)
    state.update(
        {
            "status": operation.status,
            "last_status": operation.status,
            "last_result": result_class,
            "last_result_class": result_class,
            "last_operation_id": operation_id,
            "last_tool_name": _operation_title(operation),
            "last_summary": _operation_summary(operation),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "applied_operation_ids": applied_ids,
        }
    )
    return state


async def apply_diagnostic_result_policy(
    session: Any,
    *,
    ticket_repo: Any,
    operation: Operation,
    result_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply request-template diagnostic result policy for a terminal operation."""
    if not getattr(operation, "ticket_id", None):
        return {"applied": False, "reason": "operation_without_ticket"}
    if operation.status not in TERMINAL_OPERATION_STATUSES:
        return {"applied": False, "reason": "operation_not_terminal"}

    ticket = await ticket_repo.get_ticket(str(operation.ticket_id))
    if ticket is None:
        return {"applied": False, "reason": "ticket_not_found"}

    policy = get_template_diagnostic_policy(ticket)
    if not policy:
        return {"applied": False, "reason": "policy_missing"}

    result_class = extract_diagnostic_result_class(operation, result_payload)
    if not result_class:
        return {"applied": False, "reason": "result_class_missing"}

    custom_fields = dict(getattr(ticket, "custom_fields", None) or {})
    diagnostics = custom_fields.get("diagnostics")
    if isinstance(diagnostics, dict) and str(operation.operation_id) in {
        str(item) for item in diagnostics.get("applied_operation_ids", []) if str(item or "").strip()
    }:
        return {"applied": False, "reason": "already_applied", "diagnostic_result": result_class}

    reroute_target = _get_reroute_target(policy, result_class)
    target_queue_id = (
        await _queue_id_from_reroute_target(ticket_repo, reroute_target)
        if reroute_target is not None
        else None
    )
    old_queue_id = getattr(ticket, "queue_id", None)
    routing_locked = bool(custom_fields.get(ROUTING_LOCK_KEY))
    rerouted = target_queue_id is not None and target_queue_id != old_queue_id and not routing_locked

    if rerouted:
        from tickets.ola_service import close_ola_processing

        await close_ola_processing(session, str(ticket.ticket_id), trigger="diagnostic_result_reroute")
        await session.flush()
        await session.refresh(ticket)
        custom_fields = dict(getattr(ticket, "custom_fields", None) or {})
        diagnostics = custom_fields.get("diagnostics")

    custom_fields["diagnostic_result"] = result_class
    custom_fields["diagnostics"] = _diagnostics_state(
        diagnostics=diagnostics,
        operation=operation,
        result_class=result_class,
    )
    custom_fields["diagnostics"]["reroute_target"] = reroute_target
    custom_fields["diagnostics"]["reroute_target_queue_id"] = target_queue_id
    if routing_locked:
        custom_fields["diagnostics"]["reroute_skipped_reason"] = "routing_lock"
    if reroute_target is not None and target_queue_id is None:
        custom_fields["diagnostics"]["reroute_skipped_reason"] = "queue_not_found"

    if target_queue_id is not None and not routing_locked:
        routing_decision = {
            "source": "diagnostic_policy.reroute_by_result",
            "diagnostic_result": result_class,
            "from_queue_id": old_queue_id,
            "to_queue_id": target_queue_id,
            "actions": {"queue_id": target_queue_id, "diagnostic_result": result_class},
            "matched_rule": {"diagnostic_result": result_class},
            "auto_reroute_count": _routing_count(custom_fields) + (1 if target_queue_id != old_queue_id else 0),
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }
        custom_fields[ROUTING_DECISION_KEY] = routing_decision

    updates: dict[str, Any] = {
        "custom_fields": custom_fields,
    }
    if rerouted:
        updates.update(
            {
                "queue_id": target_queue_id,
                "manual_rank": None,
                "manual_rank_updated_at": None,
                "manual_rank_updated_by": None,
            }
        )
    await ticket_repo.update_ticket(str(ticket.ticket_id), **updates)

    event_payload = {
        "operation_id": str(operation.operation_id),
        "tool_name": _operation_title(operation),
        "operation_status": operation.status,
        "diagnostic_result": result_class,
        "summary": _operation_summary(operation),
        "reroute_target": reroute_target,
        "target_queue_id": target_queue_id,
        "rerouted": rerouted,
        "ticket_status": getattr(ticket, "status", None),
    }
    await ticket_repo.add_event(
        ticket_id=str(ticket.ticket_id),
        device_id=str(ticket.device_id),
        agent_seq=None,
        event_type="diagnostic_result_classified",
        payload=event_payload,
        trace_id=getattr(operation, "trace_id", None),
        operation_id=str(operation.operation_id),
    )

    if target_queue_id is not None and not routing_locked:
        await ticket_repo.add_event(
            ticket_id=str(ticket.ticket_id),
            device_id=str(ticket.device_id),
            agent_seq=None,
            event_type="routing_applied",
            payload={
                "from_queue_id": old_queue_id,
                "to_queue_id": target_queue_id,
                "routing_source": "diagnostic_policy.reroute_by_result",
                "matched_rule": {"diagnostic_result": result_class},
                "actions": {"queue_id": target_queue_id, "diagnostic_result": result_class},
            },
            trace_id=getattr(operation, "trace_id", None),
            operation_id=str(operation.operation_id),
        )
        if rerouted:
            await ticket_repo.add_event(
                ticket_id=str(ticket.ticket_id),
                device_id=str(ticket.device_id),
                agent_seq=None,
                event_type="queue_changed",
                payload={
                    "queue_id": target_queue_id,
                    "previous_queue_id": old_queue_id,
                    "source": "diagnostic_policy.reroute_by_result",
                    "diagnostic_result": result_class,
                },
                trace_id=getattr(operation, "trace_id", None),
                operation_id=str(operation.operation_id),
            )
            updated_ticket = await ticket_repo.get_ticket(str(ticket.ticket_id))
            if updated_ticket is not None:
                from tickets.ola_service import start_ola_for_ticket

                await start_ola_for_ticket(session, updated_ticket, trigger="diagnostic_result_reroute")

    return {
        "applied": True,
        "diagnostic_result": result_class,
        "rerouted": rerouted,
        "target_queue_id": target_queue_id,
        "ticket_status": getattr(ticket, "status", None),
    }


def _is_materializable_operation(operation: Operation, *, ticket_id: str) -> bool:
    if operation.ticket_id != ticket_id:
        return False
    if operation.status not in TERMINAL_OPERATION_STATUSES:
        return False
    return bool(_operation_title(operation).strip() and _operation_summary(operation))


async def materialize_diagnostic_operation_evidence(
    session: Any,
    *,
    ticket: Any,
    operations: list[Operation],
    created_by: str | None,
) -> list[TicketEvidenceItem]:
    if not should_materialize_diagnostic_evidence(ticket):
        return []

    materialized: list[TicketEvidenceItem] = []
    for operation in operations:
        if not _is_materializable_operation(operation, ticket_id=str(ticket.ticket_id)):
            continue
        source_ref = f"operation:{operation.operation_id}"
        existing = await session.scalar(
            select(TicketEvidenceItem)
            .where(
                TicketEvidenceItem.ticket_id == ticket.ticket_id,
                TicketEvidenceItem.evidence_type == "diagnostic_result",
                TicketEvidenceItem.source_ref == source_ref,
            )
            .limit(1)
        )
        if existing is not None:
            materialized.append(existing)
            continue

        item = TicketEvidenceItem(
            ticket_id=ticket.ticket_id,
            evidence_type="diagnostic_result",
            source_ref=source_ref,
            title=_operation_title(operation),
            summary=_operation_summary(operation),
            visibility="internal",
            created_by=created_by,
        )
        session.add(item)
        await session.flush()
        materialized.append(item)
    return materialized
