export type ChangeRecord = {
  change_id: string;
  change_key: string;
  title: string;
  description: string;
  change_type: string;
  status: string;
  category?: string;
  priority: string;
  risk_level: string;
  impact_level: string;
  urgency?: string;
  source_kind?: string;
  source_ref?: string | null;
  problem_id?: string | null;
  improvement_action_id?: string | null;
  service_code?: string | null;
  offering_code?: string | null;
  planned_start_at?: string | null;
  planned_end_at?: string | null;
  emergency_justification?: string | null;
  risk_summary?: string | null;
  impact_summary?: string | null;
  implementation_summary?: string | null;
  rollback_summary?: string | null;
  validation_summary?: string | null;
  closure_summary?: string | null;
  affected_objects?: ChangeAffectedObject[];
};

export type ChangeAffectedObject = {
  affected_id: string;
  change_id: string;
  object_type: string;
  object_ref: string;
  service_code?: string | null;
  offering_code?: string | null;
  impact: string;
  planned_downtime?: boolean;
};

export type ChangeRiskAssessment = {
  assessment_id: string;
  change_id: string;
  status: string;
  risk_level: string;
  impact_level: string;
  suggested_risk_level: string;
  risk_factors: Record<string, unknown>;
};

export type ChangePlan = {
  plan_id: string;
  change_id: string;
  status: string;
  implementation_steps: Array<Record<string, unknown>>;
  rollback_steps: Array<Record<string, unknown>>;
  validation_steps: Array<Record<string, unknown>>;
};

export type ChangeApproval = {
  approval_id: string;
  change_id: string;
  approval_stage: string;
  approver_actor_id?: string | null;
  approver_role?: string | null;
  status: string;
};

export type ChangeTask = {
  task_id: string;
  change_id: string;
  title: string;
  task_type: string;
  status: string;
};

export type ChangePIR = {
  pir_id: string;
  change_id: string;
  status: string;
  implementation_successful?: boolean | null;
  rollback_used?: boolean;
  caused_incident?: boolean;
};

export type ChangeWindow = {
  window_id: string;
  title: string;
  window_type: string;
  starts_at: string;
  ends_at: string;
  service_code?: string | null;
  offering_code?: string | null;
};

export type ChangeSummary = {
  change_count: number;
  open_change_count: number;
  emergency_change_count: number;
  failed_change_count: number;
  rollback_count: number;
  pir_completion_rate: number;
  changes_by_type: Record<string, number>;
  changes_by_status: Record<string, number>;
  changes_by_risk: Record<string, number>;
  changes_by_service: Record<string, number>;
};

type OkResponse<T> = { status: "ok" } & T;
type ErrorResponse = { status: "error"; error?: string; message?: string };

export class ChangeApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ChangeApiError";
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
    throw new ChangeApiError(errorPayload?.message ?? errorPayload?.error ?? fallbackMessage, response.status);
  }
  return payload;
}

export async function fetchChangeSummary(): Promise<ChangeSummary> {
  const response = await fetch("/api/web/changes/metrics/summary", { credentials: "same-origin" });
  const payload = await readOk<{ summary: ChangeSummary }>(response, "Failed to load change summary");
  return payload.summary;
}

export async function fetchChanges(): Promise<ChangeRecord[]> {
  const response = await fetch("/api/web/changes", { credentials: "same-origin" });
  const payload = await readOk<{ changes: ChangeRecord[] }>(response, "Failed to load changes");
  return payload.changes;
}

export async function createChange(payload: {
  title: string;
  description: string;
  change_type: string;
  service_code?: string | null;
  offering_code?: string | null;
  emergency_justification?: string | null;
}): Promise<ChangeRecord> {
  const response = await fetch("/api/web/changes", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readOk<{ change: ChangeRecord }>(response, "Failed to create change");
  return result.change;
}

export async function createChangeFromProblem(problemId: string): Promise<ChangeRecord> {
  const response = await fetch(`/api/web/changes/from-problem/${encodeURIComponent(problemId)}`, {
    method: "POST",
    credentials: "same-origin",
  });
  const result = await readOk<{ change: ChangeRecord }>(response, "Failed to create change from problem");
  return result.change;
}

export async function transitionChange(changeId: string, payload: { status: string; closure_summary?: string; rollback_summary?: string; override?: boolean }): Promise<ChangeRecord> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/transition`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readOk<{ change: ChangeRecord }>(response, "Failed to transition change");
  return result.change;
}

export async function createRiskAssessment(changeId: string): Promise<ChangeRiskAssessment> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/risk`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      risk_factors: {
        service_criticality: "high",
        rollback_complexity: "medium",
        testing_confidence: "medium",
      },
    }),
  });
  const result = await readOk<{ risk: ChangeRiskAssessment }>(response, "Failed to create risk assessment");
  return result.risk;
}

export async function submitRiskAssessment(changeId: string, assessmentId: string): Promise<ChangeRiskAssessment> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/risk/${encodeURIComponent(assessmentId)}/submit`, {
    method: "POST",
    credentials: "same-origin",
  });
  const result = await readOk<{ risk: ChangeRiskAssessment }>(response, "Failed to submit risk assessment");
  return result.risk;
}

export async function approveRiskAssessment(changeId: string, assessmentId: string): Promise<ChangeRiskAssessment> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/risk/${encodeURIComponent(assessmentId)}/approve`, {
    method: "POST",
    credentials: "same-origin",
  });
  const result = await readOk<{ risk: ChangeRiskAssessment }>(response, "Failed to approve risk assessment");
  return result.risk;
}

export async function createPlan(changeId: string): Promise<ChangePlan> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/plans`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      implementation_steps: [{ title: "Implement approved change" }],
      rollback_steps: [{ title: "Restore previous state" }],
      validation_steps: [{ title: "Run health check" }],
      communication_steps: [{ title: "Notify stakeholders" }],
    }),
  });
  const result = await readOk<{ plan: ChangePlan }>(response, "Failed to create change plan");
  return result.plan;
}

export async function approvePlan(changeId: string, planId: string): Promise<ChangePlan> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/plans/${encodeURIComponent(planId)}/approve`, {
    method: "POST",
    credentials: "same-origin",
  });
  const result = await readOk<{ plan: ChangePlan }>(response, "Failed to approve change plan");
  return result.plan;
}

export async function requestApprovals(changeId: string): Promise<{ approvals: ChangeApproval[]; satisfied: boolean }> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/approvals/request`, {
    method: "POST",
    credentials: "same-origin",
  });
  return readOk<{ approvals: ChangeApproval[]; satisfied: boolean }>(response, "Failed to request approvals");
}

export async function approveApproval(changeId: string, approvalId: string): Promise<ChangeApproval> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/approvals/${encodeURIComponent(approvalId)}/approve`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision_comment: "Approved in change workspace" }),
  });
  const result = await readOk<{ approval: ChangeApproval }>(response, "Failed to approve change approval");
  return result.approval;
}

export async function createChangeWindow(payload: { title: string; window_type: string; starts_at: string; ends_at: string }): Promise<ChangeWindow> {
  const response = await fetch("/api/web/change-windows", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readOk<{ window: ChangeWindow }>(response, "Failed to create change window");
  return result.window;
}

export async function fetchChangeWindows(): Promise<ChangeWindow[]> {
  const response = await fetch("/api/web/change-windows", { credentials: "same-origin" });
  const result = await readOk<{ windows: ChangeWindow[] }>(response, "Failed to load change windows");
  return result.windows;
}

export async function scheduleChange(changeId: string, payload: { planned_start_at: string; planned_end_at: string; blackout_override?: boolean; override_justification?: string }): Promise<ChangeRecord> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/schedule`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readOk<{ change: ChangeRecord }>(response, "Failed to schedule change");
  return result.change;
}

export async function fetchChangeTasks(changeId: string): Promise<ChangeTask[]> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/tasks`, { credentials: "same-origin" });
  const result = await readOk<{ tasks: ChangeTask[] }>(response, "Failed to load change tasks");
  return result.tasks;
}

export async function createTask(changeId: string, title = "Implementation task"): Promise<ChangeTask> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/tasks`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, task_type: "implementation" }),
  });
  const result = await readOk<{ task: ChangeTask }>(response, "Failed to create change task");
  return result.task;
}

export async function completeTask(changeId: string, taskId: string): Promise<ChangeTask> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/tasks/${encodeURIComponent(taskId)}/complete`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result_notes: "Completed through change workspace" }),
  });
  const result = await readOk<{ task: ChangeTask }>(response, "Failed to complete change task");
  return result.task;
}

export async function createPir(changeId: string): Promise<ChangePIR> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/pir`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      implementation_successful: true,
      met_objectives: true,
      lessons_learned: "Validated in P5 workflow",
    }),
  });
  const result = await readOk<{ pir: ChangePIR }>(response, "Failed to create PIR");
  return result.pir;
}

export async function submitPir(changeId: string, pirId: string): Promise<ChangePIR> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/pir/${encodeURIComponent(pirId)}/submit`, {
    method: "POST",
    credentials: "same-origin",
  });
  const result = await readOk<{ pir: ChangePIR }>(response, "Failed to submit PIR");
  return result.pir;
}

export async function approvePir(changeId: string, pirId: string): Promise<ChangePIR> {
  const response = await fetch(`/api/web/changes/${encodeURIComponent(changeId)}/pir/${encodeURIComponent(pirId)}/approve`, {
    method: "POST",
    credentials: "same-origin",
  });
  const result = await readOk<{ pir: ChangePIR }>(response, "Failed to approve PIR");
  return result.pir;
}
