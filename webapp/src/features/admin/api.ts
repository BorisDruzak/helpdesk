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

export type AdminRegistryPayload = {
  summary: {
    assets: number;
    people: number;
    locations: number;
    departments: number;
    services: number;
    vendors: number;
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

export async function fetchAdminRegistry(): Promise<AdminRegistryPayload> {
  const response = await fetch("/api/web/admin/registry", {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить реестры");
}
