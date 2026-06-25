import {
  type AdminObserverQuickPayload,
  type AdminObserverRootKindFilter,
  type AdminObserverTraceStatusFilter,
  type AdminObserverTracesPayload,
  fetchAdminObserverQuick,
  fetchAdminObserverTraces,
} from "./api";

type LegacyOkResponse<T> = {
  status: "ok";
} & T;

type TypedSuccessResponse<T> = {
  status: "success";
  data: T;
};

type LegacyErrorResponse = {
  status: "error";
  error?: string;
};

export type ObserverRuntimePayload = {
  enabled: boolean;
  running: boolean;
  stats?: Record<string, number | null>;
  settings?: Record<string, unknown>;
  health?: {
    status?: string;
    issues?: string[];
  };
};

export type ObserverSignatureListItem = {
  error_signature: string;
  title?: string;
  component?: string | null;
  module_name?: string | null;
  tool_name?: string | null;
  occurrences_count?: number;
  affected_devices_count?: number;
  last_seen_at?: string | null;
  first_seen_at?: string | null;
};

export type ObserverSignatureDetailPayload = {
  signature: ObserverSignatureListItem;
  occurrences: Array<{
    occurrence_id: string;
    trace_id: string;
    span_id?: string | null;
    device_id?: string | null;
    ticket_id?: string | null;
    operation_id?: string | null;
    component?: string | null;
    module_name?: string | null;
    tool_name?: string | null;
    error_kind?: string | null;
    exception_type?: string | null;
    failure_stage?: string | null;
    severity?: string | null;
    severity_label?: string | null;
    message_norm?: string | null;
    created_at?: string | null;
  }>;
};

export type ObserverDegradationItem = {
  operation_kind?: string | null;
  operation_kind_label?: string | null;
  tool_name?: string | null;
  module_name?: string | null;
  operations_count?: number;
  timeout_count?: number;
  timeout_rate?: number;
  retried_operations_count?: number;
  retry_rate?: number;
  slow_operations_count?: number;
  slow_rate?: number;
  avg_duration_ms?: number;
  max_duration_ms?: number;
  latest_operation_at?: string | null;
  sample_trace_ids?: string[];
};

export type ObserverTraceDetailPayload = {
  trace: AdminObserverTracesPayload["traces"][number];
  summary: {
    span_count: number;
    error_count: number;
    linked_trace_count: number;
  };
  explanation?: {
    launch_source: string;
    launch_source_label: string;
    actor_role?: string | null;
    actor_id?: string | null;
    actor_display_name?: string | null;
    actor_label?: string | null;
    tool_name?: string | null;
    tool_label?: string | null;
    tool_description?: string | null;
    module_name?: string | null;
    module_label?: string | null;
    preset_id?: string | null;
    preset_label?: string | null;
    preset_description?: string | null;
    error_code?: string | null;
    error_diagnosis?: string | null;
    error_details?: string | null;
    failure_stage?: string | null;
    failure_stage_label?: string | null;
    agent_online?: boolean | null;
    agent_status_label?: string | null;
    agent_last_seen_at?: string | null;
    agent_last_handshake_at?: string | null;
    launch_path?: string[];
    next_actions?: string[];
    human_timeline?: string[];
    debug_refs?: Record<string, unknown>;
  } | null;
  spans: Array<{
    span_id: string;
    trace_id: string;
    parent_span_id?: string | null;
    source_type?: string | null;
    source_ref?: string | null;
    name: string;
    kind?: string | null;
    component?: string | null;
    event_type?: string | null;
    module_name?: string | null;
    tool_name?: string | null;
    status?: string | null;
    status_label?: string | null;
    stage_label?: string | null;
    stage_state?: string | null;
    stage_note?: string | null;
    is_failure_stage?: boolean;
    started_at?: string | null;
    finished_at?: string | null;
    duration_ms?: number | null;
    attrs_json?: Record<string, unknown>;
  }>;
  span_links: Array<{
    id: number;
    span_id: string;
    linked_trace_id?: string | null;
    linked_span_id?: string | null;
    reason?: string | null;
    attrs_json?: Record<string, unknown>;
    created_at?: string | null;
  }>;
  error_occurrences: Array<{
    occurrence_id: string;
    trace_id: string;
    span_id?: string | null;
    error_signature: string;
    device_id?: string | null;
    ticket_id?: string | null;
    operation_id?: string | null;
    component?: string | null;
    module_name?: string | null;
    tool_name?: string | null;
    error_kind?: string | null;
    exception_type?: string | null;
    failure_stage?: string | null;
    severity?: string | null;
    severity_label?: string | null;
    message_norm?: string | null;
    attrs_json?: Record<string, unknown>;
    created_at?: string | null;
  }>;
  agent_actions?: unknown[];
  agent_actions_error?: string | null;
  observer_settings?: {
    action_sync_enabled?: boolean;
    action_sync_limit?: number;
  };
};

export type ObserverAgentActionItem = {
  ts?: string | null;
  source?: string | null;
  action?: string | null;
  category?: string | null;
  stage?: string | null;
  status?: string | null;
  summary?: string | null;
  trace_id?: string | null;
  ticket_id?: string | null;
  operation_id?: string | null;
  tool_name?: string | null;
  details?: Record<string, unknown>;
};

export type ObserverDiagnosticsBundlePayload = {
  summary: {
    primary_trace_id?: string | null;
    related_trace_count?: number;
    span_count?: number;
    error_count?: number;
    agent_action_count?: number;
    agent_audit_count?: number;
    recent_log_count?: number;
  };
  runtime?: Record<string, unknown>;
  device?: Record<string, unknown> | null;
  ticket?: Record<string, unknown> | null;
  primary_trace?: AdminObserverTracesPayload["traces"][number] | null;
  related_traces?: AdminObserverTracesPayload["traces"];
  spans?: ObserverTraceDetailPayload["spans"];
  span_links?: ObserverTraceDetailPayload["span_links"];
  error_occurrences?: ObserverTraceDetailPayload["error_occurrences"];
  agent_actions?: ObserverAgentActionItem[];
  agent_actions_error?: string | null;
  signatures?: ObserverSignatureListItem[];
  degradations?: ObserverDegradationItem[];
  recent_logs?: Array<Record<string, unknown>>;
  agent_audit?: Array<Record<string, unknown>>;
  links?: Record<string, string | null>;
  recommended_next_checks?: string[];
};

export type ObserverIntegrityEvent = {
  event_id: string;
  event_type: string;
  severity: "info" | "warning" | "error" | "critical" | string;
  source: string;
  detected_at?: string | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  resolved_at?: string | null;
  device_id?: string | null;
  ticket_id?: string | null;
  operation_id?: string | null;
  command_id?: string | null;
  device_outbox_id?: number | null;
  outbox_id?: string | null;
  trace_id?: string | null;
  actor_role?: string | null;
  expected?: string | null;
  actual?: string | null;
  evidence?: Record<string, unknown>;
  dedupe_key: string;
  runbook?: string | null;
  status: "active" | "acknowledged" | "resolved" | "suppressed" | string;
  suppression_reason?: string | null;
  occurrence_count?: number | null;
  scan_observation_count?: number | null;
  recurrence_count?: number | null;
  last_reopened_at?: string | null;
  run_id?: string | null;
};

export type ObserverIntegrityPayload = {
  summary: {
    active_by_severity?: Record<string, number>;
    by_status?: Record<string, Record<string, number>>;
    active_total?: number;
    suppressed_total?: number;
    top_active?: ObserverIntegrityEvent[];
  };
  items: ObserverIntegrityEvent[];
};

type RawObserverTraceDetailPayload = Omit<ObserverTraceDetailPayload, "summary"> & {
  summary?: Partial<ObserverTraceDetailPayload["summary"]> | null;
};

export class ObserverWorkbenchApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ObserverWorkbenchApiError";
    this.status = status;
  }
}

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as T;
}

async function readLegacyOk<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<LegacyOkResponse<T> | LegacyErrorResponse>(response);
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new ObserverWorkbenchApiError(errorPayload?.error ?? fallbackMessage, response.status);
  }
  return payload as T;
}

async function readTypedOrLegacyOk<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<TypedSuccessResponse<T> | LegacyOkResponse<T> | LegacyErrorResponse>(response);
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new ObserverWorkbenchApiError(errorPayload?.error ?? fallbackMessage, response.status);
  }
  if (payload.status === "success") {
    return payload.data;
  }
  return payload as T;
}

function normalizeObserverTraceDetailPayload(
  payload: RawObserverTraceDetailPayload
): ObserverTraceDetailPayload {
  const spans = Array.isArray(payload.spans) ? payload.spans : [];
  const spanLinks = Array.isArray(payload.span_links) ? payload.span_links : [];
  const errorOccurrences = Array.isArray(payload.error_occurrences) ? payload.error_occurrences : [];
  const explanation = payload.explanation
    ? {
        ...payload.explanation,
        launch_path: Array.isArray(payload.explanation.launch_path) ? payload.explanation.launch_path : [],
        next_actions: Array.isArray(payload.explanation.next_actions) ? payload.explanation.next_actions : [],
        human_timeline: Array.isArray(payload.explanation.human_timeline) ? payload.explanation.human_timeline : [],
        debug_refs: payload.explanation.debug_refs && typeof payload.explanation.debug_refs === "object" ? payload.explanation.debug_refs : {},
      }
    : null;
  const linkedTraceCount =
    payload.summary?.linked_trace_count ??
    new Set(spanLinks.map((item) => item.linked_trace_id).filter(Boolean)).size;

  return {
    ...payload,
    explanation,
    spans,
    span_links: spanLinks,
    error_occurrences: errorOccurrences,
    summary: {
      span_count: payload.summary?.span_count ?? payload.trace.span_count ?? spans.length,
      error_count: payload.summary?.error_count ?? payload.trace.error_count ?? errorOccurrences.length,
      linked_trace_count: linkedTraceCount,
    },
  };
}

function buildTraceSearchParams(params: {
  deviceId?: string | null;
  lookbackHours?: number;
  statusFilter?: AdminObserverTraceStatusFilter;
  rootKindFilter?: AdminObserverRootKindFilter;
  limit?: number;
  minDurationMs?: number | null;
  query?: string | null;
  traceId?: string | null;
  ticketId?: string | null;
  operationId?: string | null;
  toolName?: string | null;
  moduleName?: string | null;
  errorSignature?: string | null;
  playbookRunId?: number | null;
  stepRunId?: number | null;
  route?: string | null;
}): string {
  const searchParams = new URLSearchParams();
  if (params.deviceId) {
    searchParams.set("device_id", params.deviceId);
  }
  if (params.lookbackHours) {
    searchParams.set("lookback_hours", String(params.lookbackHours));
  }
  if (params.statusFilter && params.statusFilter !== "all") {
    searchParams.set("status", params.statusFilter);
  }
  if (params.rootKindFilter && params.rootKindFilter !== "all") {
    searchParams.set("root_kind", params.rootKindFilter);
  }
  if (params.limit) {
    searchParams.set("limit", String(params.limit));
  }
  if (params.minDurationMs && params.minDurationMs > 0) {
    searchParams.set("min_duration_ms", String(params.minDurationMs));
  }
  if (params.query) {
    searchParams.set("q", params.query);
  }
  if (params.traceId) {
    searchParams.set("trace_id", params.traceId);
  }
  if (params.ticketId) {
    searchParams.set("ticket_id", params.ticketId);
  }
  if (params.operationId) {
    searchParams.set("operation_id", params.operationId);
  }
  if (params.toolName) {
    searchParams.set("tool_name", params.toolName);
  }
  if (params.moduleName) {
    searchParams.set("module_name", params.moduleName);
  }
  if (params.errorSignature) {
    searchParams.set("error_signature", params.errorSignature);
  }
  if (params.playbookRunId && params.playbookRunId > 0) {
    searchParams.set("playbook_run_id", String(params.playbookRunId));
  }
  if (params.stepRunId && params.stepRunId > 0) {
    searchParams.set("step_run_id", String(params.stepRunId));
  }
  if (params.route) {
    searchParams.set("route", params.route);
  }
  return searchParams.toString();
}

export async function fetchObserverWorkbenchQuick(params: {
  deviceId?: string | null;
  lookbackHours: number;
}): Promise<AdminObserverQuickPayload> {
  return fetchAdminObserverQuick(params);
}

export async function fetchObserverWorkbenchTraces(params: {
  deviceId?: string | null;
  lookbackHours: number;
  statusFilter: AdminObserverTraceStatusFilter;
  rootKindFilter: AdminObserverRootKindFilter;
  limit?: number;
  query?: string | null;
  traceId?: string | null;
  ticketId?: string | null;
  operationId?: string | null;
  playbookRunId?: number | null;
  stepRunId?: number | null;
  route?: string | null;
}): Promise<AdminObserverTracesPayload> {
  return fetchAdminObserverTraces(params);
}

export async function fetchObserverWorkbenchTraceDetail(
  traceId: string,
  options?: {
    includeAgentActions?: boolean;
    actionLimit?: number;
  }
): Promise<ObserverTraceDetailPayload> {
  const params = new URLSearchParams();
  if (options?.includeAgentActions) {
    params.set("include_agent_actions", "1");
    params.set("action_limit", String(options.actionLimit ?? 100));
  }
  const query = params.toString();
  const response = await fetch(
    `/api/web/admin/observer/trace-detail/${encodeURIComponent(traceId)}${query ? `?${query}` : ""}`,
    {
      credentials: "same-origin",
    }
  );
  const payload = await readTypedOrLegacyOk<RawObserverTraceDetailPayload>(
    response,
    "Не удалось загрузить детали трассы."
  );
  return normalizeObserverTraceDetailPayload(payload);
}

export async function fetchObserverDiagnosticsBundle(params: {
  traceId?: string | null;
  ticketId?: string | null;
  operationId?: string | null;
  deviceId?: string | null;
  query?: string | null;
  rootKindFilter?: AdminObserverRootKindFilter;
  playbookRunId?: number | null;
  stepRunId?: number | null;
  route?: string | null;
  lookbackHours?: number;
  includeAgentActions?: boolean;
  actionLimit?: number;
}): Promise<ObserverDiagnosticsBundlePayload> {
  const queryString = buildTraceSearchParams({
    traceId: params.traceId,
    ticketId: params.ticketId,
    operationId: params.operationId,
    deviceId: params.deviceId,
    query: params.query,
    rootKindFilter: params.rootKindFilter,
    playbookRunId: params.playbookRunId,
    stepRunId: params.stepRunId,
    route: params.route,
    lookbackHours: params.lookbackHours,
    limit: 20,
  });
  const searchParams = new URLSearchParams(queryString);
  if (params.includeAgentActions) {
    searchParams.set("include_agent_actions", "1");
    searchParams.set("action_limit", String(params.actionLimit ?? 80));
  }
  const response = await fetch(`/api/web/admin/observer/diagnostics/bundle?${searchParams.toString()}`, {
    credentials: "same-origin",
  });
  return readLegacyOk(response, "Не удалось собрать diagnostic bundle observer.");
}

export async function fetchObserverRuntime(): Promise<ObserverRuntimePayload> {
  const response = await fetch("/api/web/admin/observer/runtime", {
    credentials: "same-origin",
  });
  const payload = await readLegacyOk<{ runtime: ObserverRuntimePayload }>(
    response,
    "Не удалось загрузить runtime observer."
  );
  return payload.runtime;
}

export async function fetchObserverIntegrity(params: {
  status?: string | null;
  severity?: string | null;
  deviceId?: string | null;
  limit?: number;
} = {}): Promise<ObserverIntegrityPayload> {
  const searchParams = new URLSearchParams();
  if (params.status) searchParams.set("status", params.status);
  if (params.severity) searchParams.set("severity", params.severity);
  if (params.deviceId) searchParams.set("device_id", params.deviceId);
  if (params.limit) searchParams.set("limit", String(params.limit));
  const query = searchParams.toString();
  const response = await fetch(`/api/web/admin/observer/integrity${query ? `?${query}` : ""}`, {
    credentials: "same-origin",
  });
  return readTypedOrLegacyOk(response, "Не удалось загрузить integrity events observer.");
}

export async function fetchObserverSettings(): Promise<Record<string, unknown>> {
  const response = await fetch("/api/web/admin/observer/settings", {
    credentials: "same-origin",
  });
  const payload = await readLegacyOk<{ settings: Record<string, unknown> }>(
    response,
    "Не удалось загрузить настройки observer."
  );
  return payload.settings;
}

export async function saveObserverSettings(
  settings: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const response = await fetch("/api/web/admin/observer/settings", {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(settings),
  });
  const payload = await readLegacyOk<{ settings: Record<string, unknown> }>(
    response,
    "Не удалось сохранить настройки observer."
  );
  return payload.settings;
}

export async function fetchObserverSignatures(params: {
  deviceId?: string | null;
  lookbackHours: number;
  rootKindFilter: AdminObserverRootKindFilter;
  limit?: number;
}): Promise<ObserverSignatureListItem[]> {
  const queryString = buildTraceSearchParams({
    deviceId: params.deviceId,
    lookbackHours: params.lookbackHours,
    rootKindFilter: params.rootKindFilter,
    limit: params.limit ?? 50,
  });
  const response = await fetch(`/api/web/admin/observer/signatures?${queryString}`, {
    credentials: "same-origin",
  });
  const payload = await readLegacyOk<{ signatures: ObserverSignatureListItem[] }>(
    response,
    "Не удалось загрузить сигнатуры observer."
  );
  return payload.signatures ?? [];
}

export async function fetchObserverSignatureDetail(
  errorSignature: string
): Promise<ObserverSignatureDetailPayload> {
  const response = await fetch(`/api/web/admin/observer/signatures/${encodeURIComponent(errorSignature)}`, {
    credentials: "same-origin",
  });
  return readLegacyOk(response, "Не удалось загрузить детали сигнатуры.");
}

export async function fetchObserverDegradations(params: {
  deviceId?: string | null;
  lookbackHours: number;
  rootKindFilter: AdminObserverRootKindFilter;
  limit?: number;
  minDurationMs?: number | null;
}): Promise<ObserverDegradationItem[]> {
  const queryString = buildTraceSearchParams({
    deviceId: params.deviceId,
    lookbackHours: params.lookbackHours,
    rootKindFilter: params.rootKindFilter,
    limit: params.limit ?? 50,
    minDurationMs: params.minDurationMs ?? null,
  });
  const response = await fetch(`/api/web/admin/observer/degradations?${queryString}`, {
    credentials: "same-origin",
  });
  const payload = await readLegacyOk<{ items: ObserverDegradationItem[] }>(
    response,
    "Не удалось загрузить деградации observer."
  );
  return payload.items ?? [];
}

export async function rebuildObserverTraces(params: {
  deviceId?: string | null;
  lookbackHours: number;
  limit?: number;
}): Promise<{ projected_count: number; trace_ids: string[] }> {
  const queryString = buildTraceSearchParams({
    deviceId: params.deviceId,
    lookbackHours: params.lookbackHours,
    limit: params.limit ?? 50,
  });
  const response = await fetch(`/api/web/admin/observer/traces/rebuild?${queryString}`, {
    method: "POST",
    credentials: "same-origin",
  });
  return readLegacyOk(response, "Не удалось пересобрать observer traces.");
}
