import type {
  PublicTicketAuthorizeResult,
  PublicTicketCreatePayload,
  PublicTicketCreateResult,
  PublicTicketDetail,
  RequestFormPack,
} from "./types";

type OkResponse<T> = {
  status: "ok";
} & T;

type ErrorResponse = {
  status: "error";
  error?: string;
  message?: string;
  details?: unknown;
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

export async function createPublicTicket(payload: PublicTicketCreatePayload): Promise<PublicTicketCreateResult> {
  const response = await fetch("/public_api/tickets/create", {
    method: "POST",
    headers: publicHeaders(null, true),
    body: JSON.stringify(payload),
  });
  return readOk<PublicTicketCreateResult>(response, "Не удалось создать заявку");
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

export async function closePublicTicket(ticketId: string, token: string): Promise<void> {
  const response = await fetch(`/api/tickets/${encodeURIComponent(ticketId)}/close`, {
    method: "POST",
    headers: publicHeaders(token, true),
    body: JSON.stringify({ reason: "requester_confirmed_resolution" }),
  });
  await readOk<unknown>(response, "Не удалось подтвердить решение");
}
