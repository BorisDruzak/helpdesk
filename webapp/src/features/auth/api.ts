export type WebSession = {
  user_login: string;
  actor_role: string;
  auth_type: string;
  default_workspace: string | null;
  available_workspaces: string[];
  permissions?: string[];
  permissions_version?: string;
};

export type WebSessionRegisterDeviceLink = {
  accepted: boolean;
  purpose: string;
  expires_at?: string | null;
};

export type WebSessionRegisterResult = {
  user_login: string;
  actor_role: string;
  next_path: string;
  device_link?: WebSessionRegisterDeviceLink | null;
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

export class WebSessionApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "WebSessionApiError";
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

export async function fetchCurrentSession(): Promise<WebSession | null> {
  const response = await fetch("/api/web/session/me", {
    credentials: "same-origin"
  });

  if (response.status === 401) {
    return null;
  }

  const payload = await readJson<SuccessResponse<WebSession> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new WebSessionApiError(
      errorPayload?.error ?? "Не удалось получить сессию",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function loginWebSession(credentials: {
  login: string;
  password: string;
}): Promise<WebSession> {
  const response = await fetch("/api/web/session/login", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(credentials)
  });
  const payload = await readJson<SuccessResponse<WebSession> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new WebSessionApiError(
      errorPayload?.error ?? "Не удалось выполнить вход",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function registerWebSessionAccount(input: {
  login: string;
  password: string;
  passwordRepeat: string;
  deviceLinkCode?: string;
}): Promise<WebSessionRegisterResult> {
  const body: {
    login: string;
    password: string;
    password_repeat: string;
    device_link_code?: string;
  } = {
    login: input.login,
    password: input.password,
    password_repeat: input.passwordRepeat
  };
  const deviceLinkCode = input.deviceLinkCode?.trim();
  if (deviceLinkCode) {
    body.device_link_code = deviceLinkCode;
  }

  const response = await fetch("/api/web/session/register", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  const payload = await readJson<SuccessResponse<WebSessionRegisterResult> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new WebSessionApiError(
      errorPayload?.error ?? "Не удалось создать аккаунт",
      response.status,
      errorPayload?.error_code
    );
  }

  return payload.data;
}

export async function logoutWebSession(): Promise<void> {
  const response = await fetch("/api/web/session/logout", {
    method: "POST",
    credentials: "same-origin"
  });

  if (response.status === 401) {
    return;
  }

  if (!response.ok) {
    const payload = await readJson<ErrorResponse>(response);
    throw new WebSessionApiError(
      payload?.error ?? "Не удалось завершить сеанс",
      response.status,
      payload?.error_code
    );
  }
}
