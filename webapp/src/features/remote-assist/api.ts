import { SupportBootstrapApiError } from "../queues/api";

type ApiErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

type ApiOkResponse<T> = {
  status: "ok" | "success";
  data: T;
};

export type RemoteAssistSession = {
  session_id: string;
  ticket_id: string;
  device_id: string;
  operator_id: string;
  mode: string;
  status: string;
  reason: string | null;
  consent_status: string;
  requested_at: string | null;
  approved_at: string | null;
  denied_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  expires_at: string | null;
  max_duration_sec: number;
  close_reason: string | null;
  error_code: string | null;
  error_message: string | null;
};

export type RemoteAssistRequestResult = {
  session_id: string;
  status: string;
  expires_at: string;
  message: string;
};

export type RemoteAssistViewerInfo = RemoteAssistSession & {
  signaling_url: string;
  token: string;
  ice_servers: RTCIceServer[];
  turn_warning?: boolean;
};

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as T;
}

function assertOk<T>(payload: ApiOkResponse<T> | ApiErrorResponse | null, response: Response, fallback: string): T {
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new SupportBootstrapApiError(errorPayload?.error ?? fallback, response.status, errorPayload?.error_code);
  }
  return payload.data;
}

export async function fetchRemoteAssistSessions(ticketId: string): Promise<RemoteAssistSession[]> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/remote-assist/sessions`, {
    credentials: "same-origin",
  });
  const payload = await readJson<ApiOkResponse<{ sessions: RemoteAssistSession[] }> | ApiErrorResponse>(response);
  return assertOk(payload, response, "Не удалось загрузить сессии удалённой помощи").sessions;
}

export async function requestRemoteAssist(
  ticketId: string,
  payload: {
    deviceId: string;
    mode?: string;
    reason: string;
    durationMinutes: number;
  },
): Promise<RemoteAssistRequestResult> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/remote-assist/request`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      device_id: payload.deviceId,
      mode: payload.mode ?? "view_only",
      reason: payload.reason,
      duration_minutes: payload.durationMinutes,
    }),
  });
  const result = await readJson<ApiOkResponse<RemoteAssistRequestResult> | ApiErrorResponse>(response);
  return assertOk(result, response, "Не удалось запросить удалённую помощь");
}

export async function fetchRemoteAssistViewer(sessionId: string): Promise<RemoteAssistViewerInfo> {
  const response = await fetch(`/api/web/remote-assist/${encodeURIComponent(sessionId)}/viewer`, {
    credentials: "same-origin",
  });
  const result = await readJson<ApiOkResponse<RemoteAssistViewerInfo> | ApiErrorResponse>(response);
  return assertOk(result, response, "Не удалось открыть viewer удалённой помощи");
}

export async function endRemoteAssistSession(sessionId: string, reason = "operator_finished"): Promise<RemoteAssistSession> {
  const response = await fetch(`/api/web/remote-assist/${encodeURIComponent(sessionId)}/end`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ reason }),
  });
  const result = await readJson<ApiOkResponse<RemoteAssistSession> | ApiErrorResponse>(response);
  return assertOk(result, response, "Не удалось завершить сессию удалённой помощи");
}
