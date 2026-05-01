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
  validation: Record<string, unknown>;
  process_mapping: Record<string, unknown>;
};

export type AdminFormsPlaybookTrigger = {
  event: "ticket_created";
  playbook_key: string;
  module_kind: "diagnostic" | "remediation";
  enabled: boolean;
};

export type AdminFormsFormItem = {
  key: string;
  request_kind: string;
  ticket_type?: string | null;
  title: string;
  description: string | null;
  category_id?: number | null;
  service_id?: number | null;
  subcategory_id?: number | null;
  default_queue_id?: number | null;
  sla_policy_id?: number | null;
  suggested_playbook_id?: string | null;
  field_roles?: Record<string, string[]>;
  priority_policy?: Record<string, unknown>;
  routing_policy?: Record<string, unknown>;
  approval_policy?: Record<string, unknown>;
  diagnostic_policy?: Record<string, unknown>;
  ola_policy?: Record<string, unknown>;
  closure_policy?: Record<string, unknown>;
  visibility_policy?: Record<string, unknown>;
  notification_policy?: Record<string, unknown>;
  reporting_policy?: Record<string, unknown>;
  fields: AdminFormsFieldItem[];
  playbook_triggers?: AdminFormsPlaybookTrigger[];
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
    preview_endpoint: string;
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
    ticket_type?: string | null;
    title: string;
    description: string;
    category_id?: number | null;
    service_id?: number | null;
    subcategory_id?: number | null;
    default_queue_id?: number | null;
    sla_policy_id?: number | null;
    suggested_playbook_id?: string | null;
    field_roles?: Record<string, string[]>;
    priority_policy?: Record<string, unknown>;
    routing_policy?: Record<string, unknown>;
    approval_policy?: Record<string, unknown>;
    diagnostic_policy?: Record<string, unknown>;
    ola_policy?: Record<string, unknown>;
    closure_policy?: Record<string, unknown>;
    visibility_policy?: Record<string, unknown>;
    notification_policy?: Record<string, unknown>;
    reporting_policy?: Record<string, unknown>;
    playbook_triggers?: AdminFormsPlaybookTrigger[];
    fields: Array<{
      key: string;
      label: string;
      type: AdminFormsFieldType;
      required: boolean;
      placeholder?: string;
      help_text?: string;
      options: AdminFormsFieldOption[];
      validation?: Record<string, unknown>;
      process_mapping?: Record<string, unknown>;
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

export type AdminFormsRoutePreviewResult = {
  ticket_type: string;
  request_kind: string;
  target_queue_id: number | null;
  target_queue_name: string | null;
  fallback_applied: boolean;
  matched_rule: {
    id: number;
    priority_order: number;
    target_queue_id: number;
    target_queue_name: string | null;
    condition_json: Record<string, unknown> | null;
  } | null;
  summary_rows: Array<{
    key: string;
    label: string;
    value: string;
  }>;
};

export type AdminHelpdeskPolicyItem = {
  kind: string;
  table: string;
  code: string;
  version: string;
  title: string;
  description: string | null;
  scope_level: string;
  scope_ref: string | null;
  config: Record<string, unknown>;
  is_active: boolean;
  published_at: string | null;
  created_at: string | null;
  created_by: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type AdminHelpdeskPolicyDiffChange = {
  path: string;
  from: unknown;
  to: unknown;
};

export type AdminHelpdeskPolicyDiffResult = {
  kind: string;
  code: string;
  from_policy: AdminHelpdeskPolicyItem;
  to_policy: AdminHelpdeskPolicyItem;
  changes: AdminHelpdeskPolicyDiffChange[];
};

export type AdminHelpdeskRequestTemplateItem = {
  template_code: string;
  version: string;
  public_title: string;
  internal_name: string | null;
  description: string | null;
  ticket_type: string;
  category_id: number | null;
  service_id: number | null;
  subcategory_id: number | null;
  form_schema_id: string | null;
  workflow_profile_id: string | null;
  priority_policy_code: string | null;
  routing_policy_code: string | null;
  sla_policy_id: number | null;
  sla_policy_code: string | null;
  ola_policy_code: string | null;
  approval_policy_code: string | null;
  diagnostic_policy_code: string | null;
  closure_policy_code: string | null;
  visibility_policy_code: string | null;
  notification_policy_code: string | null;
  reporting_policy_code: string | null;
  config: Record<string, unknown>;
  overrides: Record<string, unknown>;
  is_active: boolean;
  published_at: string | null;
  created_at: string | null;
  created_by: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type AdminHelpdeskSmartViewItem = {
  code: string;
  version: string;
  title: string;
  description: string | null;
  scope_level: string;
  scope_ref: string | null;
  filter: Record<string, unknown>;
  sort: Array<Record<string, unknown>>;
  columns: string[];
  is_active: boolean;
  published_at: string | null;
  created_at: string | null;
  created_by: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type AdminHelpdeskTicketTypeItem = {
  code: string;
  version: string;
  title: string;
  description: string | null;
  default_workflow_profile_id: string | null;
  default_priority_policy_code: string | null;
  default_routing_policy_code: string | null;
  default_sla_policy_id: number | null;
  default_sla_policy_code: string | null;
  default_ola_policy_code: string | null;
  default_approval_policy_code: string | null;
  default_diagnostic_policy_code: string | null;
  default_closure_policy_code: string | null;
  default_visibility_policy_code: string | null;
  default_notification_policy_code: string | null;
  default_reporting_policy_code: string | null;
  feature_flags: Record<string, boolean>;
  config: Record<string, unknown>;
  is_active: boolean;
  published_at: string | null;
  created_at: string | null;
  created_by: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type AdminHelpdeskFormSchemaItem = {
  schema_id: string;
  version: string;
  title: string;
  description: string | null;
  form_key: string | null;
  request_template_code: string | null;
  ticket_type: string | null;
  fields: Array<{
    key: string;
    label: string;
    type: string;
    required: boolean;
    options: Array<Record<string, unknown>>;
    validation: Record<string, unknown>;
    process_mapping: Record<string, unknown>;
    visibility: Record<string, unknown>;
    sort_order: number;
  }>;
  conditions: Array<{
    condition: Record<string, unknown>;
    show_fields: string[];
    require_fields: string[];
    sort_order: number;
  }>;
  config: Record<string, unknown>;
  is_active: boolean;
  published_at: string | null;
  created_at: string | null;
  created_by: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type AdminHelpdeskModelPayload = {
  summary: {
    request_templates_count: number;
    active_request_templates_count: number;
    ticket_types_count: number;
    active_ticket_types_count: number;
    form_schemas_count: number;
    active_form_schemas_count: number;
    policies_count: number;
    active_policies_count: number;
    smart_views_count: number;
    active_smart_views_count: number;
  };
  capabilities: {
    registry_endpoint: string;
    publish_from_form_endpoint: string;
    publish_policy_endpoint: string;
    policy_diff_endpoint?: string | null;
    policy_deactivate_endpoint?: string | null;
    policy_rollback_endpoint?: string | null;
    publish_ticket_type_endpoint: string;
    ticket_type_deactivate_endpoint?: string | null;
    ticket_type_rollback_endpoint?: string | null;
    publish_form_schema_endpoint: string;
    publish_smart_view_endpoint: string;
    inheritance_order: string[];
    policy_kinds: string[];
  };
  request_templates: AdminHelpdeskRequestTemplateItem[];
  ticket_types: AdminHelpdeskTicketTypeItem[];
  form_schemas: AdminHelpdeskFormSchemaItem[];
  policies: Record<string, AdminHelpdeskPolicyItem[]>;
  smart_views: AdminHelpdeskSmartViewItem[];
};

export type AdminHelpdeskPublishFromFormResult = {
  request_template: AdminHelpdeskRequestTemplateItem;
  form_schema: AdminHelpdeskFormSchemaItem;
  policies: Record<string, AdminHelpdeskPolicyItem>;
  message: string;
};

export type AdminHelpdeskPublishPolicyResult = {
  policy: AdminHelpdeskPolicyItem;
  message: string;
};

export type AdminHelpdeskPolicyLifecycleResult = {
  policy: AdminHelpdeskPolicyItem;
  message: string;
};

export type AdminHelpdeskPublishSmartViewResult = {
  smart_view: AdminHelpdeskSmartViewItem;
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

export async function fetchHelpdeskModelRegistry(): Promise<AdminHelpdeskModelPayload> {
  const response = await fetch("/api/web/admin/helpdesk-model/policies", {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить реестр шаблонов и политик");
}

export async function publishHelpdeskTemplateFromForm(payload: {
  form: AdminFormsSaveRequest["forms"][number];
  publish_policies?: boolean;
}): Promise<AdminHelpdeskPublishFromFormResult> {
  const response = await fetch("/api/web/admin/helpdesk-model/request-templates/publish-from-form", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ ...payload, publish_policies: payload.publish_policies ?? true })
  });
  return readSuccessResponse(response, "Не удалось опубликовать шаблон обращения в реестр");
}

export async function publishHelpdeskPolicy(payload: {
  kind: string;
  code: string;
  title: string;
  description?: string | null;
  scope_level: string;
  scope_ref?: string | null;
  config: Record<string, unknown>;
  requested_version?: string | null;
}): Promise<AdminHelpdeskPublishPolicyResult> {
  const response = await fetch("/api/web/admin/helpdesk-model/policies/publish", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось опубликовать политику в реестр");
}

export async function diffHelpdeskPolicyVersions(payload: {
  kind: string;
  code: string;
  from_version: string;
  to_version: string;
}): Promise<AdminHelpdeskPolicyDiffResult> {
  const response = await fetch("/api/web/admin/helpdesk-model/policies/diff", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось сравнить версии политики");
}

export async function deactivateHelpdeskPolicyVersion(payload: {
  kind: string;
  code: string;
  version: string;
}): Promise<AdminHelpdeskPolicyLifecycleResult> {
  const response = await fetch("/api/web/admin/helpdesk-model/policies/deactivate", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось деактивировать версию политики");
}

export async function rollbackHelpdeskPolicyVersion(payload: {
  kind: string;
  code: string;
  target_version: string;
}): Promise<AdminHelpdeskPolicyLifecycleResult> {
  const response = await fetch("/api/web/admin/helpdesk-model/policies/rollback", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось откатить политику");
}

export async function publishHelpdeskSmartView(payload: {
  code: string;
  title: string;
  description?: string | null;
  scope_level: string;
  scope_ref?: string | null;
  filter: Record<string, unknown>;
  sort: Array<Record<string, unknown>>;
  columns: string[];
  requested_version?: string | null;
}): Promise<AdminHelpdeskPublishSmartViewResult> {
  const response = await fetch("/api/web/admin/helpdesk-model/smart-views/publish", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось опубликовать smart view в реестр");
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

export async function previewAdminFormRoute(payload: {
  form: AdminFormsSaveRequest["forms"][number];
  form_payload: Record<string, string | boolean>;
}): Promise<AdminFormsRoutePreviewResult> {
  const response = await fetch("/api/web/admin/forms/route-preview", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось построить preview маршрута");
}
