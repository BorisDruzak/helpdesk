import type { DeviceOperationsPayload, FetchDeviceOperationsParams } from "./types";

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class DeviceOperationsApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "DeviceOperationsApiError";
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
    throw new DeviceOperationsApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code,
    );
  }
  return payload.data;
}

function buildDeviceOperationsUrl(deviceId: string, params: FetchDeviceOperationsParams = {}): string {
  const searchParams = new URLSearchParams();
  const setBool = (key: keyof FetchDeviceOperationsParams) => {
    const value = params[key];
    if (typeof value === "boolean") {
      searchParams.set(key, value ? "true" : "false");
    }
  };
  const setNumber = (key: keyof FetchDeviceOperationsParams) => {
    const value = params[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      searchParams.set(key, String(value));
    }
  };
  setBool("include_traces");
  setBool("include_outbox");
  setBool("include_history");
  setNumber("trace_limit");
  setNumber("outbox_limit");
  setNumber("operation_limit");
  const query = searchParams.toString();
  return `/api/web/admin/device-operations/${encodeURIComponent(deviceId)}${query ? `?${query}` : ""}`;
}

export async function fetchDeviceOperations(
  deviceId: string,
  params?: FetchDeviceOperationsParams,
): Promise<DeviceOperationsPayload> {
  const response = await fetch(buildDeviceOperationsUrl(deviceId, params), {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить операции устройства.");
}
