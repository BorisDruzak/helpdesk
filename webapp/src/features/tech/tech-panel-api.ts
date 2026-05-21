export type TechStatus = "ok" | "success" | "warning" | "degraded" | "error" | "critical" | string;
export type TechReadinessStatus = "ready" | "degraded" | "blocked";
export type TechGateStatus = "ok" | "warning" | "blocked" | "unknown";

export type TechOverviewPayload = {
  alerts?: TechAlert[];
  agent_health?: Record<string, unknown>;
  audit_counters?: Record<string, unknown>;
  generated_at?: string | null;
  operations_health?: Record<string, unknown>;
  postgres_health?: Record<string, unknown>;
  service_health?: Record<string, unknown>;
  update_health?: Record<string, unknown>;
};

export type TechAlert = {
  created_at?: string | null;
  description?: string | null;
  id?: string | number | null;
  severity?: TechStatus;
  title?: string | null;
  [key: string]: unknown;
};

export type TechLogEntry = {
  created_at?: string | null;
  id?: string | number | null;
  level?: string | null;
  logger?: string | null;
  message?: string | null;
  ts?: string | null;
  [key: string]: unknown;
};

export type TechStuckOperation = {
  deadline_at?: string | null;
  device_id?: string | null;
  kind?: string | null;
  operation_id?: string | null;
  queued_at?: string | null;
  sent_at?: string | null;
  started_at?: string | null;
  status?: string | null;
  ticket_id?: string | number | null;
};

export type TechAuditEvent = {
  action?: string | null;
  actor_id?: string | null;
  actor_role?: string | null;
  created_at?: string | null;
  device_id?: string | null;
  entity_id?: string | number | null;
  entity_type?: string | null;
  event_type?: string | null;
  id?: string | number | null;
  severity?: TechStatus;
  title?: string | null;
  [key: string]: unknown;
};

export type TechPanelSnapshot = {
  agentAuditEvents: TechAuditEvent[];
  alerts: TechAlert[];
  logs: TechLogEntry[];
  overview: TechOverviewPayload;
  stuckOperations: TechStuckOperation[];
  userAuditEvents: TechAuditEvent[];
};

export type TechReadinessGate = {
  key: string;
  title: string;
  status: TechGateStatus;
  severity: "info" | "warning" | "critical";
  description: string;
  evidence?: string | null;
  action_label?: string | null;
  action_href?: string | null;
};

export type TechSmokeStep = {
  key: string;
  status: string;
  title?: string | null;
  error?: string | null;
  [key: string]: unknown;
};

export type TechSmokeResult = {
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  steps?: TechSmokeStep[];
  artifact?: string | null;
  [key: string]: unknown;
};

export type TechMarkerStatus = {
  status?: string | null;
  finished_at?: string | null;
  target?: string | null;
  duration_seconds?: number | null;
  artifact?: string | null;
  [key: string]: unknown;
};

export type TechProblemDevice = {
  device_id: string;
  hostname?: string | null;
  status?: string | null;
  last_seen_at?: string | null;
  agent_version?: string | null;
  reasons?: string[];
  href?: string | null;
};

export type TechInventorySchedulerDetails = {
  enabled?: boolean | null;
  running?: boolean | null;
  active_task_count?: number | null;
  duplicate_task_detected?: boolean | null;
  last_tick_at?: string | null;
  last_error?: string | null;
  [key: string]: unknown;
};

export type TechPanelV2Snapshot = {
  generated_at: string;
  readiness: {
    status: TechReadinessStatus;
    score?: number | null;
    blockers: TechReadinessGate[];
    warnings: TechReadinessGate[];
    gates: TechReadinessGate[];
  };
  security: {
    auth_mode: {
      db_users_enabled: boolean;
      config_fallback_enabled: boolean;
      in_memory_fallback_possible: boolean;
      status: TechGateStatus;
      notes: string[];
    };
    session_cookie: {
      secure?: boolean | null;
      httponly?: boolean | null;
      samesite?: "strict" | "lax" | "none" | "unknown" | null;
      status: TechGateStatus;
      notes: string[];
    };
    token_channels: {
      query_token_allowed: boolean;
      query_token_attempts_recent?: number | null;
      status: TechGateStatus;
    };
    agent_connection_policy: {
      mode?: string | null;
      status: TechGateStatus;
      pending_requests: number;
      stale_pending_requests: number;
    };
    audit: {
      failed_logins_recent: number;
      locked_users_count: number;
      invalid_agent_tokens_recent: number;
    };
  };
  runtime: {
    services: Array<{ key: string; title: string; status: "ok" | "degraded" | "down" | "unknown"; details?: string | null; last_seen_at?: string | null }>;
    web_sockets: { ui_connections: number; agent_connections: number };
    schedulers: {
      operation_watchdog: string;
      ticket_sla_watchdog: string;
      ticket_auto_close_watchdog: string;
      inventory_scheduler?: string | null;
      observer_refresh_runtime?: string | null;
    };
    scheduler_details?: {
      inventory_scheduler?: TechInventorySchedulerDetails | null;
      [key: string]: TechInventorySchedulerDetails | null | undefined;
    };
  };
  database: {
    persistence_enabled: boolean;
    reachable: boolean;
    latency_ms?: number | null;
    database?: string | null;
    pool_status?: string | null;
    alembic_current?: string | null;
    alembic_head?: string | null;
    migrations_status: TechGateStatus;
    last_backup?: TechMarkerStatus | null;
    last_restore_drill?: TechMarkerStatus | null;
  };
  agents: {
    total: number;
    online: number;
    offline: number;
    stale: number;
    pending_connection_requests: number;
    reprovision_required: number;
    invalid_token_recent: number;
    below_baseline?: number | null;
    update_in_progress: number;
    update_failed_recent: number;
    update_timed_out_recent: number;
    awaiting_handshake_confirm: number;
    problem_devices: TechProblemDevice[];
    below_baseline_devices?: TechProblemDevice[];
    baseline?: {
      min_version?: string | null;
      below_baseline_count?: number | null;
      devices?: TechProblemDevice[];
    };
  };
  operations: {
    queued_stuck: number;
    sent_stuck: number;
    running_stuck: number;
    waiting_consent?: number | null;
    recent_failed?: number | null;
    outbox_backlog?: number | null;
    recent_nack_count?: number | null;
    items: TechStuckOperation[];
  };
  logs: {
    problem_logs: TechLogEntry[];
    error_count?: number | null;
    warning_count?: number | null;
    critical_count?: number | null;
  };
  alerts: TechAlert[];
  release: {
    branch?: string | null;
    commit?: string | null;
    deployed_at?: string | null;
    webapp_bundle_commit?: string | null;
    gate?: "full" | "quick" | "bypassed" | "unknown";
    dirty?: boolean | null;
    remote_profile?: string | null;
  };
  smoke: {
    last_health_smoke?: TechSmokeResult | null;
    last_business_smoke?: TechSmokeResult | null;
    status: TechGateStatus;
  };
  links: {
    observer: string;
    inventory: string;
    device_operations?: string | null;
    agent_updates: string;
    command_center: string;
    approval_center: string;
    logs?: string | null;
  };
};

export type TechLocatorSeverity = "ok" | "info" | "warning" | "critical" | "unknown";
export type TechLocatorKind = "ticket" | "device" | "hostname" | "operation" | "trace" | "log" | "unknown";

export type TechLocatorLink = {
  label: string;
  href: string;
  kind:
    | "ticket"
    | "device_operations"
    | "observer"
    | "operation"
    | "approval_center"
    | "command_center"
    | "inventory"
    | "agent_updates"
    | "logs";
};

export type TechLocatorMatch = {
  kind: TechLocatorKind;
  id: string;
  title: string;
  status?: string | null;
  severity: TechLocatorSeverity;
  reason: string;
  context: {
    ticket_id?: string | null;
    ticket_code?: string | null;
    device_id?: string | null;
    hostname?: string | null;
    operation_id?: string | null;
    trace_id?: string | null;
    requester_id?: string | null;
    queue_id?: string | number | null;
    assignee_id?: string | null;
    tool_name?: string | null;
    operation_status?: string | null;
    agent_online?: boolean | null;
    last_seen_at?: string | null;
  };
  signals: {
    ticket_open?: boolean;
    ticket_sla_risk?: boolean;
    agent_offline?: boolean;
    stale_agent?: boolean;
    failed_operation?: boolean;
    stuck_operation?: boolean;
    waiting_consent?: boolean;
    outbox_backlog?: boolean;
    observer_errors?: boolean;
    pending_approval?: boolean;
    pending_consent?: boolean;
    inventory_missing_or_stale?: boolean;
  };
  links: TechLocatorLink[];
};

export type TechLocatorPayload = {
  status: "ok";
  query: string;
  normalized_query: string;
  generated_at: string;
  matches: TechLocatorMatch[];
  summary: {
    match_count: number;
    highest_severity: TechLocatorSeverity;
    primary_diagnosis?: string | null;
  };
};

type ErrorResponse = {
  error?: string;
  error_code?: string;
  status: "error";
};

export class TechPanelApiError extends Error {
  errorCode?: string;
  status: number;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "TechPanelApiError";
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

async function readLegacyResponse<T extends Record<string, unknown>>(
  response: Response,
  fallbackMessage: string,
): Promise<T> {
  const payload = await readJson<(T & { status?: "ok" | "success" }) | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new TechPanelApiError(errorPayload?.error ?? fallbackMessage, response.status, errorPayload?.error_code);
  }
  return payload as T;
}

async function readSnapshotResponse(response: Response): Promise<TechPanelV2Snapshot> {
  const payload = await readJson<TechPanelV2Snapshot | ErrorResponse>(response);
  if (!response.ok || !payload || (payload as ErrorResponse).status === "error") {
    const errorPayload = payload && (payload as ErrorResponse).status === "error" ? (payload as ErrorResponse) : null;
    throw new TechPanelApiError(
      errorPayload?.error ?? "Не удалось загрузить снимок техпанели.",
      response.status,
      errorPayload?.error_code,
    );
  }
  return payload as TechPanelV2Snapshot;
}

export async function fetchTechOverview(): Promise<TechOverviewPayload> {
  const response = await fetch("/api/web/admin/tech/overview", { credentials: "same-origin" });
  const payload = await readLegacyResponse<{ overview?: TechOverviewPayload }>(
    response,
    "Не удалось загрузить обзор техпанели.",
  );
  return payload.overview ?? {};
}

export async function fetchTechAlerts(): Promise<TechAlert[]> {
  const response = await fetch("/api/web/admin/tech/alerts", { credentials: "same-origin" });
  const payload = await readLegacyResponse<{ alerts?: TechAlert[] }>(
    response,
    "Не удалось загрузить сигналы техпанели.",
  );
  return payload.alerts ?? [];
}

export async function fetchTechLogs(limit = 50): Promise<TechLogEntry[]> {
  const response = await fetch(`/api/web/admin/tech/logs?limit=${encodeURIComponent(String(limit))}`, {
    credentials: "same-origin",
  });
  const payload = await readLegacyResponse<{ logs?: TechLogEntry[] }>(
    response,
    "Не удалось загрузить проблемные логи.",
  );
  return payload.logs ?? [];
}

export async function fetchTechStuckOperations(): Promise<TechStuckOperation[]> {
  const response = await fetch("/api/web/admin/tech/operations/stuck", { credentials: "same-origin" });
  const payload = await readLegacyResponse<{ operations?: TechStuckOperation[] }>(
    response,
    "Не удалось загрузить зависшие операции.",
  );
  return payload.operations ?? [];
}

export async function fetchTechAgentAudit(limit = 30): Promise<TechAuditEvent[]> {
  const response = await fetch(`/api/web/admin/tech/agents/audit?limit=${encodeURIComponent(String(limit))}`, {
    credentials: "same-origin",
  });
  const payload = await readLegacyResponse<{ events?: TechAuditEvent[] }>(
    response,
    "Не удалось загрузить аудит агентов.",
  );
  return payload.events ?? [];
}

export async function fetchTechUserAudit(limit = 30): Promise<TechAuditEvent[]> {
  const response = await fetch(`/api/web/admin/tech/users/audit?limit=${encodeURIComponent(String(limit))}`, {
    credentials: "same-origin",
  });
  const payload = await readLegacyResponse<{ events?: TechAuditEvent[] }>(
    response,
    "Не удалось загрузить аудит пользователей.",
  );
  return payload.events ?? [];
}

export async function fetchTechPanelSnapshot(): Promise<TechPanelSnapshot> {
  const [overview, alerts, logs, stuckOperations, agentAuditEvents, userAuditEvents] = await Promise.all([
    fetchTechOverview(),
    fetchTechAlerts(),
    fetchTechLogs(50),
    fetchTechStuckOperations(),
    fetchTechAgentAudit(30),
    fetchTechUserAudit(30),
  ]);

  return {
    agentAuditEvents,
    alerts: alerts.length ? alerts : overview.alerts ?? [],
    logs,
    overview,
    stuckOperations,
    userAuditEvents,
  };
}

export async function fetchTechPanelV2Snapshot(): Promise<TechPanelV2Snapshot> {
  const response = await fetch("/api/web/admin/tech/snapshot", { credentials: "same-origin" });
  return readSnapshotResponse(response);
}

export async function locateTechQuery(query: string): Promise<TechLocatorPayload> {
  const normalized = query.trim();
  const response = await fetch(`/api/web/admin/tech/locate?q=${encodeURIComponent(normalized)}`, {
    credentials: "same-origin",
  });
  const payload = await readJson<TechLocatorPayload | ErrorResponse>(response);
  if (!response.ok || !payload || (payload as ErrorResponse).status === "error") {
    const errorPayload = payload && (payload as ErrorResponse).status === "error" ? (payload as ErrorResponse) : null;
    throw new TechPanelApiError(
      errorPayload?.error ?? "Не удалось выполнить быструю локализацию проблемы.",
      response.status,
      errorPayload?.error_code,
    );
  }
  return payload as TechLocatorPayload;
}
