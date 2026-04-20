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
  hot_traces: Array<{
    trace_id: string;
    root_kind: string | null;
    root_kind_label: string;
    status: string | null;
    status_label: string;
    ticket_id: string | null;
    device_id: string | null;
    duration_ms: number | null;
    error_count: number;
    span_count: number;
    started_at: string | null;
    finished_at: string | null;
  }>;
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

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class AdminObserverQuickApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminObserverQuickApiError";
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

export async function fetchAdminObserverQuick(lookbackHours: number): Promise<AdminObserverQuickPayload> {
  const searchParams = new URLSearchParams();
  searchParams.set("lookback_hours", String(lookbackHours));
  const response = await fetch(`/api/web/admin/observer/quick?${searchParams.toString()}`, {
    credentials: "same-origin"
  });
  const payload = await readJson<SuccessResponse<AdminObserverQuickPayload> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new AdminObserverQuickApiError(
      errorPayload?.error ?? "Не удалось загрузить observer quick.",
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}
