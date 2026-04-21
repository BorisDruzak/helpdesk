export type AdminModulesRolloutSettings = {
  preferred_version_rollout_mode: string;
  preferred_version_rollout_mode_label: string;
  sync_after_preferred_change: boolean;
};

export type AdminModuleVersionItem = {
  version: string;
  created_at: string | null;
  uploaded_by: string | null;
  manifest_version: number | null;
  module_api_version: string | null;
  owner_scope: string | null;
  validation_status: string;
  validation_status_label: string;
  preflight_status: string;
  preflight_status_label: string;
  is_preferred: boolean;
  tools_count: number;
  platforms: string[];
  tool_ids: string[];
  warnings_count: number;
  file_exists: boolean;
};

export type AdminModuleFamilyItem = {
  module_name: string;
  preferred_version: string | null;
  preferred_assigned: boolean;
  latest_version: string | null;
  owner_scope: string | null;
  module_api_version: string | null;
  validation_status: string;
  validation_status_label: string;
  version_count: number;
  tools_count: number;
  platforms: string[];
  tool_ids: string[];
  warnings_count: number;
  has_missing_files: boolean;
  versions: AdminModuleVersionItem[];
};

export type AdminModulesPayload = {
  query: string;
  summary: {
    visible_count: number;
    preferred_count: number;
    invalid_count: number;
    missing_files_count: number;
  };
  rollout_settings: AdminModulesRolloutSettings;
  modules: AdminModuleFamilyItem[];
};

export type AdminModulePreferredVersionActionPayload = {
  module_name: string;
  preferred_version: string | null;
  updated_at: string | null;
  updated_by: string | null;
  message: string;
  rollout_summary: {
    mode: string;
    should_sync: boolean;
    desired_updates: number;
    sync_enqueued: number;
    refresh_enqueued: number;
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

export class AdminModulesApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminModulesApiError";
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
    throw new AdminModulesApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

type FetchAdminModulesParams = {
  query: string;
};

type PatchAdminModulesRolloutSettingsParams = {
  preferred_version_rollout_mode?: string;
  sync_after_preferred_change?: boolean;
};

type SetAdminModulePreferredVersionParams = {
  moduleName: string;
  version: string | null;
};

function buildAdminModulesUrl(params: FetchAdminModulesParams): string {
  const searchParams = new URLSearchParams();
  if (params.query.trim()) {
    searchParams.set("query", params.query.trim());
  }
  const queryString = searchParams.toString();
  return queryString ? `/api/web/admin/modules?${queryString}` : "/api/web/admin/modules";
}

export async function fetchAdminModules(
  params: FetchAdminModulesParams
): Promise<AdminModulesPayload> {
  const response = await fetch(buildAdminModulesUrl(params), {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить реестр модулей");
}

export async function patchAdminModulesRolloutSettings(
  params: PatchAdminModulesRolloutSettingsParams
): Promise<AdminModulesRolloutSettings> {
  const response = await fetch("/api/web/admin/modules/rollout_settings", {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(params)
  });
  return readSuccessResponse(response, "Не удалось сохранить rollout policy модулей");
}

export async function setAdminModulePreferredVersion(
  params: SetAdminModulePreferredVersionParams
): Promise<AdminModulePreferredVersionActionPayload> {
  const response = await fetch(`/api/web/admin/modules/${encodeURIComponent(params.moduleName)}/preferred`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      version: params.version
    })
  });
  return readSuccessResponse(response, "Не удалось обновить preferred-версию модуля");
}
