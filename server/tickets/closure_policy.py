"""Executable closure policy for request templates."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import TicketEvidenceItem
from tickets.statuses import extract_priority_class


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


def _evidence_priorities(policy: dict[str, Any]) -> set[str]:
    priorities = _normalize_priority_list(policy.get("require_evidence_for_priorities"))
    priorities |= _normalize_priority_list(policy.get("require_diagnostic_evidence_for_priorities"))
    return priorities


async def _ticket_has_evidence(session: Any, ticket: Any) -> bool:
    if _has_text(getattr(ticket, "evidence_ref", None)):
        return True
    evidence_id = await session.scalar(
        select(TicketEvidenceItem.id)
        .where(TicketEvidenceItem.ticket_id == ticket.ticket_id)
        .limit(1)
    )
    return evidence_id is not None


async def validate_closure_policy(
    session: Any,
    ticket: Any,
    *,
    to_status: str,
    resolution_code: str | None,
    resolution_summary: str | None,
) -> dict[str, Any]:
    if ticket is None or to_status != "resolved":
        return {"applied": False}

    policy = get_template_closure_policy(ticket)
    if not policy:
        return {"applied": False}

    if policy.get("require_resolution_code") and not _has_text(
        resolution_code or getattr(ticket, "resolution_code", None)
    ):
        raise ValueError("closure_policy requires resolution_code")

    if policy.get("require_public_summary") and not _has_text(
        resolution_summary
        or getattr(ticket, "requester_resolution_summary", None)
        or getattr(ticket, "resolution_summary", None)
    ):
        raise ValueError("closure_policy requires resolution_summary")

    priority_class = extract_priority_class(ticket)
    evidence_priorities = _evidence_priorities(policy)
    if priority_class in evidence_priorities and not await _ticket_has_evidence(session, ticket):
        raise ValueError("closure_policy requires evidence for this priority")

    return {
        "applied": True,
        "policy": {
            "require_resolution_code": bool(policy.get("require_resolution_code")),
            "require_public_summary": bool(policy.get("require_public_summary")),
            "require_evidence_for_priorities": sorted(evidence_priorities),
        },
        "priority_class": priority_class,
    }
