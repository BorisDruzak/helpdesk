from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def primitive(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: primitive(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [primitive(item) for item in value]
    return value


def feedback_to_dict(row: Any) -> dict[str, Any]:
    return {
        "feedback_id": row.feedback_id,
        "ticket_id": row.ticket_id,
        "rating": row.rating,
        "sentiment": row.sentiment,
        "resolution_confirmed": row.resolution_confirmed,
        "problem_resolved": row.problem_resolved,
        "response_time_satisfaction": row.response_time_satisfaction,
        "communication_satisfaction": row.communication_satisfaction,
        "quality_satisfaction": row.quality_satisfaction,
        "reason_codes": list(row.reason_codes or []),
        "comment": row.comment,
        "visibility": row.visibility,
        "source_surface": row.source_surface,
        "service_code": row.service_code,
        "offering_code": row.offering_code,
        "submitted_at": iso(row.submitted_at),
        "updated_at": iso(row.updated_at),
        "is_latest": row.is_latest,
    }


def review_to_dict(row: Any) -> dict[str, Any]:
    return {
        "review_id": row.review_id,
        "ticket_id": row.ticket_id,
        "review_type": row.review_type,
        "severity": row.severity,
        "status": row.status,
        "assigned_to_actor_id": row.assigned_to_actor_id,
        "owner_actor_id": row.owner_actor_id,
        "queue_id": row.queue_id,
        "service_code": row.service_code,
        "offering_code": row.offering_code,
        "due_at": iso(row.due_at),
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
        "closed_at": iso(row.closed_at),
        "trigger_payload": primitive(row.trigger_payload or {}),
        "findings_json": primitive(row.findings_json or {}),
        "score": row.score,
        "reviewer_actor_id": row.reviewer_actor_id,
        "review_notes": row.review_notes,
    }


def action_to_dict(row: Any) -> dict[str, Any]:
    return {
        "action_id": row.action_id,
        "source_kind": row.source_kind,
        "source_ref": row.source_ref,
        "ticket_id": row.ticket_id,
        "review_id": row.review_id,
        "feedback_id": row.feedback_id,
        "service_code": row.service_code,
        "offering_code": row.offering_code,
        "action_type": row.action_type,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "priority": row.priority,
        "owner_actor_id": row.owner_actor_id,
        "due_at": iso(row.due_at),
        "created_by": row.created_by,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
        "closed_at": iso(row.closed_at),
        "outcome_notes": row.outcome_notes,
    }
