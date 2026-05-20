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
    generated_at: "2026-05-19T10:00:00+00:00",
    scope: "team",
    filters: {
      window_hours: 24,
      limit_per_section: 8,
      queue: null,
      assignee: null,
      query: null,
    },
    summary: {
      total_attention_items: 1,
      critical_count: 1,
      warning_count: 2,
      info_count: 0,
      new_unassigned_count: 1,
      operator_action_count: 0,
      unread_user_messages_count: 0,
      sla_risk_count: 1,
      ola_risk_count: 0,
      pending_approval_count: 0,
      pending_consent_count: 0,
      failed_operation_count: 0,
      agent_offline_active_count: 0,
      diagnostics_recommended_count: 0,
      closure_blocked_count: 0,
      similar_spikes_count: 0,
    },
    sections: [
      {
        key: "new_unassigned",
        title: "Новые без владельца",
        description: "Активные тикеты без назначенного исполнителя.",
        severity: "warning",
        count: 1,
        updated_at: "2026-05-19T09:30:00+00:00",
        action: { label: "Открыть в очереди", href: "/app/tickets?smart_view=unassigned" },
        items: [
          {
            id: "ticket-1:new",
            ticket_id: "ticket-1",
            ticket_number: "T-000001",
            title: "Нужно настроить VPN",
            status: "queued",
            priority: "P2",
            queue: "service-desk",
            assignee: null,
            requester_name: "Иван Петров",
            service_code: "network",
            reason: "Активный тикет еще не назначен исполнителю",
            href: "/app/tickets/ticket-1",
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
            title: "Нужно настроить VPN",
            status: "queued",
            priority: "P2",
            reason: "SLA скоро будет нарушен",
            href: "/app/tickets/ticket-1",
            sla: { state: "risk", due_at: "2026-05-19T11:00:00+00:00", remaining_seconds: 3600 },
          },
        ],
      },
      {
        key: "similar_tickets_spike",
        title: "Похожие обращения / всплеск",
        description: "Найдены похожие тикеты.",
        severity: "warning",
        count: 0,
        action: { label: "Открыть в очереди", href: "/app/tickets" },
        items: [],
      },
    ],
    metadata: {},
    ...overrides,
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
  it("renders Russian command center sections and ticket links", async () => {
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(payload());
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue({
      views: { needs_action: 0, sla_risk: 0, unassigned: 0, requester_replied: 0 },
      queues: [{ id: "service-desk", code: "service-desk", name: "Service Desk", count: 1 }],
      smart_view_counts: [],
      smart_view_options: [],
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "Рабочий центр" })).toBeInTheDocument();
    expect(screen.getByText("Сначала обработать")).toBeInTheDocument();
    expect((await screen.findAllByText("Нужно настроить VPN")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Новые без владельца").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Открыть тикет" })[0]).toHaveAttribute("href", "/app/tickets/ticket-1");
    expect(screen.getAllByText("SLA риск").length).toBeGreaterThan(0);
  });

  it("renders calm empty state when there are no attention items", async () => {
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
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue({
      views: { needs_action: 0, sla_risk: 0, unassigned: 0, requester_replied: 0 },
      queues: [],
      smart_view_counts: [],
      smart_view_options: [],
    });

    renderPage();

    expect(await screen.findByText("Нет срочных действий")).toBeInTheDocument();
    expect(screen.getByText(/Новые сообщения, SLA-риск, ошибки операций/)).toBeInTheDocument();
  });

  it("masks historical mojibake in primary ticket fields", async () => {
    const data = payload();
    data.sections[0].items[0] = {
      ...data.sections[0].items[0],
      title: "\u0420\u045c broken title",
      requester_name: "\u0420\u045c requester",
    };
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(data);
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue({
      views: { needs_action: 0, sla_risk: 0, unassigned: 0, requester_replied: 0 },
      queues: [],
      smart_view_counts: [],
      smart_view_options: [],
    });

    renderPage();

    expect((await screen.findAllByText("Без названия")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Инициатор: Пользователь не указан").length).toBeGreaterThan(0);
    expect(screen.queryByText("\u0420\u045c broken title")).not.toBeInTheDocument();
  });

  it("passes selected queue to the typed API", async () => {
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(payload());
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue({
      views: { needs_action: 0, sla_risk: 0, unassigned: 0, requester_replied: 0 },
      queues: [{ id: "q1", code: "service-desk", name: "Service Desk", count: 4 }],
      smart_view_counts: [],
      smart_view_options: [],
    });

    renderPage();
    await screen.findByRole("heading", { name: "Рабочий центр" });

    await waitFor(() => expect(fetchOperatorCommandCenter).toHaveBeenCalledWith(expect.objectContaining({ scope: "team" })));
  });

  it("passes search query and section limit to the typed API", async () => {
    vi.mocked(fetchOperatorCommandCenter).mockResolvedValue(payload());
    vi.mocked(fetchSupportWorkspaceSummary).mockResolvedValue({
      views: { needs_action: 0, sla_risk: 0, unassigned: 0, requester_replied: 0 },
      queues: [],
      smart_view_counts: [],
      smart_view_options: [],
    });

    renderPage();
    await screen.findByRole("heading", { name: "Рабочий центр" });

    fireEvent.change(screen.getByPlaceholderText("Тикет, инициатор, услуга, устройство"), {
      target: { value: "T-000569" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Найти" }).closest("form") as HTMLFormElement);
    fireEvent.change(screen.getByRole("combobox", { name: "Показывать" }), {
      target: { value: "20" },
    });

    await waitFor(() =>
      expect(fetchOperatorCommandCenter).toHaveBeenCalledWith(
        expect.objectContaining({ query: "T-000569", limit_per_section: 20 }),
      ),
    );
  });
});
