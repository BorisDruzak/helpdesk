from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


CanonicalRiskLevel = Literal["safe_read", "sensitive_read", "system_write", "code_exec"]
LegacyRiskLevel = Literal["safe_readonly", "sensitive_read", "write_action", "break_glass"]
LifecycleStatus = Literal["experimental", "stable", "deprecated", "removed"]
ArtifactSensitivity = Literal["internal", "sensitive", "secret"]
ToolKind = Literal["diagnostic", "remediation"]
EnvelopeStatus = Literal["ok", "error", "partial", "skipped"]

COMMON_ERROR_CODES = {
    "VALIDATION_ERROR",
    "UNSUPPORTED_PLATFORM",
    "TIMEOUT",
    "ACCESS_DENIED",
    "CONSENT_REQUIRED",
    "DEPENDENCY_MISSING",
    "DNS_NXDOMAIN",
    "TCP_CONNECT_FAILED",
    "HTTP_407_PROXY_AUTH",
    "TLS_CERT_INVALID",
}

LEGACY_TO_CANONICAL_RISK: dict[str, str] = {
    "safe_readonly": "safe_read",
    "sensitive_read": "sensitive_read",
    "write_action": "system_write",
    "dangerous": "code_exec",
    "break_glass": "code_exec",
    "safe_write": "system_write",
    "safe_read": "safe_read",
    "system_write": "system_write",
    "code_exec": "code_exec",
}

CANONICAL_TO_LEGACY_RISK: dict[str, str] = {
    "safe_read": "safe_readonly",
    "sensitive_read": "sensitive_read",
    "system_write": "write_action",
    "code_exec": "break_glass",
}


def normalize_risk_level(value: Any, default: str = "safe_read") -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    return LEGACY_TO_CANONICAL_RISK.get(normalized, default)


def to_legacy_risk_level(value: Any, default: str = "safe_readonly") -> str:
    normalized = normalize_risk_level(value, "safe_read")
    return CANONICAL_TO_LEGACY_RISK.get(normalized, default)


def is_reserved_namespace(tool_name: str) -> bool:
    reserved = {
        "dns",
        "network",
        "tcp",
        "http",
        "tls",
        "system",
        "service",
        "file",
        "process",
        "browser",
    }
    prefix = str(tool_name or "").split(".", 1)[0].strip().lower()
    return prefix in reserved


class ArtifactTypeDescriptor(BaseModel):
    kind: str = Field(..., description="Semantic artifact kind such as screenshot or headers_dump")
    mime: Optional[str] = Field(default=None, description="Declared mime type")
    sensitivity: ArtifactSensitivity = Field(default="internal")
    retention_policy: Optional[str] = Field(default=None, description="Retention hint")


class ArtifactDescriptor(BaseModel):
    artifact_id: Optional[str] = None
    name: str
    mime: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    url: Optional[str] = None
    local_path: Optional[str] = None
    ttl_seconds: Optional[int] = None
    kind: Optional[str] = None
    expires_at: Optional[str] = None
    sensitivity: ArtifactSensitivity = Field(default="internal")


class DependencyDeclaration(BaseModel):
    min_agent_version: Optional[str] = None
    required_binaries: list[str] = Field(default_factory=list)
    required_python_packages: list[str] = Field(default_factory=list)
    required_services: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)


class RedactionPolicy(BaseModel):
    enabled: bool = True
    redact_headers: bool = True
    redact_env: bool = True
    redact_fields: list[str] = Field(default_factory=lambda: ["authorization", "cookie", "token", "password", "secret", "api_key"])
    allow_raw_sensitive_data: bool = False


class ResourcePolicy(BaseModel):
    max_runtime_sec: Optional[int] = Field(default=None, ge=1, le=3600)
    max_stdout_bytes: Optional[int] = Field(default=65536, ge=0)
    max_stderr_bytes: Optional[int] = Field(default=65536, ge=0)
    max_artifact_count: Optional[int] = Field(default=8, ge=0)
    max_artifact_bytes: Optional[int] = Field(default=50 * 1024 * 1024, ge=0)
    max_subprocess_count: Optional[int] = Field(default=4, ge=0)
    allowed_filesystem_scope: list[str] = Field(default_factory=list)
    allowed_external_hosts: list[str] = Field(default_factory=list)


class ToolMetadata(BaseModel):
    domain: str = Field(default="system")
    platforms: list[str] = Field(default_factory=lambda: ["any"])
    risk_level: CanonicalRiskLevel = Field(default="safe_read")
    scopes: list[str] = Field(default_factory=list)
    requires_consent: bool = False
    allow_roles: Optional[list[str]] = None
    timeout_sec: Optional[int] = Field(default=None, ge=1, le=3600)
    idempotent: bool = False
    origin: str = Field(default="builtin")
    side_effects: bool = False
    tool_kind: ToolKind = Field(default="diagnostic")


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    category: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class ToolExecutionMetrics(BaseModel):
    duration_ms: Optional[int] = None
    attempt: int = 1
    request_id: Optional[str] = None
    command: Optional[str] = None


class ToolExecutionEnvelope(BaseModel):
    status: EnvelopeStatus
    output: dict[str, Any] = Field(default_factory=dict)
    error: Optional[ToolError] = None
    artifacts: list[ArtifactDescriptor] = Field(default_factory=list)
    metrics: ToolExecutionMetrics = Field(default_factory=ToolExecutionMetrics)
    changed: bool = False
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ToolManifest(BaseModel):
    canonical_id: str
    aliases: list[str] = Field(default_factory=list)
    method: str
    description: str = ""
    contract_version: str = "1.0.0"
    params_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    presentation_schema: dict[str, Any] = Field(default_factory=dict)
    metadata: ToolMetadata = Field(default_factory=ToolMetadata)
    dependencies: DependencyDeclaration = Field(default_factory=DependencyDeclaration)
    lifecycle: LifecycleStatus = Field(default="stable")
    error_codes: list[str] = Field(default_factory=list)
    artifact_types: list[ArtifactTypeDescriptor] = Field(default_factory=list)
    redaction: RedactionPolicy = Field(default_factory=RedactionPolicy)
    resources: ResourcePolicy = Field(default_factory=ResourcePolicy)
