"""Executable closure policy for request templates."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select

from app.db.models import (
    TicketActionLog,
    TicketApproval,
    TicketEvent,
    TicketEvidenceItem,
    TicketWorklog,
)
from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
from tickets.statuses import extract_priority_class


MODULE_EVENT_TYPES = {
    "tool_call_started",
    "tool_call_result",
    "playbook_started",
    "playbook_completed",
    "playbook_failed",
}


def get_template_closure_policy(ticket: Any) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    if not isinstance(request_template, dict):
        return {}
    closure_policy = request_template.get("closure_policy") or {}
    return closure_policy if isinstance(closure_policy, dict) else {}


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _normalize_priority_list(value: Any) -> set[str]:
    if not isinstance(value, list | tuple | set):
        return set()
    return {str(item or "").strip().upper() for item in value if str(item or "").strip()}


def _section(policy: dict[str, Any], key: str) -> dict[str, Any]:
    value = policy.get(key)
    return value if isinstance(value, dict) else {}


def _policy_value(
    policy: dict[str, Any],
    key: str,
    *,
    section: str | None = None,
    default: Any = None,
) -> Any:
    nested = _section(policy, section) if section else {}
    if key in nested:
        return nested.get(key)
    return policy.get(key, default)


def _policy_bool(policy: dict[str, Any], key: str, *, section: str | None = None) -> bool:
    return bool(_policy_value(policy, key, section=section))


def _normalize_code_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    codes: list[str] = []
    seen: set[str] = set()
    for item in value:
        code = str(item or "").strip()
        if not code or code in seen:
            continue
        codes.append(code)
        seen.add(code)
    return codes


def _evidence_priorities(policy: dict[str, Any]) -> set[str]:
    evidence = _section(policy, "evidence")
    priorities = _normalize_priority_list(_policy_value(policy, "require_evidence_for_priorities", section="evidence"))
    priorities |= _normalize_priority_list(evidence.get("require_diagnostic_evidence_for_priorities"))
    return priorities


def _requester_confirmation(policy: dict[str, Any]) -> dict[str, Any]:
    raw = _section(policy, "requester_confirmation")
    has_legacy_auto_close = policy.get("auto_close_after_days") is not None
    if not raw and not has_legacy_auto_close:
        return {}
    required = bool(raw.get("required", True if has_legacy_auto_close else False))
    raw_auto_close = raw.get("auto_close_after_days", policy.get("auto_close_after_days"))
    auto_close_after_days: int | None = None
    if raw_auto_close not in (None, ""):
        try:
            parsed = int(raw_auto_close)
            if parsed > 0:
                auto_close_after_days = parsed
        except (TypeError, ValueError):
            auto_close_after_days = None
    return {
        "required": required,
        "auto_close_after_days": auto_close_after_days,
        "reopen_on_negative_feedback": bool(raw.get("reopen_on_negative_feedback", True)),
    }


async def _ticket_has_evidence(session: Any, ticket: Any) -> bool:
    if _has_text(getattr(ticket, "evidence_ref", None)):
        return True
    evidence_id = await session.scalar(
        select(TicketEvidenceItem.id)
        .where(TicketEvidenceItem.ticket_id == ticket.ticket_id)
        .limit(1)
    )
    return evidence_id is not None


async def _ticket_has_worklog(session: Any, ticket: Any) -> bool:
    worklog_id = await session.scalar(
        select(TicketWorklog.id)
        .where(TicketWorklog.ticket_id == ticket.ticket_id)
        .limit(1)
    )
    return worklog_id is not None


async def _ticket_module_was_used(session: Any, ticket: Any) -> bool:
    event_id = await session.scalar(
        select(TicketEvent.id)
        .where(
            TicketEvent.ticket_id == ticket.ticket_id,
            TicketEvent.event_type.in_(sorted(MODULE_EVENT_TYPES)),
        )
        .limit(1)
    )
    return event_id is not None


async def _ticket_has_operation_log(session: Any, ticket: Any) -> bool:
    action_id = await session.scalar(
        select(TicketActionLog.id)
        .where(
            TicketActionLog.ticket_id == ticket.ticket_id,
            or_(
                TicketActionLog.operation_id.isnot(None),
                TicketActionLog.action_type.in_(
                    [
                        "diagnostic_operation",
                        "remediation_operation",
                        "tool_call",
                        "playbook_run",
                    ]
                ),
            ),
        )
        .limit(1)
    )
    if action_id is not None:
        return True
    evidence_id = await session.scalar(
        select(TicketEvidenceItem.id)
        .where(
            TicketEvidenceItem.ticket_id == ticket.ticket_id,
            TicketEvidenceItem.evidence_type.in_(["operation_log", "diagnostic_result"]),
        )
        .limit(1)
    )
    return evidence_id is not None


def _approval_policy_used(ticket: Any) -> bool:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if not isinstance(custom_fields, dict):
        return False
    request_template = custom_fields.get("request_template") or {}
    if not isinstance(request_template, dict):
        return False
    approval_policy = request_template.get("approval_policy")
    if isinstance(approval_policy, dict) and approval_policy:
        return bool(approval_policy.get("required", True))
    policy_refs = request_template.get("policy_refs") if isinstance(request_template.get("policy_refs"), dict) else {}
    return bool(
        request_template.get("approval_policy_code")
        or (isinstance(policy_refs, dict) and policy_refs.get("approval"))
    )


async def _ticket_has_any_approval(session: Any, ticket: Any) -> bool:
    approval_id = await session.scalar(
        select(TicketApproval.id)
        .where(TicketApproval.ticket_id == ticket.ticket_id)
        .limit(1)
    )
    return approval_id is not None


async def _ticket_has_approved_approval(session: Any, ticket: Any) -> bool:
    approval_id = await session.scalar(
        select(TicketApproval.id)
        .where(
            TicketApproval.ticket_id == ticket.ticket_id,
            TicketApproval.status == "approved",
        )
        .limit(1)
    )
    return approval_id is not None


def _requirement(key: str, label: str, met: bool, detail: str | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "met": bool(met),
        "detail": detail or "",
    }


async def build_closure_requirements(session: Any, ticket: Any) -> list[dict[str, Any]]:
    """Return support-facing closure checklist for the current ticket state."""
    if ticket is None:
        return []
    policy = await resolve_effective_ticket_policy(session, ticket, "closure")
    requirements: list[dict[str, Any]] = []
    if not policy:
        if getattr(ticket, "evidence_required", False):
            requirements.append(
                _requirement(
                    "legacy_evidence",
                    "Доказательство решения",
                    await _ticket_has_evidence(session, ticket),
                    "Добавьте evidence_ref или запись evidence перед решением.",
                )
            )
        return requirements

    resolution_code = getattr(ticket, "resolution_code", None)
    public_summary = getattr(ticket, "requester_resolution_summary", None) or getattr(ticket, "resolution_summary", None)
    internal_summary = getattr(ticket, "resolution_summary", None)

    if _policy_bool(policy, "require_resolution_code", section="before_resolved"):
        allowed_resolution_codes = _normalize_code_list(
            _policy_value(policy, "allowed_resolution_codes", section="before_resolved")
        )
        code_allowed = not allowed_resolution_codes or str(resolution_code or "").strip() in allowed_resolution_codes
        requirements.append(
            _requirement(
                "resolution_code",
                "Код решения",
                _has_text(resolution_code) and code_allowed,
                (
                    "Укажите код решения из списка: " + ", ".join(allowed_resolution_codes)
                    if allowed_resolution_codes
                    else "Укажите код решения."
                ),
            )
        )
    elif _normalize_code_list(_policy_value(policy, "allowed_resolution_codes", section="before_resolved")):
        allowed_resolution_codes = _normalize_code_list(
            _policy_value(policy, "allowed_resolution_codes", section="before_resolved")
        )
        requirements.append(
            _requirement(
                "allowed_resolution_code",
                "Код решения из разрешённого списка",
                str(resolution_code or "").strip() in allowed_resolution_codes,
                "Разрешённые коды: " + ", ".join(allowed_resolution_codes),
            )
        )

    if _policy_bool(policy, "require_public_summary", section="before_resolved"):
        requirements.append(
            _requirement(
                "public_summary",
                "Публичный итог для заявителя",
                _has_text(public_summary),
                "Заполните итог, который увидит заявитель.",
            )
        )
    if _policy_bool(policy, "require_internal_summary", section="before_resolved"):
        requirements.append(
            _requirement(
                "internal_summary",
                "Внутренний итог решения",
                _has_text(internal_summary),
                "Заполните внутреннее описание причины и действий.",
            )
        )
    if _policy_bool(policy, "require_worklog", section="before_resolved"):
        requirements.append(
            _requirement(
                "worklog",
                "Worklog",
                await _ticket_has_worklog(session, ticket),
                "Добавьте запись о выполненной работе.",
            )
        )

    priority_class = extract_priority_class(ticket)
    evidence_priorities = _evidence_priorities(policy)
    if priority_class in evidence_priorities:
        requirements.append(
            _requirement(
                "priority_evidence",
                f"Доказательство для {priority_class}",
                await _ticket_has_evidence(session, ticket),
                "Для этого приоритета нужно приложить evidence.",
            )
        )
    if _policy_bool(policy, "require_operation_log_if_module_used", section="evidence") and await _ticket_module_was_used(session, ticket):
        requirements.append(
            _requirement(
                "operation_log",
                "Журнал операции",
                await _ticket_has_operation_log(session, ticket),
                "Модуль или playbook запускался, нужен operation log или диагностическое evidence.",
            )
        )
    if _policy_bool(policy, "require_approval_if_approval_policy_used", section="evidence"):
        approval_used = _approval_policy_used(ticket) or await _ticket_has_any_approval(session, ticket)
        if approval_used:
            requirements.append(
                _requirement(
                    "approval_evidence",
                    "Согласование подтверждено",
                    await _ticket_has_approved_approval(session, ticket),
                    "Нужна approved-запись в согласованиях.",
                )
            )

    requester_confirmation = _requester_confirmation(policy)
    if requester_confirmation:
        requirements.append(
            _requirement(
                "requester_confirmation",
                "Подтверждение заявителя",
                True,
                "Будет запрошено после перевода в Решено.",
            )
        )
    return requirements


async def validate_closure_policy(
    session: Any,
    ticket: Any,
    *,
    to_status: str,
    resolution_code: str | None,
    resolution_summary: str | None,
    requester_resolution_summary: str | None = None,
) -> dict[str, Any]:
    if ticket is None or to_status != "resolved":
        return {"applied": False}

    policy = await resolve_effective_ticket_policy(session, ticket, "closure")
    if not policy:
        return {"applied": False}

    effective_resolution_code = resolution_code or getattr(ticket, "resolution_code", None)
    public_summary = (
        requester_resolution_summary
        or resolution_summary
        or getattr(ticket, "requester_resolution_summary", None)
        or getattr(ticket, "resolution_summary", None)
    )
    internal_summary = resolution_summary or getattr(ticket, "resolution_summary", None)

    if _policy_bool(policy, "require_resolution_code", section="before_resolved") and not _has_text(
        effective_resolution_code
    ):
        raise ValueError("closure_policy requires resolution_code")

    allowed_resolution_codes = _normalize_code_list(
        _policy_value(policy, "allowed_resolution_codes", section="before_resolved")
    )
    if allowed_resolution_codes and str(effective_resolution_code or "").strip() not in allowed_resolution_codes:
        raise ValueError("closure_policy allowed_resolution_codes does not include resolution_code")

    if _policy_bool(policy, "require_public_summary", section="before_resolved") and not _has_text(public_summary):
        raise ValueError("closure_policy requires resolution_summary")

    if _policy_bool(policy, "require_internal_summary", section="before_resolved") and not _has_text(internal_summary):
        raise ValueError("closure_policy requires internal_summary")

    if _policy_bool(policy, "require_worklog", section="before_resolved") and not await _ticket_has_worklog(session, ticket):
        raise ValueError("closure_policy requires worklog")

    priority_class = extract_priority_class(ticket)
    evidence_priorities = _evidence_priorities(policy)
    if priority_class in evidence_priorities and not await _ticket_has_evidence(session, ticket):
        raise ValueError("closure_policy requires evidence for this priority")

    operation_log_required = False
    if _policy_bool(policy, "require_operation_log_if_module_used", section="evidence"):
        module_was_used = await _ticket_module_was_used(session, ticket)
        operation_log_required = module_was_used
        if module_was_used and not await _ticket_has_operation_log(session, ticket):
            raise ValueError("closure_policy requires operation_log because a module was used")

    approval_evidence_required = False
    if _policy_bool(policy, "require_approval_if_approval_policy_used", section="evidence"):
        approval_used = _approval_policy_used(ticket) or await _ticket_has_any_approval(session, ticket)
        approval_evidence_required = approval_used
        if approval_used and not await _ticket_has_approved_approval(session, ticket):
            raise ValueError("closure_policy requires approved approval evidence")

    requester_confirmation = _requester_confirmation(policy)

    return {
        "applied": True,
        "policy": {
            "before_resolved": {
                "require_resolution_code": _policy_bool(policy, "require_resolution_code", section="before_resolved"),
                "require_public_summary": _policy_bool(policy, "require_public_summary", section="before_resolved"),
                "require_internal_summary": _policy_bool(policy, "require_internal_summary", section="before_resolved"),
                "require_worklog": _policy_bool(policy, "require_worklog", section="before_resolved"),
            },
            "require_evidence_for_priorities": sorted(evidence_priorities),
            "evidence": {
                "require_operation_log_if_module_used": _policy_bool(
                    policy,
                    "require_operation_log_if_module_used",
                    section="evidence",
                ),
                "require_approval_if_approval_policy_used": _policy_bool(
                    policy,
                    "require_approval_if_approval_policy_used",
                    section="evidence",
                ),
            },
            "allowed_resolution_codes": allowed_resolution_codes,
        },
        "priority_class": priority_class,
        "operation_log_required": operation_log_required,
        "approval_evidence_required": approval_evidence_required,
        **({"requester_confirmation": requester_confirmation} if requester_confirmation else {}),
    }
