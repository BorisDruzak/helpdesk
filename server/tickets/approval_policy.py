"""Executable approval policy for request templates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import TicketApproval, TicketQueueMember
from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy


DEFAULT_APPROVAL_PROTECTED_STATUSES = {"assigned", "in_progress", "scheduled", "resolved"}
ACTIVE_APPROVAL_STATUSES = {"requested", "pending", "waiting"}


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


def _ticket_custom_fields(ticket: Any) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    return custom_fields if isinstance(custom_fields, dict) else {}


def _request_template_context(ticket: Any) -> dict[str, Any]:
    request_template = _ticket_custom_fields(ticket).get("request_template") or {}
    return request_template if isinstance(request_template, dict) else {}


def _extract_actor_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, dict):
        for key in ("user_id", "approver_id", "actor_id", "id", "login", "value"):
            actor_id = str(value.get(key) or "").strip()
            if actor_id:
                return [actor_id]
        return []
    if isinstance(value, list | tuple | set):
        result: list[str] = []
        for item in value:
            result.extend(_extract_actor_ids(item))
        return result
    normalized = str(value or "").strip()
    return [normalized] if normalized else []


def _form_field_value(ticket: Any, field: str) -> Any:
    custom_fields = _ticket_custom_fields(ticket)
    for container_key in ("request_form_data", "form_payload", "request_form_summary"):
        current: Any = custom_fields.get(container_key) or {}
        if not isinstance(current, dict):
            continue
        value: Any = current
        for part in field.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(part)
        if value not in (None, "", []):
            return value
    return None


def _configured_user_ids(source: dict[str, Any]) -> list[str]:
    for key in ("user_id", "approver_id", "actor_id", "id"):
        actor_id = str(source.get(key) or "").strip()
        if actor_id:
            return [actor_id]
    for key in ("users", "user_ids", "approver_ids", "actors", "actor_ids"):
        values = _extract_actor_ids(source.get(key))
        if values:
            return values
    return []


async def _resolve_approval_source(
    session: Any,
    ticket: Any,
    source: Any,
) -> tuple[str, list[str]]:
    if isinstance(source, str):
        source = {"type": source}
    if not isinstance(source, dict):
        return "", []
    source_type = str(source.get("type") or source.get("source") or "").strip()
    if source_type in {"explicit_user", "user", "specific_user"}:
        return source_type or "explicit_user", _configured_user_ids(source)
    if source_type in {"explicit_users", "users", "group_members"}:
        return source_type or "explicit_users", _configured_user_ids(source)
    if source_type in {"group", "approval_group"}:
        group_id = str(source.get("group_id") or source.get("id") or source.get("code") or "").strip()
        return source_type, [f"group:{group_id}"] if group_id else []
    if source_type == "security_role":
        role = str(source.get("role") or source.get("role_id") or "security").strip()
        return source_type, [f"role:{role}"] if role else []
    if source_type == "form_field":
        field = str(source.get("field") or source.get("field_key") or "").strip()
        return source_type, _extract_actor_ids(_form_field_value(ticket, field)) if field else []
    if source_type == "requester_manager":
        custom_fields = _ticket_custom_fields(ticket)
        requester_profile = custom_fields.get("requester_profile") or {}
        if not isinstance(requester_profile, dict):
            requester_profile = {}
        values = _extract_actor_ids(
            requester_profile.get("manager_id")
            or requester_profile.get("manager_login")
            or custom_fields.get("requester_manager_id")
            or getattr(ticket, "requester_manager_id", None)
        )
        return source_type, values
    if source_type == "service_owner":
        request_template = _request_template_context(ticket)
        values = _extract_actor_ids(
            request_template.get("service_owner_id")
            or request_template.get("service_owner")
            or request_template.get("owner_id")
            or _ticket_custom_fields(ticket).get("service_owner_id")
        )
        return source_type, values
    if source_type == "queue_lead":
        queue_id = getattr(ticket, "queue_id", None)
        if not queue_id:
            return source_type, []
        rows = await session.execute(
            select(TicketQueueMember.actor_id)
            .where(
                TicketQueueMember.queue_id == queue_id,
                TicketQueueMember.role_in_queue.in_(("queue_lead", "lead", "owner")),
            )
            .order_by(TicketQueueMember.actor_id.asc())
        )
        return source_type, [str(actor_id) for actor_id in rows.scalars().all() if str(actor_id or "").strip()]
    return source_type, []


async def _resolve_approvers(session: Any, ticket: Any, policy: dict[str, Any]) -> tuple[str, list[str]]:
    source = policy.get("approver_source") or policy.get("approvers") or {}
    source_type, approver_ids = await _resolve_approval_source(session, ticket, source)
    if approver_ids:
        return source_type, approver_ids
    fallback = source.get("fallback") if isinstance(source, dict) else None
    if fallback:
        fallback_type, fallback_ids = await _resolve_approval_source(session, ticket, fallback)
        if fallback_ids:
            return fallback_type, fallback_ids
    return source_type, []


async def _list_ticket_approval_statuses(session: Any, ticket_id: str) -> list[str]:
    rows = await session.execute(
        select(TicketApproval.status).where(TicketApproval.ticket_id == ticket_id)
    )
    return [_approval_status(item) for item in rows.scalars().all()]


def _approval_mode(policy: dict[str, Any]) -> str:
    mode = str(policy.get("approval_mode") or "any_one").strip().lower()
    return mode if mode in {"any_one", "all", "sequential"} else "any_one"


async def _active_approval_keys(session: Any, ticket_id: str) -> dict[tuple[str, str | None], str]:
    rows = await session.execute(
        select(TicketApproval.approval_type, TicketApproval.approver_id, TicketApproval.status)
        .where(TicketApproval.ticket_id == ticket_id)
    )
    return {
        (str(approval_type or "").strip(), str(approver_id).strip() if approver_id is not None else None): _approval_status(status)
        for approval_type, approver_id, status in rows.all()
        if _approval_status(status) in ACTIVE_APPROVAL_STATUSES
    }


async def ensure_approval_requests(
    session: Any,
    ticket: Any,
    *,
    actor_id: str,
    actor_role: str,
) -> dict[str, Any]:
    if ticket is None:
        return {"requests_created": 0, "approval_requests": []}
    policy = await resolve_effective_ticket_policy(session, ticket, "approval")
    if not policy or not policy.get("required"):
        return {"requests_created": 0, "approval_requests": []}
    source_type, approver_ids = await _resolve_approvers(session, ticket, policy)
    approval_mode = _approval_mode(policy)
    active_keys = await _active_approval_keys(session, ticket.ticket_id)
    sequential_has_requested = any(status == "requested" for status in active_keys.values())
    now = datetime.now(timezone.utc)
    created: list[dict[str, Any]] = []
    for approver_id in dict.fromkeys(approver_ids):
        key = (source_type or "approval_policy", approver_id)
        if key in active_keys:
            continue
        status = "requested"
        if approval_mode == "sequential" and sequential_has_requested:
            status = "pending"
        elif approval_mode == "sequential":
            sequential_has_requested = True
        session.add(
            TicketApproval(
                ticket_id=ticket.ticket_id,
                approval_type=key[0],
                approver_id=approver_id,
                status=status,
                reason="approval_policy_request",
                requested_by=actor_id,
                requested_at=now,
            )
        )
        created.append(
            {
                "approval_type": key[0],
                "approver_id": approver_id,
                "source": source_type or "approval_policy",
                "status": status,
            }
        )
    if created:
        await session.flush()
    return {
        "requests_created": len(created),
        "approval_requests": created,
        "approval_mode": approval_mode,
        "approver_source": source_type or None,
        "actor_id": actor_id,
        "actor_role": actor_role,
    }


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

    approval_mode = _approval_mode(policy)
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

    policy = await resolve_effective_ticket_policy(session, ticket, "approval")
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
