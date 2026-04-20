export type AdminDeviceUpdatesPayload = {
  device_id: string;
  device_label: string;
  online: boolean;
  target: string | null;
  current_version: string | null;
  release_channel: string;
  is_release: boolean;
  summary: {
    status: string | null;
    label: string;
    summary: string | null;
  };
  recommendation: {
    update_available: boolean;
    recommendation_source: string;
    recommendation_source_label: string;
    comparison: string;
    comparison_label: string;
    recommended_reason: string | null;
    recommended_reason_label: string | null;
    recommended_build: {
      target: string;
      channel: string;
      version: string;
    } | null;
    assigned_rollout: {
      target: string;
      channel: string;
      version: string;
      updated_at: string | null;
      updated_by: string | null;
    } | null;
  };
  action: {
    enabled: boolean;
    label: string;
    reason_required: boolean;
    endpoint: string;
  };
};

export type AdminDeviceUpdateRunPayload = {
  device_id: string;
  operation_id: string;
  status: string;
  message: string;
  build_source: string;
  poll_url: string;
  build: {
    target: string;
    channel: string;
    version: string;
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

export class AdminDeviceUpdatesApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminDeviceUpdatesApiError";
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
    throw new AdminDeviceUpdatesApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

export async function fetchAdminDeviceUpdates(deviceId: string): Promise<AdminDeviceUpdatesPayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/updates`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить update workflow устройства");
}

export async function runAdminDeviceUpdate(
  deviceId: string,
  payload: { reason: string; restart_delay_sec?: number | null }
): Promise<AdminDeviceUpdateRunPayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/updates/run`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось поставить обновление в очередь");
}
