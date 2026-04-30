"""Executable diagnostic policy helpers for request templates."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import Operation, TicketEvidenceItem

TERMINAL_OPERATION_STATUSES = {"succeeded", "failed", "denied", "timed_out", "canceled"}


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


def _operation_title(operation: Operation) -> str:
    return str(operation.tool_name or operation.command_name or operation.kind or operation.operation_id)


def _operation_summary(operation: Operation) -> str | None:
    summary = operation.result_summary or operation.error_message or operation.status
    return str(summary).strip() if summary else None


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
