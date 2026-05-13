export type ExecutionTarget =
  | "agent_builtin"
  | "agent_managed_module"
  | "agent_recipe"
  | "server_builtin"
  | "server_connector"
  | "observer_query"
  | "remote_assist"
  | "manual"
  | "hybrid";

export type CapabilityReadinessStatus =
  | "available"
  | "install_required"
  | "installing"
  | "unsupported_platform"
  | "agent_offline"
  | "runner_not_installed"
  | "runner_install_required"
  | "runner_installing"
  | "runner_outdated"
  | "primitive_not_supported"
  | "recipe_not_published"
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
  runner_provider_id?: string | null;
  min_runner_version?: string | null;
  primitive_id?: string | null;
  primitive_version?: string | null;
  recipe_version_id?: string | null;
  capability_version_id?: string | null;
  supports_auto_install_runner?: boolean;
  tool_kind?: CapabilityToolKind | null;
  risk_level?: CapabilityRiskLevel | null;
  readiness?: CapabilityReadinessStatus | string;
  reason?: string | null;
  reason_code?: string | null;
  actions?: string[];
  side_effects?: boolean;
  requires_consent?: boolean;
  requires_device?: boolean;
  requires_agent_online?: boolean;
  supports_auto_install?: boolean;
  requires_integration?: boolean;
  integration_key?: string | null;
  install_required_on_agent?: boolean;
  platforms?: string[];
  params_schema?: unknown;
  output_schema?: unknown;
  output_contract?: unknown;
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

export interface AgentRecipePrimitive {
  primitive_id: string;
  primitive_version: string;
  title: string;
  description?: string | null;
  platforms: string[];
  runner_provider_id?: string;
  runner_version?: string;
  params_schema?: unknown;
  output_schema?: unknown;
  output_contract?: unknown;
  safety?: Record<string, unknown>;
  risk_level?: string;
}

export interface AgentRecipeCreatePayload {
  canonical_id: string;
  title: string;
  description?: string;
  primitive_id: string;
  primitive_version?: string;
  platforms: Array<"win32" | "linux">;
  min_runner_version?: string;
  domain?: string;
  evidence_kind?: string;
  params?: Record<string, unknown>;
  recipe?: Record<string, unknown>;
  evidence_mapping?: Record<string, unknown>;
}

export interface AgentRecipeCreateResult {
  capability_id: string;
  capability_version_id: string;
  recipe_version_id: string;
  capability: CapabilityDescriptor;
}

export interface RunnerRolloutTarget {
  target_id: string;
  device_id: string;
  wave_id?: string | null;
  module_name: string;
  target_version: string;
  rollback_version?: string | null;
  status: string;
  current_version?: string | null;
  operation_id?: string | null;
  last_error_code?: string | null;
  last_error_message?: string | null;
  desired_set_at?: string | null;
  completed_at?: string | null;
}

export interface RunnerRolloutWave {
  wave_id: string;
  wave_index: number;
  status: string;
  target_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  targets: RunnerRolloutTarget[];
}

export interface RunnerRolloutPlan {
  plan_id: string;
  module_name: string;
  target_version: string;
  rollback_version?: string | null;
  status: string;
  strategy: string;
  canary_size: number;
  wave_size: number;
  max_concurrency: number;
  target_count: number;
  created_by?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  rolled_back_at?: string | null;
  waves: RunnerRolloutWave[];
  targets: RunnerRolloutTarget[];
  current_wave?: RunnerRolloutWave | null;
  summary: Record<string, number>;
  metadata?: Record<string, unknown>;
}

export interface RunnerRolloutSummary {
  provider_id: string;
  module_name: string;
  installed_active_devices: number;
  rollout_targets: number;
  versions: Array<{ version: string; count: number }>;
  latest_plan?: RunnerRolloutPlan | null;
}

export interface RunnerRolloutPayload {
  summary: RunnerRolloutSummary;
  plans: RunnerRolloutPlan[];
}

export interface RunnerRolloutCreatePayload {
  target_version: string;
  rollback_version?: string;
  target_device_ids?: string[];
  canary_size?: number;
  wave_size?: number;
  max_concurrency?: number;
}
