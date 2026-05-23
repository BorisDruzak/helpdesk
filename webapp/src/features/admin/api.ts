export type AdminBootstrapPayload = {
  workspace: string;
  features: string[];
  observer: {
    quick_endpoint: string;
    traces_endpoint: string;
  };
};

export type AdminStatusFilter = "all" | "online" | "offline";

export type AdminDevicesPayload = {
  query: string;
  status_filter: AdminStatusFilter;
  summary: {
    visible_count: number;
    online_count: number;
    rollout_targets: number;
    duplicate_hosts: number;
    cleanup_candidates: number;
  };
  filters: {
    status_options: Array<{
      value: AdminStatusFilter;
      label: string;
    }>;
  };
  rollout: Array<{
    target: string;
    channel: string;
    version: string;
    updated_at: string | null;
    updated_by: string | null;
  }>;
  devices: Array<{
    device_id: string;
    hostname: string | null;
    os: string | null;
    agent_version: string | null;
    target: string | null;
    online: boolean;
    last_seen_at: string | null;
    connection_status_label: string;
    latest_update: {
      status: string | null;
      label: string;
      summary: string | null;
    };
    identity_summary: {
      machine_id: string;
      install_id: string | null;
      machine_id_source: string | null;
      identity_scheme: string | null;
      source_label: string;
      is_stable: boolean;
    };
    duplicate_warning: {
      kind: string;
      severity: "danger" | "info" | "neutral" | "success" | "warning";
      title: string;
      description: string;
      duplicate_count: number;
      cleanup_available: boolean;
    } | null;
  }>;
};

export type AdminDeviceCleanupPayload = {
  hostname: string;
  applied: boolean;
  archived_count: number;
  candidates: Array<{
    device_id: string;
    hostname: string | null;
    agent_version: string | null;
    last_seen_at: string | null;
    machine_id_source: string | null;
    online: boolean;
  }>;
  kept_device_ids: string[];
};

export type AdminDeviceArchivePayload = {
  device_id: string;
  was_online: boolean;
  is_deleted: boolean;
  deleted_by: string | null;
  delete_reason: string | null;
};

export type AdminDeviceTokensPayload = {
  device_id: string;
  summary: {
    total_count: number;
    active_count: number;
    revoked_count: number;
  };
  tokens: Array<{
    token_hash: string;
    token_prefix: string | null;
    created_at: string | null;
    expires_at: string | null;
    revoked_at: string | null;
    last_used_at: string | null;
    is_active: boolean;
  }>;
};

export type AdminDeviceInventoryPayload = {
  device_id: string;
  latest_snapshot: {
    id: string;
    source_tool: string;
    collected_at: string;
    status: string;
    summary: string | null;
    result: Record<string, unknown>;
    presentation_schema?: Record<string, unknown>;
    effective_presentation_schema?: Record<string, unknown>;
    presentation_schema_source?: "module_default" | "server_override" | "none";
    device_card_slots?: string[];
  } | null;
  history: Array<{
    id: string;
    collected_at: string;
    status: string;
    summary: string | null;
  }>;
  binding?: AdminDeviceInventoryBinding | null;
  binding_history?: AdminDeviceInventoryBindingHistoryItem[];
  refresh_policy?: AdminDeviceInventoryRefreshPolicy | null;
  refresh_runs?: AdminDeviceInventoryRefreshRun[];
  last_refresh_run?: AdminDeviceInventoryRefreshRun | null;
  profiles?: AdminDeviceProfileItem[];
  binding_suggestions?: AdminBindingSuggestionItem[];
  presence?: AdminDevicePresencePayload | null;
};

export type AdminDeviceInventoryBinding = {
  device_id: string;
  person_id?: string | null;
  asset_id?: string | null;
  source_binding_id?: string | null;
  registration_status?: string | null;
  building: string | null;
  floor: string | null;
  room: string | null;
  department: string | null;
  responsible_user: string | null;
  responsible_user_login: string | null;
  inventory_number: string | null;
  status: string | null;
  tags: string[];
  notes: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type AdminDeviceInventoryBindingUpdate = Omit<AdminDeviceInventoryBinding, "device_id" | "updated_at" | "updated_by">;

export type AdminDeviceInventoryBindingHistoryItem = {
  changed_at: string;
  changed_by: string | null;
  changed_fields: string[];
  old_binding: Record<string, unknown> | null;
  new_binding: Record<string, unknown>;
  reason: string | null;
};

export type AdminDeviceInventoryRefreshPolicy = {
  id: string | null;
  scope: string;
  device_id: string | null;
  enabled: boolean;
  interval_minutes: number;
  jitter_minutes: number;
  last_requested_at: string | null;
  next_due_at: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type AdminDeviceInventoryRefreshRun = {
  id: string;
  device_id: string | null;
  policy_id: string | null;
  bulk_operation_id?: string | null;
  requested_at: string;
  requested_by: string | null;
  status: string;
  job_id: string | null;
  error: string | null;
  completed_at: string | null;
};

export type AdminDeviceProfileItem = {
  requester_id: string | null;
  display_name: string | null;
  full_name: string | null;
  department: string | null;
  building: string | null;
  room: string | null;
  phone: string | null;
  email: string | null;
  login: string | null;
  last_seen_at: string | null;
  source: string;
  status: string;
  active: boolean;
};

export type AdminBindingSuggestionItem = {
  id: string;
  device_id: string;
  source: string;
  source_ref: string | null;
  suggested_binding: Record<string, unknown>;
  profile_snapshot: Record<string, unknown>;
  status: "pending" | "applied" | "ignored" | "rejected" | string;
  confidence: string | null;
  created_at: string;
  updated_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
};

export type AdminDevicePresencePayload = {
  device_id: string;
  latest: {
    id: string;
    collected_at: string;
    received_at: string | null;
    session_state: string | null;
    current_user: string | null;
    idle_seconds: number | null;
    locked: boolean | null;
    result: Record<string, unknown>;
  } | null;
  today: {
    date: string;
    active_seconds: number;
    idle_seconds: number;
    locked_seconds: number;
    offline_seconds: number;
    unknown_seconds: number;
    updated_at: string | null;
  } | null;
  history: Array<{
    id: string;
    collected_at: string;
    session_state: string | null;
    current_user: string | null;
    idle_seconds: number | null;
    locked: boolean | null;
  }>;
};

export type AdminInventoryBindingImportResult = {
  dry_run: boolean;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  changes: Array<{
    row: number;
    device_id: string | null;
    hostname: string | null;
    action: "update" | "skip" | "error" | string;
    changed_fields: string[];
    errors: string[];
  }>;
};

export type AdminInventoryDashboardPayload = {
  totals: Record<string, number>;
  freshness: Record<string, number>;
  by_os: Array<{ label: string; count: number }>;
  by_building: Array<{ label: string; count: number }>;
  by_department: Array<{ label: string; count: number }>;
  binding_gaps: Record<string, number>;
  health: {
    high_disk_usage?: number;
    missing_key_apps?: Array<Record<string, unknown>>;
  };
  refresh: Record<string, unknown>;
  attention?: Record<string, Array<Record<string, unknown>>>;
};

export type AdminBulkRefreshResult = {
  dry_run: boolean;
  selected_count: number;
  online_count: number;
  offline_count: number;
  estimated_waves: number;
  operation_id?: string | null;
  status?: string | null;
  items: Array<{
    device_id: string;
    hostname: string | null;
    status: string;
    reason: string | null;
    wave_index?: number;
  }>;
};

export type AdminDeviceInventoryCollectPayload = {
  device_id: string;
  tool_name: string;
  operation_id: string | null;
  status: string;
  message: string;
  poll_url: string | null;
};

export type AdminConnectionPolicy = "reject_all" | "accept_all" | "manual";

export type AdminConnectionRequestItem = {
  device_id: string;
  status: string;
  ip_address: string | null;
  hostname: string | null;
  created_at: string | null;
  metadata: Record<string, unknown>;
};

export type AdminConnectionRequestsPayload = {
  connection_requests: AdminConnectionRequestItem[];
  count: number;
};

export type AdminRegistryPayload = {
  summary: {
    assets: number;
    people: number;
    locations: number;
    departments: number;
    services: number;
    vendors: number;
    registrations_pending: number;
    registrations_conflicts: number;
    unregistered_devices: number;
    active_bindings: number;
    stale_bindings: number;
    data_quality_issues: number;
    suggestions: number;
  };
  assets: Array<{
    id: string;
    asset_type: string;
    name: string | null;
    hostname: string | null;
    serial_number: string | null;
    inventory_number: string | null;
    status: string;
    source: string;
    device_id: string | null;
    assigned_person_id: string | null;
    location_id: string | null;
    department_id: string | null;
    service_id: string | null;
    vendor_id: string | null;
    owner_name: string | null;
    registration_status: string | null;
    active_binding_id: string | null;
    active_person_id: string | null;
    active_person_name: string | null;
    pending_claim_count: number;
    last_claim_at: string | null;
    current_os_user: string | null;
    department_name: string | null;
    location_name: string | null;
    service_name: string | null;
    vendor_name: string | null;
    ticket_count: number;
    last_seen_at: string | null;
    updated_at: string | null;
  }>;
  people: Array<{
    id: string;
    display_name: string;
    full_name: string | null;
    phone: string | null;
    email: string | null;
    department_id: string | null;
    location_id: string | null;
    department_name: string | null;
    location_name: string | null;
    source: string;
    status: string;
    updated_at: string | null;
  }>;
  locations: Array<{
    id: string;
    building: string | null;
    floor: string | null;
    room: string | null;
    display_name: string;
    source: string;
    status: string;
    updated_at: string | null;
  }>;
  departments: Array<{
    id: string;
    code: string | null;
    name: string;
    source: string;
    status: string;
    updated_at: string | null;
  }>;
  services: Array<{
    id: string;
    code: string | null;
    name: string;
    support_queue: string | null;
    owner_person_id: string | null;
    vendor_id: string | null;
    source: string;
    status: string;
    updated_at: string | null;
  }>;
  vendors: Array<{
    id: string;
    code: string | null;
    name: string;
    contact_name: string | null;
    phone: string | null;
    email: string | null;
    source: string;
    status: string;
    updated_at: string | null;
  }>;
  data_quality: Array<{
    kind: string;
    severity: "danger" | "info" | "neutral" | "success" | "warning";
    title: string;
    description: string;
    object_type: string;
    object_id: string;
  }>;
  suggestions: Array<{
    kind: string;
    confidence: number;
    title: string;
    description: string;
    object_type: string;
    object_id: string;
  }>;
  registration_claims: AdminRegistrationClaim[];
  active_bindings: AdminDeviceUserBinding[];
};

export type AdminRegistrationClaim = {
  claim_id: string;
  device_id: string;
  asset_id: string | null;
  person_id: string | null;
  person_name: string | null;
  status: string;
  claim_type: string;
  relationship_type: string;
  confidence: number | null;
  submitted_at: string | null;
  conflict_reason: string | null;
  profile_snapshot: Record<string, unknown>;
};

export type AdminDeviceUserBinding = {
  binding_id: string;
  device_id: string;
  asset_id: string | null;
  person_id: string;
  person_name: string | null;
  relationship_type: string;
  status: string;
  confirmed_at: string | null;
  confirmed_by_admin: string | null;
};

export type AdminRegistrationTimelineItem = {
  event_id: string;
  claim_id: string | null;
  binding_id: string | null;
  device_id: string;
  person_id: string | null;
  event_type: string;
  actor_id: string | null;
  actor_role: string | null;
  event_at: string | null;
  payload: Record<string, unknown>;
};

export type AdminAccountLoginRequest = {
  request_id: string;
  device_id: string;
  requested_account: Record<string, unknown>;
  matched_person_id: string | null;
  base_binding_id: string | null;
  base_person_id: string | null;
  status: string;
  verification_method: string;
  reason: string | null;
  requested_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  resulting_session_id: string | null;
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

type OkResponse<T> = {
  status: "ok";
} & T;

export class AdminWorkspaceApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminWorkspaceApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

export async function fetchAdminRegistrationClaims(status?: string): Promise<{ items: AdminRegistrationClaim[] }> {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  const response = await fetch(`/api/web/admin/registry/registrations${params.toString() ? `?${params}` : ""}`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить заявки регистрации");
}

export async function approveAdminRegistrationClaim(
  claimId: string,
  replaceExisting = false,
  adminOverrideUserConfirmation = false,
  reason?: string
): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/registrations/${encodeURIComponent(claimId)}/approve`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      replace_existing: replaceExisting,
      admin_override_user_confirmation: adminOverrideUserConfirmation,
      reason,
    })
  });
  await readSuccessResponse(response, "Не удалось подтвердить регистрацию");
}

export async function rejectAdminRegistrationClaim(claimId: string, reason: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/registrations/${encodeURIComponent(claimId)}/reject`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason })
  });
  await readSuccessResponse(response, "Не удалось отклонить регистрацию");
}

export async function revokeAdminDeviceUserBinding(bindingId: string, reason: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/bindings/${encodeURIComponent(bindingId)}/revoke`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason })
  });
  await readSuccessResponse(response, "Не удалось отозвать привязку");
}

export async function fetchAdminDeviceRegistrationTimeline(deviceId: string): Promise<{ items: AdminRegistrationTimelineItem[] }> {
  const response = await fetch(`/api/web/admin/registry/devices/${encodeURIComponent(deviceId)}/registration-timeline`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить историю регистрации");
}

export async function fetchAdminAccountLoginRequests(status?: string): Promise<{ items: AdminAccountLoginRequest[] }> {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  const response = await fetch(`/api/web/admin/registry/account-login-requests${params.toString() ? `?${params}` : ""}`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить заявки на вход в другой аккаунт");
}

export async function approveAdminAccountLoginRequest(requestId: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/account-login-requests/${encodeURIComponent(requestId)}/approve`, {
    method: "POST",
    credentials: "same-origin"
  });
  await readSuccessResponse(response, "Не удалось подтвердить вход в другой аккаунт");
}

export async function rejectAdminAccountLoginRequest(requestId: string, reason: string): Promise<void> {
  const response = await fetch(`/api/web/admin/registry/account-login-requests/${encodeURIComponent(requestId)}/reject`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason })
  });
  await readSuccessResponse(response, "Не удалось отклонить вход в другой аккаунт");
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
    throw new AdminWorkspaceApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

async function readOkResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<OkResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "ok") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new AdminWorkspaceApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  const { status: _status, ...data } = payload;
  return data as T;
}

export async function fetchAdminBootstrap(): Promise<AdminBootstrapPayload> {
  const response = await fetch("/api/web/admin/bootstrap", {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить рабочее место администрирования");
}

type AdminDevicesParams = {
  statusFilter: AdminStatusFilter;
  query: string;
};

function buildAdminDevicesUrl(params: AdminDevicesParams): string {
  const searchParams = new URLSearchParams();
  if (params.statusFilter && params.statusFilter !== "all") {
    searchParams.set("status", params.statusFilter);
  }
  if (params.query.trim()) {
    searchParams.set("query", params.query.trim());
  }
  const queryString = searchParams.toString();
  return queryString ? `/api/web/admin/devices?${queryString}` : "/api/web/admin/devices";
}

export async function fetchAdminDevices(params: AdminDevicesParams): Promise<AdminDevicesPayload> {
  const response = await fetch(buildAdminDevicesUrl(params), {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить inventory устройств");
}

export async function cleanupAdminEnvUuidDuplicates(payload: {
  hostname: string;
  keepDeviceId?: string;
  apply: boolean;
}): Promise<AdminDeviceCleanupPayload> {
  const response = await fetch("/api/web/admin/devices/cleanup_env_duplicates", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      hostname: payload.hostname,
      keep_device_id: payload.keepDeviceId,
      apply: payload.apply
    })
  });
  return readSuccessResponse(response, "Не удалось выполнить безопасную чистку дублей");
}

export async function archiveAdminDevice(deviceId: string, reason: string): Promise<AdminDeviceArchivePayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ reason }),
  });
  return readOkResponse(response, "Не удалось архивировать агента");
}

export async function fetchAdminDeviceTokens(deviceId: string): Promise<AdminDeviceTokensPayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/tokens`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить токены устройства");
}

export async function fetchAdminDeviceInventory(deviceId: string): Promise<AdminDeviceInventoryPayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/inventory`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить инвентарь устройства");
}

export async function saveAdminDeviceInventoryBinding(
  deviceId: string,
  payload: AdminDeviceInventoryBindingUpdate,
  reason?: string | null
): Promise<AdminDeviceInventoryBinding> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/binding`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(reason ? { binding: payload, reason } : payload)
  });
  return readSuccessResponse(response, "Не удалось сохранить привязку устройства");
}

export async function importAdminInventoryBindings(payload: {
  csv_text: string;
  dry_run: boolean;
  reason?: string | null;
}): Promise<AdminInventoryBindingImportResult> {
  const response = await fetch("/api/web/admin/inventory/bindings/import", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось импортировать привязки");
}

export async function fetchAdminInventoryDashboard(staleDays = 7): Promise<AdminInventoryDashboardPayload> {
  const searchParams = new URLSearchParams();
  searchParams.set("stale_days", String(staleDays));
  const response = await fetch(`/api/web/admin/inventory/dashboard?${searchParams.toString()}`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить сводку парка");
}

export function adminInventoryBindingsExportUrl(): string {
  return "/api/web/admin/inventory/bindings/export.csv";
}

export function adminInventoryExportUrl(staleDays = 7): string {
  const searchParams = new URLSearchParams();
  searchParams.set("stale_days", String(staleDays));
  return `/api/web/admin/inventory/export.csv?${searchParams.toString()}`;
}

export function adminInventoryExportXlsxUrl(staleDays = 7): string {
  const searchParams = new URLSearchParams();
  searchParams.set("stale_days", String(staleDays));
  return `/api/web/admin/inventory/export.xlsx?${searchParams.toString()}`;
}

export async function bulkRefreshAdminInventory(payload: {
  device_ids?: string[];
  mode: "selected" | "stale" | "missing" | "department" | "building";
  filters?: Record<string, unknown>;
  wave?: { batch_size?: number; delay_seconds?: number; skip_offline?: boolean };
  dry_run: boolean;
}): Promise<AdminBulkRefreshResult> {
  const response = await fetch("/api/web/admin/inventory/bulk-refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось запустить массовое обновление инвентаря");
}

export async function applyAdminDeviceBindingSuggestion(
  deviceId: string,
  suggestionId: string,
  fields: string[],
  reason?: string | null
): Promise<AdminDeviceInventoryBinding> {
  const response = await fetch(
    `/api/web/admin/devices/${encodeURIComponent(deviceId)}/binding-suggestions/${encodeURIComponent(suggestionId)}/apply`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields, reason })
    }
  );
  return readSuccessResponse(response, "Не удалось применить предложение привязки");
}

export async function ignoreAdminDeviceBindingSuggestion(
  deviceId: string,
  suggestionId: string,
  reason?: string | null
): Promise<AdminBindingSuggestionItem> {
  const response = await fetch(
    `/api/web/admin/devices/${encodeURIComponent(deviceId)}/binding-suggestions/${encodeURIComponent(suggestionId)}/ignore`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason })
    }
  );
  return readSuccessResponse(response, "Не удалось игнорировать предложение привязки");
}

export async function collectAdminDevicePresence(deviceId: string): Promise<AdminDeviceInventoryCollectPayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/presence/collect`, {
    method: "POST",
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось отправить presence.collect");
}

export async function saveAdminDeviceInventoryRefreshPolicy(
  deviceId: string,
  payload: Pick<AdminDeviceInventoryRefreshPolicy, "enabled" | "interval_minutes" | "jitter_minutes">
): Promise<AdminDeviceInventoryRefreshPolicy> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/inventory/refresh-policy`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось сохранить расписание инвентаря");
}

export async function collectAdminDeviceInventory(deviceId: string): Promise<AdminDeviceInventoryCollectPayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/inventory/collect`, {
    method: "POST",
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось отправить inventory.collect");
}

export async function revokeAdminDeviceToken(deviceId: string, tokenHash: string): Promise<void> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/tokens/revoke`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ token_hash: tokenHash })
  });
  await readSuccessResponse(response, "Не удалось отозвать токен устройства");
}

export async function fetchAdminConnectionPolicy(): Promise<{ policy: AdminConnectionPolicy }> {
  const response = await fetch("/api/web/admin/connection_policy", {
    credentials: "same-origin"
  });
  return readOkResponse(response, "Не удалось загрузить политику подключения агентов");
}

export async function updateAdminConnectionPolicy(policy: AdminConnectionPolicy): Promise<{ policy: AdminConnectionPolicy }> {
  const response = await fetch("/api/web/admin/connection_policy", {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ policy })
  });
  return readOkResponse(response, "Не удалось сохранить политику подключения агентов");
}

export async function fetchAdminConnectionRequests(): Promise<AdminConnectionRequestsPayload> {
  const response = await fetch("/api/web/admin/connection_requests", {
    credentials: "same-origin"
  });
  return readOkResponse(response, "Не удалось загрузить запросы подключения агентов");
}

export async function approveAdminConnectionRequest(deviceId: string): Promise<void> {
  const response = await fetch(`/api/web/admin/connection_requests/${encodeURIComponent(deviceId)}/approve`, {
    method: "POST",
    credentials: "same-origin"
  });
  await readOkResponse(response, "Не удалось одобрить подключение агента");
}

export async function rejectAdminConnectionRequest(deviceId: string): Promise<void> {
  const response = await fetch(`/api/web/admin/connection_requests/${encodeURIComponent(deviceId)}/reject`, {
    method: "POST",
    credentials: "same-origin"
  });
  await readOkResponse(response, "Не удалось отклонить подключение агента");
}

export async function fetchAdminRegistry(): Promise<AdminRegistryPayload> {
  const response = await fetch("/api/web/admin/registry", {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить реестры");
}
