type SuccessResponse<T> = {
  status: "ok";
} & T;

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
  details?: unknown;
  preflight_errors?: string[];
  conflicts?: unknown[];
};

export type ModuleWorkbenchRolloutSettings = {
  preferred_version_rollout_mode: string;
  sync_after_preferred_change: boolean;
};

export type ModuleWorkbenchVersionRecord = {
  module_name: string;
  version: string;
  sha256?: string;
  size?: number;
  created_at: string | null;
  uploaded_by: string | null;
  manifest_version?: number | null;
  module_api_version?: string | null;
  owner_scope?: string | null;
  legacy_manifest?: boolean;
  validation_status: string;
  validation_status_label?: string | null;
  preflight_status: string;
  preflight_status_label?: string | null;
  warnings?: string[];
  platforms?: string[];
  tools_count?: number;
  has_full_metadata?: boolean;
  is_preferred?: boolean;
  preferred_version?: string | null;
  tool_ids?: string[];
  file_exists?: boolean;
  file_missing?: boolean;
  storage_path?: string;
  manifest_json?: Record<string, unknown>;
  validation_json?: Record<string, unknown>;
  tools?: Array<Record<string, unknown>>;
  requirements?: string[];
  optional_requirements?: string[];
};

export type ModuleWorkbenchFamilyRecord = {
  module_name: string;
  preferred_version: string | null;
  preferred_assigned: boolean;
  latest_version: string | null;
  owner_scope: string | null;
  module_api_version: string | null;
  versions: ModuleWorkbenchVersionRecord[];
};

export type ModuleWorkbenchSourceFile = {
  path: string;
  size_bytes: number;
  language: string;
  content: string;
  detected_tools?: Array<{
    method?: string;
    tool_name?: string;
    strategy?: string;
  }>;
  parse_errors?: string[];
};

export type ModuleWorkbenchToolDraft = {
  tool_name: string;
  aliases: string[];
  method_name: string;
  description: string;
  params_schema: Record<string, unknown> | unknown[];
  output_schema: Record<string, unknown> | unknown[];
  output_contract: Record<string, unknown>;
  presets: Array<Record<string, unknown>>;
  capabilities: string[];
  metadata: Record<string, unknown>;
  contract_version: string;
  dependencies: Record<string, unknown>;
  lifecycle: string;
  error_codes: Array<Record<string, unknown> | string>;
  artifact_types: Array<Record<string, unknown> | string>;
  redaction: Record<string, unknown>;
  resources: Record<string, unknown>;
  user_function_body: string;
  reconstruction_strategy?: string;
};

export type ModuleWorkbenchDraft = {
  module_name: string;
  version: string;
  module_api_version: string;
  owner_scope: string;
  description: string;
  platforms: string[];
  requirements: string[];
  optional_requirements: string[];
  min_agent_version: string | null;
  entrypoint: string;
  tools: ModuleWorkbenchToolDraft[];
  warnings: string[];
  source: {
    manifest_json_text: string;
    module_py_text: string;
    files: ModuleWorkbenchSourceFile[];
    decomposition: {
      resolved_tools: number;
      unresolved_tools: string[];
      available_methods: string[];
      available_tool_names: string[];
    };
  };
};

export type ModuleWorkbenchListPayload = {
  modules: ModuleWorkbenchFamilyRecord[];
  count: number;
  rollout_settings: ModuleWorkbenchRolloutSettings;
};

export type ModuleWorkbenchDetailPayload = {
  module: ModuleWorkbenchVersionRecord;
  editable_spec: ModuleWorkbenchDraft;
};

export type ModuleWorkbenchValidationPayload = {
  validation_json?: Record<string, unknown>;
  manifest_json?: Record<string, unknown>;
  manifest_summary?: Record<string, unknown>;
  module_exists?: boolean;
  publish_ready?: boolean;
  conflicts?: Array<Record<string, unknown>>;
  preflight_errors?: string[];
  editable_preview?: ModuleWorkbenchDraft;
};

export type ModuleWorkbenchSavePayload = {
  message?: string;
  module_name?: string;
  version?: string;
  preferred_version?: string | null;
  rollout_summary?: {
    mode: string;
    should_sync: boolean;
    desired_updates: number;
    sync_enqueued: number;
    refresh_enqueued?: number;
  } | null;
};

export type ModuleArchiveUploadPayload = {
  module_name: string;
  version: string;
  sha256: string;
  size: number;
  download_path: string;
  preflight_status: string;
  validation_status: string;
  manifest_version: number;
  warnings: string[];
  tools_count: number;
  validation_json?: Record<string, unknown>;
};

export class ModuleWorkbenchApiError extends Error {
  status: number;
  errorCode?: string;
  details?: unknown;
  conflicts?: unknown[];
  preflightErrors?: string[];

  constructor(message: string, status: number, options?: Partial<ModuleWorkbenchApiError>) {
    super(message);
    this.name = "ModuleWorkbenchApiError";
    this.status = status;
    this.errorCode = options?.errorCode;
    this.details = options?.details;
    this.conflicts = options?.conflicts;
    this.preflightErrors = options?.preflightErrors;
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
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new ModuleWorkbenchApiError(errorPayload?.error ?? fallbackMessage, response.status, {
      errorCode: errorPayload?.error_code,
      details: errorPayload?.details,
      conflicts: errorPayload?.conflicts,
      preflightErrors: errorPayload?.preflight_errors,
    });
  }
  return payload as T;
}

export async function fetchModuleWorkbenchList(query: string): Promise<ModuleWorkbenchListPayload> {
  void query;
  const response = await fetch("/api/modules/workbench", {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить реестр модулей.");
}

export async function fetchModuleWorkbenchDetail(
  moduleName: string,
  version: string
): Promise<ModuleWorkbenchDetailPayload> {
  const response = await fetch(
    `/api/modules/workbench/${encodeURIComponent(moduleName)}/${encodeURIComponent(version)}`,
    {
      credentials: "same-origin",
    }
  );
  return readSuccessResponse(response, "Не удалось открыть версию модуля.");
}

export async function patchModuleWorkbenchRolloutSettings(
  payload: ModuleWorkbenchRolloutSettings
): Promise<ModuleWorkbenchRolloutSettings> {
  const response = await fetch("/api/modules/rollout_settings", {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const data = await readSuccessResponse<{ rollout_settings: ModuleWorkbenchRolloutSettings }>(
    response,
    "Не удалось сохранить настройки раскатки модулей."
  );
  return data.rollout_settings;
}

export async function setModuleWorkbenchPreferredVersion(
  moduleName: string,
  version: string | null
): Promise<{
  module_name: string;
  preferred_version: string | null;
  message?: string;
  updated_at?: string | null;
  updated_by?: string | null;
  rollout_summary?: ModuleWorkbenchSavePayload["rollout_summary"];
}> {
  const response = await fetch(`/api/modules/${encodeURIComponent(moduleName)}/preferred`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ version }),
  });
  return readSuccessResponse(response, "Не удалось обновить preferred-версию модуля.");
}

export async function validateModuleWorkbenchDraft(
  payload: Record<string, unknown>
): Promise<ModuleWorkbenchValidationPayload> {
  const response = await fetch("/api/modules/authoring/validate", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Серверная проверка модуля завершилась ошибкой.");
}

export async function saveModuleWorkbenchDraft(
  payload: Record<string, unknown>
): Promise<ModuleWorkbenchSavePayload> {
  const response = await fetch("/api/modules/authoring/publish", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось опубликовать модуль.");
}

export async function uploadModuleWorkbenchArchive(payload: {
  file: File;
  moduleName: string;
  version: string;
  overwrite: boolean;
}): Promise<ModuleArchiveUploadPayload> {
  const formData = new FormData();
  formData.append("file", payload.file);
  formData.append("module_name", payload.moduleName);
  formData.append("version", payload.version);
  formData.append("overwrite", payload.overwrite ? "true" : "false");

  const response = await fetch("/api/modules/upload", {
    method: "POST",
    credentials: "same-origin",
    body: formData,
  });
  return readSuccessResponse(response, "Не удалось загрузить архив модуля.");
}

export async function deleteModuleWorkbenchVersion(
  moduleName: string,
  version: string
): Promise<{
  module_name: string;
  version: string;
}> {
  const response = await fetch(
    `/api/modules/${encodeURIComponent(moduleName)}/${encodeURIComponent(version)}`,
    {
      method: "DELETE",
      credentials: "same-origin",
    }
  );
  return readSuccessResponse(response, "Не удалось удалить версию модуля.");
}
