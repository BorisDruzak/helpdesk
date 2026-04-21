export type AdminFormsFieldType = "text" | "textarea" | "select" | "radio" | "checkbox";

export type AdminFormsFieldOption = {
  value: string;
  label: string;
};

export type AdminFormsVisibleWhen = {
  field: string;
  equals: string | null;
  values: string[];
};

export type AdminFormsFieldItem = {
  key: string;
  label: string;
  type: AdminFormsFieldType;
  type_label: string;
  required: boolean;
  placeholder: string | null;
  help_text: string | null;
  options: AdminFormsFieldOption[];
  visible_when: AdminFormsVisibleWhen | null;
};

export type AdminFormsFormItem = {
  key: string;
  request_kind: string;
  title: string;
  description: string | null;
  fields: AdminFormsFieldItem[];
};

export type AdminFormsSummary = {
  pack_key: string;
  version: string;
  title: string;
  description: string | null;
  forms_count: number;
  fields_count: number;
  required_fields_count: number;
  last_published_at: string | null;
  last_published_by: string | null;
};

export type AdminFormsPayload = {
  summary: AdminFormsSummary;
  capabilities: {
    current_endpoint: string;
    save_endpoint: string;
    field_type_options: Array<{
      value: AdminFormsFieldType;
      label: string;
    }>;
  };
  forms: AdminFormsFormItem[];
};

export type AdminFormsSaveRequest = {
  title: string;
  description: string;
  forms: Array<{
    key: string;
    request_kind: string;
    title: string;
    description: string;
    fields: Array<{
      key: string;
      label: string;
      type: AdminFormsFieldType;
      required: boolean;
      placeholder?: string;
      help_text?: string;
      options: AdminFormsFieldOption[];
      visible_when?: {
        field: string;
        equals?: string;
        values?: string[];
      };
    }>;
  }>;
};

export type AdminFormsSaveResult = {
  summary: AdminFormsSummary;
  forms: AdminFormsFormItem[];
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

export class AdminFormsApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminFormsApiError";
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
    throw new AdminFormsApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

export async function fetchAdminFormsCatalog(): Promise<AdminFormsPayload> {
  const response = await fetch("/api/web/admin/forms/current", {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить каталог форм");
}

export async function saveAdminFormsCatalog(
  payload: AdminFormsSaveRequest
): Promise<AdminFormsSaveResult> {
  const response = await fetch("/api/web/admin/forms/save", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось опубликовать каталог форм");
}
