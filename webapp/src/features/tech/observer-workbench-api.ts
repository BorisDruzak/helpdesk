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

function buildTraceSearchParams(params: {
  deviceId?: string | null;
  lookbackHours?: number;
  statusFilter?: AdminObserverTraceStatusFilter;
  rootKindFilter?: AdminObserverRootKindFilter;
  limit?: number;
  minDurationMs?: number | null;
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
    `/api/admin/tech/traces/${encodeURIComponent(traceId)}${query ? `?${query}` : ""}`,
    {
      credentials: "same-origin",
    }
  );
  return readLegacyOk(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РґРµС‚Р°Р»Рё С‚СЂР°СЃСЃС‹.");
}

export async function fetchObserverRuntime(): Promise<ObserverRuntimePayload> {
  const response = await fetch("/api/admin/tech/traces/runtime", {
    credentials: "same-origin",
  });
  const payload = await readLegacyOk<{ runtime: ObserverRuntimePayload }>(
    response,
    "Не удалось загрузить runtime observer."
  );
  return payload.runtime;
}

export async function fetchObserverSettings(): Promise<Record<string, unknown>> {
  const response = await fetch("/api/admin/settings/observer", {
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
  const response = await fetch("/api/admin/settings/observer", {
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
  const response = await fetch(`/api/admin/tech/signatures?${queryString}`, {
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
  const response = await fetch(`/api/admin/tech/signatures/${encodeURIComponent(errorSignature)}`, {
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
  const response = await fetch(`/api/admin/tech/degradations?${queryString}`, {
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
  const response = await fetch(`/api/admin/tech/traces/rebuild?${queryString}`, {
    method: "POST",
    credentials: "same-origin",
  });
  return readLegacyOk(response, "Не удалось пересобрать observer traces.");
}
