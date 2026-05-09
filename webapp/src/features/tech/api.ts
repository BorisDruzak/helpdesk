export type AdminObserverTraceStatusFilter = "all" | "running" | "failed" | "succeeded" | "timed_out";
export type AdminObserverRootKindFilter =
  | "all"
  | "ticket"
  | "tool_call"
  | "agent_update"
  | "module_install"
  | "module_reconcile"
  | "module_remove"
  | "playbook_run"
  | "web_auth"
  | "observer_runtime"
  | "consent";

export type AdminObserverTraceItem = {
  trace_id: string;
  root_span_id: string | null;
  root_kind: string | null;
  root_kind_label: string;
  status: string | null;
  status_label: string;
  ticket_id: string | null;
  ticket_code?: string | null;
  ticket_title?: string | null;
  ticket_status?: string | null;
  ticket_status_label?: string | null;
  ticket_priority?: string | null;
  queue_name?: string | null;
  requester_display_name?: string | null;
  device_id: string | null;
  device_hostname?: string | null;
  device_label?: string | null;
  operation_id: string | null;
  operation_label?: string | null;
  latest_error_label?: string | null;
  latest_error_stage?: string | null;
  primary_tool_name?: string | null;
  primary_module_name?: string | null;
  display_title?: string | null;
  display_subtitle?: string | null;
  job_id: string | null;
  duration_ms: number | null;
  error_count: number;
  span_count: number;
  started_at: string | null;
  finished_at: string | null;
  attrs_json: Record<string, unknown>;
};

export type AdminObserverQuickPayload = {
  summary: {
    lookback_hours: number;
    recent_trace_count: number;
    hot_trace_count: number;
    signature_count: number;
    degradation_group_count: number;
    dangerous_flow_count: number;
  };
  runtime: {
    enabled: boolean;
    running: boolean;
    health_status: string;
    health_status_label: string;
    pending_trace_count: number | null;
    last_projected_at: string | null;
    issues: string[];
  };
  hot_traces: AdminObserverTraceItem[];
  top_signatures: Array<{
    error_signature: string;
    title: string;
    tool_name: string | null;
    component: string | null;
    occurrences_count: number;
    affected_devices_count: number;
    last_seen_at: string | null;
  }>;
  top_degradations: Array<{
    operation_kind: string | null;
    operation_kind_label: string;
    tool_name: string | null;
    operations_count: number;
    timeout_count: number;
    retried_operations_count: number;
    slow_operations_count: number;
    max_duration_ms: number;
    latest_operation_at: string | null;
  }>;
  dangerous_flows: Array<{
    root_kind: string;
    root_kind_label: string;
    operations_count: number;
    error_count: number;
    timeout_count: number;
    retried_count: number;
    active_count: number;
    latest_operation_at: string | null;
  }>;
  links: {
    quick_endpoint: string;
    traces_endpoint: string;
    runtime_endpoint: string;
  };
};

export type AdminObserverTracesPayload = {
  query: {
    device_id: string | null;
    lookback_hours: number;
    status_filter: AdminObserverTraceStatusFilter;
    root_kind_filter: AdminObserverRootKindFilter;
    limit: number;
    query?: string | null;
    trace_id?: string | null;
    ticket_id?: string | null;
    operation_id?: string | null;
    tool_name?: string | null;
    module_name?: string | null;
    error_signature?: string | null;
    min_duration_ms?: number | null;
    playbook_run_id?: number | null;
    step_run_id?: number | null;
    route?: string | null;
  };
  summary: {
    visible_count: number;
    active_count: number;
    error_count: number;
    selected_trace_id: string | null;
  };
  filters: {
    status_options: Array<{
      value: AdminObserverTraceStatusFilter;
      label: string;
    }>;
    root_kind_options: Array<{
      value: AdminObserverRootKindFilter;
      label: string;
    }>;
  };
  traces: AdminObserverTraceItem[];
  links: {
    detail_endpoint_template: string;
    runtime_endpoint: string;
  };
};

export type AdminObserverTraceDetailPayload = {
  trace: AdminObserverTraceItem;
  summary: {
    span_count: number;
    error_count: number;
    linked_trace_count: number;
  };
  spans: Array<{
    span_id: string;
    trace_id: string;
    parent_span_id: string | null;
    source_type: string | null;
    source_ref: string | null;
    name: string;
    kind: string | null;
    component: string | null;
    event_type: string | null;
    module_name: string | null;
    tool_name: string | null;
    status: string | null;
    status_label: string;
    started_at: string | null;
    finished_at: string | null;
    duration_ms: number | null;
    attrs_json: Record<string, unknown>;
  }>;
  span_links: Array<{
    id: number;
    span_id: string;
    linked_trace_id: string | null;
    linked_span_id: string | null;
    reason: string | null;
    attrs_json: Record<string, unknown>;
    created_at: string | null;
  }>;
  error_occurrences: Array<{
    occurrence_id: string;
    trace_id: string;
    span_id: string | null;
    error_signature: string;
    device_id: string | null;
    ticket_id: string | null;
    operation_id: string | null;
    component: string | null;
    module_name: string | null;
    tool_name: string | null;
    error_kind: string | null;
    exception_type: string | null;
    failure_stage: string | null;
    severity: string | null;
    severity_label: string;
    message_norm: string | null;
    stack_hash: string | null;
    attrs_json: Record<string, unknown>;
    created_at: string | null;
  }>;
};

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class AdminObserverApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminObserverApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as T;
}

async function readSuccessResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<SuccessResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new AdminObserverApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

type ObserverQuickParams = {
  lookbackHours: number;
  deviceId?: string | null;
};

type ObserverTracesParams = {
  deviceId?: string | null;
  lookbackHours: number;
  statusFilter: AdminObserverTraceStatusFilter;
  rootKindFilter: AdminObserverRootKindFilter;
  limit?: number;
  query?: string | null;
  traceId?: string | null;
  ticketId?: string | null;
  operationId?: string | null;
  toolName?: string | null;
  moduleName?: string | null;
  errorSignature?: string | null;
  minDurationMs?: number | null;
  playbookRunId?: number | null;
  stepRunId?: number | null;
  route?: string | null;
};

function buildObserverSearchParams(params: {
  deviceId?: string | null;
  lookbackHours?: number;
  statusFilter?: AdminObserverTraceStatusFilter;
  rootKindFilter?: AdminObserverRootKindFilter;
  limit?: number;
  query?: string | null;
  traceId?: string | null;
  ticketId?: string | null;
  operationId?: string | null;
  toolName?: string | null;
  moduleName?: string | null;
  errorSignature?: string | null;
  minDurationMs?: number | null;
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
  if (params.minDurationMs && params.minDurationMs > 0) {
    searchParams.set("min_duration_ms", String(params.minDurationMs));
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

export async function fetchAdminObserverQuick(params: ObserverQuickParams): Promise<AdminObserverQuickPayload> {
  const queryString = buildObserverSearchParams({
    deviceId: params.deviceId,
    lookbackHours: params.lookbackHours
  });
  const response = await fetch(`/api/web/admin/observer/quick?${queryString}`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить быстрый срез observer.");
}

export async function fetchAdminObserverTraces(params: ObserverTracesParams): Promise<AdminObserverTracesPayload> {
  const queryString = buildObserverSearchParams({
    deviceId: params.deviceId,
    lookbackHours: params.lookbackHours,
    statusFilter: params.statusFilter,
    rootKindFilter: params.rootKindFilter,
    limit: params.limit ?? 12,
    query: params.query,
    traceId: params.traceId,
    ticketId: params.ticketId,
    operationId: params.operationId,
    toolName: params.toolName,
    moduleName: params.moduleName,
    errorSignature: params.errorSignature,
    minDurationMs: params.minDurationMs,
    playbookRunId: params.playbookRunId,
    stepRunId: params.stepRunId,
    route: params.route,
  });
  const response = await fetch(`/api/web/admin/observer/traces?${queryString}`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить список трасс.");
}

export async function fetchAdminObserverTraceDetail(traceId: string): Promise<AdminObserverTraceDetailPayload> {
  const response = await fetch(`/api/web/admin/observer/traces/${traceId}`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить детали трассы.");
}
