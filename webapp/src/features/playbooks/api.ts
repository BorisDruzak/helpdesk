export type AdminPlaybookBlockCatalogItem = {
  id: string;
  label: string;
  tool: string | null;
  tool_name?: string | null;
  block_type: string;
  module_kind: "diagnostic" | "remediation";
  module_name?: string | null;
  description: string;
  default_params: Record<string, unknown>;
  changes_device: boolean;
  requires_confirmation: boolean;
  requires_consent?: boolean;
  output_contract: Record<string, unknown>;
  condition_hints?: {
    status_path?: string;
    status_values?: string[];
    success_values?: string[];
    error_values?: string[];
    summary_path?: string;
    error_code_path?: string;
    error_codes?: string[];
    condition_templates?: Array<{ label: string; expression: string }>;
    compact_fields?: Array<Record<string, unknown>>;
  };
  source?: string | null;
  install_required?: boolean;
  install_policy?: string | null;
  supported_platforms?: string[];
  min_agent_version?: string | null;
  risk_level?: string | null;
  params_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  presets?: Array<{
    preset_id?: string;
    id?: string;
    label?: string;
    description?: string | null;
    params?: Record<string, unknown>;
  }>;
  error_codes?: string[];
};

export type AdminScenarioTemplateItem = {
  key: string;
  title: string;
  problem: string;
  recommended_form_keys: string[];
  block_ids: string[];
};

export type AdminPlaybookItem = {
  key: string;
  name: string;
  domain: string | null;
  version: string | null;
  status: string;
  blocks_count: number;
  updated_at: string | null;
};

export type AdminPlaybookPayload = {
  capabilities: {
    catalog_endpoint: string;
    save_endpoint: string;
    block_types: Array<{ value: string; label: string }>;
    module_kind_options: Array<{ value: string; label: string }>;
  };
  block_catalog: AdminPlaybookBlockCatalogItem[];
  scenario_templates: AdminScenarioTemplateItem[];
  playbooks: AdminPlaybookItem[];
};

export type AdminPlaybookDraftBlock = {
  id: string;
  type: "diagnostic" | "decision" | "report";
  module_kind: "diagnostic";
  tool: string | null;
  label: string;
  preset_id?: string | null;
  install_policy?: string | null;
  tool_manifest?: AdminPlaybookBlockCatalogItem | null;
  params: Record<string, unknown>;
  condition?: string | null;
  timeout_sec?: number | null;
  continue_on_error?: boolean;
  parallel_group?: string | null;
};

export type AdminPlaybookDraftRequest = {
  key: string;
  name: string;
  domain: string;
  version?: string | null;
  blocks: AdminPlaybookDraftBlock[];
};

export type AdminPlaybookSaveResult = {
  key: string;
  version: string;
  status: string;
  blocks_count: number;
  message: string;
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

export class AdminPlaybooksApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminPlaybooksApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function readSuccessResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = (await response.json().catch(() => null)) as SuccessResponse<T> | ErrorResponse | null;
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new AdminPlaybooksApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

export async function fetchAdminPlaybooksCatalog(): Promise<AdminPlaybookPayload> {
  const response = await fetch("/api/web/admin/playbooks/catalog", {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить каталог плейбуков");
}

export async function saveAdminPlaybook(
  payload: AdminPlaybookDraftRequest
): Promise<AdminPlaybookSaveResult> {
  const response = await fetch("/api/web/admin/playbooks/save", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось опубликовать плейбук");
}
