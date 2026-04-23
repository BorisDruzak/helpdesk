export type WebSettingsPayload = {
  capabilities: {
    can_write: boolean;
    actor_role: string;
  };
  overview: {
    queues_count: number;
    active_queues_count: number;
    routing_rules_count: number;
    active_routing_rules_count: number;
    sla_policies_count: number;
    calendars_count: number;
    resolution_codes_count: number;
    audit_records_count: number;
  };
  routing_builder: {
    operators: Array<{
      value: string;
      label: string;
    }>;
    fields: Array<{
      field: string;
      label: string;
      source: string;
      form_key: string | null;
      form_title: string | null;
      field_type: string | null;
    }>;
    forms: Array<{
      key: string;
      request_kind: string;
      title: string;
      fields: Array<{
        key: string;
        label: string;
        field: string;
        type: string;
      }>;
    }>;
  };
  queues: Array<{
    id: number;
    code: string;
    name: string;
    is_triage: boolean;
    is_active: boolean;
    auto_assign_enabled: boolean;
    open_tickets_count: number;
    enabled_routing_rules_count: number;
    members: Array<{
      actor_id: string;
      role_in_queue: string | null;
    }>;
    ola_targets: Array<{
      priority: string;
      ack_min: number;
      processing_min: number;
    }>;
  }>;
  routing_rules: Array<{
    id: number;
    enabled: boolean;
    priority_order: number;
    condition_json: Record<string, unknown> | null;
    target_queue_id: number;
    target_queue_name: string | null;
  }>;
  sla_policies: Array<{
    id: number;
    name: string;
    timezone: string;
    business_hours_json: Record<string, unknown> | null;
    calendar_id: number | null;
    calendar_name: string | null;
    is_default: boolean;
    is_active: boolean;
    open_tickets_count: number;
    targets: Array<{
      priority: string;
      first_response_min: number;
      resolution_min: number;
    }>;
    priority_matrix: Array<{
      impact: number;
      urgency: number;
      priority: string;
    }>;
  }>;
  calendars: Array<{
    id: number;
    code: string;
    name: string;
    timezone: string;
    weekly_hours_json: Record<string, unknown> | null;
    holidays_json: Record<string, unknown> | null;
    is_active: boolean;
    created_at: string | null;
    updated_at: string | null;
  }>;
  resolution_codes: Array<{
    code: string;
    name: string;
    is_active: boolean;
    sort_order: number;
    usage_count: number;
  }>;
  audit: Array<{
    id: number;
    entity_type: string;
    entity_id: string;
    action: string;
    actor_id: string;
    actor_role: string;
    trace_id: string | null;
    created_at: string | null;
  }>;
};

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type LegacyOkResponse<T> =
  | ({ status: "ok" } & T)
  | { status: "error"; error?: string; error_code?: string };

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class WebSettingsApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "WebSettingsApiError";
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
    throw new WebSettingsApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

async function readLegacyOk<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<LegacyOkResponse<T>>(response);
  if (!response.ok || !payload || payload.status !== "ok") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new WebSettingsApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload;
}

async function requestJson<TResponse>(
  url: string,
  init: RequestInit,
  fallbackMessage: string
): Promise<TResponse> {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {})
    }
  });
  return readLegacyOk<TResponse>(response, fallbackMessage);
}

export async function fetchWebSettingsPayload(): Promise<WebSettingsPayload> {
  const response = await fetch("/api/web/settings", {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить настройки.");
}

export async function createWebSettingsQueue(payload: {
  code: string;
  name: string;
  is_triage: boolean;
  auto_assign_enabled: boolean;
}) {
  return requestJson<{ queue: { id: number } }>(
    "/api/web/settings/queues",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    "Не удалось создать очередь."
  );
}

export async function updateWebSettingsQueue(
  queueId: number,
  payload: Partial<{
    code: string;
    name: string;
    is_triage: boolean;
    is_active: boolean;
    auto_assign_enabled: boolean;
  }>
) {
  return requestJson<{ queue: { id: number } }>(
    `/api/web/settings/queues/${queueId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload)
    },
    "Не удалось сохранить очередь."
  );
}

export async function upsertWebSettingsQueueMember(
  queueId: number,
  actorId: string,
  payload: { role_in_queue: string | null }
) {
  return requestJson<{ member: { actor_id: string } }>(
    `/api/web/settings/queues/${queueId}/members/${encodeURIComponent(actorId)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload)
    },
    "Не удалось обновить участника очереди."
  );
}

export async function deleteWebSettingsQueueMember(queueId: number, actorId: string) {
  return requestJson<Record<string, never>>(
    `/api/web/settings/queues/${queueId}/members/${encodeURIComponent(actorId)}`,
    {
      method: "DELETE"
    },
    "Не удалось удалить участника очереди."
  );
}

export async function saveWebSettingsOlaTargets(
  queueId: number,
  olaTargets: Array<{ priority: string; ack_min: number; processing_min: number }>
) {
  return requestJson<{ ola_targets: Array<{ priority: string }> }>(
    `/api/web/settings/queues/${queueId}/ola_targets`,
    {
      method: "PUT",
      body: JSON.stringify({ ola_targets: olaTargets })
    },
    "Не удалось сохранить OLA-цели."
  );
}

export async function createWebSettingsRoutingRule(payload: {
  enabled: boolean;
  priority_order: number;
  condition_json: Record<string, unknown>;
  target_queue_id: number;
}) {
  return requestJson<{ routing_rule: { id: number } }>(
    "/api/web/settings/routing_rules",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    "Не удалось создать правило маршрутизации."
  );
}

export async function updateWebSettingsRoutingRule(
  ruleId: number,
  payload: Partial<{
    enabled: boolean;
    priority_order: number;
    condition_json: Record<string, unknown>;
    target_queue_id: number;
  }>
) {
  return requestJson<{ routing_rule: { id: number } }>(
    `/api/web/settings/routing_rules/${ruleId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload)
    },
    "Не удалось обновить правило маршрутизации."
  );
}

export async function createWebSettingsSlaPolicy(payload: {
  name: string;
  timezone: string;
  business_hours_json?: Record<string, unknown> | null;
  calendar_id?: number | null;
  is_default?: boolean;
}) {
  return requestJson<{ sla_policy: { id: number } }>(
    "/api/web/settings/sla_policies",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    "Не удалось создать SLA-политику."
  );
}

export async function updateWebSettingsSlaPolicy(
  policyId: number,
  payload: Partial<{
    name: string;
    timezone: string;
    business_hours_json: Record<string, unknown> | null;
    calendar_id: number | null;
    is_default: boolean;
    is_active: boolean;
  }>
) {
  return requestJson<{ sla_policy: { id: number } }>(
    `/api/web/settings/sla_policies/${policyId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload)
    },
    "Не удалось обновить SLA-политику."
  );
}

export async function setWebSettingsDefaultSlaPolicy(policyId: number) {
  return requestJson<{ sla_policy: { id: number } }>(
    `/api/web/settings/sla_policies/${policyId}/set_default`,
    {
      method: "POST"
    },
    "Не удалось назначить политику по умолчанию."
  );
}

export async function saveWebSettingsSlaTargets(
  policyId: number,
  targets: Array<{ priority: string; first_response_min: number; resolution_min: number }>
) {
  return requestJson<{ targets: Array<{ priority: string }> }>(
    `/api/web/settings/sla_policies/${policyId}/targets`,
    {
      method: "PUT",
      body: JSON.stringify({ targets })
    },
    "Не удалось сохранить SLA-цели."
  );
}

export async function saveWebSettingsPriorityMatrix(
  policyId: number,
  matrix: Array<{ impact: number; urgency: number; priority: string }>
) {
  return requestJson<{ matrix: Array<{ impact: number; urgency: number }> }>(
    `/api/web/settings/sla_policies/${policyId}/priority_matrix`,
    {
      method: "PUT",
      body: JSON.stringify({ matrix })
    },
    "Не удалось сохранить матрицу приоритетов."
  );
}

export async function createWebSettingsCalendar(payload: {
  code: string;
  name: string;
  timezone: string;
  weekly_hours_json?: Record<string, unknown> | null;
  holidays_json?: Record<string, unknown> | null;
}) {
  return requestJson<{ calendar: { id: number } }>(
    "/api/web/settings/calendars",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    "Не удалось создать календарь."
  );
}

export async function updateWebSettingsCalendar(
  calendarId: number,
  payload: Partial<{
    code: string;
    name: string;
    timezone: string;
    weekly_hours_json: Record<string, unknown> | null;
    holidays_json: Record<string, unknown> | null;
    is_active: boolean;
  }>
) {
  return requestJson<{ calendar: { id: number } }>(
    `/api/web/settings/calendars/${calendarId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload)
    },
    "Не удалось сохранить календарь."
  );
}

export async function createWebSettingsResolutionCode(payload: {
  code: string;
  name: string;
  is_active: boolean;
  sort_order: number;
}) {
  return requestJson<{ resolution_code: { code: string } }>(
    "/api/web/settings/resolution_codes",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    "Не удалось создать код решения."
  );
}

export async function updateWebSettingsResolutionCode(
  code: string,
  payload: Partial<{
    name: string;
    is_active: boolean;
    sort_order: number;
  }>
) {
  return requestJson<{ resolution_code: { code: string } }>(
    `/api/web/settings/resolution_codes/${encodeURIComponent(code)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload)
    },
    "Не удалось сохранить код решения."
  );
}

export async function deleteWebSettingsResolutionCode(code: string) {
  return requestJson<Record<string, never>>(
    `/api/web/settings/resolution_codes/${encodeURIComponent(code)}`,
    {
      method: "DELETE"
    },
    "Не удалось удалить код решения."
  );
}
