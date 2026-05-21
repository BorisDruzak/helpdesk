import type { ApprovalConsentCenterPayload, FetchApprovalConsentCenterParams } from "./types";

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class ApprovalConsentCenterApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "ApprovalConsentCenterApiError";
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

export function buildApprovalConsentCenterUrl(params: FetchApprovalConsentCenterParams = {}) {
  const searchParams = new URLSearchParams();
  for (const key of ["scope", "kind", "status", "risk", "object_type", "queue", "assignee"] as const) {
    const value = params[key];
    if (value) {
      searchParams.set(key, value);
    }
  }
  for (const [key, value] of Object.entries({
    due_window_hours: params.due_window_hours,
    limit: params.limit,
    offset: params.offset,
  })) {
    if (typeof value === "number" && Number.isFinite(value)) {
      searchParams.set(key, String(Math.floor(value)));
    }
  }
  const suffix = searchParams.toString();
  return `/api/web/support/approvals${suffix ? `?${suffix}` : ""}`;
}

export async function fetchApprovalConsentCenter(
  params: FetchApprovalConsentCenterParams = {},
): Promise<ApprovalConsentCenterPayload> {
  const response = await fetch(buildApprovalConsentCenterUrl(params), {
    credentials: "same-origin",
  });
  const payload = await readJson<SuccessResponse<ApprovalConsentCenterPayload> | ErrorResponse>(response);

  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new ApprovalConsentCenterApiError(
      errorPayload?.error ?? "Не удалось загрузить центр согласований",
      response.status,
      errorPayload?.error_code,
    );
  }

  return payload.data;
}
