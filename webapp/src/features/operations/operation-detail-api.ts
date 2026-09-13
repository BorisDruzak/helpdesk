export type OperationDetail = {
  accepted_at?: string | null;
  actor_role?: string | null;
  deadline_at?: string | null;
  device_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  finished_at?: string | null;
  job_id?: string | null;
  kind?: string | null;
  max_retries?: number | null;
  operation_id: string;
  queued_at?: string | null;
  result_event_id?: string | null;
  result_summary?: string | null;
  retry_count?: number | null;
  retry_of_operation_id?: string | null;
  sent_at?: string | null;
  started_at?: string | null;
  status?: string | null;
  ticket_id?: string | null;
  tool_name?: string | null;
  trace_id?: string | null;
};

export type OperationDetailPayload = {
  operation: OperationDetail;
  links: {
    device_operations?: string | null;
    observer?: string | null;
    ticket?: string | null;
  };
};

type SuccessResponse = {
  status: "success";
  operation: OperationDetail;
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class OperationDetailApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "OperationDetailApiError";
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

function redactText(value: string | null | undefined): string | null | undefined {
  if (!value) return value;
  return value.replace(
    /(password|passwd|token|secret|api[_-]?key|authorization|cookie)\s*[:=]\s*[^,\s;]+/gi,
    (_match, key: string) => `${key}=***REDACTED***`,
  );
}

function sanitizeOperation(operation: OperationDetail): OperationDetail {
  return {
    ...operation,
    error_message: redactText(operation.error_message),
    result_summary: redactText(operation.result_summary),
  };
}

function linksForOperation(operation: OperationDetail): OperationDetailPayload["links"] {
  return {
    device_operations: operation.device_id ? `/app/admin/device?device=${encodeURIComponent(operation.device_id)}` : null,
    observer: operation.trace_id
      ? `/app/admin/observer?trace_id=${encodeURIComponent(operation.trace_id)}`
      : operation.operation_id
        ? `/app/admin/observer?operation_id=${encodeURIComponent(operation.operation_id)}`
        : null,
    ticket: operation.ticket_id ? `/app/tickets/${encodeURIComponent(operation.ticket_id)}` : null,
  };
}

export async function fetchOperationDetail(operationId: string): Promise<OperationDetailPayload> {
  const response = await fetch(`/api/web/admin/operations/${encodeURIComponent(operationId)}`, {
    credentials: "same-origin",
  });
  const payload = await readJson<SuccessResponse | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new OperationDetailApiError(
      errorPayload?.error ?? "Не удалось загрузить операцию.",
      response.status,
      errorPayload?.error_code,
    );
  }
  const operation = sanitizeOperation(payload.operation);
  return { operation, links: linksForOperation(operation) };
}
