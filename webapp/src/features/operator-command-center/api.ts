export type CommandCenterScope = "my" | "team" | "all";
export type CommandCenterSeverity = "critical" | "warning" | "info";
export type CommandCenterTimerStateName = "ok" | "risk" | "breached" | "unknown";

export type CommandCenterTimerState = {
  state?: CommandCenterTimerStateName;
  due_at?: string | null;
  remaining_seconds?: number | null;
} | null;

export type CommandCenterItem = {
  id: string;
  ticket_id: string;
  ticket_number?: string | null;
  title: string;
  status: string;
  priority?: string | null;
  queue?: string | null;
  assignee?: string | null;
  requester_name?: string | null;
  service_code?: string | null;
  offering_code?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  next_action_owner?: string | null;
  next_action_due_at?: string | null;
  requires_operator_action?: boolean;
  unread_user_messages?: number;
  sla?: CommandCenterTimerState;
  ola?: CommandCenterTimerState;
  operation?: {
    id?: string | null;
    status?: string | null;
    tool_name?: string | null;
    failed_at?: string | null;
    error_summary?: string | null;
  } | null;
  agent?: {
    device_id?: string | null;
    connection_state?: string;
    last_seen_at?: string | null;
  } | null;
  diagnostics?: {
    recommended?: boolean;
    profile_code?: string | null;
    reason?: string | null;
  } | null;
  closure?: {
    blocked?: boolean;
    missing_count?: number | null;
    primary_blocker?: string | null;
  } | null;
  similar_group?: {
    group_key: string;
    count: number;
    window_hours: number;
    sample_ticket_ids: string[];
    reason: string;
  } | null;
  reason: string;
  href: string;
};

export type CommandCenterSection = {
  key:
    | "new_unassigned"
    | "operator_action"
    | "unread_user_messages"
    | "sla_risk"
    | "ola_risk"
    | "pending_approval"
    | "pending_consent"
    | "failed_operation"
    | "agent_offline_active"
    | "diagnostics_recommended"
    | "closure_blocked"
    | "similar_tickets_spike";
  title: string;
  description: string;
  severity: CommandCenterSeverity;
  count: number;
  updated_at?: string | null;
  items: CommandCenterItem[];
  action?: {
    label: string;
    href: string;
  } | null;
};

export type OperatorCommandCenterPayload = {
  generated_at: string;
  scope: CommandCenterScope;
  filters: {
    queue?: string | null;
    assignee?: string | null;
    query?: string | null;
    window_hours: number;
    limit_per_section: number;
  };
  summary: {
    total_attention_items: number;
    critical_count: number;
    warning_count: number;
    info_count: number;
    new_unassigned_count: number;
    operator_action_count: number;
    unread_user_messages_count: number;
    sla_risk_count: number;
    ola_risk_count: number;
    pending_approval_count: number;
    pending_consent_count: number;
    failed_operation_count: number;
    agent_offline_active_count: number;
    diagnostics_recommended_count: number;
    closure_blocked_count: number;
    similar_spikes_count: number;
  };
  sections: CommandCenterSection[];
  metadata?: Record<string, unknown>;
};

export type FetchOperatorCommandCenterParams = {
  scope?: CommandCenterScope;
  queue?: string;
  assignee?: string;
  query?: string;
  limit_per_section?: number;
  window_hours?: number;
  sla_risk_minutes?: number;
  ola_risk_minutes?: number;
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

export class OperatorCommandCenterApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "OperatorCommandCenterApiError";
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

function buildCommandCenterUrl(params: FetchOperatorCommandCenterParams = {}) {
  const searchParams = new URLSearchParams();
  if (params.scope) {
    searchParams.set("scope", params.scope);
  }
  if (params.queue) {
    searchParams.set("queue", params.queue);
  }
  if (params.assignee) {
    searchParams.set("assignee", params.assignee);
  }
  if (params.query) {
    searchParams.set("query", params.query);
  }
  for (const [key, value] of Object.entries({
    limit_per_section: params.limit_per_section,
    window_hours: params.window_hours,
    sla_risk_minutes: params.sla_risk_minutes,
    ola_risk_minutes: params.ola_risk_minutes,
  })) {
    if (typeof value === "number" && Number.isFinite(value)) {
      searchParams.set(key, String(Math.floor(value)));
    }
  }
  const suffix = searchParams.toString();
  return `/api/web/support/command-center${suffix ? `?${suffix}` : ""}`;
}

export async function fetchOperatorCommandCenter(
  params: FetchOperatorCommandCenterParams = {},
): Promise<OperatorCommandCenterPayload> {
  const response = await fetch(buildCommandCenterUrl(params), {
    credentials: "same-origin",
  });
  const payload = await readJson<SuccessResponse<OperatorCommandCenterPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new OperatorCommandCenterApiError(
      errorPayload?.error ?? "Не удалось загрузить рабочий центр",
      response.status,
      errorPayload?.error_code,
    );
  }

  return payload.data;
}
