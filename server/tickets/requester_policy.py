from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import TicketFeedback
from quality.feedback_service import DEFAULT_FEEDBACK_WINDOW_DAYS
from quality.policy_service import QualityPolicyService
from tickets.closure_policy import get_template_closure_policy


REQUESTER_TERMINAL_MESSAGE_STATUSES = {"resolved", "closed", "canceled", "cancelled", "archived"}
REQUESTER_FEEDBACK_STATUSES = {"resolved", "closed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _custom_fields(ticket: Any) -> dict[str, Any]:
    value = getattr(ticket, "custom_fields", None)
    return value if isinstance(value, dict) else {}


def _requester_action_policy(ticket: Any) -> dict[str, Any]:
    custom_fields = _custom_fields(ticket)
    request_template = custom_fields.get("request_template")
    candidates = [
        custom_fields.get("requester_action_policy"),
        custom_fields.get("requester_actions"),
        request_template.get("requester_action_policy") if isinstance(request_template, dict) else None,
        request_template.get("requester_actions") if isinstance(request_template, dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def _resolution_confirmation_pending(ticket: Any) -> bool:
    custom_fields = _custom_fields(ticket)
    state = custom_fields.get("resolution_confirmation")
    if isinstance(state, dict):
        return bool(state.get("pending"))
    if "resolution_confirmation_pending" in custom_fields:
        return bool(custom_fields.get("resolution_confirmation_pending"))
    return False


def _policy_enabled(policy: dict[str, Any], key: str, default: bool = True) -> bool:
    if key not in policy:
        return default
    return bool(policy.get(key))


def _feedback_window_open(ticket: Any, *, now: datetime | None = None) -> bool:
    anchor = _as_aware(getattr(ticket, "closed_at", None)) or _as_aware(getattr(ticket, "resolved_at", None))
    if anchor is None:
        return True
    return (now or _now()) - anchor <= timedelta(days=DEFAULT_FEEDBACK_WINDOW_DAYS)


def _closure_allows_reopen(ticket: Any) -> bool:
    policy = get_template_closure_policy(ticket)
    confirmation = policy.get("requester_confirmation") if isinstance(policy.get("requester_confirmation"), dict) else {}
    if "reopen_on_negative_feedback" in confirmation:
        return bool(confirmation.get("reopen_on_negative_feedback"))
    if "reopen_on_negative_feedback" in policy:
        return bool(policy.get("reopen_on_negative_feedback"))
    return True


def has_latest_requester_feedback(ticket: Any) -> bool:
    return bool(getattr(ticket, "_requester_has_latest_feedback", False))


def latest_requester_feedback_allows_reopen(ticket: Any) -> bool:
    value = getattr(ticket, "_requester_latest_feedback_reopen_available", None)
    return True if value is None else bool(value)


def requester_ticket_actions(ticket: Any, *, now: datetime | None = None) -> dict[str, bool]:
    status = str(getattr(ticket, "status", None) or "").strip().lower()
    policy = _requester_action_policy(ticket)
    in_feedback_window = _feedback_window_open(ticket, now=now)
    latest_feedback_present = has_latest_requester_feedback(ticket)

    can_send_message = (
        bool(status)
        and status not in REQUESTER_TERMINAL_MESSAGE_STATUSES
        and _policy_enabled(policy, "can_send_message", True)
    )
    can_attach_files = can_send_message and _policy_enabled(policy, "can_attach_files", True)
    can_confirm_solution = (
        status == "resolved"
        and _resolution_confirmation_pending(ticket)
        and _policy_enabled(policy, "can_confirm_solution", True)
    )
    can_rate_solution = (
        status in REQUESTER_FEEDBACK_STATUSES
        and in_feedback_window
        and not latest_feedback_present
        and _policy_enabled(policy, "can_rate_solution", True)
    )
    can_reopen = (
        status in REQUESTER_FEEDBACK_STATUSES
        and in_feedback_window
        and _closure_allows_reopen(ticket)
        and latest_requester_feedback_allows_reopen(ticket)
        and _policy_enabled(policy, "can_reopen", True)
    )
    return {
        "can_send_message": can_send_message,
        "can_attach_files": can_attach_files,
        "can_confirm_solution": can_confirm_solution,
        "can_rate_solution": can_rate_solution,
        "can_reopen": can_reopen,
    }


async def annotate_requester_ticket_policy_state(session: Any, tickets: list[Any]) -> None:
    ticket_ids = [str(getattr(ticket, "ticket_id", "") or "") for ticket in tickets if getattr(ticket, "ticket_id", None)]
    if not ticket_ids:
        return
    result = await session.execute(
        select(TicketFeedback)
        .where(TicketFeedback.ticket_id.in_(ticket_ids))
        .where(TicketFeedback.is_latest.is_(True))
    )
    latest_feedback_by_ticket_id = {str(feedback.ticket_id): feedback for feedback in result.scalars().all()}
    policy_service = QualityPolicyService(session)
    policy_cache: dict[tuple[str | None, str | None, int | None], dict[str, Any]] = {}
    for ticket in tickets:
        ticket_id = str(getattr(ticket, "ticket_id", "") or "")
        feedback = latest_feedback_by_ticket_id.get(ticket_id)
        setattr(ticket, "_requester_has_latest_feedback", feedback is not None)
        if feedback is None:
            setattr(ticket, "_requester_latest_feedback_reopen_available", None)
            continue
        cache_key = (
            getattr(ticket, "service_code", None),
            getattr(ticket, "offering_code", None),
            getattr(ticket, "queue_id", None),
        )
        policy = policy_cache.get(cache_key)
        if policy is None:
            policy = await policy_service.effective_policy(
                service_code=cache_key[0],
                offering_code=cache_key[1],
                queue_id=cache_key[2],
            )
            policy_cache[cache_key] = policy
        threshold = int(policy.get("low_csat_threshold", 3))
        setattr(
            ticket,
            "_requester_latest_feedback_reopen_available",
            int(feedback.rating) <= threshold or feedback.problem_resolved is False,
        )
