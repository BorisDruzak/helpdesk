from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


EXECUTION_TARGETS = {
    "server_builtin",
    "server_connector",
    "observer_query",
    "manual",
    "endpoint_operation",
}

READINESS_STATUSES = {
    "available",
    "consent_required",
    "integration_not_configured",
    "credentials_missing",
    "mapping_missing",
    "permission_denied",
    "disabled_by_policy",
    "unavailable",
    "unknown",
}


@dataclass(frozen=True)
class CapabilityDescriptor:
    id: str
    title: str
    description: str = ""
    provider_id: str = ""
    provider_type: str = ""
    execution_target: str = "endpoint_operation"
    tool_kind: str = "diagnostic"
    risk_level: str = "low"
    side_effects: bool = False
    requires_consent: bool = False
    requires_device: bool = False
    requires_integration: bool = False
    integration_key: Optional[str] = None
    requires_credentials: bool = False
    requires_mapping: bool = False
    requires_policy: bool = False
    required_permission: Optional[str] = None
    policy_key: Optional[str] = None
    mapping_key: Optional[str] = None
    platforms: List[str] = field(default_factory=list)
    params_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    output_contract: Dict[str, Any] = field(default_factory=dict)
    presentation_schema: Dict[str, Any] = field(default_factory=dict)
    effective_presentation_schema: Dict[str, Any] = field(default_factory=dict)
    presentation_schema_source: str = "none"
    has_presentation_override: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    source: str = "external_endpoint"

    def __post_init__(self) -> None:
        module_default = self.presentation_schema if isinstance(self.presentation_schema, dict) else {}
        effective = self.effective_presentation_schema if isinstance(self.effective_presentation_schema, dict) else {}
        source = self.presentation_schema_source
        if not effective and source != "server_override" and module_default:
            object.__setattr__(self, "effective_presentation_schema", dict(module_default))
            if source == "none":
                object.__setattr__(self, "presentation_schema_source", "module_default")
        elif not effective and source not in {"module_default", "server_override"}:
            object.__setattr__(self, "effective_presentation_schema", {})
            object.__setattr__(self, "presentation_schema_source", "none")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityReadiness:
    capability_id: str
    title: str
    execution_target: str
    readiness: str
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    actions: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    requires_consent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosticEvidencePreview:
    kind: str
    domain: str
    perspective: str
    title: str
    summary: str
    status: str
    source_type: str
    source_id: str
    artifact_refs: List[str] = field(default_factory=list)
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
