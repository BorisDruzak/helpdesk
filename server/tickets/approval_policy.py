"""Executable approval policy for request templates."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models import TicketApproval


DEFAULT_APPROVAL_PROTECTED_STATUSES = {"assigned", "in_progress", "scheduled", "resolved"}


def get_template_approval_policy(ticket: Any) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    if not isinstance(request_template, dict):
        return {}
    approval_policy = request_template.get("approval_policy") or {}
    return approval_policy if isinstance(approval_policy, dict) else {}


def _approval_status(value: Any) -> str:
    return str(value or "").strip().lower()


def _policy_statuses(policy: dict[str, Any]) -> dict[str, str]:
    raw_statuses = policy.get("statuses") or {}
    if not isinstance(raw_statuses, dict):
        raw_statuses = {}
    return {
        "waiting_status": str(raw_statuses.get("waiting_status") or "waiting_on_approval").strip(),
        "approved_transition": str(raw_statuses.get("approved_transition") or "").strip(),
        "rejected_transition": str(raw_statuses.get("rejected_transition") or "canceled").strip(),
    }


def _protected_statuses(policy: dict[str, Any]) -> set[str]:
    protected = set(DEFAULT_APPROVAL_PROTECTED_STATUSES)
    statuses = _policy_statuses(policy)
    if statuses["approved_transition"]:
        protected.add(statuses["approved_transition"])
    raw_protected = policy.get("protected_statuses")
    if isinstance(raw_protected, list | tuple | set):
        protected.update(str(item or "").strip() for item in raw_protected if str(item or "").strip())
    return protected


async def _list_ticket_approval_statuses(session: Any, ticket_id: str) -> list[str]:
    rows = await session.execute(
        select(TicketApproval.status).where(TicketApproval.ticket_id == ticket_id)
    )
    return [_approval_status(item) for item in rows.scalars().all()]


def _decision_for_statuses(policy: dict[str, Any], approval_statuses: list[str]) -> dict[str, Any]:
    approved_count = sum(1 for status in approval_statuses if status == "approved")
    rejected_count = sum(1 for status in approval_statuses if status in {"rejected", "denied", "declined"})
    requested_count = len(approval_statuses)
    pending_count = sum(
        1
        for status in approval_statuses
        if status not in {"approved", "rejected", "denied", "declined", "canceled", "cancelled"}
    )

    if rejected_count:
        raise ValueError("approval_policy rejected approval blocks transition")

    approval_mode = str(policy.get("approval_mode") or "any_one").strip().lower()
    if approval_mode in {"all", "sequential"}:
        if not requested_count or approved_count != requested_count or pending_count:
            raise ValueError("approval_policy requires all approvals to be approved")
    elif approved_count < 1:
        raise ValueError("approval_policy requires approved approval")

    return {
        "approval_mode": approval_mode if approval_mode else "any_one",
        "approved_count": approved_count,
        "requested_count": requested_count,
        "pending_count": pending_count,
    }


async def validate_approval_policy(
    session: Any,
    ticket: Any,
    *,
    from_status: str,
    to_status: str,
) -> dict[str, Any]:
    if ticket is None:
        return {"applied": False}

    policy = get_template_approval_policy(ticket)
    if not policy or not policy.get("required"):
        return {"applied": False}

    statuses = _policy_statuses(policy)
    if to_status == statuses["waiting_status"]:
        return {
            "applied": True,
            "waiting_status": statuses["waiting_status"],
            "required": True,
            "gate": "waiting",
        }

    if to_status == statuses["rejected_transition"]:
        return {
            "applied": True,
            "required": True,
            "gate": "rejected_transition",
        }

    if to_status not in _protected_statuses(policy):
        return {"applied": False}

    approval_statuses = await _list_ticket_approval_statuses(session, ticket.ticket_id)
    decision = _decision_for_statuses(policy, approval_statuses)
    return {
        "applied": True,
        "required": True,
        "from_status": from_status,
        "to_status": to_status,
        **decision,
    }
