export type AccessPermissionItem = {
  code: string;
  label: string;
  description: string;
  risk: "high" | "normal" | string;
};

export type AccessPermissionGroup = {
  code: string;
  label: string;
  permissions: AccessPermissionItem[];
};

export type AccessRoleItem = {
  code: string;
  label: string;
  permissions: string[];
};

export type AccessCatalogPayload = {
  version: string;
  roles: AccessRoleItem[];
  groups: AccessPermissionGroup[];
};

export type AccessUserItem = {
  user_login: string;
  actor_role: string;
  role_label: string;
  is_active: boolean;
  groups: string[];
  queue_count: number;
};

export type AccessQueueItem = {
  queue_id: number;
  queue_code: string;
  queue_name: string;
  is_active: boolean;
  members_count: number;
};

export type AccessSummaryPayload = {
  version: string;
  users: AccessUserItem[];
  queues: AccessQueueItem[];
  access_groups: Array<Record<string, unknown>>;
  notes: string[];
};

export type AccessEffectivePayload = {
  actor_id: string;
  actor_role: string;
  role_label: string;
  permissions: string[];
  workspaces: string[];
  groups: string[];
  queues: Array<{
    queue_id: number;
    queue_code: string;
    queue_name: string;
    role_in_queue: string | null;
  }>;
  sources: Record<string, string | string[]>;
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

export class AccessControlApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AccessControlApiError";
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
    throw new AccessControlApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code,
    );
  }
  return payload.data;
}

export async function fetchAccessCatalog(): Promise<AccessCatalogPayload> {
  const response = await fetch("/api/web/admin/access/catalog", {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить каталог RBAC");
}

export async function fetchAccessSummary(): Promise<AccessSummaryPayload> {
  const response = await fetch("/api/web/admin/access/summary", {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить сводку RBAC");
}

export async function fetchEffectiveAccess(user: {
  actorRole: string;
  userLogin: string;
}): Promise<AccessEffectivePayload> {
  const searchParams = new URLSearchParams({
    actor_id: user.userLogin,
    actor_role: user.actorRole,
  });
  const response = await fetch(`/api/web/admin/access/effective?${searchParams.toString()}`, {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось рассчитать effective access");
}
