import { SupportBootstrapApiError } from "../queues/api";

type ApiErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

type ApiSuccessResponse<T> = {
  status: "success";
  data: T;
};

type ApiOkResponse<T> = {
  status: "ok";
} & T;

export type DiagnosticStatus = "ok" | "warning" | "error" | "info" | "unknown" | string;

export type DiagnosticEvidence = {
  id: string;
  ticket_id: string;
  session_id: string | null;
  step_id: string | null;
  source_type: string;
  source_id: string | null;
  provider_id: string | null;
  capability_id: string | null;
  kind: string;
  domain: string;
  perspective: string;
  title: string;
  summary: string | null;
  status: DiagnosticStatus;
  severity: string | null;
  confidence: number | null;
  observed_at: string | null;
  normalized_payload: Record<string, unknown>;
  artifact_refs: Array<Record<string, unknown>>;
  trace_id: string | null;
  passport_eligible: boolean;
  selected_for_passport: boolean;
};

export type DiagnosticFinding = {
  id: string;
  ticket_id: string;
  session_id: string | null;
  root_cause_code: string | null;
  title: string;
  description: string | null;
  confidence: number | null;
  status: string;
  evidence_ids: string[];
  recommended_actions: string[];
};

export type DiagnosticPerspectiveSummary = {
  count: number;
  status: DiagnosticStatus;
  latest: DiagnosticEvidence | null;
};

export type DiagnosticRecommendedAction = {
  id: string;
  title: string;
  kind?: string;
  capability_id?: string;
};

export type DiagnosticProfile = {
  id: string;
  version: string;
  title: string;
  recommended_capabilities: string[];
  recommended_playbooks: string[];
  required_evidence_kinds: string[];
  optional_evidence_kinds: string[];
};

export type DiagnosticOverview = {
  ticket_id: string;
  device_id: string | null;
  status: DiagnosticStatus;
  summary: string;
  profile: DiagnosticProfile;
  evidence_counts: Record<string, number>;
  perspectives: Record<string, DiagnosticPerspectiveSummary>;
  latest_evidence: DiagnosticEvidence[];
  latest_operations: Array<Record<string, unknown>>;
  latest_playbooks: Array<Record<string, unknown>>;
  remote_assist: {
    count: number;
    latest: Record<string, unknown> | null;
  };
  observer: {
    root_trace_id: string | null;
    available: boolean;
  };
  artifacts: {
    count: number;
    items: Array<Record<string, unknown>>;
  };
  findings: DiagnosticFinding[];
  recommended_actions: DiagnosticRecommendedAction[];
};

export type DiagnosticSession = {
  id: string;
  ticket_id: string;
  profile_id: string | null;
  profile_version: string | null;
  status: string;
  trigger_source: string | null;
  started_by_user_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  summary: string | null;
  confidence: number | null;
};

export type DiagnosticBundle = {
  id: string;
  ticket_id: string;
  session_id: string | null;
  status: string;
  summary: string | null;
  evidence_ids: string[];
  artifact_refs: Array<Record<string, unknown>>;
  observer_trace_ids: string[];
  remote_assist_session_ids: string[];
  payload: Record<string, unknown>;
};

export type PassportAttachedEvidence = {
  id: number;
  ticket_id: string;
  passport_id: number | null;
  evidence_type: string;
  source_ref: string | null;
  source_kind: string | null;
  source_id: string | null;
  title: string;
  summary: string | null;
  verification_status: string;
};

export type DiagnosticCapability = {
  id: string;
  capability_id?: string;
  title: string;
  description?: string | null;
  provider_id: string | null;
  provider_type?: string | null;
  source?: string | null;
  execution_target: string;
  tool_kind?: string | null;
  risk_level: string;
  readiness: string;
  reason: string | null;
  reason_code?: string | null;
  actions: string[];
  side_effects?: boolean;
  requires_consent: boolean;
  requires_device?: boolean;
  requires_agent_online?: boolean;
  supports_auto_install?: boolean;
  requires_integration: boolean;
  integration_key: string | null;
  install_required_on_agent: boolean;
  platforms?: string[];
  params_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  output_contract?: Record<string, unknown>;
  evidence?: {
    produces_evidence?: boolean;
    kind?: string;
    domain?: string;
    perspective?: string;
    passport_eligible?: boolean;
    [key: string]: unknown;
  };
  artifacts?: {
    may_produce_artifacts?: boolean;
    artifact_kinds?: string[];
    [key: string]: unknown;
  };
  aliases?: string[];
};

export type DiagnosticCapabilityRunResult = {
  status: string;
  capability_id?: string;
  execution_target?: string;
  provider_id?: string;
  operation_id?: string | null;
  event_id?: string | number | null;
  diagnostic_evidence_id?: string | null;
  evidence_persisted?: boolean;
  output?: Record<string, unknown>;
  evidence?: Record<string, unknown>;
  message?: string;
  error?: string;
  error_code?: string;
  [key: string]: unknown;
};

export type DiagnosticProviderCredentialRef = {
  id?: string;
  credential_key: string;
  secret_ref: string;
  status: string;
  metadata?: Record<string, unknown>;
};

export type DiagnosticProviderConfig = {
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
};

function ticketDiagnosticsBase(ticketId: string): string {
  return `/api/web/support/tickets/${encodeURIComponent(ticketId)}/diagnostics`;
}

export type DiagnosticProfileRunResult = {
  ticket_id: string;
  profile_id: string;
  session: DiagnosticSession;
  steps: Array<Record<string, unknown>>;
  evidence_count: number;
  selected_for_passport_count: number;
  latest_evidence: DiagnosticEvidence[];
  findings: DiagnosticFinding[];
};

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as T;
}

function assertSuccess<T>(payload: ApiSuccessResponse<T> | ApiErrorResponse | null, response: Response, fallback: string): T {
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(errorPayload?.error ?? fallback, response.status, errorPayload?.error_code);
  }
  return payload.data;
}

function assertOk<T>(payload: ApiOkResponse<T> | ApiErrorResponse | null, response: Response, fallback: string): T {
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(errorPayload?.error ?? fallback, response.status, errorPayload?.error_code);
  }
  return payload as ApiOkResponse<T>;
}

export async function getTicketDiagnosticsOverview(ticketId: string): Promise<DiagnosticOverview> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/overview`, {
    credentials: "same-origin",
  });
  const payload = await readJson<ApiSuccessResponse<DiagnosticOverview> | ApiErrorResponse>(response);
  return assertSuccess(payload, response, "Unable to load diagnostics overview");
}

export async function listTicketDiagnosticCapabilities(ticketId: string): Promise<DiagnosticCapability[]> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/capabilities`, {
    credentials: "same-origin",
  });
  const payload = await readJson<ApiOkResponse<{ capabilities: DiagnosticCapability[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load diagnostic capabilities").capabilities;
}

export async function runTicketDiagnosticCapability(
  ticketId: string,
  capabilityId: string,
  payload: { params?: Record<string, unknown>; session_id?: string | null; timeout_ms?: number } = {},
): Promise<DiagnosticCapabilityRunResult> {
  const response = await fetch(
    `${ticketDiagnosticsBase(ticketId)}/capabilities/${encodeURIComponent(capabilityId)}/run`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const result = await readJson<DiagnosticCapabilityRunResult | ApiErrorResponse>(response);
  if (!response.ok || !result || result.status === "error") {
    const errorPayload = result && result.status === "error" ? result : null;
    throw new SupportBootstrapApiError(
      errorPayload?.error ?? "Unable to run diagnostic capability",
      response.status,
      errorPayload?.error_code,
    );
  }
  return result as DiagnosticCapabilityRunResult;
}

export async function listDiagnosticSessions(ticketId: string): Promise<DiagnosticSession[]> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/sessions`, { credentials: "same-origin" });
  const payload = await readJson<ApiOkResponse<{ sessions: DiagnosticSession[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load diagnostic sessions").sessions;
}

export async function createDiagnosticSession(ticketId: string, payload: { profile_id?: string; trigger_source?: string }): Promise<DiagnosticSession> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/sessions`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readJson<ApiOkResponse<{ session: DiagnosticSession }> | ApiErrorResponse>(response);
  return assertOk(result, response, "Unable to create diagnostic session").session;
}

export async function listDiagnosticEvidence(ticketId: string): Promise<DiagnosticEvidence[]> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/evidence`, { credentials: "same-origin" });
  const payload = await readJson<ApiOkResponse<{ evidence: DiagnosticEvidence[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load diagnostic evidence").evidence;
}

export async function createManualEvidence(
  ticketId: string,
  payload: {
    title: string;
    summary?: string;
    status?: string;
    kind?: string;
    domain?: string;
    perspective?: string;
    passport_eligible?: boolean;
  },
): Promise<DiagnosticEvidence> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/evidence/manual`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readJson<ApiOkResponse<{ evidence: DiagnosticEvidence }> | ApiErrorResponse>(response);
  return assertOk(result, response, "Unable to create manual diagnostic evidence").evidence;
}

export async function updateDiagnosticEvidence(ticketId: string, evidenceId: string, patch: { selected_for_passport?: boolean }): Promise<DiagnosticEvidence> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/evidence/${encodeURIComponent(evidenceId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  const payload = await readJson<ApiOkResponse<{ evidence: DiagnosticEvidence }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to update diagnostic evidence").evidence;
}

export async function listDiagnosticFindings(ticketId: string): Promise<DiagnosticFinding[]> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/findings`, { credentials: "same-origin" });
  const payload = await readJson<ApiOkResponse<{ findings: DiagnosticFinding[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load diagnostic findings").findings;
}

export async function evaluateDiagnosticFindings(ticketId: string): Promise<DiagnosticFinding[]> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/findings/evaluate`, {
    method: "POST",
    credentials: "same-origin",
  });
  const payload = await readJson<ApiOkResponse<{ findings: DiagnosticFinding[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to evaluate diagnostic findings").findings;
}

export async function buildDiagnosticBundle(ticketId: string, payload: Record<string, unknown> = {}): Promise<DiagnosticBundle> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/bundle`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readJson<ApiOkResponse<{ bundle: DiagnosticBundle }> | ApiErrorResponse>(response);
  return assertOk(result, response, "Unable to build diagnostic bundle").bundle;
}

export async function runDiagnosticProfile(
  ticketId: string,
  payload: { profile_id?: string; params?: Record<string, unknown>; auto_select_evidence?: boolean },
): Promise<DiagnosticProfileRunResult> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/run-profile`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readJson<ApiOkResponse<DiagnosticProfileRunResult> | ApiErrorResponse>(response);
  return assertOk(result, response, "Unable to run diagnostic profile");
}

export async function attachSelectedDiagnosticEvidenceToPassport(ticketId: string): Promise<PassportAttachedEvidence[]> {
  const response = await fetch(`${ticketDiagnosticsBase(ticketId)}/passport/attach-selected`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const result = await readJson<ApiOkResponse<{ evidence: PassportAttachedEvidence[]; attached_count: number }> | ApiErrorResponse>(response);
  return assertOk(result, response, "Unable to attach diagnostic evidence to passport").evidence;
}

export async function listDiagnosticProviderConfigs(): Promise<DiagnosticProviderConfig[]> {
  const response = await fetch("/api/web/admin/diagnostics/providers/configs", { credentials: "same-origin" });
  const payload = await readJson<ApiOkResponse<{ provider_configs: DiagnosticProviderConfig[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Unable to load diagnostic provider configs").provider_configs;
}

export async function upsertDiagnosticProviderConfig(
  providerId: string,
  payload: {
    provider_type?: string;
    integration_key?: string | null;
    enabled?: boolean;
    config?: Record<string, unknown>;
    credential_refs?: Array<{
      credential_key: string;
      secret_ref: string;
      status?: string;
      metadata?: Record<string, unknown>;
    }>;
    health?: Record<string, unknown>;
  },
): Promise<DiagnosticProviderConfig> {
  const response = await fetch(`/api/web/admin/diagnostics/providers/configs/${encodeURIComponent(providerId)}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readJson<ApiOkResponse<{ provider_config: DiagnosticProviderConfig }> | ApiErrorResponse>(response);
  return assertOk(result, response, "Unable to save diagnostic provider config").provider_config;
}
