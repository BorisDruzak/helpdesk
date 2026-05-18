import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveApproval,
  approvePlan,
  approvePir,
  approveRiskAssessment,
  completeTask,
  createChange,
  createChangeFromProblem,
  createChangeWindow,
  createPir,
  createPlan,
  createRiskAssessment,
  createTask,
  fetchChangeSummary,
  fetchChangeTasks,
  fetchChangeWindows,
  fetchChanges,
  requestApprovals,
  scheduleChange,
  submitRiskAssessment,
  submitPir,
  transitionChange,
} from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("change api", () => {
  it("loads summary, list, windows and tasks", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/changes/metrics/summary") {
        return jsonResponse({
          status: "ok",
          summary: {
            change_count: 1,
            open_change_count: 1,
            emergency_change_count: 0,
            failed_change_count: 0,
            rollback_count: 0,
            pir_completion_rate: 0,
            changes_by_type: { normal: 1 },
            changes_by_status: { draft: 1 },
            changes_by_risk: { medium: 1 },
            changes_by_service: { network: 1 },
          },
        });
      }
      if (url === "/api/web/changes") {
        return jsonResponse({
          status: "ok",
          changes: [{ change_id: "chg-1", change_key: "CHG-000001", title: "VPN", description: "VPN", change_type: "normal", status: "draft", priority: "medium", risk_level: "medium", impact_level: "medium" }],
        });
      }
      if (url === "/api/web/change-windows") {
        return jsonResponse({ status: "ok", windows: [{ window_id: "w1", title: "Night", window_type: "maintenance", starts_at: "2026-05-18T10:00:00Z", ends_at: "2026-05-18T11:00:00Z" }] });
      }
      if (url === "/api/web/changes/chg-1/tasks") {
        return jsonResponse({ status: "ok", tasks: [{ task_id: "t1", change_id: "chg-1", title: "Deploy", task_type: "implementation", status: "pending" }] });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    expect((await fetchChangeSummary()).change_count).toBe(1);
    expect((await fetchChanges())[0]?.change_key).toBe("CHG-000001");
    expect((await fetchChangeWindows())[0]?.window_type).toBe("maintenance");
    expect((await fetchChangeTasks("chg-1"))[0]?.title).toBe("Deploy");
  });

  it("mutates change workflow", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/changes") {
        return jsonResponse({ status: "ok", change: { change_id: "chg-1", change_key: "CHG-000001", title: "VPN", description: "VPN", change_type: "normal", status: "draft", priority: "medium", risk_level: "medium", impact_level: "medium" } });
      }
      if (url === "/api/web/changes/from-problem/problem-1") {
        return jsonResponse({ status: "ok", change: { change_id: "chg-2", change_key: "CHG-000002", title: "Permanent fix", description: "Fix", change_type: "normal", status: "draft", priority: "high", risk_level: "high", impact_level: "high" } });
      }
      if (url === "/api/web/changes/chg-1/transition") {
        return jsonResponse({ status: "ok", change: { change_id: "chg-1", change_key: "CHG-000001", title: "VPN", description: "VPN", change_type: "normal", status: "submitted", priority: "medium", risk_level: "medium", impact_level: "medium" } });
      }
      if (url === "/api/web/changes/chg-1/risk") {
        return jsonResponse({ status: "ok", risk: { assessment_id: "r1", change_id: "chg-1", status: "draft", risk_level: "high", impact_level: "high", suggested_risk_level: "high", risk_factors: {} } });
      }
      if (url === "/api/web/changes/chg-1/risk/r1/submit") {
        return jsonResponse({ status: "ok", risk: { assessment_id: "r1", change_id: "chg-1", status: "submitted", risk_level: "high", impact_level: "high", suggested_risk_level: "high", risk_factors: {} } });
      }
      if (url === "/api/web/changes/chg-1/risk/r1/approve") {
        return jsonResponse({ status: "ok", risk: { assessment_id: "r1", change_id: "chg-1", status: "approved", risk_level: "high", impact_level: "high", suggested_risk_level: "high", risk_factors: {} } });
      }
      if (url === "/api/web/changes/chg-1/plans") {
        return jsonResponse({ status: "ok", plan: { plan_id: "p1", change_id: "chg-1", status: "draft", implementation_steps: [], rollback_steps: [], validation_steps: [] } });
      }
      if (url === "/api/web/changes/chg-1/plans/p1/approve") {
        return jsonResponse({ status: "ok", plan: { plan_id: "p1", change_id: "chg-1", status: "approved", implementation_steps: [], rollback_steps: [], validation_steps: [] } });
      }
      if (url === "/api/web/changes/chg-1/approvals/request") {
        return jsonResponse({ status: "ok", approvals: [{ approval_id: "a1", change_id: "chg-1", approval_stage: "cab", status: "pending" }], satisfied: false });
      }
      if (url === "/api/web/changes/chg-1/approvals/a1/approve") {
        return jsonResponse({ status: "ok", approval: { approval_id: "a1", change_id: "chg-1", approval_stage: "cab", status: "approved" } });
      }
      if (url === "/api/web/change-windows") {
        return jsonResponse({ status: "ok", window: { window_id: "w1", title: "Night", window_type: "maintenance", starts_at: "2026-05-18T10:00:00Z", ends_at: "2026-05-18T11:00:00Z" } });
      }
      if (url === "/api/web/changes/chg-1/schedule") {
        return jsonResponse({ status: "ok", change: { change_id: "chg-1", change_key: "CHG-000001", title: "VPN", description: "VPN", change_type: "normal", status: "scheduled", priority: "medium", risk_level: "medium", impact_level: "medium" } });
      }
      if (url === "/api/web/changes/chg-1/tasks") {
        return jsonResponse({ status: "ok", task: { task_id: "t1", change_id: "chg-1", title: "Deploy", task_type: "implementation", status: "pending" } });
      }
      if (url === "/api/web/changes/chg-1/tasks/t1/complete") {
        return jsonResponse({ status: "ok", task: { task_id: "t1", change_id: "chg-1", title: "Deploy", task_type: "implementation", status: "done" } });
      }
      if (url === "/api/web/changes/chg-1/pir") {
        return jsonResponse({ status: "ok", pir: { pir_id: "pir-1", change_id: "chg-1", status: "draft", implementation_successful: true } });
      }
      if (url === "/api/web/changes/chg-1/pir/pir-1/submit") {
        return jsonResponse({ status: "ok", pir: { pir_id: "pir-1", change_id: "chg-1", status: "submitted", implementation_successful: true } });
      }
      if (url === "/api/web/changes/chg-1/pir/pir-1/approve") {
        return jsonResponse({ status: "ok", pir: { pir_id: "pir-1", change_id: "chg-1", status: "approved", implementation_successful: true } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    await createChange({ title: "VPN", description: "VPN", change_type: "normal" });
    await createChangeFromProblem("problem-1");
    await transitionChange("chg-1", { status: "submitted" });
    const risk = await createRiskAssessment("chg-1");
    await submitRiskAssessment("chg-1", risk.assessment_id);
    await approveRiskAssessment("chg-1", risk.assessment_id);
    const plan = await createPlan("chg-1");
    await approvePlan("chg-1", plan.plan_id);
    await requestApprovals("chg-1");
    await approveApproval("chg-1", "a1");
    await createChangeWindow({ title: "Night", window_type: "maintenance", starts_at: "2026-05-18T10:00:00Z", ends_at: "2026-05-18T11:00:00Z" });
    await scheduleChange("chg-1", { planned_start_at: "2026-05-18T10:00:00Z", planned_end_at: "2026-05-18T11:00:00Z" });
    const task = await createTask("chg-1");
    await completeTask("chg-1", task.task_id);
    const pir = await createPir("chg-1");
    await submitPir("chg-1", pir.pir_id);
    await approvePir("chg-1", pir.pir_id);

    expect(fetchMock).toHaveBeenCalledTimes(17);
  });
});
