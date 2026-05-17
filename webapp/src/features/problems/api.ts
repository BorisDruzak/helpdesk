export type ProblemRecord = {
  problem_id: string;
  problem_key: string;
  title: string;
  description: string;
  status: string;
  severity: string;
  priority: string;
  service_code?: string | null;
  offering_code?: string | null;
  owner_actor_id?: string | null;
  assignee_actor_id?: string | null;
  root_cause_summary?: string | null;
  workaround_summary?: string | null;
  permanent_fix_summary?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProblemCandidate = {
  candidate_id: string;
  status: string;
  signal_type: string;
  title: string;
  summary: string;
  service_code?: string | null;
  offering_code?: string | null;
  ticket_count: number;
  reopen_count: number;
  low_csat_count: number;
  sla_breach_count: number;
  failed_kb_count: number;
  confidence_score?: number | null;
  converted_problem_id?: string | null;
};

export type ProblemTicketLink = {
  link_id: string;
  problem_id: string;
  ticket_id: string;
  link_type: string;
  evidence_summary?: string | null;
  unlinked_at?: string | null;
};

export type TicketProblemLink = {
  problem: ProblemRecord;
  link: ProblemTicketLink;
};

export type ProblemSummary = {
  open_problem_count: number;
  candidate_count: number;
  linked_ticket_count: number;
  unresolved_known_errors: number;
  problems_without_rca: number;
  problems_by_status: Record<string, number>;
  problems_by_severity: Record<string, number>;
  problems_by_service: Record<string, number>;
};

export type ProblemRca = {
  rca_id: string;
  problem_id: string;
  version_number: number;
  status: string;
  methodology: string;
  problem_statement: string;
  impact_summary?: string | null;
  root_cause: string;
  root_cause_category?: string | null;
};

type OkResponse<T> = { status: "ok" } & T;
type ErrorResponse = { status: "error"; error?: string; message?: string };

export class ProblemApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ProblemApiError";
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
    throw new ProblemApiError(errorPayload?.message ?? errorPayload?.error ?? fallbackMessage, response.status);
  }
  return payload;
}

export async function fetchProblemSummary(): Promise<ProblemSummary> {
  const response = await fetch("/api/web/problems/metrics/summary", { credentials: "same-origin" });
  const payload = await readOk<{ summary: ProblemSummary }>(response, "Failed to load problem summary");
  return payload.summary;
}

export async function fetchProblems(filters?: { ticketId?: string | null }): Promise<ProblemRecord[]> {
  const params = new URLSearchParams();
  if (filters?.ticketId) {
    params.set("ticket_id", filters.ticketId);
  }
  const response = await fetch(`/api/web/problems${params.size ? `?${params.toString()}` : ""}`, { credentials: "same-origin" });
  const payload = await readOk<{ problems?: ProblemRecord[]; items?: TicketProblemLink[] }>(response, "Failed to load problems");
  if (payload.items) {
    return payload.items.map((item) => item.problem);
  }
  return payload.problems ?? [];
}

export async function fetchTicketProblemLinks(ticketId: string): Promise<TicketProblemLink[]> {
  const response = await fetch(`/api/web/problems?ticket_id=${encodeURIComponent(ticketId)}`, { credentials: "same-origin" });
  const payload = await readOk<{ items: TicketProblemLink[] }>(response, "Failed to load ticket problems");
  return payload.items;
}

export async function createProblem(payload: {
  title: string;
  description: string;
  severity: string;
  priority: string;
  service_code?: string | null;
  offering_code?: string | null;
}): Promise<ProblemRecord> {
  const response = await fetch("/api/web/problems", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readOk<{ problem: ProblemRecord }>(response, "Failed to create problem");
  return result.problem;
}

export async function linkProblemTicket(problemId: string, ticketId: string, evidenceSummary?: string): Promise<ProblemTicketLink> {
  const response = await fetch(`/api/web/problems/${encodeURIComponent(problemId)}/link-ticket`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticket_id: ticketId, link_type: "confirmed", evidence_summary: evidenceSummary ?? "" }),
  });
  const result = await readOk<{ link: ProblemTicketLink }>(response, "Failed to link ticket");
  return result.link;
}

export async function transitionProblem(problemId: string, payload: { status: string; root_cause_summary?: string; workaround_summary?: string; permanent_fix_summary?: string }): Promise<ProblemRecord> {
  const response = await fetch(`/api/web/problems/${encodeURIComponent(problemId)}/transition`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readOk<{ problem: ProblemRecord }>(response, "Failed to transition problem");
  return result.problem;
}

export async function fetchProblemCandidates(): Promise<ProblemCandidate[]> {
  const response = await fetch("/api/web/problem-candidates", { credentials: "same-origin" });
  const payload = await readOk<{ candidates: ProblemCandidate[] }>(response, "Failed to load problem candidates");
  return payload.candidates;
}

export async function scanProblemCandidates(): Promise<{ created: number; updated: number; candidates: ProblemCandidate[] }> {
  const response = await fetch("/api/web/problem-candidates/scan", { method: "POST", credentials: "same-origin" });
  const payload = await readOk<{ scan: { created: number; updated: number; candidates: ProblemCandidate[] } }>(response, "Failed to scan problem candidates");
  return payload.scan;
}

export async function convertProblemCandidate(candidateId: string): Promise<{ problem: ProblemRecord }> {
  const response = await fetch(`/api/web/problem-candidates/${encodeURIComponent(candidateId)}/convert`, {
    method: "POST",
    credentials: "same-origin",
  });
  return readOk<{ problem: ProblemRecord }>(response, "Failed to convert problem candidate");
}

export async function createProblemRca(problemId: string, payload: { problem_statement: string; root_cause: string; methodology: string }): Promise<ProblemRca> {
  const response = await fetch(`/api/web/problems/${encodeURIComponent(problemId)}/rca`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readOk<{ rca: ProblemRca }>(response, "Failed to create RCA");
  return result.rca;
}

export async function approveProblemRca(problemId: string, rcaId: string): Promise<ProblemRca> {
  const response = await fetch(`/api/web/problems/${encodeURIComponent(problemId)}/rca/${encodeURIComponent(rcaId)}/approve`, {
    method: "POST",
    credentials: "same-origin",
  });
  const result = await readOk<{ rca: ProblemRca }>(response, "Failed to approve RCA");
  return result.rca;
}

export async function createKnownErrorDraft(problemId: string): Promise<unknown> {
  const response = await fetch(`/api/web/problems/${encodeURIComponent(problemId)}/known-error-draft`, { method: "POST", credentials: "same-origin" });
  const result = await readOk<{ link: unknown }>(response, "Failed to create known error draft");
  return result.link;
}

export async function createWorkaroundDraft(problemId: string): Promise<unknown> {
  const response = await fetch(`/api/web/problems/${encodeURIComponent(problemId)}/workaround-draft`, { method: "POST", credentials: "same-origin" });
  const result = await readOk<{ link: unknown }>(response, "Failed to create workaround draft");
  return result.link;
}
