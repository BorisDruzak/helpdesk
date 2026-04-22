type SuccessResponse<T> = {
  status: "ok" | "success";
} & T;

type ErrorResponse = {
  status: "error";
  error?: string;
  details?: unknown;
};

export type TicketFormsPackSummary = {
  pack_key: string;
  version: string;
  title: string;
  description?: string | null;
  forms_count: number;
  fields_count: number;
  required_fields_count: number;
  created_at?: string | null;
  created_by?: string | null;
  notes?: string | null;
  is_preferred?: boolean;
};

export type TicketFormsPackListPayload = {
  pack_key: string;
  current: TicketFormsPackSummary | null;
  preferred: {
    pack_key: string;
    version: string;
    updated_at?: string | null;
    updated_by?: string | null;
  } | null;
  packs: TicketFormsPackSummary[];
};

export type TicketFormsPackDetailPayload = {
  pack: Record<string, unknown>;
};

export class TicketFormsCatalogApiError extends Error {
  status: number;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "TicketFormsCatalogApiError";
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

async function readSuccessResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<SuccessResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status === "error") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new TicketFormsCatalogApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.details
    );
  }
  return payload as T;
}

export async function fetchTicketFormsPackList(): Promise<TicketFormsPackListPayload> {
  const response = await fetch("/api/ticket_forms/packs?pack_key=request_forms", {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить версии каталога форм.");
}

export async function fetchTicketFormsPackVersion(version: string): Promise<TicketFormsPackDetailPayload> {
  const response = await fetch(`/api/ticket_forms/packs/request_forms/${encodeURIComponent(version)}`, {
    credentials: "same-origin",
  });
  return readSuccessResponse(response, "Не удалось загрузить выбранную версию каталога.");
}

export async function setTicketFormsPackPreferred(version: string): Promise<{
  preferred: {
    pack_key: string;
    version: string;
    updated_at?: string | null;
    updated_by?: string | null;
  };
}> {
  const response = await fetch(
    `/api/ticket_forms/packs/request_forms/${encodeURIComponent(version)}/preferred`,
    {
      method: "PATCH",
      credentials: "same-origin",
    }
  );
  return readSuccessResponse(response, "Не удалось сделать версию каталога активной.");
}
