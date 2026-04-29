export type WebSession = {
  user_login: string;
  actor_role: string;
  auth_type: string;
  default_workspace: string | null;
  available_workspaces: string[];
  permissions?: string[];
  permissions_version?: string;
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
