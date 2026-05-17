from __future__ import annotations

from datetime import date, datetime
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


def _redacted_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    allowed = {"ticket_ids", "ticket_count", "reopen_count", "low_csat_count", "sla_breach_count", "failed_kb_count", "top_reopen_reasons", "window_start", "window_end"}
    return {key: value for key, value in evidence.items() if key in allowed}
