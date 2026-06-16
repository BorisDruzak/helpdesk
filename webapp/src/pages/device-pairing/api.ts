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

export type RegistryOption = {
  value: string;
  label: string;
};

export type DeviceRegistrationConfirmationPayload = {
  department_id?: string;
  location_id?: string;
};

export type RegistryOptionsPayload = {
  departments?: RegistryOption[];
  locations?: RegistryOption[];
};

export type DevicePairingCodeLookupPayload = {
  pairing_id: string;
  purpose: DevicePairingPurpose;
  expires_at?: string | null;
  next_url: string;
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

function safePairingErrorMessage(errorPayload: ErrorResponse | null, fallbackMessage: string): string {
  const error = errorPayload?.error?.trim() ?? "";
  if (errorPayload?.error_code === "PAIRING_FORBIDDEN") {
    return "Текущий веб-аккаунт не привязан к этому компьютеру. Выйдите и войдите под привязанным пользователем или привяжите устройство через регистрацию.";
  }
  const normalized = error.toLowerCase();
  if (normalized.includes("department_id")) {
    return "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u043e\u0434\u0440\u0430\u0437\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u0438\u0437 \u0441\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a\u0430.";
  }
  if (normalized.includes("location_id")) {
    return "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043b\u043e\u043a\u0430\u0446\u0438\u044e \u0438\u0437 \u0441\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a\u0430.";
  }
  if (normalized.includes("_id") || normalized.includes(" not found")) {
    return fallbackMessage;
  }
  return error || fallbackMessage;
}

async function readSuccess<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<SuccessResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new DevicePairingApiError(
      safePairingErrorMessage(errorPayload, fallbackMessage),
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

export async function lookupDevicePairingCode(pairingCode: string): Promise<DevicePairingCodeLookupPayload> {
  const response = await fetch("/api/web/registry/browser-pairings/lookup", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ pairing_code: pairingCode.trim() }),
  });
  return readSuccess<DevicePairingCodeLookupPayload>(response, "Код подключения не найден или истек");
}

export async function fetchRegistryOptions(): Promise<RegistryOptionsPayload> {
  const response = await fetch("/api/registry/options", {
    credentials: "same-origin",
    cache: "no-store",
  });
  return readSuccess<RegistryOptionsPayload>(response, "Не удалось загрузить справочники регистрации");
}

export async function confirmDevicePairing(
  pairingId: string,
  purpose: DevicePairingPurpose,
  registrationPayload: DeviceRegistrationConfirmationPayload = {},
): Promise<DevicePairingPayload> {
  const response = await fetch(
    `/api/web/registry/browser-pairings/${encodeURIComponent(pairingId)}/${purpose}/confirm`,
    {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(registrationPayload),
    },
  );
  return readSuccess<DevicePairingPayload>(response, "Не удалось подтвердить устройство");
}
