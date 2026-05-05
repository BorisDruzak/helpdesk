import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  fetchSupportQueue,
  fetchSupportTicketWorkspace,
  postSupportTicketReroute,
  type SupportQueuePayload,
  type SupportQueueScope,
  type SupportTicketWorkspacePayload,
} from "../../features/queues/api";
import { TicketListPage } from "./list-page";

vi.mock("../../features/queues/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/queues/api")>();
  return {
    ...actual,
    fetchSupportQueue: vi.fn(),
    fetchSupportTicketWorkspace: vi.fn(),
    postSupportTicketReroute: vi.fn(),
  };
});

vi.mock("../../features/auth/session-provider", () => ({
  useSession: () => ({
    session: {
      actor_role: "support",
      user_login: "support-test",
    },
  }),
}));

const fetchSupportQueueMock = vi.mocked(fetchSupportQueue);
const fetchSupportTicketWorkspaceMock = vi.mocked(fetchSupportTicketWorkspace);
const postSupportTicketRerouteMock = vi.mocked(postSupportTicketReroute);

function queuePayload(overrides: Partial<SupportQueuePayload> = {}): SupportQueuePayload {
  return {
    scope: overrides.scope ?? "all",
    query: overrides.query ?? "",
    status_filter: overrides.status_filter ?? "all",
    smart_view: overrides.smart_view ?? "all",
    summary: {
      visible_count: 2,
      selected_ticket_id: "ticket-1",
      scope_counts: [
        { value: "all", label: "Все доступные", count: 8 },
        { value: "mine", label: "Только мои", count: 3 },
      ],
      status_counts: [
        { value: "all", label: "Все статусы", count: 8 },
        { value: "in_progress", label: "В работе", count: 5 },
        { value: "waiting_on_user", label: "Ожидает пользователя", count: 1 },
      ],
      smart_view_counts: [
        { value: "all", label: "Все", count: 8 },
        { value: "ola_risk", label: "Риск внутренней очереди", count: 2 },
        { value: "sla_risk", label: "Риск по сроку ответа", count: 1 },
        { value: "regional_vip_risk", label: "Региональный VIP риск", count: 4 },
      ],
      queue_counts: [{ id: 1, code: "networks", name: "networks", count: 2 }],
      ...overrides.summary,
    },
    filters: {
      scope_options: [
        { value: "all", label: "Все доступные" },
        { value: "mine", label: "Только мои" },
      ],
      status_options: [
        { value: "all", label: "Все статусы" },
        { value: "in_progress", label: "В работе" },
      ],
      smart_view_options: [
        { value: "all", label: "Все" },
        { value: "ola_risk", label: "Риск внутренней очереди" },
        { value: "sla_risk", label: "Риск по сроку ответа" },
        { value: "regional_vip_risk", label: "Региональный VIP риск" },
      ],
      ...overrides.filters,
    },
    tickets:
      overrides.tickets ?? [
        {
          ticket_id: "ticket-1",
          ticket_code: "T-000001",
          title: "Проверить OLA очередь",
          status: "in_progress",
          status_label: "В работе",
          requester_status: "in_work",
          requester_status_label: "Заявка в работе",
          next_action_owner: "support",
          next_action_due_at: null,
          status_reason: null,
          priority: "P1",
          priority_class: "P1",
          queue_code: "networks",
          assignee_id: "support-test",
          assignee_display_name: "support-test",
          requester_display_name: "Иван Петров",
          device_id: "device-1",
          updated_at: "2026-05-03T09:00:00+05:00",
          created_at: "2026-05-03T08:30:00+05:00",
          requires_operator_action: true,
          unread_user_messages: 0,
        },
      ],
  };
}

function workspacePayload(overrides: Partial<SupportTicketWorkspacePayload> = {}): SupportTicketWorkspacePayload {
  return {
    detail: {
      ticket: {
        ticket_id: "ticket-1",
        ticket_code: "T-000001",
        title: "Проверить OLA очередь",
        description: "Описание",
        status: "in_progress",
        status_label: "В работе",
        requester_display_name: "Иван Петров",
        device_id: "device-1",
        priority: "P1",
        priority_class: "P1",
        first_response_due_at: null,
        resolution_due_at: null,
        queue: { id: 1, code: "networks", name: "networks" },
        assignee_id: "support-test",
        updated_at: "2026-05-03T09:00:00+05:00",
        created_at: "2026-05-03T08:30:00+05:00",
        queue_members: [],
      },
      request_form: null,
      observer: {
        ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
        summary: {
          ticket_id: "ticket-1",
          trace_count: 0,
          active_trace_count: 0,
          error_trace_count: 0,
          signature_count: 0,
        },
      },
      timeline: [],
      snapshot: {
        last_event_id: 0,
        notification_unread: 0,
        presence: {
          requester_online: false,
          support_online: true,
          agent_online: false,
        },
        device: {
          device_id: "device-1",
          hostname: "PC-1",
          os: "Windows",
          agent_version: null,
          last_seen_at: null,
          online: false,
        },
        latest_operations: [],
      },
      actions: {
        status_options: [{ value: "waiting_on_user", label: "Ждёт пользователя" }],
        can_send_internal_note: true,
      },
    },
    tools: { ticket_id: "ticket-1", device_id: "device-1", tools: [] },
    playbooks: { ticket_id: "ticket-1", device_id: "device-1", playbooks: [] },
    passport: {
      ticket_id: "ticket-1",
      status: "missing",
      passport: null,
      evidence: [],
      actions: [],
      approvals: [],
      related_objects: [],
    },
    knowledge: {
      ticket_id: "ticket-1",
      similar_tickets: [],
      articles: [],
      ai_summary: { text: null, sources: [] },
    },
    ...overrides,
  };
}

function renderTicketListPage(initialEntry = "/app/tickets") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/app/tickets" element={<TicketListPage />} />
          <Route path="/app/tickets/:ticketId" element={<TicketListPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("TicketListPage", () => {
  it("renders built-in and custom smart-view counts and sends selected smart view to the queue API", async () => {
    fetchSupportTicketWorkspaceMock.mockResolvedValue(workspacePayload());
    fetchSupportQueueMock.mockImplementation(async ({ scope, statusFilter, smartView, query }) =>
      queuePayload({
        scope: scope as SupportQueueScope,
        status_filter: statusFilter,
        smart_view: smartView ?? "all",
        query,
        summary: {
          visible_count: smartView === "regional_vip_risk" ? 4 : 2,
          selected_ticket_id: "ticket-1",
          scope_counts: [
            { value: "all", label: "Все доступные", count: 8 },
            { value: "mine", label: "Только мои", count: 3 },
          ],
          status_counts: [
            { value: "all", label: "Все статусы", count: 8 },
            { value: "in_progress", label: "В работе", count: 5 },
            { value: "waiting_on_user", label: "Ожидает пользователя", count: 1 },
          ],
          smart_view_counts: [
            { value: "all", label: "Все", count: 8 },
            { value: "ola_risk", label: "Риск внутренней очереди", count: 2 },
            { value: "sla_risk", label: "Риск по сроку ответа", count: 1 },
            { value: "regional_vip_risk", label: "Региональный VIP риск", count: 4 },
          ],
          queue_counts: [{ id: 1, code: "networks", name: "networks", count: 2 }],
        },
      }),
    );

    renderTicketListPage();

    expect(await screen.findByText("Рабочие срезы")).toBeInTheDocument();
    expect(await screen.findByText("Проверить OLA очередь")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /SLA риск\s*1/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Риск внутренней очереди\s*2/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Региональный VIP риск\s*4/ })).toBeInTheDocument();
    expect(screen.getByText("networks")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Региональный VIP риск\s*4/ }));

    await waitFor(() => {
      expect(fetchSupportQueueMock).toHaveBeenCalledWith(
        expect.objectContaining({
          smartView: "regional_vip_risk",
        }),
      );
    });
  });

  it("loads selected ticket through the aggregate workspace endpoint and exposes tested More actions", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(workspacePayload());
    postSupportTicketRerouteMock.mockResolvedValue({
      ticket_id: "ticket-1",
      action: "reroute",
      status: "in_progress",
      status_label: "В работе",
      queue: { id: 1, code: "networks", name: "networks" },
      assignee_id: "support-test",
      priority: "P1",
      priority_class: "P1",
      auto_assigned: false,
    });

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByText("Проверить OLA очередь")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchSupportTicketWorkspaceMock).toHaveBeenCalledWith("ticket-1");
    });

    fireEvent.click(screen.getByRole("button", { name: "Ещё" }));

    expect(screen.getByRole("button", { name: "Назначить на себя" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сменить очередь" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Изменить приоритет" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Пересчитать маршрут" }));

    await waitFor(() => {
      expect(postSupportTicketRerouteMock).toHaveBeenCalledWith("ticket-1", { reason: "manual_recalculate" });
    });
  });
});
