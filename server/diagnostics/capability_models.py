from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


EXECUTION_TARGETS = {
    "agent_builtin",
    "agent_managed_module",
    "agent_recipe",
    "server_builtin",
    "server_connector",
    "observer_query",
    "remote_assist",
    "manual",
    "hybrid",
}

READINESS_STATUSES = {
    "available",
    "install_required",
    "installing",
    "unsupported_platform",
    "agent_offline",
    "runner_not_installed",
    "runner_install_required",
    "runner_installing",
    "runner_outdated",
    "primitive_not_supported",
    "recipe_not_published",
    "missing_dependency",
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
    execution_target: str = "agent_managed_module"
    tool_kind: str = "diagnostic"
    risk_level: str = "low"
    side_effects: bool = False
    requires_consent: bool = False
    requires_device: bool = False
    requires_agent_online: bool = False
    supports_auto_install: bool = False
    requires_integration: bool = False
    integration_key: Optional[str] = None
    requires_credentials: bool = False
    requires_mapping: bool = False
    requires_policy: bool = False
    required_permission: Optional[str] = None
    policy_key: Optional[str] = None
    mapping_key: Optional[str] = None
    install_required_on_agent: bool = False
    platforms: List[str] = field(default_factory=list)
    params_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    output_contract: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    source: str = "managed_module"
    runner_provider_id: Optional[str] = None
    min_runner_version: Optional[str] = None
    primitive_id: Optional[str] = None
    primitive_version: Optional[str] = None
    recipe_version_id: Optional[str] = None
    capability_version_id: Optional[str] = None
    supports_auto_install_runner: bool = False

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
