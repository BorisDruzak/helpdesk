from __future__ import annotations

from typing import Any

PROBLEM_STATUSES = {
    "new",
    "candidate",
    "investigating",
    "known_error",
    "workaround_available",
    "permanent_fix_planned",
    "permanent_fix_in_progress",
    "resolved",
    "closed",
    "canceled",
}

PROBLEM_TERMINAL_STATUSES = {"closed", "canceled"}

PROBLEM_TRANSITIONS = {
    "new": {"investigating", "candidate", "canceled"},
    "candidate": {"investigating", "canceled"},
    "investigating": {"known_error", "workaround_available", "permanent_fix_planned", "resolved", "canceled"},
    "known_error": {"workaround_available", "permanent_fix_planned", "resolved", "canceled"},
    "workaround_available": {"permanent_fix_planned", "permanent_fix_in_progress", "resolved", "canceled"},
    "permanent_fix_planned": {"permanent_fix_in_progress", "resolved", "canceled"},
    "permanent_fix_in_progress": {"resolved", "canceled"},
    "resolved": {"closed", "investigating"},
    "closed": set(),
    "canceled": set(),
}

PROBLEM_SEVERITIES = {"low", "medium", "high", "critical"}
PROBLEM_PRIORITIES = {"low", "medium", "high", "critical"}
PROBLEM_ROOT_CAUSE_CATEGORIES = {
    "software_defect",
    "configuration",
    "infrastructure",
    "network",
    "access_policy",
    "user_process",
    "vendor",
    "documentation_gap",
    "knowledge_gap",
    "monitoring_gap",
    "unknown",
    "other",
}

PROBLEM_CANDIDATE_STATUSES = {"open", "accepted", "dismissed", "merged", "converted"}
PROBLEM_DETECTION_SIGNAL_TYPES = {
    "repeated_incident_pattern",
    "low_csat_pattern",
    "reopen_pattern",
    "sla_breach_pattern",
    "qa_failed_pattern",
    "manual",
}

PROBLEM_RCA_STATUSES = {"draft", "in_review", "approved", "rejected", "archived"}
PROBLEM_RCA_METHODOLOGIES = {"five_whys", "fishbone", "timeline", "fault_tree", "vendor_rca", "narrative"}

PROBLEM_ACTION_TYPES = {"perform_rca", "implement_permanent_fix", "validate_workaround", "update_known_error"}

KNOWN_ERROR_LINK_TYPES = {"known_error", "workaround", "permanent_fix_article", "support_runbook", "requester_article"}
KNOWN_ERROR_VISIBILITIES = {"support_internal", "requester_safe", "admin_internal"}


def clean_text(value: Any, *, max_length: int | None = None) -> str | None:
    result = str(value or "").strip()
    if not result:
        return None
    return result[:max_length] if max_length else result


def normalize_problem_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    legacy = {
        "new": "new",
        "investigating": "investigating",
        "mitigated": "workaround_available",
        "resolved": "resolved",
        "closed": "closed",
    }
    status = legacy.get(status, status)
    if status not in PROBLEM_STATUSES:
        raise ValueError("status is invalid")
    return status


def can_transition_problem(current_status: str, new_status: str) -> bool:
    current = normalize_problem_status(current_status)
    new = normalize_problem_status(new_status)
    return new in PROBLEM_TRANSITIONS.get(current, set())


def validate_choice(value: Any, allowed: set[str], field: str, *, default: str | None = None) -> str:
    raw = str(value or default or "").strip().lower()
    if raw not in allowed:
        raise ValueError(f"{field} is invalid")
    return raw


def validate_problem_resolution_payload(payload: dict[str, Any]) -> None:
    if not clean_text(payload.get("root_cause_summary")):
        raise ValueError("root cause summary is required before resolving a problem")
    if not clean_text(payload.get("permanent_fix_summary")) and not clean_text(payload.get("no_permanent_fix_reason")):
        raise ValueError("permanent fix summary or documented no-permanent-fix reason is required")
