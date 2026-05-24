import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchSupportWorkspaceSummary } from "../../features/queues/api";
import { fetchOperatorCommandCenter, type OperatorCommandCenterPayload } from "../../features/operator-command-center/api";
import { SupportCommandCenterPage } from "./command-center-page";

vi.mock("../../features/operator-command-center/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/operator-command-center/api")>();
  return {
    ...actual,
    fetchOperatorCommandCenter: vi.fn(),
  };
});

vi.mock("../../features/queues/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/queues/api")>();
  return {
    ...actual,
    fetchSupportWorkspaceSummary: vi.fn(),
  };
});

function payload(overrides: Partial<OperatorCommandCenterPayload> = {}): OperatorCommandCenterPayload {
  return {
    generated_at: "2026-05-24T10:00:00+00:00",
    scope: "team",
    filters: {
      window_hours: 24,
      limit_per_section: 8,
      queue: null,
      assignee: null,
      query: null,
    },
    summary: {
      total_attention_items: 3,
      critical_count: 2,
      warning_count: 2,
      info_count: 1,
      new_unassigned_count: 1,
      operator_action_count: 0,
      unread_user_messages_count: 1,
      sla_risk_count: 1,
      ola_risk_count: 0,
      pending_approval_count: 0,
      pending_consent_count: 0,
      failed_operation_count: 1,
      agent_offline_active_count: 0,
      diagnostics_recommended_count: 0,
      closure_blocked_count: 1,
      similar_spikes_count: 0,
    },
    sections: [
      {
        key: "new_unassigned",
        title: "Новые без владельца",
        description: "Активные тикеты без назначенного исполнителя.",
        severity: "warning",
        count: 1,
        updated_at: "2026-05-24T09:30:00+00:00",
        action: { label: "Открыть в очереди", href: "/app/tickets?smart_view=unassigned" },
        items: [
          {
            id: "ticket-1:new",
            ticket_id: "ticket-1",
            ticket_number: "T-000001",
            title: "Настроить VPN",
            status: "queued",
            priority: "P1",
            queue: "Service Desk",
            assignee: null,
            requester_name: "Иван Петров",
            service_code: "network",
            offering_code: "vpn",
            reason: "Активный тикет еще не назначен исполнителю",
            href: "/app/tickets/ticket-1",
            updated_at: "2026-05-24T09:20:00+00:00",
          },
        ],
      },
      {
        key: "sla_risk",
        title: "SLA риск",
        description: "Срок ответа близок к нарушению.",
        severity: "critical",
        count: 1,
        action: { label: "Открыть в очереди", href: "/app/tickets?smart_view=sla_risk" },
        items: [
          {
            id: "ticket-1:sla",
            ticket_id: "ticket-1",
            ticket_number: "T-000001",
            title: "Настроить VPN",
            status: "queued",
            priority: "P1",
            queue: "Service Desk",
            requester_name: "Иван Петров",
            reason: "SLA уже нарушен",
            href: "/app/tickets/ticket-1",
            sla: { state: "breached", due_at: "2026-05-24T09:00:00+00:00", remaining_seconds: -3600 },
            updated_at: "2026-05-24T09:25:00+00:00",
          },
        ],
      },
      {
        key: "unread_user_messages",
        title: "Сообщения пользователей",
        description: "Пользователь ждет ответа.",
        severity: "warning",
        count: 1,
        items: [
          {
            id: "ticket-1:message",
            ticket_id: "ticket-1",
            ticket_number: "T-000001",
            title: "Настроить VPN",
            status: "queued",
            priority: "P1",
            queue: "Service Desk",
            requester_name: "Иван Петров",
            unread_user_messages: 2,
            reason: "Есть новые сообщения пользователя",
            href: "/app/tickets/ticket-1",
          },
        ],
      },
      {
        key: "failed_operation",
        title: "Ошибки операций",
        description: "Операции завершились ошибкой.",
        severity: "critical",
        count: 1,
        items: [
          {
            id: "ticket-2:failed",
            ticket_id: "ticket-2",
            ticket_number: "T-000002",
            title: "Собрать логи",
            status: "in_progress",
            priority: "P2",
            queue: "L2",
            assignee: "operator",
            requester_name: "Мария",
            reason: "Операция завершилась ошибкой",
            href: "/app/tickets/ticket-2",
            operation: { id: "op-1", status: "failed", tool_name: "diag.logs.collect", error_summary: "timeout" },
          },
        ],
      },
      {
        key: "closure_blocked",
        title: "Блокеры закрытия",
        description: "Не выполнены требования закрытия.",
        severity: "warning",
        count: 1,
        items: [
          {
            id: "ticket-3:closure",
            ticket_id: "ticket-3",
            ticket_number: "T-000003",
            title: "Закрыть обращение",
            status: "resolved",
            priority: "P3",
            queue: "Service Desk",
            assignee: "operator",
            requester_name: "Олег",
            reason: "Не хватает публичного итога",
            href: "/app/tickets/ticket-3",
            closure: { blocked: true, missing_count: 1, primary_blocker: "Нужен публичный итог" },
          },
        ],
      },
    ],
    metadata: {},
    ...overrides,
  };
}

function summary() {
  return {
    views: { needs_action: 2, sla_risk: 1, unassigned: 1, requester_replied: 1 },
    queues: [{ id: "service-desk", code: "service-desk", name: "Service Desk", count: 2 }],
    smart_view_counts: [],
    smart_view_options: [],
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SupportCommandCenterPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("SupportCommandCenterPage", () => {
  it("renders Action Inbox title and task-first rows", async () => {
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(payload());
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue(summary());

    renderPage();

    expect(await screen.findByRole("heading", { name: "Центр действий" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Action Inbox" })).toBeInTheDocument();
    expect(await screen.findByText("Спасти SLA")).toBeInTheDocument();
    expect(screen.getByText("Настроить VPN")).toBeInTheDocument();
    expect(screen.getAllByText("SLA риск").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Сообщения пользователей").length).toBeGreaterThan(0);
  });

  it("renders Ticket Briefing after selecting a task", async () => {
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(payload());
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue(summary());

    renderPage();
    fireEvent.click(await screen.findByText("Настроить VPN"));

    expect(screen.getByRole("heading", { name: "T-000001" })).toBeInTheDocument();
    expect(screen.getByText("Почему в центре действий")).toBeInTheDocument();
    expect(screen.getAllByText("Иван Петров").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Открыть guided workspace" })).toHaveAttribute("href", "/app/tickets/ticket-1");
  });

  it("shows empty state when there are no tasks", async () => {
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(
      payload({
        summary: {
          total_attention_items: 0,
          critical_count: 0,
          warning_count: 0,
          info_count: 0,
          new_unassigned_count: 0,
          operator_action_count: 0,
          unread_user_messages_count: 0,
          sla_risk_count: 0,
          ola_risk_count: 0,
          pending_approval_count: 0,
          pending_consent_count: 0,
          failed_operation_count: 0,
          agent_offline_active_count: 0,
          diagnostics_recommended_count: 0,
          closure_blocked_count: 0,
          similar_spikes_count: 0,
        },
        sections: [],
      }),
    );
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue(summary());

    renderPage();

    expect(await screen.findByText("Нет срочных действий")).toBeInTheDocument();
    expect(screen.getByText("Выберите задачу слева, чтобы увидеть краткий анализ тикета.")).toBeInTheDocument();
  });

  it("Kanban mode renders grouped columns", async () => {
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(payload());
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue(summary());

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Kanban" }));

    expect(screen.getByRole("heading", { name: "Kanban" })).toBeInTheDocument();
    expect(screen.getByText("SLA risk")).toBeInTheDocument();
    expect(screen.getByText("Operations / Diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Closure")).toBeInTheDocument();
  });

  it("passes search query and section limit to the typed API", async () => {
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(payload());
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue(summary());

    renderPage();
    await screen.findByRole("heading", { name: "Центр действий" });

    fireEvent.change(screen.getByPlaceholderText("Тикет, инициатор, услуга, устройство"), {
      target: { value: "T-000002" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Найти" }).closest("form") as HTMLFormElement);
    fireEvent.change(screen.getByRole("combobox", { name: "Источник" }), {
      target: { value: "20" },
    });

    await waitFor(() =>
      expect(fetchOperatorCommandCenter).toHaveBeenCalledWith(
        expect.objectContaining({ query: "T-000002", limit_per_section: 20 }),
      ),
    );
  });
});
