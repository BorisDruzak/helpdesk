export type QualitySummary = {
  avg_csat: number | null;
  feedback_count: number;
  negative_csat_count: number;
  reopen_count: number;
  sla_breach_count: number;
  qa_review_count: number;
  improvement_action_count: number;
};

export type ServiceQualityRow = {
  service_code: string;
  offering_code: string;
  ticket_count: number;
  resolved_count: number;
  closed_count: number;
  feedback_count: number;
  avg_csat: number | null;
  negative_csat_count: number;
  reopen_count: number;
  reopen_rate: number;
  sla_breach_count: number;
  sla_breach_rate: number;
  knowledge_attempt_count: number;
  ticket_after_failed_knowledge_count: number;
  qa_review_count: number;
  qa_failed_count: number;
  improvement_action_count: number;
};

export type QualityReview = {
  review_id: string;
  ticket_id: string;
  review_type: string;
  severity: string;
  status: string;
  service_code?: string | null;
  offering_code?: string | null;
  assigned_to_actor_id?: string | null;
  owner_actor_id?: string | null;
  score?: number | null;
  due_at?: string | null;
  created_at?: string | null;
  closed_at?: string | null;
};

export type ImprovementAction = {
  action_id: string;
  source_kind: string;
  ticket_id?: string | null;
  review_id?: string | null;
  feedback_id?: string | null;
  service_code?: string | null;
  offering_code?: string | null;
  action_type: string;
  title: string;
  description?: string | null;
  status: string;
  priority: string;
  owner_actor_id?: string | null;
  due_at?: string | null;
  created_at?: string | null;
  closed_at?: string | null;
};

export type QualityPolicy = {
  low_csat_threshold: number;
  reopen_review_enabled: boolean;
  sla_breach_review_enabled: boolean;
  high_priority_review_enabled: boolean;
  missing_evidence_review_enabled: boolean;
  random_sample_percent: number;
  qa_due_hours: number;
};

type OkResponse<T> = { status: "ok" } & T;
type ErrorResponse = { status: "error"; error?: string; message?: string };

export class QualityApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "QualityApiError";
    this.status = status;
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
    throw new QualityApiError(errorPayload?.message ?? errorPayload?.error ?? fallbackMessage, response.status);
  }
  return payload;
}

function ticketFilter(ticketId?: string | null): string {
  if (!ticketId) {
    return "";
  }
  return `?ticket_id=${encodeURIComponent(ticketId)}`;
}

export async function fetchQualitySummary(): Promise<QualitySummary> {
  const response = await fetch("/api/web/quality/summary", { credentials: "same-origin" });
  const payload = await readOk<{ summary: QualitySummary }>(response, "Failed to load quality summary");
  return payload.summary;
}

export async function fetchServiceQuality(): Promise<ServiceQualityRow[]> {
  const response = await fetch("/api/web/quality/service-quality", { credentials: "same-origin" });
  const payload = await readOk<{ rows: ServiceQualityRow[] }>(response, "Failed to load service quality");
  return payload.rows;
}

export async function fetchQualityReviews(ticketId?: string | null): Promise<QualityReview[]> {
  const response = await fetch(`/api/web/quality/reviews${ticketFilter(ticketId)}`, { credentials: "same-origin" });
  const payload = await readOk<{ reviews: QualityReview[] }>(response, "Failed to load quality reviews");
  return payload.reviews;
}

export async function fetchImprovementActions(ticketId?: string | null): Promise<ImprovementAction[]> {
  const response = await fetch(`/api/web/quality/improvement-actions${ticketFilter(ticketId)}`, { credentials: "same-origin" });
  const payload = await readOk<{ actions: ImprovementAction[] }>(response, "Failed to load improvement actions");
  return payload.actions;
}

export async function createImprovementAction(payload: {
  source_kind: string;
  ticket_id?: string | null;
  service_code?: string | null;
  offering_code?: string | null;
  action_type: string;
  title: string;
  description: string;
  priority: string;
  owner_actor_id?: string | null;
}): Promise<ImprovementAction> {
  const response = await fetch("/api/web/quality/improvement-actions", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readOk<{ action: ImprovementAction }>(response, "Failed to create improvement action");
  return result.action;
}

export async function completeQualityReview(reviewId: string, score: number): Promise<QualityReview> {
  const response = await fetch(`/api/web/quality/reviews/${encodeURIComponent(reviewId)}/complete`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ score, findings: { improvement_needed: score < 80 } }),
  });
  const result = await readOk<{ review: QualityReview }>(response, "Failed to complete quality review");
  return result.review;
}

export async function closeImprovementAction(actionId: string, outcomeNotes: string): Promise<ImprovementAction> {
  const response = await fetch(`/api/web/quality/improvement-actions/${encodeURIComponent(actionId)}/close`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outcome_notes: outcomeNotes }),
  });
  const result = await readOk<{ action: ImprovementAction }>(response, "Failed to close improvement action");
  return result.action;
}

export async function fetchQualityPolicy(): Promise<QualityPolicy> {
  const response = await fetch("/api/web/quality/policies", { credentials: "same-origin" });
  const payload = await readOk<{ policy: QualityPolicy }>(response, "Failed to load quality policy");
  return payload.policy;
}

