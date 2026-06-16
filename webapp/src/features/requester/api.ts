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
  RequesterDeviceDetail,
  RequesterProfileDetail,
  RequesterAttachmentUploadResult,
  RequesterProfileUpdatePayload,
  RequesterProfileUpdateResult,
  RequesterRegistryOptionsPayload,
  RequesterOnBehalfPeopleSearchResult,
  RequesterTicketCreatePayload,
  RequesterTicketCreateResult,
  RequesterConsent,
  RequesterConsentDecisionResult,
  RequesterTicketClaimPublicResult,
  RequesterTicketDetail,
  RequesterTicketPreviewPayload,
  RequesterTicketCloseResult,
  RequesterTicketFeedbackPayload,
  RequesterTicketFeedbackResult,
  RequesterTicketMessageResult,
  RequesterTicketReopenPayload,
  RequesterTicketReopenResult,
  RequesterContextPreview,
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

export async function fetchRequesterConsents(statuses: string[] = ["pending"]): Promise<RequesterConsent[]> {
  const params = statuses.length ? `?status=${encodeURIComponent(statuses.join(","))}` : "";
  const response = await fetch(`/api/web/requester/consents${params}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  const payload = await readSuccess<{ consents: RequesterConsent[] }>(
    response,
    "Не удалось загрузить запросы согласия",
  );
  return payload.consents ?? [];
}

async function decideRequesterConsent(
  consentId: string,
  decision: "approve" | "deny",
  reason?: string | null,
): Promise<RequesterConsentDecisionResult> {
  const body: { reason?: string } = {};
  if (reason?.trim()) {
    body.reason = reason.trim();
  }
  const response = await fetch(`/api/web/requester/consents/${encodeURIComponent(consentId)}/${decision}`, {
    method: "POST",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify(body),
  });
  return readSuccess<RequesterConsentDecisionResult>(response, "Не удалось сохранить решение по согласию");
}

export function approveRequesterConsent(
  consentId: string,
  reason?: string | null,
): Promise<RequesterConsentDecisionResult> {
  return decideRequesterConsent(consentId, "approve", reason);
}

export function denyRequesterConsent(
  consentId: string,
  reason?: string | null,
): Promise<RequesterConsentDecisionResult> {
  return decideRequesterConsent(consentId, "deny", reason);
}

export async function fetchRequesterDevice(deviceId: string): Promise<RequesterDeviceDetail> {
  const response = await fetch(`/api/web/requester/devices/${encodeURIComponent(deviceId)}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  return readSuccess<RequesterDeviceDetail>(response, "Не удалось загрузить устройство");
}

export async function fetchRequesterProfile(): Promise<RequesterProfileDetail> {
  const response = await fetch("/api/web/requester/profile", {
    credentials: "same-origin",
    cache: "no-store",
  });
  return readSuccess<RequesterProfileDetail>(response, "Не удалось загрузить профиль");
}

export async function updateRequesterProfile(payload: RequesterProfileUpdatePayload): Promise<RequesterProfileUpdateResult> {
  const response = await fetch("/api/web/requester/profile", {
    method: "PUT",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  return readSuccess<RequesterProfileUpdateResult>(response, "Не удалось сохранить профиль");
}

export async function fetchRequesterRegistryOptions(): Promise<RequesterRegistryOptionsPayload> {
  const response = await fetch("/api/registry/options", {
    credentials: "same-origin",
    cache: "no-store",
  });
  return readSuccess<RequesterRegistryOptionsPayload>(response, "Не удалось загрузить справочники профиля");
}

export async function searchRequesterOnBehalfPeople(params: {
  form_key: string;
  q: string;
  request_template_key?: string;
  form_pack_key?: string;
  form_pack_version?: string;
}): Promise<RequesterOnBehalfPeopleSearchResult> {
  const search = new URLSearchParams();
  search.set("form_key", params.form_key);
  search.set("q", params.q);
  if (params.request_template_key) {
    search.set("request_template_key", params.request_template_key);
  }
  if (params.form_pack_key) {
    search.set("form_pack_key", params.form_pack_key);
  }
  if (params.form_pack_version) {
    search.set("form_pack_version", params.form_pack_version);
  }
  const response = await fetch(`/api/web/requester/on-behalf/people?${search.toString()}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  return readSuccess<RequesterOnBehalfPeopleSearchResult>(response, "Не удалось найти сотрудника");
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

export async function claimPublicRequesterTicket(
  ticketId: string,
  code: string,
): Promise<RequesterTicketClaimPublicResult> {
  const response = await fetch("/api/web/requester/tickets/claim-public", {
    method: "POST",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify({ ticket_id: ticketId, code }),
  });
  return readSuccess<RequesterTicketClaimPublicResult>(response, "Не удалось привязать обращение");
}

export async function previewRequesterTicket(
  payload: RequesterTicketPreviewPayload,
): Promise<ServiceCatalogSafePreview> {
  const response = await fetch("/api/web/requester/tickets/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  return readSuccess<ServiceCatalogSafePreview>(response, "Requester ticket preview failed");
}

export async function fetchRequesterTicket(ticketId: string): Promise<RequesterTicketDetail> {
  const response = await fetch(`/api/web/requester/tickets/${encodeURIComponent(ticketId)}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  return readSuccess<RequesterTicketDetail>(response, "Не удалось загрузить обращение");
}

export async function sendRequesterTicketMessage(
  ticketId: string,
  text: string,
  attachmentRefs: string[] = [],
): Promise<RequesterTicketMessageResult> {
  const body: { text: string; attachment_refs?: string[] } = { text };
  if (attachmentRefs.length) {
    body.attachment_refs = attachmentRefs;
  }
  const response = await fetch(`/api/web/requester/tickets/${encodeURIComponent(ticketId)}/message`, {
    method: "POST",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify(body),
  });
  return readSuccess<RequesterTicketMessageResult>(response, "Не удалось отправить сообщение");
}

export async function uploadRequesterTicketAttachment(
  ticketId: string,
  file: File,
): Promise<RequesterAttachmentUploadResult> {
  const body = new FormData();
  body.append("ticket_id", ticketId);
  body.append("kind", "file");
  body.append("file", file);
  const response = await fetch("/api/upload", {
    method: "POST",
    credentials: "same-origin",
    body,
  });
  const payload = await readJson<(RequesterAttachmentUploadResult & { status: "success" }) | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new RequesterApiError(
      errorPayload?.message ?? errorPayload?.error ?? "Не удалось загрузить вложение",
      response.status,
      errorPayload?.details ?? errorPayload?.error_code,
    );
  }
  return {
    artifact_id: payload.artifact_id,
    filename: payload.filename,
    url: payload.url,
    size: payload.size,
    sha256: payload.sha256,
    mime_type: payload.mime_type,
    kind: payload.kind,
  };
}

export async function closeRequesterTicket(ticketId: string): Promise<RequesterTicketCloseResult> {
  const response = await fetch(`/api/web/requester/tickets/${encodeURIComponent(ticketId)}/close`, {
    method: "POST",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify({ reason: "requester_confirmed_resolution" }),
  });
  return readSuccess<RequesterTicketCloseResult>(response, "Requester ticket close failed");
}

export async function submitRequesterTicketFeedback(
  ticketId: string,
  payload: RequesterTicketFeedbackPayload,
): Promise<RequesterTicketFeedbackResult> {
  const response = await fetch(`/api/web/requester/tickets/${encodeURIComponent(ticketId)}/feedback`, {
    method: "POST",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  return readSuccess<RequesterTicketFeedbackResult>(response, "Requester feedback failed");
}

export async function reopenRequesterTicket(
  ticketId: string,
  payload: RequesterTicketReopenPayload,
): Promise<RequesterTicketReopenResult> {
  const response = await fetch(`/api/web/requester/tickets/${encodeURIComponent(ticketId)}/reopen`, {
    method: "POST",
    credentials: "same-origin",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  return readSuccess<RequesterTicketReopenResult>(response, "Requester ticket reopen failed");
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
  requester_context?: RequesterContextPreview;
  device_metadata?: Record<string, unknown>;
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
