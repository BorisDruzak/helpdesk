from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from diagnostics.capability_models import CapabilityDescriptor, DiagnosticEvidencePreview


SUCCESS_STATUSES = {"ok", "success", "succeeded", "completed", "created"}
ERROR_STATUSES = {"error", "failed", "timed_out", "timeout"}
WARNING_STATUSES = {"warning", "denied", "canceled", "cancelled", "expired"}
INFO_STATUSES = {"info", "queued", "sent", "accepted", "running", "waiting_consent", "unsupported"}


def _status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in SUCCESS_STATUSES:
        return "ok"
    if raw in ERROR_STATUSES:
        return "error"
    if raw in WARNING_STATUSES:
        return "warning"
    if raw in INFO_STATUSES:
        return "info"
    return "unknown"


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _artifact_refs(result: Dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in result.get("artifact_refs") or result.get("artifacts") or []:
        if isinstance(item, dict):
            artifact_id = item.get("artifact_id") or item.get("id")
            artifact_kind = item.get("kind") or item.get("artifact_kind")
            ref = {
                key: value
                for key, value in {
                    "artifact_id": str(artifact_id) if artifact_id else None,
                    "kind": str(artifact_kind) if artifact_kind else None,
                    "path": str(item.get("path")) if item.get("path") else None,
                }.items()
                if value is not None
            }
            if ref:
                refs.append(ref)
        elif isinstance(item, str) and item:
            refs.append({"artifact_id": item})
    return refs


def _capability_version(capability: CapabilityDescriptor, result: Dict[str, Any]) -> str | None:
    explicit = result.get("capability_version") or result.get("version")
    if explicit:
        return str(explicit)
    output_contract = capability.output_contract or {}
    if output_contract.get("version"):
        return str(output_contract["version"])
    return None


def _source_type(operation: Dict[str, Any], capability: CapabilityDescriptor, result: Dict[str, Any]) -> str:
    explicit = result.get("source_type") or operation.get("source_type")
    if explicit:
        return str(explicit)
    if result.get("operation_id") or operation.get("operation_id"):
        return "operation"
    if capability.execution_target == "manual":
        return "manual"
    if capability.execution_target == "remote_assist":
        return "remote_assist"
    if capability.execution_target == "observer_query":
        return "observer"
    if capability.execution_target == "server_connector":
        return "monitoring"
    if capability.execution_target == "server_builtin":
        return "operation" if (result.get("operation_id") or operation.get("operation_id")) else "server_capability"
    return capability.execution_target or "capability"


def _source_id(operation: Dict[str, Any], capability: CapabilityDescriptor, result: Dict[str, Any]) -> str:
    for key in ("source_id", "operation_id", "session_id", "query_id", "evidence_id", "id"):
        value = result.get(key)
        if value:
            return str(value)
    for key in ("source_id", "operation_id", "session_id", "query_id", "id"):
        value = operation.get(key)
        if value:
            return str(value)
    return str(capability.id)


def normalize_tool_result_to_evidence_values(
    operation: Dict[str, Any],
    capability_descriptor: CapabilityDescriptor,
    result: Dict[str, Any],
) -> dict[str, Any]:
    """Normalize a capability result into values suitable for diagnostic_evidence.

    The older preview helper below delegates to this mapper, so providers that only
    return previews keep working while persistence gets stable provenance fields.
    """

    operation = dict(operation or {})
    result = dict(result or {})
    evidence = capability_descriptor.evidence or {}
    output = result.get("output") if isinstance(result.get("output"), dict) else {}
    summary = str(
        result.get("summary")
        or result.get("message")
        or output.get("summary")
        or result.get("error_message")
        or result.get("error_code")
        or ""
    )
    artifact_refs = _artifact_refs(result)
    raw_status = result.get("diagnostic_status") or result.get("status") or operation.get("status")
    source_type = _source_type(operation, capability_descriptor, result)
    source_id = _source_id(operation, capability_descriptor, result)
    actor_id = result.get("actor_id") or operation.get("actor_id")
    capability_version = _capability_version(capability_descriptor, result)
    trace_id = operation.get("trace_id") or result.get("trace_id")
    normalized_payload = {
        "capability": {
            "id": capability_descriptor.id,
            "provider_id": capability_descriptor.provider_id,
            "provider_type": capability_descriptor.provider_type,
            "execution_target": capability_descriptor.execution_target,
            "version": capability_version,
            "source": capability_descriptor.source,
        },
        "provenance": {
            "source_type": source_type,
            "source_id": source_id,
            "operation_id": result.get("operation_id") or operation.get("operation_id"),
            "session_id": result.get("session_id") or operation.get("session_id"),
            "query_id": result.get("query_id") or operation.get("query_id"),
            "trace_id": trace_id,
            "actor_id": actor_id,
        },
        "result": _json_safe(
            {
                "status": result.get("status"),
                "diagnostic_status": result.get("diagnostic_status"),
                "summary": summary,
                "output": output,
                "error_code": result.get("error_code"),
                "error_message": result.get("error_message"),
            }
        ),
    }
    return {
        "source_type": source_type,
        "source_id": source_id,
        "provider_id": capability_descriptor.provider_id,
        "provider_type": capability_descriptor.provider_type,
        "capability_id": capability_descriptor.id,
        "capability_version": capability_version,
        "kind": str(evidence.get("kind") or capability_descriptor.id),
        "domain": str(evidence.get("domain") or capability_descriptor.provider_id or "diagnostic"),
        "perspective": str(evidence.get("perspective") or capability_descriptor.execution_target or "hybrid"),
        "title": str(result.get("title") or capability_descriptor.title),
        "summary": summary,
        "status": _status(raw_status),
        "severity": result.get("severity"),
        "confidence": result.get("confidence"),
        "normalized_payload": normalized_payload,
        "raw_ref": result.get("raw_ref"),
        "artifact_refs": artifact_refs,
        "trace_id": str(trace_id) if trace_id else None,
        "redaction_level": result.get("redaction_level"),
        "tags": [str(item) for item in (result.get("tags") or []) if str(item).strip()],
        "passport_eligible": bool(evidence.get("passport_eligible", False)),
    }


def normalize_tool_result_to_evidence_stub(
    operation: Dict[str, Any],
    capability_descriptor: CapabilityDescriptor,
    result: Dict[str, Any],
) -> DiagnosticEvidencePreview:
    values = normalize_tool_result_to_evidence_values(operation, capability_descriptor, result)
    artifact_refs: List[str] = []
    for item in values.get("artifact_refs") or []:
        if isinstance(item, dict):
            ref = item.get("artifact_id") or item.get("path") or item.get("kind")
            if ref:
                artifact_refs.append(str(ref))
    return DiagnosticEvidencePreview(
        kind=values["kind"],
        domain=values["domain"],
        perspective=values["perspective"],
        title=values["title"],
        summary=values["summary"],
        status=values["status"],
        source_type=values["source_type"],
        source_id=values["source_id"],
        artifact_refs=artifact_refs,
        trace_id=values.get("trace_id"),
    )
