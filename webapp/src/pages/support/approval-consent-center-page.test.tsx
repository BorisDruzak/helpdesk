import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appNavigation } from "../../app/navigation";
import { fetchApprovalConsentCenter } from "../../features/approval-consent-center/api";
import type { ApprovalConsentCenterPayload } from "../../features/approval-consent-center/types";
import { ApprovalConsentCenterPage } from "./approval-consent-center-page";

vi.mock("../../features/approval-consent-center/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/approval-consent-center/api")>();
  return {
    ...actual,
    fetchApprovalConsentCenter: vi.fn(),
  };
});

function payload(overrides: Partial<ApprovalConsentCenterPayload> = {}): ApprovalConsentCenterPayload {
  return {
    generated_at: "2026-05-21T10:00:00+00:00",
    scope: "team",
    filters: {
      kind: null,
      status: "pending",
      risk: null,
      object_type: null,
      queue: null,
      assignee: null,
      due_window_hours: null,
      limit: 50,
      offset: 0,
    },
    summary: {
      total_count: 2,
      pending_count: 2,
      overdue_count: 1,
      high_risk_count: 1,
      waiting_user_count: 1,
      waiting_approver_count: 1,
      blocking_sla_count: 1,
      ticket_approvals_count: 1,
      change_approvals_count: 0,
      risky_tool_consents_count: 0,
      remote_assist_consents_count: 1,
      closure_approvals_count: 0,
      policy_overrides_count: 0,
    },
    sections: [
      {
        key: "waiting_me",
        title: "Ждёт меня",
        description: "Согласования, где текущий оператор указан исполнителем или согласующим.",
        count: 1,
        severity: "warning",
      },
      {
        key: "remote_assist_consents",
        title: "Удалённая помощь",
        description: "Remote Assist сессии, ожидающие согласия пользователя.",
        count: 1,
        severity: "warning",
      },
    ],
    items: [
      {
        id: "ticket_approval:1",
        kind: "ticket_approval",
        status: "pending",
        title: "Нужен доступ к Directum",
        reason: "Требуется согласование владельца услуги",
        object_type: "ticket",
        object_id: "ticket-1",
        ticket_id: "ticket-1",
        ticket_number: "T-000001",
        requester_name: "Иван Петров",
        requested_by: "support-1",
        approver: "manager-1",
        risk: "high",
        due_at: "2026-05-21T11:00:00+00:00",
        created_at: "2026-05-21T09:00:00+00:00",
        updated_at: "2026-05-21T09:00:00+00:00",
        blocking: { blocks_ticket_progress: true, blocks_sla: true },
        context: { queue: "10", assignee: "support-1", service_code: "directum" },
        actions: [{ key: "open_ticket", label: "Открыть тикет", href: "/app/tickets/ticket-1", enabled: true }],
      },
      {
        id: "remote_assist_consent:session-1",
        kind: "remote_assist_consent",
        status: "pending",
        title: "Удалённая помощь ждёт согласия пользователя",
        reason: "Нужно визуально проверить ошибку",
        object_type: "remote_assist",
        object_id: "session-1",
        ticket_id: "ticket-1",
        remote_assist_session_id: "session-1",
        device_id: "device-1",
        requester_name: "user-1",
        requested_by: "support-1",
        approver: "user-1",
        risk: "medium",
        due_at: "2026-05-21T11:10:00+00:00",
        blocking: { blocks_remote_assist: true, blocks_ticket_progress: true },
        context: {},
        actions: [
          { key: "open_ticket", label: "Открыть тикет", href: "/app/tickets/ticket-1", enabled: true },
          { key: "approve", label: "Approve", enabled: false, disabled_reason: "Нет безопасного endpoint в этом cut" },
        ],
      },
    ],
    ...overrides,
  };
}

function renderPage(initialPath = "/app/support/approvals") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <ApprovalConsentCenterPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ApprovalConsentCenterPage", () => {
  it("renders Russian title, KPI strip, sections and item links", async () => {
    vi.mocked(fetchApprovalConsentCenter).mockResolvedValue(payload());

    renderPage();

    expect(await screen.findByRole("heading", { name: "Центр согласований и согласий" })).toBeInTheDocument();
    expect(await screen.findByText("Всего ожидает")).toBeInTheDocument();
    expect(screen.getAllByText("Ждёт меня").length).toBeGreaterThan(0);
    expect(screen.getByText("Нужен доступ к Directum")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Открыть тикет" })[0]).toHaveAttribute("href", "/app/tickets/ticket-1");
    expect(screen.queryByText(/secret|SDP|TURN/i)).not.toBeInTheDocument();
  });

  it("renders empty state", async () => {
    vi.mocked(fetchApprovalConsentCenter).mockResolvedValue(
      payload({
        summary: {
          total_count: 0,
          pending_count: 0,
          overdue_count: 0,
          high_risk_count: 0,
          waiting_user_count: 0,
          waiting_approver_count: 0,
          blocking_sla_count: 0,
          ticket_approvals_count: 0,
          change_approvals_count: 0,
          risky_tool_consents_count: 0,
          remote_assist_consents_count: 0,
          closure_approvals_count: 0,
          policy_overrides_count: 0,
        },
        items: [],
      }),
    );

    renderPage();

    expect(await screen.findByText("Нет ожидающих согласований")).toBeInTheDocument();
  });

  it("passes filters to API and reads initial kind from query", async () => {
    vi.mocked(fetchApprovalConsentCenter).mockResolvedValue(payload());

    renderPage("/app/support/approvals?kind=pending_consent");
    await screen.findByRole("heading", { name: "Центр согласований и согласий" });

    await waitFor(() =>
      expect(fetchApprovalConsentCenter).toHaveBeenCalledWith(expect.objectContaining({ kind: "pending_consent" })),
    );

    fireEvent.change(screen.getByLabelText("Риск"), { target: { value: "high" } });

    await waitFor(() =>
      expect(fetchApprovalConsentCenter).toHaveBeenCalledWith(expect.objectContaining({ kind: "pending_consent", risk: "high" })),
    );
  });

  it("adds approval center to support navigation", () => {
    expect(appNavigation).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          label: "Согласования",
          to: "/app/support/approvals",
          permission: "ticket.queue.view",
        }),
      ]),
    );
  });
});
