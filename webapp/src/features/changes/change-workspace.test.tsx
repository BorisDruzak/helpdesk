import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveApproval,
  approvePlan,
  approveRiskAssessment,
  createChange,
  createPlan,
  createRiskAssessment,
  fetchChangeSummary,
  fetchChangeTasks,
  fetchChangeWindows,
  fetchChanges,
  requestApprovals,
  scheduleChange,
  submitRiskAssessment,
} from "./api";
import { ChangeWorkspace } from "./change-workspace";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    approveApproval: vi.fn(),
    approvePlan: vi.fn(),
    approveRiskAssessment: vi.fn(),
    createChange: vi.fn(),
    createPlan: vi.fn(),
    createRiskAssessment: vi.fn(),
    fetchChangeSummary: vi.fn(),
    fetchChangeTasks: vi.fn(),
    fetchChangeWindows: vi.fn(),
    fetchChanges: vi.fn(),
    requestApprovals: vi.fn(),
    scheduleChange: vi.fn(),
    submitRiskAssessment: vi.fn(),
  };
});

const approveApprovalMock = vi.mocked(approveApproval);
const approvePlanMock = vi.mocked(approvePlan);
const approveRiskAssessmentMock = vi.mocked(approveRiskAssessment);
const createChangeMock = vi.mocked(createChange);
const createPlanMock = vi.mocked(createPlan);
const createRiskAssessmentMock = vi.mocked(createRiskAssessment);
const fetchChangeSummaryMock = vi.mocked(fetchChangeSummary);
const fetchChangeTasksMock = vi.mocked(fetchChangeTasks);
const fetchChangeWindowsMock = vi.mocked(fetchChangeWindows);
const fetchChangesMock = vi.mocked(fetchChanges);
const requestApprovalsMock = vi.mocked(requestApprovals);
const scheduleChangeMock = vi.mocked(scheduleChange);
const submitRiskAssessmentMock = vi.mocked(submitRiskAssessment);

function renderWorkspace() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ChangeWorkspace />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ChangeWorkspace", () => {
  it("shows changes and runs governance actions", async () => {
    fetchChangeSummaryMock.mockResolvedValue({
      change_count: 1,
      open_change_count: 1,
      emergency_change_count: 0,
      failed_change_count: 0,
      rollback_count: 0,
      failure_rate: 0.1,
      rollback_rate: 0.05,
      average_lead_time_hours: 12.5,
      average_implementation_duration_hours: 2,
      emergency_retrospective_overdue_count: 1,
      pir_completion_rate: 0.8,
      changes_by_type: { normal: 1 },
      changes_by_status: { draft: 1 },
      changes_by_risk: { medium: 1 },
      changes_by_service: { network: 1 },
    });
    fetchChangesMock.mockResolvedValue([
      {
        change_id: "chg-1",
        change_key: "CHG-000001",
        title: "VPN permanent fix",
        description: "VPN permanent fix",
        change_type: "normal",
        status: "draft",
        priority: "medium",
        risk_level: "medium",
        impact_level: "medium",
        service_code: "network",
        offering_code: "network.vpn_issue",
        affected_objects: [],
      },
    ]);
    fetchChangeWindowsMock.mockResolvedValue([
      {
        window_id: "w1",
        title: "Night",
        window_type: "maintenance",
        starts_at: "2026-05-18T10:00:00Z",
        ends_at: "2026-05-18T11:00:00Z",
        recurrence_rule: "FREQ=WEEKLY;BYDAY=MO",
      },
    ]);
    fetchChangeTasksMock.mockResolvedValue([]);
    createChangeMock.mockResolvedValue({
      change_id: "chg-2",
      change_key: "CHG-000002",
      title: "Firewall update",
      description: "Firewall update",
      change_type: "normal",
      status: "draft",
      priority: "medium",
      risk_level: "medium",
      impact_level: "medium",
    });
    createRiskAssessmentMock.mockResolvedValue({ assessment_id: "r1", change_id: "chg-1", status: "draft", risk_level: "medium", impact_level: "medium", suggested_risk_level: "medium", risk_factors: {} });
    submitRiskAssessmentMock.mockResolvedValue({ assessment_id: "r1", change_id: "chg-1", status: "submitted", risk_level: "medium", impact_level: "medium", suggested_risk_level: "medium", risk_factors: {} });
    approveRiskAssessmentMock.mockResolvedValue({ assessment_id: "r1", change_id: "chg-1", status: "approved", risk_level: "medium", impact_level: "medium", suggested_risk_level: "medium", risk_factors: {} });
    createPlanMock.mockResolvedValue({ plan_id: "p1", change_id: "chg-1", status: "draft", implementation_steps: [], rollback_steps: [], validation_steps: [] });
    approvePlanMock.mockResolvedValue({ plan_id: "p1", change_id: "chg-1", status: "approved", implementation_steps: [], rollback_steps: [], validation_steps: [] });
    requestApprovalsMock.mockResolvedValue({ approvals: [{ approval_id: "a1", change_id: "chg-1", approval_stage: "cab", status: "pending" }], satisfied: false });
    approveApprovalMock.mockResolvedValue({ approval_id: "a1", change_id: "chg-1", approval_stage: "cab", status: "approved" });
    scheduleChangeMock.mockResolvedValue({
      change_id: "chg-1",
      change_key: "CHG-000001",
      title: "VPN permanent fix",
      description: "VPN permanent fix",
      change_type: "normal",
      status: "scheduled",
      priority: "medium",
      risk_level: "medium",
      impact_level: "medium",
    });

    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "Change workspace" })).toBeInTheDocument();
    expect((await screen.findAllByText("CHG-000001")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Night")).toBeInTheDocument();
    expect(await screen.findByText("Failure rate")).toBeInTheDocument();
    expect(await screen.findByText("10%")).toBeInTheDocument();
    expect(await screen.findByText("12.5h")).toBeInTheDocument();
    expect(await screen.findByText("FREQ=WEEKLY;BYDAY=MO")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Change title"), { target: { value: "Firewall update" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(createChangeMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Approve risk" }));
    await waitFor(() => expect(createRiskAssessmentMock).toHaveBeenCalledWith("chg-1"));
    await waitFor(() => expect(submitRiskAssessmentMock).toHaveBeenCalledWith("chg-1", "r1"));
    await waitFor(() => expect(approveRiskAssessmentMock).toHaveBeenCalledWith("chg-1", "r1"));

    fireEvent.click(screen.getByRole("button", { name: "Approve plan" }));
    await waitFor(() => expect(createPlanMock).toHaveBeenCalledWith("chg-1"));
    await waitFor(() => expect(approvePlanMock).toHaveBeenCalledWith("chg-1", "p1"));

    fireEvent.click(screen.getByRole("button", { name: "Request approval" }));
    await waitFor(() => expect(requestApprovalsMock).toHaveBeenCalledWith("chg-1"));
    fireEvent.click(screen.getByRole("button", { name: "Approve request" }));
    await waitFor(() => expect(approveApprovalMock).toHaveBeenCalledWith("chg-1", "a1"));

    fireEvent.click(screen.getByRole("button", { name: "Schedule" }));
    await waitFor(() => expect(scheduleChangeMock).toHaveBeenCalled());
  });
});
