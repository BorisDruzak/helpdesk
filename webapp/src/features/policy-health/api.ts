export type PolicyHealthStatus = "ok" | "warning" | "error";
export type PolicyIssueSeverity = "critical" | "error" | "warning" | "info";

export type PolicyHealthIssue = {
  severity: PolicyIssueSeverity;
  kind: string;
  policy_kind: string;
  message: string;
  path: string | null;
  reference: string | null;
  suggested_fix: string | null;
};

export type PolicyHealthCheck = {
  status: string;
  reference: string | null;
  policy_title?: string | null;
  rule_count?: number;
  resolved_queue?: string | number | null;
  assignee_strategy?: string | null;
  matched_rule?: string | null;
};

export type PolicyHealthTemplate = {
  template_id: string;
  template_code: string;
  template_name: string;
  version: string;
  status: "published" | "draft" | "archived";
  owner: string | null;
  health_status: PolicyHealthStatus;
  health_score: number;
  conflict_count: number;
  issue_count: number;
  issues_by_severity: Record<PolicyIssueSeverity, number>;
  checks: Record<string, PolicyHealthCheck>;
  issues: PolicyHealthIssue[];
  last_checked_at: string;
};

export type PolicyHealthDashboard = {
  status: "ok";
  templates: PolicyHealthTemplate[];
  summary: {
    total: number;
    ok: number;
    warning: number;
    error: number;
  };
};

export type PolicyHealthSimulationResult = {
  template_code: string;
  routing: Record<string, unknown>;
  priority: Record<string, unknown>;
  sla: Record<string, unknown>;
  ola: Record<string, unknown>;
  approval: Record<string, unknown>;
  closure: Record<string, unknown>;
  visibility: Record<string, unknown>;
  diagnostic: Record<string, unknown>;
  warnings: string[];
  would_create_ticket: false;
};

export type PolicySimulationPayload = {
  template_code: string;
  service_code?: string | null;
  offering_code?: string | null;
  offering_full_code?: string | null;
  request_form_data: Record<string, unknown>;
  custom_fields?: Record<string, unknown>;
  device_metadata?: Record<string, unknown>;
  requester_context?: Record<string, unknown>;
};

async function readJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.details ?? payload?.error ?? fallbackMessage);
  }
  return payload as T;
}

export async function fetchPolicyHealthDashboard(): Promise<PolicyHealthDashboard> {
  const response = await fetch("/api/web/admin/helpdesk/policy-health", {
    credentials: "same-origin",
  });
  return readJson(response, "Не удалось загрузить health dashboard");
}

export async function simulatePolicyHealth(payload: PolicySimulationPayload): Promise<PolicyHealthSimulationResult> {
  const response = await fetch("/api/web/admin/helpdesk/policy-health/simulate", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson(response, "Не удалось выполнить dry-run");
}
