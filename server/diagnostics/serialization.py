from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.db.models import DiagnosticBundle, DiagnosticEvidence, DiagnosticFinding, DiagnosticSession, DiagnosticStep, Operation, RemoteAccessSession, TicketEvidenceItem


def iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def number(value: Any) -> float | None:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def evidence_to_dict(item: DiagnosticEvidence) -> dict[str, Any]:
    return {
        "id": item.id,
        "ticket_id": item.ticket_id,
        "session_id": item.session_id,
        "step_id": item.step_id,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "provider_id": item.provider_id,
        "capability_id": item.capability_id,
        "kind": item.kind,
        "domain": item.domain,
        "perspective": item.perspective,
        "title": item.title,
        "summary": item.summary,
        "status": item.status,
        "severity": item.severity,
        "confidence": number(item.confidence),
        "observed_at": iso(item.observed_at),
        "normalized_payload": item.normalized_payload or {},
        "raw_ref": item.raw_ref,
        "artifact_refs": item.artifact_refs or [],
        "trace_id": item.trace_id,
        "redaction_level": item.redaction_level,
        "tags": item.tags or [],
        "passport_eligible": item.passport_eligible,
        "selected_for_passport": item.selected_for_passport,
        "created_by": item.created_by,
        "created_at": iso(item.created_at),
    }


def session_to_dict(item: DiagnosticSession, *, steps: list[DiagnosticStep] | None = None) -> dict[str, Any]:
    payload = {
        "id": item.id,
        "ticket_id": item.ticket_id,
        "profile_id": item.profile_id,
        "profile_version": item.profile_version,
        "status": item.status,
        "trigger_source": item.trigger_source,
        "started_by_user_id": item.started_by_user_id,
        "started_at": iso(item.started_at),
        "finished_at": iso(item.finished_at),
        "summary": item.summary,
        "confidence": number(item.confidence),
        "created_at": iso(item.created_at),
        "updated_at": iso(item.updated_at),
    }
    if steps is not None:
        payload["steps"] = [step_to_dict(step) for step in steps]
    return payload


def step_to_dict(item: DiagnosticStep) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "ticket_id": item.ticket_id,
        "step_type": item.step_type,
        "provider_id": item.provider_id,
        "capability_id": item.capability_id,
        "operation_id": item.operation_id,
        "playbook_run_id": item.playbook_run_id,
        "playbook_step_id": item.playbook_step_id,
        "remote_assist_session_id": item.remote_assist_session_id,
        "observer_trace_id": item.observer_trace_id,
        "external_ref": item.external_ref,
        "status": item.status,
        "started_at": iso(item.started_at),
        "finished_at": iso(item.finished_at),
        "result_summary": item.result_summary,
        "error_code": item.error_code,
        "error_message": item.error_message,
        "created_at": iso(item.created_at),
    }


def finding_to_dict(item: DiagnosticFinding) -> dict[str, Any]:
    return {
        "id": item.id,
        "ticket_id": item.ticket_id,
        "session_id": item.session_id,
        "root_cause_code": item.root_cause_code,
        "title": item.title,
        "description": item.description,
        "confidence": number(item.confidence),
        "status": item.status,
        "evidence_ids": item.evidence_ids or [],
        "recommended_actions": item.recommended_actions or [],
        "created_by": item.created_by,
        "created_at": iso(item.created_at),
        "updated_at": iso(item.updated_at),
    }


def bundle_to_dict(item: DiagnosticBundle) -> dict[str, Any]:
    return {
        "id": item.id,
        "ticket_id": item.ticket_id,
        "session_id": item.session_id,
        "created_by_user_id": item.created_by_user_id,
        "status": item.status,
        "summary": item.summary,
        "evidence_ids": item.evidence_ids or [],
        "artifact_refs": item.artifact_refs or [],
        "observer_trace_ids": item.observer_trace_ids or [],
        "remote_assist_session_ids": item.remote_assist_session_ids or [],
        "payload": item.payload or {},
        "created_at": iso(item.created_at),
    }


def operation_to_dict(item: Operation) -> dict[str, Any]:
    return {
        "operation_id": item.operation_id,
        "ticket_id": item.ticket_id,
        "device_id": item.device_id,
        "kind": item.kind,
        "tool_name": item.tool_name,
        "status": item.status,
        "trace_id": item.trace_id,
        "queued_at": iso(item.queued_at),
        "started_at": iso(item.started_at),
        "finished_at": iso(item.finished_at),
        "result_summary": item.result_summary,
        "error_code": item.error_code,
        "error_message": item.error_message,
        "playbook_run_id": item.playbook_run_id,
    }


def remote_session_to_dict(item: RemoteAccessSession) -> dict[str, Any]:
    return {
        "id": item.id,
        "ticket_id": item.ticket_id,
        "device_id": item.device_id,
        "operator_id": item.operator_id,
        "mode": item.mode,
        "status": item.status,
        "consent_required": item.consent_required,
        "consent_status": item.consent_status,
        "requested_at": iso(item.requested_at),
        "started_at": iso(item.started_at),
        "ended_at": iso(item.ended_at),
        "close_reason": item.close_reason,
        "error_code": item.error_code,
        "error_message": item.error_message,
    }


def ticket_evidence_to_dict(item: TicketEvidenceItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "ticket_id": item.ticket_id,
        "passport_id": item.passport_id,
        "evidence_type": item.evidence_type,
        "source_ref": item.source_ref,
        "source_kind": item.source_kind,
        "source_id": item.source_id,
        "required_fact": item.required_fact,
        "section_key": item.section_key,
        "artifact_id": item.artifact_id,
        "title": item.title,
        "summary": item.summary,
        "visibility": item.visibility,
        "verification_status": item.verification_status,
        "captured_at": iso(item.captured_at),
        "metadata_json": item.metadata_json or {},
        "export_visibility": item.export_visibility,
        "created_by": item.created_by,
        "created_at": iso(item.created_at),
    }
