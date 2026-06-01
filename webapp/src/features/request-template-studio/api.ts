import type { AdminFormsSaveRequest, AdminHelpdeskFormSchemaItem, AdminHelpdeskRequestTemplateItem } from "../forms-builder/api";

export type RequestStudioIssue = {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  path: string | null;
  suggested_fix: string | null;
};

export type RequestStudioOfferingDraft = {
  service_code: string;
  code: string;
  public_title: string;
  short_description?: string | null;
  description?: string | null;
  lifecycle_status?: "draft" | "published" | "retired";
  visibility: "public" | "internal" | "restricted";
  request_type?: string | null;
  ticket_type_code?: string | null;
  request_template_key: string;
  form_schema_id?: string | null;
  routing_policy_code?: string | null;
  sla_policy_code?: string | null;
  approval_policy_code?: string | null;
  closure_policy_code?: string | null;
  visibility_policy_code?: string | null;
  notification_policy_code?: string | null;
  default_queue_id?: number | null;
  metadata?: Record<string, unknown>;
};

export type RequestStudioDraftPayload = {
  form: AdminFormsSaveRequest["forms"][number];
  offering: RequestStudioOfferingDraft;
  publish_service?: boolean;
  publish_offering?: boolean;
  confirmation_token?: string | null;
};

export type RequestStudioValidationResult = {
  status: "ok" | "warning" | "error";
  can_publish: boolean;
  issues: RequestStudioIssue[];
  confirmation_token: string | null;
};

export type RequestStudioDiffChange = {
  path: string;
  label: string;
  from_value: unknown;
  to_value: unknown;
  change_type: "added" | "removed" | "changed" | "unchanged";
  severity: "info" | "warning" | "danger";
};

export type RequestStudioObjectDiff = {
  object_type: "form_schema" | "request_template" | "offering" | "service";
  object_code: string;
  action: "create" | "update" | "noop" | "blocked";
  title: string;
  changes: RequestStudioDiffChange[];
  warnings: string[];
};

export type RequestStudioPublishPreview = {
  validation: RequestStudioValidationResult;
  steps: Array<{
    key: string;
    label: string;
    status: "ready" | "blocked" | "will_update" | "will_publish";
    details: string | null;
  }>;
  confirmation_token: string | null;
  expires_at: string | null;
  diffs: RequestStudioObjectDiff[];
  summary: {
    creates?: number;
    updates?: number;
    noops?: number;
    blocked?: number;
    warnings?: number;
  };
  message: string;
};

export type RequestStudioPublishResult = {
  validation: RequestStudioValidationResult;
  request_template: AdminHelpdeskRequestTemplateItem;
  form_schema: AdminHelpdeskFormSchemaItem;
  service: Record<string, unknown> | null;
  offering: Record<string, unknown>;
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

export class RequestStudioApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "RequestStudioApiError";
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
    throw new RequestStudioApiError(errorPayload?.error ?? fallbackMessage, response.status, errorPayload?.error_code);
  }
  return payload.data;
}

export async function validateRequestStudioDraft(payload: RequestStudioDraftPayload): Promise<RequestStudioValidationResult> {
  const response = await fetch("/api/web/admin/request-studio/validate-draft", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось проверить draft Request Studio");
}

export async function previewRequestStudioPublish(payload: RequestStudioDraftPayload): Promise<RequestStudioPublishPreview> {
  const response = await fetch("/api/web/admin/request-studio/publish-preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось подготовить публикацию из Studio");
}

export async function publishRequestStudioDraft(payload: RequestStudioDraftPayload): Promise<RequestStudioPublishResult> {
  const response = await fetch("/api/web/admin/request-studio/publish", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readSuccessResponse(response, "Не удалось опубликовать тип обращения из Studio");
}
