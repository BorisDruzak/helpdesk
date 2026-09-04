export type ExecutionTarget =
  | "server_builtin"
  | "server_connector"
  | "observer_query"
  | "manual"
  | "endpoint_operation";

export type CapabilityReadinessStatus =
  | "available"
  | "unsupported_platform"
  | "missing_dependency"
  | "consent_required"
  | "integration_not_configured"
  | "credentials_missing"
  | "mapping_missing"
  | "permission_denied"
  | "disabled_by_policy"
  | "unavailable"
  | "unknown"
  | string;

export type CapabilityRiskLevel = "low" | "medium" | "high" | "critical" | "dangerous" | string;
export type CapabilityToolKind = "diagnostic" | "remediation" | "enrichment" | "admin" | string;

export interface CapabilityEvidenceMetadata {
  produces_evidence?: boolean;
  kind?: string;
  domain?: string;
  perspective?: "endpoint" | "server" | "monitoring" | "observer" | "remote_assist" | "manual" | "hybrid" | string;
  passport_eligible?: boolean;
  status_mapping?: unknown;
  severity_mapping?: unknown;
  summary_template?: string;
  artifact_mapping?: unknown;
  [key: string]: unknown;
}

export interface CapabilityArtifactsMetadata {
  may_produce_artifacts?: boolean;
  artifact_kinds?: string[];
  [key: string]: unknown;
}

export interface CapabilityReadiness {
  status: CapabilityReadinessStatus;
  reason?: string | null;
  reason_code?: string | null;
  actions?: string[];
}

export interface CapabilityDescriptor {
  id: string;
  capability_id?: string;
  title: string;
  description?: string | null;
  provider_id: string | null;
  provider_type?: string | null;
  source?: string | null;
  execution_target: ExecutionTarget | string;
  tool_kind?: CapabilityToolKind | null;
  risk_level?: CapabilityRiskLevel | null;
  readiness?: CapabilityReadinessStatus | string;
  reason?: string | null;
  reason_code?: string | null;
  actions?: string[];
  side_effects?: boolean;
  requires_consent?: boolean;
  requires_device?: boolean;
  requires_integration?: boolean;
  integration_key?: string | null;
  platforms?: string[];
  params_schema?: unknown;
  output_schema?: unknown;
  output_contract?: unknown;
  presentation_schema?: unknown;
  effective_presentation_schema?: unknown;
  presentation_schema_source?: "module_default" | "server_override" | "none" | string;
  has_presentation_override?: boolean;
  evidence?: CapabilityEvidenceMetadata;
  artifacts?: CapabilityArtifactsMetadata;
  aliases?: string[];
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface DiagnosticProviderCredentialRef {
  id?: string;
  credential_key: string;
  secret_ref: string;
  status: string;
  metadata?: Record<string, unknown>;
}

export interface DiagnosticProviderConfig {
  id: string;
  provider_id: string;
  provider_type: string;
  integration_key: string | null;
  enabled: boolean;
  status: string;
  config: Record<string, unknown>;
  redaction: Record<string, unknown>;
  health: Record<string, unknown>;
  credential_refs: DiagnosticProviderCredentialRef[];
}

export interface ProviderSummary {
  provider_id: string;
  provider_type: string;
  execution_targets: string[];
  capability_count: number;
  evidence_count: number;
  high_risk_count: number;
  integration_key?: string | null;
  config?: DiagnosticProviderConfig | null;
}

export interface EvidenceMappingRow {
  capability: CapabilityDescriptor;
  mapping_status: "configured" | "inferred" | "missing" | "read-only" | "invalid";
}

export interface ToolPresentationDetail {
  tool_id: string;
  tool_version?: string | null;
  module_default_schema: unknown;
  override_schema: unknown | null;
  effective_schema: unknown;
  source: "module_default" | "server_override" | "none";
  enabled?: boolean;
  updated_at?: string | null;
  updated_by?: string | null;
}
