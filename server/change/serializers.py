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


def change_to_dict(row: Any, *, affected_objects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return primitive(
        {
            "change_id": row.change_id,
            "change_key": row.change_key,
            "title": row.title,
            "description": row.description,
            "change_type": row.change_type,
            "status": row.status,
            "category": row.category,
            "priority": row.priority,
            "risk_level": row.risk_level,
            "impact_level": row.impact_level,
            "urgency": row.urgency,
            "source_kind": row.source_kind,
            "source_ref": row.source_ref,
            "problem_id": row.problem_id,
            "improvement_action_id": row.improvement_action_id,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "request_type": row.request_type,
            "reporting_category": row.reporting_category,
            "owner_actor_id": row.owner_actor_id,
            "assignee_actor_id": row.assignee_actor_id,
            "planned_start_at": row.planned_start_at,
            "planned_end_at": row.planned_end_at,
            "blackout_override": row.blackout_override,
            "emergency_justification": row.emergency_justification,
            "risk_summary": row.risk_summary,
            "impact_summary": row.impact_summary,
            "implementation_summary": row.implementation_summary,
            "rollback_summary": row.rollback_summary,
            "validation_summary": row.validation_summary,
            "closure_summary": row.closure_summary,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "affected_objects": affected_objects or [],
        }
    )


def affected_object_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "affected_id": row.affected_id,
            "change_id": row.change_id,
            "object_type": row.object_type,
            "object_ref": row.object_ref,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "impact": row.impact,
            "planned_downtime": row.planned_downtime,
            "notes": row.notes,
        }
    )


def risk_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "assessment_id": row.assessment_id,
            "change_id": row.change_id,
            "version_number": row.version_number,
            "status": row.status,
            "risk_level": row.risk_level,
            "impact_level": row.impact_level,
            "suggested_risk_level": row.suggested_risk_level,
            "risk_factors": row.risk_factors_json or {},
            "mitigation_plan": row.mitigation_plan,
            "test_plan_summary": row.test_plan_summary,
            "approved_by_actor_id": row.approved_by_actor_id,
        }
    )


def plan_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "plan_id": row.plan_id,
            "change_id": row.change_id,
            "version_number": row.version_number,
            "status": row.status,
            "implementation_steps": row.implementation_steps_json or [],
            "rollback_steps": row.rollback_steps_json or [],
            "validation_steps": row.validation_steps_json or [],
            "communication_steps": row.communication_steps_json or [],
            "downtime_expected": row.downtime_expected,
            "downtime_minutes": row.downtime_minutes,
        }
    )


def approval_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "approval_id": row.approval_id,
            "change_id": row.change_id,
            "approval_stage": row.approval_stage,
            "approver_actor_id": row.approver_actor_id,
            "approver_role": row.approver_role,
            "approver_group": row.approver_group,
            "required": row.required,
            "status": row.status,
            "decision_comment": row.decision_comment,
            "decided_by_actor_id": row.decided_by_actor_id,
            "requested_at": row.requested_at,
            "decided_at": row.decided_at,
        }
    )


def window_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "window_id": row.window_id,
            "title": row.title,
            "window_type": row.window_type,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "object_type": row.object_type,
            "object_ref": row.object_ref,
            "starts_at": row.starts_at,
            "ends_at": row.ends_at,
        }
    )


def task_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "task_id": row.task_id,
            "change_id": row.change_id,
            "title": row.title,
            "description": row.description,
            "task_type": row.task_type,
            "status": row.status,
            "owner_actor_id": row.owner_actor_id,
            "order_index": row.order_index,
            "result_notes": row.result_notes,
        }
    )


def pir_to_dict(row: Any) -> dict[str, Any]:
    return primitive(
        {
            "pir_id": row.pir_id,
            "change_id": row.change_id,
            "status": row.status,
            "implementation_successful": row.implementation_successful,
            "rollback_used": row.rollback_used,
            "caused_incident": row.caused_incident,
            "met_objectives": row.met_objectives,
            "downtime_actual_minutes": row.downtime_actual_minutes,
            "lessons_learned": row.lessons_learned,
        }
    )

