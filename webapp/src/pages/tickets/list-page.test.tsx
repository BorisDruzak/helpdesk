import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { fetchSupportQueue, type SupportQueuePayload, type SupportQueueScope } from "../../features/queues/api";
import { TicketListPage } from "./list-page";

vi.mock("../../features/queues/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/queues/api")>();
  return {
    ...actual,
    fetchSupportQueue: vi.fn(),
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

function renderTicketListPage() {
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
      <MemoryRouter>
        <TicketListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("TicketListPage", () => {
  it("renders built-in and custom smart-view counts and sends selected smart view to the queue API", async () => {
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
});
