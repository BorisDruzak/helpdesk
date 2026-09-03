from __future__ import annotations

from typing import List

from diagnostics.capability_models import CapabilityDescriptor


def _manual_capability(capability_id: str, title: str, description: str, *, kind: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=capability_id,
        title=title,
        description=description,
        provider_id="manual",
        provider_type="manual_provider",
        execution_target="manual",
        required_permission="diagnostics.create_manual_evidence",
        source="manual",
        params_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "status": {"type": "string", "enum": ["ok", "warning", "error", "info", "unknown"]},
                "severity": {"type": "string", "enum": ["none", "low", "medium", "high", "critical"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "artifact_refs": {"type": "array"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "selected_for_passport": {"type": "boolean"},
                "passport_eligible": {"type": "boolean"},
                "raw_ref": {"type": "string"},
                "redaction_level": {"type": "string"},
            },
            "additionalProperties": True,
        },
        output_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "ticket_id": {"type": "string"},
                "kind": {"type": "string"},
                "status": {"type": "string"},
                "selected_for_passport": {"type": "boolean"},
            },
            "additionalProperties": True,
        },
        output_contract={
            "kind": "manual.evidence",
            "status_field": "diagnostic_status",
            "summary_field": "summary",
            "primary_id_field": "evidence_id",
            "supports_evidence_preview": True,
        },
        evidence={
            "produces_evidence": True,
            "kind": kind,
            "domain": "manual",
            "perspective": "manual",
            "passport_eligible": True,
        },
    )


def list_static_capabilities() -> List[CapabilityDescriptor]:
    return [
        CapabilityDescriptor(
            id="observer.ticket.summary",
            title="Observer: ticket summary",
            description="Summarize existing observer traces for a ticket.",
            provider_id="observer",
            provider_type="observer_provider",
            execution_target="observer_query",
            requires_device=False,
            required_permission="observer.trace.view",
            source="observer",
            params_schema={
                "type": "object",
                "properties": {
                    "trace_limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "signature_limit": {"type": "integer", "minimum": 1, "maximum": 25},
                    "span_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "occurrence_limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "root_trace_id": {"type": ["string", "null"]},
                    "health": {"type": "object"},
                    "counts": {"type": "object"},
                    "latest_error": {"type": ["object", "null"]},
                    "top_signature": {"type": ["object", "null"]},
                    "related_traces": {"type": "array"},
                    "recent_occurrences": {"type": "array"},
                    "links": {"type": "object"},
                },
                "additionalProperties": True,
            },
            output_contract={
                "kind": "observer.ticket_summary",
                "status_field": "diagnostic_status",
                "summary_field": "summary",
                "primary_id_field": "root_trace_id",
                "supports_evidence_preview": True,
            },
            evidence={
                "produces_evidence": True,
                "kind": "observer.summary",
                "domain": "observer",
                "perspective": "observer",
                "passport_eligible": True,
            },
        ),
        CapabilityDescriptor(
            id="observer.trace.bundle",
            title="Observer: trace bundle",
            description="Bundle observer traces for diagnostic review.",
            provider_id="observer",
            provider_type="observer_provider",
            execution_target="observer_query",
            requires_device=False,
            required_permission="observer.trace.view",
            source="observer",
            params_schema={
                "type": "object",
                "properties": {
                    "trace_id": {"type": "string"},
                    "operation_id": {"type": "string"},
                    "device_id": {"type": "string"},
                    "q": {"type": "string"},
                    "query": {"type": "string"},
                    "lookback_hours": {"type": "integer", "minimum": 1, "maximum": 720},
                    "trace_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "signature_limit": {"type": "integer", "minimum": 1, "maximum": 25},
                    "degradation_limit": {"type": "integer", "minimum": 1, "maximum": 25},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "primary_trace_id": {"type": ["string", "null"]},
                    "primary_trace": {"type": ["object", "null"]},
                    "health": {"type": "object"},
                    "counts": {"type": "object"},
                    "related_traces": {"type": "array"},
                    "error_occurrences": {"type": "array"},
                    "signatures": {"type": "array"},
                    "degradations": {"type": "array"},
                    "recommended_next_checks": {"type": "array"},
                    "links": {"type": "object"},
                },
                "additionalProperties": True,
            },
            output_contract={
                "kind": "observer.trace_bundle",
                "status_field": "diagnostic_status",
                "summary_field": "summary",
                "primary_id_field": "primary_trace_id",
                "supports_evidence_preview": True,
            },
            evidence={
                "produces_evidence": True,
                "kind": "observer.trace_bundle",
                "domain": "observer",
                "perspective": "observer",
                "passport_eligible": True,
            },
        ),
        _manual_capability(
            "manual.visual_check",
            "Manual: visual check",
            "Record a manual operator observation.",
            kind="manual.visual_check",
        ),
        _manual_capability(
            "manual.vendor_response",
            "Manual: vendor response",
            "Record a vendor response as manual diagnostic evidence.",
            kind="manual.vendor_response",
        ),
        _manual_capability(
            "manual.operator_note",
            "Manual: operator note",
            "Record an operator note as diagnostic evidence.",
            kind="manual.operator_note",
        ),
        _manual_capability(
            "manual.customer_confirmation",
            "Manual: customer confirmation",
            "Record requester/customer confirmation as diagnostic evidence.",
            kind="manual.customer_confirmation",
        ),
    ]
