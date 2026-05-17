from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any


def primitive(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [primitive(item) for item in value]
    if isinstance(value, dict):
        return {key: primitive(item) for key, item in value.items()}
    return value


def problem_to_dict(row: Any) -> dict[str, Any]:
    operational = _problem_operational_status(row)
    return primitive(
        {
            "problem_id": row.problem_id,
            "problem_key": row.problem_key,
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "severity": row.severity,
            "priority": row.priority,
            "impact": row.impact,
            "urgency": row.urgency,
            "source_kind": row.source_kind,
            "source_ref": row.source_ref,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "request_type": row.request_type,
            "reporting_category": row.reporting_category,
            "owner_actor_id": row.owner_actor_id or row.owner_id,
            "assignee_actor_id": row.assignee_actor_id,
            "queue_id": row.queue_id,
            "opened_at": row.opened_at,
            "known_error_at": row.known_error_at,
            "workaround_available_at": row.workaround_available_at,
            "investigation_due_at": getattr(row, "investigation_due_at", None),
            "known_error_due_at": getattr(row, "known_error_due_at", None),
            "workaround_due_at": getattr(row, "workaround_due_at", None),
            "rca_due_at": getattr(row, "rca_due_at", None),
            "resolution_due_at": getattr(row, "resolution_due_at", None),
            "closure_due_at": getattr(row, "closure_due_at", None),
            "breached_milestones": getattr(row, "breached_milestones", []) or [],
            "next_due_milestone": operational["next_due_milestone"],
            "next_due_at": operational["next_due_at"],
            "is_overdue": operational["is_overdue"],
            "resolved_at": row.resolved_at,
            "closed_at": row.closed_at,
            "root_cause_summary": row.root_cause_summary or row.root_cause,
            "root_cause_category": row.root_cause_category,
            "workaround_summary": row.workaround_summary or row.workaround,
            "permanent_fix_summary": row.permanent_fix_summary,
            "closure_summary": row.closure_summary,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


def ticket_link_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "link_id": row.link_id,
            "problem_id": row.problem_id,
            "ticket_id": row.ticket_id,
            "link_type": row.link_type,
            "confidence_score": row.confidence_score,
            "evidence_summary": row.evidence_summary,
            "linked_by_actor_id": row.linked_by_actor_id or row.linked_by,
            "linked_at": row.linked_at,
            "unlinked_at": row.unlinked_at,
        }
    )


def candidate_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "candidate_id": row.candidate_id,
            "fingerprint": row.fingerprint,
            "fingerprint_version": getattr(row, "fingerprint_version", 1),
            "evidence_hash": getattr(row, "evidence_hash", None),
            "status": row.status,
            "signal_type": row.signal_type,
            "title": row.title,
            "summary": row.summary,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "request_type": row.request_type,
            "ticket_count": row.ticket_count,
            "reopen_count": row.reopen_count,
            "low_csat_count": row.low_csat_count,
            "sla_breach_count": row.sla_breach_count,
            "failed_kb_count": row.failed_kb_count,
            "confidence_score": row.confidence_score,
            "converted_problem_id": row.converted_problem_id,
            "first_seen_at": getattr(row, "first_seen_at", None),
            "last_seen_at": getattr(row, "last_seen_at", None),
            "dismissed_until": getattr(row, "dismissed_until", None),
            "merged_into_candidate_id": getattr(row, "merged_into_candidate_id", None),
            "duplicate_count": getattr(row, "duplicate_count", 0),
            "evidence": _redacted_evidence(row.evidence_json or {}),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


def rca_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "rca_id": row.rca_id,
            "problem_id": row.problem_id,
            "version_number": row.version_number,
            "status": row.status,
            "methodology": row.methodology,
            "problem_statement": row.problem_statement,
            "impact_summary": row.impact_summary,
            "root_cause": row.root_cause,
            "root_cause_category": row.root_cause_category,
            "reviewer_actor_id": row.reviewer_actor_id,
            "approved_by_actor_id": row.approved_by_actor_id,
            "created_at": row.created_at,
            "reviewed_at": row.reviewed_at,
            "approved_at": row.approved_at,
        }
    )


def scanner_run_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "run_id": row.run_id,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "status": row.status,
            "triggered_by": row.triggered_by,
            "lookback_hours": row.lookback_hours,
            "rules_run": row.rules_run or [],
            "candidates_created": row.candidates_created,
            "candidates_updated": row.candidates_updated,
            "candidates_skipped": row.candidates_skipped,
            "errors": row.errors_json or [],
            "duration_ms": row.duration_ms,
            "metadata": row.metadata_json or {},
        }
    )


def _redacted_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "ticket_ids",
        "ticket_count",
        "reopen_count",
        "low_csat_count",
        "sla_breach_count",
        "failed_kb_count",
        "top_reopen_reasons",
        "breach_type_counts",
        "review_type_counts",
        "event_type_counts",
        "knowledge_item_ids",
        "gap_finding_ids",
        "gap_type_counts",
        "window_start",
        "window_end",
    }
    return {key: value for key, value in evidence.items() if key in allowed}


def _problem_operational_status(row: Any) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    breached = list(getattr(row, "breached_milestones", []) or [])
    due_fields = [
        ("investigation", getattr(row, "investigation_due_at", None), getattr(row, "investigation_started_at", None)),
        ("known_error", getattr(row, "known_error_due_at", None), getattr(row, "known_error_at", None)),
        ("workaround", getattr(row, "workaround_due_at", None), getattr(row, "workaround_available_at", None)),
        ("rca", getattr(row, "rca_due_at", None), None),
        ("resolution", getattr(row, "resolution_due_at", None), getattr(row, "resolved_at", None)),
        ("closure", getattr(row, "closure_due_at", None), getattr(row, "closed_at", None)),
    ]
    for milestone, due_at, actual_at in due_fields:
        if due_at and due_at < now and actual_at is None and milestone not in breached:
            breached.append(milestone)
    next_due = None
    next_due_at = None
    for milestone, due_at, actual_at in due_fields:
        if actual_at is not None or due_at is None:
            continue
        if next_due_at is None or due_at < next_due_at:
            next_due = milestone
            next_due_at = due_at
    return {"breached_milestones": breached, "next_due_milestone": next_due, "next_due_at": next_due_at, "is_overdue": bool(breached)}
