export type WebReportsPayload = {
  period: {
    days: number;
    start_at: string;
    end_at: string;
    queue_id: number | null;
  };
  filters: {
    queue_options: Array<{
      value: string;
      label: string;
    }>;
  };
  summary: {
    open_backlog_count: number;
    closed_in_period_count: number;
    avg_resolution_minutes: number | null;
    first_response_compliance_percent: number | null;
    resolution_compliance_percent: number | null;
    reopen_rate_percent: number | null;
  };
  daily_trend: Array<{
    day: string;
    created_count: number;
    closed_count: number;
  }>;
  backlog_by_priority: Array<{
    priority: string;
    priority_label: string;
    count: number;
  }>;
  aging_buckets: Array<{
    bucket: string;
    count: number;
  }>;
  status_age: Array<{
    status: string;
    status_label: string;
    count: number;
    avg_age_seconds: number;
  }>;
  top_queues: Array<{
    queue_id: number | null;
    queue_label: string;
    open_count: number;
  }>;
  top_requesters: Array<{
    requester_id: string;
    count: number;
  }>;
  request_kinds: Array<{
    key: string;
    label: string;
    count: number;
  }>;
  recent_tickets: Array<{
    ticket_id: string;
    ticket_code: string;
    title: string;
    status: string;
    status_label: string;
    queue_label: string;
    requester_id: string | null;
    created_at: string | null;
    updated_at: string | null;
  }>;
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

export class WebReportsApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "WebReportsApiError";
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
    throw new WebReportsApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

type FetchWebReportsParams = {
  days: number;
  queueId?: number | null;
};

function buildReportsUrl(params: FetchWebReportsParams): string {
  const searchParams = new URLSearchParams();
  searchParams.set("days", String(params.days));
  if (params.queueId !== null && params.queueId !== undefined) {
    searchParams.set("queue_id", String(params.queueId));
  }
  return `/api/web/reports/summary?${searchParams.toString()}`;
}

export async function fetchWebReportsSummary(
  params: FetchWebReportsParams
): Promise<WebReportsPayload> {
  const response = await fetch(buildReportsUrl(params), {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить реальные отчёты.");
}
