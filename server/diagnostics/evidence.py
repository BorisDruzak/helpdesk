from __future__ import annotations

from typing import Any, Dict, List

from diagnostics.capability_models import CapabilityDescriptor, DiagnosticEvidencePreview


def normalize_tool_result_to_evidence_stub(
    operation: Dict[str, Any],
    capability_descriptor: CapabilityDescriptor,
    result: Dict[str, Any],
) -> DiagnosticEvidencePreview:
    evidence = capability_descriptor.evidence or {}
    status = str(result.get("status") or operation.get("status") or "unknown")
    output = result.get("output") if isinstance(result.get("output"), dict) else {}
    summary = str(result.get("summary") or result.get("message") or output.get("summary") or "")
    artifact_refs: List[str] = []
    for item in result.get("artifacts") or []:
        if isinstance(item, dict):
            ref = item.get("id") or item.get("artifact_id") or item.get("path")
            if ref:
                artifact_refs.append(str(ref))
        elif isinstance(item, str):
            artifact_refs.append(item)
    return DiagnosticEvidencePreview(
        kind=str(evidence.get("kind") or capability_descriptor.id),
        domain=str(evidence.get("domain") or capability_descriptor.provider_id),
        perspective=str(evidence.get("perspective") or capability_descriptor.execution_target),
        title=capability_descriptor.title,
        summary=summary,
        status=status,
        source_type=capability_descriptor.execution_target,
        source_id=str(operation.get("operation_id") or capability_descriptor.id),
        artifact_refs=artifact_refs,
        trace_id=operation.get("trace_id") or result.get("trace_id"),
    )
