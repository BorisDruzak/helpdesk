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
