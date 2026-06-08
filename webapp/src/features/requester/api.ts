import type {
  PublicTicketAuthorizeResult,
  PublicTicketCreatePayload,
  PublicTicketCreateResult,
  PublicTicketDetail,
  PublicTicketFeedbackPayload,
  PublicTicketFeedbackResult,
  PublicTicketReopenPayload,
  PublicTicketReopenResult,
  KnowledgeSuggestResult,
  ServiceCatalogPreviewPayload,
  ServiceCatalogSafePreview,
  ServiceCatalogCurrent,
  RequestFormPack,
  RequesterBootstrap,
  RequesterTicketCreatePayload,
  RequesterTicketCreateResult,
  AuthenticatedRequesterTicket,
} from "./types";

type OkResponse<T> = {
  status: "ok";
} & T;

type ErrorResponse = {
  status: "error";
  error?: string;
  message?: string;
  details?: unknown;
  error_code?: string;
};

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

export class RequesterApiError extends Error {
  status: number;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "RequesterApiError";
    this.status = status;
    this.details = details;
  }
}

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as T;
}

async function readOk<T>(response: Response, fallbackMessage: string): Promise<OkResponse<T>> {
  const payload = await readJson<OkResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "ok") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new RequesterApiError(
      errorPayload?.message ?? errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.details,
    );
  }
  return payload;
}

async function readSuccess<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<SuccessResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new RequesterApiError(
      errorPayload?.message ?? errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.details ?? errorPayload?.error_code,
    );
  }
  return payload.data;
}

function publicHeaders(token?: string | null, json = false): HeadersInit {
  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (json) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

export async function fetchPublicFormPack(): Promise<RequestFormPack> {
  const response = await fetch("/public_api/ticket_forms/current?pack_key=request_forms", {
    cache: "no-store",
  });
  const payload = await readOk<{ pack: RequestFormPack }>(response, "Не удалось загрузить форму заявки");
  return payload.pack;
}

export async function fetchServiceCatalogCurrent(): Promise<ServiceCatalogCurrent> {
  const response = await fetch("/api/service-catalog/current", {
    cache: "no-store",
  });
  const payload = await readOk<ServiceCatalogCurrent>(response, "Не удалось загрузить каталог услуг");
  return payload;
}

export async function createPublicTicket(payload: PublicTicketCreatePayload): Promise<PublicTicketCreateResult> {
  const response = await fetch("/public_api/tickets/create", {
    method: "POST",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  return readOk<PublicTicketCreateResult>(response, "Не удалось создать заявку");
}

export async function fetchRequesterBootstrap(): Promise<RequesterBootstrap> {
  const response = await fetch("/api/web/requester/bootstrap", {
    credentials: "same-origin",
    cache: "no-store",
  });
  return readSuccess<RequesterBootstrap>(response, "Не удалось загрузить кабинет заявителя");
}

export async function fetchRequesterTickets(): Promise<AuthenticatedRequesterTicket[]> {
  const response = await fetch("/api/web/requester/tickets", {
    credentials: "same-origin",
    cache: "no-store",
  });
  const payload = await readSuccess<{ tickets: AuthenticatedRequesterTicket[] }>(
    response,
    "Не удалось загрузить обращения",
  );
  return payload.tickets ?? [];
}

export async function createRequesterTicket(
  payload: RequesterTicketCreatePayload,
): Promise<RequesterTicketCreateResult> {
  const response = await fetch("/api/web/requester/tickets", {
    method: "POST",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  return readSuccess<RequesterTicketCreateResult>(response, "Не удалось создать обращение");
}

export async function previewServiceCatalogRequest(
  payload: ServiceCatalogPreviewPayload,
): Promise<ServiceCatalogSafePreview> {
  const response = await fetch("/api/service-catalog/preview", {
    method: "POST",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  return readOk<ServiceCatalogSafePreview>(response, "Не удалось построить безопасный preview обращения");
}

export async function suggestKnowledge(payload: {
  service_code?: string;
  offering_code?: string;
  request_template_key?: string;
  query?: string;
  form_payload?: Record<string, unknown>;
  surface: "requester_portal" | "agent_gui" | "support_workspace";
  urgency?: string;
  impact?: string;
}): Promise<KnowledgeSuggestResult> {
  const response = await fetch("/api/knowledge/suggest", {
    method: "POST",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  const result = await readOk<KnowledgeSuggestResult>(response, "Не удалось подобрать инструкции");
  return {
    suggestions: result.suggestions ?? [],
    known_errors: result.known_errors ?? [],
    workarounds: result.workarounds ?? [],
    rollout: result.rollout,
  };
}

export async function recordKnowledgeFeedback(payload: {
  item_id?: string | null;
  version_id?: string | null;
  event_type: "suggested" | "viewed" | "helpful" | "not_helpful" | "deflected" | "ticket_created_after_view";
  service_code?: string;
  offering_code?: string;
  request_template_key?: string;
  surface: "requester_portal" | "agent_gui" | "support_workspace";
  metadata?: Record<string, unknown>;
}): Promise<void> {
  const response = await fetch("/api/knowledge/feedback", {
    method: "POST",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  await readOk<unknown>(response, "Не удалось сохранить оценку знания");
}

export async function authorizePublicTicket(
  ticketId: string,
  code: string,
): Promise<PublicTicketAuthorizeResult> {
  const response = await fetch(`/public_api/tickets/${encodeURIComponent(ticketId)}/authorize`, {
    method: "POST",
    headers: publicHeaders(null, true),
    body: JSON.stringify({ code }),
  });
  return readOk<PublicTicketAuthorizeResult>(response, "Не удалось авторизоваться в тикете");
}

export async function fetchPublicTicket(ticketId: string, token: string): Promise<PublicTicketDetail> {
  const response = await fetch(`/api/tickets/${encodeURIComponent(ticketId)}`, {
    headers: publicHeaders(token),
  });
  return readOk<PublicTicketDetail>(response, "Не удалось загрузить тикет");
}

export async function sendPublicTicketMessage(
  ticketId: string,
  token: string,
  text: string,
): Promise<void> {
  const response = await fetch(`/api/tickets/${encodeURIComponent(ticketId)}/message`, {
    method: "POST",
    headers: publicHeaders(token, true),
    body: JSON.stringify({ text, visibility: "public" }),
  });
  await readOk<unknown>(response, "Не удалось отправить сообщение");
}

export async function sendPublicTicketConfirmation(
  ticketId: string,
  token: string,
  requestId: string,
  optionId: "confirm" | "reject",
): Promise<void> {
  const text = optionId === "confirm" ? "Подтверждаю решение" : "Решение не принято";
  const response = await fetch(`/api/tickets/${encodeURIComponent(ticketId)}/message`, {
    method: "POST",
    headers: publicHeaders(token, true),
    body: JSON.stringify({
      text,
      visibility: "public",
      metadata: {
        confirmation_response: {
          request_id: requestId,
          option_id: optionId,
        },
      },
    }),
  });
  await readOk<unknown>(response, "Не удалось отправить подтверждение");
}

export async function submitPublicTicketFeedback(
  ticketId: string,
  token: string,
  payload: PublicTicketFeedbackPayload,
): Promise<PublicTicketFeedbackResult> {
  const response = await fetch(`/public_api/tickets/${encodeURIComponent(ticketId)}/feedback`, {
    method: "POST",
    headers: publicHeaders(token, true),
    body: JSON.stringify(payload),
  });
  return readOk<PublicTicketFeedbackResult>(response, "Failed to save feedback");
}

export async function reopenPublicTicket(
  ticketId: string,
  token: string,
  payload: PublicTicketReopenPayload,
): Promise<PublicTicketReopenResult> {
  const response = await fetch(`/public_api/tickets/${encodeURIComponent(ticketId)}/reopen`, {
    method: "POST",
    headers: publicHeaders(token, true),
    body: JSON.stringify(payload),
  });
  return readOk<PublicTicketReopenResult>(response, "Failed to reopen ticket");
}

export async function closePublicTicket(ticketId: string, token: string): Promise<void> {
  const response = await fetch(`/api/tickets/${encodeURIComponent(ticketId)}/close`, {
    method: "POST",
    headers: publicHeaders(token, true),
    body: JSON.stringify({ reason: "requester_confirmed_resolution" }),
  });
  await readOk<unknown>(response, "Не удалось подтвердить решение");
}
