from __future__ import annotations

from typing import Any


FEEDBACK_REASON_CODES = {
    "slow_response",
    "slow_resolution",
    "not_resolved",
    "problem_returned",
    "unclear_instruction",
    "poor_communication",
    "wrong_category",
    "wrong_priority",
    "too_many_questions",
    "knowledge_article_failed",
    "temporary_workaround_only",
    "other",
}

REOPEN_REASON_CODES = {
    "not_resolved",
    "problem_returned",
    "incomplete_work",
    "wrong_resolution",
    "unclear_instruction",
    "requester_disagreed",
    "closed_too_early",
    "new_information",
    "wrong_category_or_queue",
    "dependency_failed",
    "knowledge_article_failed",
    "other",
}

QUALITY_REVIEW_TYPES = {
    "low_csat",
    "reopened",
    "sla_breached",
    "high_priority",
    "missing_evidence",
    "closure_policy_exception",
    "negative_kb_feedback",
    "random_sample",
    "manager_request",
    "quality_audit",
}

REVIEW_STATUSES = {"open", "assigned", "in_review", "passed", "failed", "action_required", "dismissed"}
REVIEW_SEVERITIES = {"critical", "high", "medium", "low", "info"}

IMPROVEMENT_ACTION_TYPES = {
    "update_kb_article",
    "create_kb_article",
    "create_known_error",
    "improve_request_form",
    "update_routing_policy",
    "adjust_sla_policy",
    "add_diagnostic_playbook",
    "train_support",
    "open_problem_candidate",
    "create_change_candidate",
    "contact_requester",
    "process_review",
    "perform_rca",
    "implement_permanent_fix",
    "validate_workaround",
    "update_known_error",
    "other",
}

ACTION_STATUSES = {"open", "assigned", "in_progress", "blocked", "done", "dismissed"}
ACTION_PRIORITIES = {"low", "medium", "high", "critical"}

SOURCE_SURFACES = {"requester_portal", "public_ticket_page", "agent_gui", "email_link", "support_entered", "api"}
VISIBILITIES = {"support_internal", "manager_aggregate", "requester_visible"}


def _text(value: Any, *, max_length: int | None = None) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    if max_length is not None:
        return cleaned[:max_length]
    return cleaned


def _int_rating(payload: dict[str, Any], key: str, *, required: bool = False) -> int | None:
    raw = payload.get(key)
    if raw in (None, ""):
        if required:
            raise ValueError(f"{key} is required")
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be 1..5") from exc
    if value < 1 or value > 5:
        raise ValueError(f"{key} must be 1..5")
    return value


def _reason_codes(raw: Any, allowed: set[str], *, field: str = "reason_codes") -> list[str]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list | tuple | set):
        raise ValueError(f"{field} must be a list")
    result: list[str] = []
    for item in raw:
        code = str(item or "").strip()
        if not code:
            continue
        if code not in allowed:
            raise ValueError(f"{field} contains unknown code: {code}")
        if code not in result:
            result.append(code)
    return result


def sentiment_for_rating(rating: int) -> str:
    if rating >= 4:
        return "positive"
    if rating == 3:
        return "neutral"
    return "negative"


def validate_feedback_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rating = _int_rating(payload, "rating", required=True)
    reason_codes = _reason_codes(payload.get("reason_codes"), FEEDBACK_REASON_CODES)
    comment = _text(payload.get("comment"), max_length=2000)
    source_surface = str(payload.get("source_surface") or "api").strip() or "api"
    if source_surface not in SOURCE_SURFACES:
        raise ValueError("source_surface is invalid")
    visibility = str(payload.get("visibility") or "requester_visible").strip() or "requester_visible"
    if visibility not in VISIBILITIES:
        raise ValueError("visibility is invalid")
    result = {
        "ticket_id": _text(payload.get("ticket_id")),
        "rating": rating,
        "sentiment": sentiment_for_rating(rating),
        "resolution_confirmed": payload.get("resolution_confirmed"),
        "problem_resolved": payload.get("problem_resolved"),
        "response_time_satisfaction": _int_rating(payload, "response_time_satisfaction"),
        "communication_satisfaction": _int_rating(payload, "communication_satisfaction"),
        "quality_satisfaction": _int_rating(payload, "quality_satisfaction"),
        "reason_codes": reason_codes,
        "comment": comment,
        "visibility": visibility,
        "source_surface": source_surface,
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }
    if not result["ticket_id"]:
        raise ValueError("ticket_id is required")
    if "other" in reason_codes and not comment:
        raise ValueError("comment is required when reason_codes contains other")
    return result


def validate_reopen_reason(reason_code: str, reason_comment: str | None) -> str:
    code = str(reason_code or "").strip()
    if code not in REOPEN_REASON_CODES:
        raise ValueError("reason_code is invalid")
    if code == "other" and not str(reason_comment or "").strip():
        raise ValueError("reason_comment is required when reason_code is other")
    return code


def requester_safe_quality_summary(payload: dict[str, Any]) -> dict[str, Any]:
    latest = payload.get("latest_feedback") if isinstance(payload.get("latest_feedback"), dict) else None
    safe: dict[str, Any] = {"reopen_available": bool(payload.get("reopen_available"))}
    if latest:
        safe["latest_feedback"] = {
            "feedback_id": latest.get("feedback_id"),
            "rating": latest.get("rating"),
            "sentiment": latest.get("sentiment"),
            "problem_resolved": latest.get("problem_resolved"),
            "resolution_confirmed": latest.get("resolution_confirmed"),
            "submitted_at": latest.get("submitted_at"),
            "reason_codes": list(latest.get("reason_codes") or []),
            "comment": latest.get("comment"),
        }
    return safe
