export type DevicePairingPurpose = "login" | "registration";

export type DevicePairingPayload = {
  pairing_id: string;
  purpose: DevicePairingPurpose;
  status: string;
  expires_at?: string | null;
  binding_id?: string | null;
  claim_id?: string | null;
  registration?: {
    status?: string | null;
    device_id?: string | null;
  } | null;
  device?: {
    device_id?: string | null;
    hostname?: string | null;
    os?: string | null;
    agent_version?: string | null;
  } | null;
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

export class DevicePairingApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "DevicePairingApiError";
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

async function readSuccess<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<SuccessResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new DevicePairingApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code,
    );
  }
  return payload.data;
}

export async function fetchDevicePairing(pairingId: string): Promise<DevicePairingPayload> {
  const response = await fetch(`/api/web/registry/browser-pairings/${encodeURIComponent(pairingId)}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  return readSuccess<DevicePairingPayload>(response, "Не удалось загрузить привязку устройства");
}

export async function confirmDevicePairing(
  pairingId: string,
  purpose: DevicePairingPurpose,
): Promise<DevicePairingPayload> {
  const response = await fetch(
    `/api/web/registry/browser-pairings/${encodeURIComponent(pairingId)}/${purpose}/confirm`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    },
  );
  return readSuccess<DevicePairingPayload>(response, "Не удалось подтвердить устройство");
}
