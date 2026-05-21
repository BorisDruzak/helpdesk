export type TechStatus = "ok" | "success" | "warning" | "degraded" | "error" | "critical" | string;

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
