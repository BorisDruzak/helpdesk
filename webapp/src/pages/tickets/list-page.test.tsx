import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  fetchSupportQueue,
  fetchSupportTicketPassportEvidenceCandidates,
  fetchSupportTicketTimeline,
  fetchSupportTicketWorkspace,
  linkSupportTicketPassportEvidence,
  postSupportOperationCancel,
  postSupportOperationRetry,
  postSupportTicketWorklog,
  postSupportTicketAssign,
  postSupportTicketPriority,
  postSupportTicketQueue,
  postSupportTicketReroute,
  postSupportTicketStatus,
  type SupportQueuePayload,
  type SupportTicketTimelinePayload,
  type SupportQueueScope,
  type SupportTicketWorkspacePayload,
} from "../../features/queues/api";
import { TicketListPage } from "./list-page";

vi.mock("../../features/queues/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/queues/api")>();
  return {
    ...actual,
    fetchSupportQueue: vi.fn(),
    fetchSupportTicketPassportEvidenceCandidates: vi.fn(),
    fetchSupportTicketTimeline: vi.fn(),
    fetchSupportTicketWorkspace: vi.fn(),
    linkSupportTicketPassportEvidence: vi.fn(),
    postSupportOperationCancel: vi.fn(),
    postSupportOperationRetry: vi.fn(),
    postSupportTicketWorklog: vi.fn(),
    postSupportTicketAssign: vi.fn(),
    postSupportTicketPriority: vi.fn(),
    postSupportTicketQueue: vi.fn(),
    postSupportTicketReroute: vi.fn(),
    postSupportTicketStatus: vi.fn(),
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
const fetchSupportTicketPassportEvidenceCandidatesMock = vi.mocked(fetchSupportTicketPassportEvidenceCandidates);
const fetchSupportTicketTimelineMock = vi.mocked(fetchSupportTicketTimeline);
const fetchSupportTicketWorkspaceMock = vi.mocked(fetchSupportTicketWorkspace);
const linkSupportTicketPassportEvidenceMock = vi.mocked(linkSupportTicketPassportEvidence);
const postSupportOperationCancelMock = vi.mocked(postSupportOperationCancel);
const postSupportOperationRetryMock = vi.mocked(postSupportOperationRetry);
const postSupportTicketWorklogMock = vi.mocked(postSupportTicketWorklog);
const postSupportTicketAssignMock = vi.mocked(postSupportTicketAssign);
const postSupportTicketPriorityMock = vi.mocked(postSupportTicketPriority);
const postSupportTicketQueueMock = vi.mocked(postSupportTicketQueue);
const postSupportTicketRerouteMock = vi.mocked(postSupportTicketReroute);
const postSupportTicketStatusMock = vi.mocked(postSupportTicketStatus);

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
        registry: {
          person_id: "person-1",
          person_display_name: "Александр Смирнов",
          person_phone: "+7 (495) 123-45-67",
          person_email: "a.smirnov@example.test",
          person_source: "manual",
          department_id: "department-1",
          department_name: "Отдел маркетинга",
          location_id: "location-1",
          location_display_name: "БЦ, 3 этаж, каб. 305",
          building: "БЦ",
          floor: "3",
          room: "305",
          asset_id: "asset-1",
          asset_name: "PC-1",
          asset_type: "pc",
          service_id: "service-1",
          service_name: "Корпоративный сайт",
          service_owner_queue_id: 7,
          service_owner_queue_name: "Web L2",
          service_source: "registry",
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
    sla_ola: {
      first_response: { due_at: null, remaining_seconds: null, target_seconds: null, status: "unknown" },
      resolution: { due_at: null, remaining_seconds: null, target_seconds: null, status: "unknown" },
      ola_ack: { due_at: null, remaining_seconds: null, target_seconds: null, status: "unknown" },
      ola_processing: { due_at: null, remaining_seconds: null, target_seconds: null, status: "unknown" },
    },
    passport_readiness: {
      ticket_id: "ticket-1",
      status: "missing",
      done: 0,
      total: 4,
      items: [
        { key: "problem_identified", label: "Проблема идентифицирована", status: "pending" },
        { key: "cause_found", label: "Причина установлена", status: "pending" },
        { key: "solution_applied", label: "Решение применено", status: "pending" },
        { key: "verified_and_closed", label: "Проверка и закрытие", status: "pending" },
      ],
    },
    closure_plan: {
      ticket_id: "ticket-1",
      ready_for_resolution: true,
      missing_count: 0,
      total: 0,
      evidence_candidate_count: 0,
      recommended_next_action: null,
      blockers: [],
    },
    ...overrides,
  };
}

function timelinePayload(overrides: Partial<SupportTicketTimelinePayload> = {}): SupportTicketTimelinePayload {
  return {
    ticket_id: "ticket-1",
    filter: "diagnostics",
    total: 1,
    limit: 80,
    items: [
      {
        message_id: null,
        event_id: 99,
        event_type: "tool_call_result",
        event_category: "diagnostics",
        event_label: "Tool Call Result",
        event_details: {},
        from_role: "system",
        sender_display_name: "Система",
        text: "Результат инструмента: dns.resolve",
        ts: "2026-05-03T09:20:00+05:00",
        visibility: "system",
        direction: "system",
        attachments: [],
        reply_to: null,
        tool_name: "dns.resolve",
        tool_status: "succeeded",
        result_summary: "Filtered DNS result",
        result_preview: null,
        operation_steps: [
          { name: "DNS", status: "ok", value: "example.test -> 192.0.2.10" },
          { name: "HTTP", status: "error", value: "502 Bad Gateway", details: "Upstream returned an invalid gateway response." },
        ],
      },
    ],
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
  window.localStorage.clear();
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

  it("loads selected ticket through the aggregate workspace endpoint and captures a reason before reroute", async () => {
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
    expect(screen.getByRole("button", { name: "Сменить статус" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сменить очередь" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Изменить приоритет" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Пересчитать маршрут" }));

    expect(screen.getByRole("dialog", { name: "Пересчитать маршрут" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Пересчитать" })).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Например: ручная корректировка по диагностике"), {
      target: { value: "manual_recalculate" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Пересчитать" }));

    await waitFor(() => {
      expect(postSupportTicketRerouteMock).toHaveBeenCalledWith("ticket-1", { reason: "manual_recalculate" });
    });
  });

  it("shows a ticket-not-found workspace edge state instead of a raw error", async () => {
    const baseQueuePayload = queuePayload();
    fetchSupportQueueMock.mockResolvedValue(
      queuePayload({
        summary: { ...baseQueuePayload.summary, selected_ticket_id: null, visible_count: 0 },
        tickets: [],
      }),
    );
    fetchSupportTicketWorkspaceMock.mockRejectedValue(new Error("404 not found"));

    renderTicketListPage("/app/tickets/missing-ticket");

    expect(await screen.findByText("Тикет не найден")).toBeInTheDocument();
    expect(screen.getByText("Он мог быть закрыт, удалён или недоступен в текущей очереди.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Вернуться к очереди" }));

    expect(await screen.findByText("Выберите тикет из очереди")).toBeInTheDocument();
  });

  it("shows a permission-denied workspace edge state for forbidden tickets", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockRejectedValue(new Error("403 forbidden"));

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByText("Недостаточно прав")).toBeInTheDocument();
    expect(screen.getByText("У вашей роли нет доступа к этому тикету или внутренним данным.")).toBeInTheDocument();
  });

  it("renders actionable empty timeline states for all and filtered views", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(workspacePayload());
    fetchSupportTicketTimelineMock.mockResolvedValue(timelinePayload({ items: [], total: 0 }));

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByText("В таймлайне пока нет событий")).toBeInTheDocument();
    expect(screen.getByText("Новые сообщения, диагностика и системные изменения появятся здесь.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Диагностика" }));

    expect(await screen.findByText("Нет событий: Диагностика")).toBeInTheDocument();
    expect(screen.getByText("Смените фильтр или откройте все события таймлайна.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Показать все события" }));

    expect(await screen.findByText("В таймлайне пока нет событий")).toBeInTheDocument();
  });

  it("sends selected status, queue, priority and assign targets through reason-capturing controls", async () => {
    const baseQueuePayload = queuePayload();
    fetchSupportQueueMock.mockResolvedValue(
      queuePayload({
        summary: {
          ...baseQueuePayload.summary,
          queue_counts: [
            { id: 1, code: "networks", name: "networks", count: 2 },
            { id: 2, code: "servers", name: "Серверы", count: 4 },
          ],
        },
      }),
    );
    fetchSupportTicketWorkspaceMock.mockResolvedValue(workspacePayload());
    postSupportTicketStatusMock.mockResolvedValue({ ticket_id: "ticket-1", status: "waiting_on_user", status_label: "Ждёт пользователя" });
    postSupportTicketQueueMock.mockResolvedValue({
      ticket_id: "ticket-1",
      action: "queue",
      status: "in_progress",
      status_label: "В работе",
      queue: { id: 2, code: "servers", name: "Серверы" },
      assignee_id: "support-test",
      priority: "P1",
      priority_class: "P1",
      auto_assigned: false,
    });
    postSupportTicketPriorityMock.mockResolvedValue({
      ticket_id: "ticket-1",
      action: "priority",
      status: "in_progress",
      status_label: "В работе",
      queue: { id: 1, code: "networks", name: "networks" },
      assignee_id: "support-test",
      priority: "P1",
      priority_class: "P0",
      auto_assigned: false,
    });
    postSupportTicketAssignMock.mockResolvedValue({
      ticket_id: "ticket-1",
      action: "assign",
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

    fireEvent.click(screen.getByRole("button", { name: "Ещё" }));
    fireEvent.click(screen.getByRole("button", { name: "Сменить статус" }));
    fireEvent.change(screen.getByPlaceholderText("Например: ручная корректировка по диагностике"), {
      target: { value: "status reason" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Применить статус" }));
    await waitFor(() => {
      expect(postSupportTicketStatusMock).toHaveBeenCalledWith("ticket-1", "waiting_on_user", {
        reason: "status reason",
        internalComment: undefined,
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "Ещё" }));
    fireEvent.click(screen.getByRole("button", { name: "Сменить очередь" }));
    fireEvent.change(screen.getByLabelText("Целевая очередь"), { target: { value: "2" } });
    fireEvent.change(screen.getByPlaceholderText("Например: ручная корректировка по диагностике"), {
      target: { value: "queue reason" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Переместить" }));
    await waitFor(() => {
      expect(postSupportTicketQueueMock).toHaveBeenCalledWith("ticket-1", {
        queueId: 2,
        reason: "queue reason",
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "Ещё" }));
    fireEvent.click(screen.getByRole("button", { name: "Изменить приоритет" }));
    fireEvent.click(screen.getByRole("button", { name: /P2/ }));
    fireEvent.change(screen.getByPlaceholderText("Например: ручная корректировка по диагностике"), {
      target: { value: "priority reason" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Изменить" }));
    await waitFor(() => {
      expect(postSupportTicketPriorityMock).toHaveBeenCalledWith("ticket-1", {
        priority: "P2",
        reason: "priority reason",
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "Ещё" }));
    fireEvent.click(screen.getByRole("button", { name: "Назначить на себя" }));
    fireEvent.change(screen.getByPlaceholderText("Например: ручная корректировка по диагностике"), {
      target: { value: "assign reason" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Назначить" }));
    await waitFor(() => {
      expect(postSupportTicketAssignMock).toHaveBeenCalledWith("ticket-1", {
        assigneeId: "support-test",
        reason: "assign reason",
        comment: undefined,
      });
    });
  });

  it("loads filtered timeline tab through the typed timeline endpoint", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(workspacePayload());
    fetchSupportTicketTimelineMock.mockResolvedValue(timelinePayload());

    renderTicketListPage("/app/tickets/ticket-1");

    await waitFor(() => {
      expect(fetchSupportTicketWorkspaceMock).toHaveBeenCalledWith("ticket-1");
    });
    expect(await screen.findByText("Проверить OLA очередь")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Диагностика" }));

    await waitFor(() => {
      expect(fetchSupportTicketTimelineMock).toHaveBeenCalledWith("ticket-1", "diagnostics");
    });
    expect(await screen.findByText("Filtered DNS result")).toBeInTheDocument();
    expect(await screen.findByText("Upstream returned an invalid gateway response.")).toBeInTheDocument();
  });

  it("renders running operations and disabled tool/playbook reasons in the tools sidebar", async () => {
    const payload = workspacePayload();
    payload.detail.snapshot.latest_operations = [
      {
        operation_id: "op-running",
        kind: "tool",
        status: "running",
        display_status: null,
        display_label: null,
        scope: "ticket",
        tool_name: "dns.resolve",
        command_name: null,
        queued_at: "2026-05-03T09:19:00+05:00",
        started_at: "2026-05-03T09:19:01+05:00",
        finished_at: null,
        duration_ms: 1253,
        trace_id: "trace-running-1",
        retry_count: 0,
        max_retries: 3,
        retryable: false,
        can_retry: false,
        can_cancel: true,
        retry_url: null,
        cancel_url: "/api/operations/op-running/cancel",
        retry_disabled_reason: "status_not_retryable",
        cancel_disabled_reason: null,
        policy_labels: ["cancel:available"],
        error_code: null,
        error_category: null,
        details_url: "/api/operations/op-running",
        result_summary: null,
        error_message: null,
      },
      {
        operation_id: "op-failed",
        kind: "tool",
        status: "failed",
        display_status: null,
        display_label: "HTTP check",
        scope: "ticket",
        tool_name: "diagnose.website",
        command_name: null,
        queued_at: "2026-05-05T09:40:00+05:00",
        started_at: "2026-05-05T09:40:00+05:00",
        finished_at: "2026-05-05T09:41:00+05:00",
        duration_ms: 59000,
        trace_id: "trace-failed-1",
        retry_count: 1,
        max_retries: 3,
        retryable: true,
        can_retry: true,
        can_cancel: false,
        retry_url: "/api/operations/op-failed/retry",
        cancel_url: null,
        retry_disabled_reason: null,
        cancel_disabled_reason: "already_finished",
        policy_labels: ["cancel:already_finished", "retry:available"],
        error_code: "HTTP_502",
        error_category: "execution",
        details_url: "/api/operations/op-failed",
        result_summary: null,
        error_message: "HTTP 502",
      },
    ];
    payload.tools = {
      ticket_id: "ticket-1",
      device_id: "device-1",
      tools: [
        {
          tool_name: "dns.resolve",
          module_name: "network",
          description: "Проверка DNS",
          domain: "network",
          tool_kind: "diagnostic",
          risk_level: "low",
          requires_consent: false,
          install_required: true,
          required_permission: "module.tool.run.low_risk",
          allowed_roles: ["support", "admin"],
          policy_labels: [
            "permission:module.tool.run.low_risk",
            "roles:support,admin",
            "consent:not_required",
            "install:required",
          ],
          source: "agent",
          params_schema: [],
          presets: [],
        },
      ],
    };
    payload.playbooks = {
      ticket_id: "ticket-1",
      device_id: "device-1",
      playbooks: [
        ...Array.from({ length: 8 }, (_, index) => ({
          playbook_version_id: 100 + index,
          key: `extra.playbook.${index}`,
          name: index === 0 ? "Диагностика сайта" : `Extra playbook ${index}`,
          domain: "diagnostics",
          version: "1.0",
          status: "published",
          blocks_count: 1,
          required_tools: [],
          missing_tools: index === 0 ? ["http.check"] : [],
          missing_params: [],
          can_run: false,
          readiness_label: index === 0 ? "Нет инструментов" : "Недоступно",
          updated_at: null,
        })),
        {
          playbook_version_id: 1,
          key: "diagnose.website",
          name: "Диагностика сайта",
          domain: "network",
          version: "1.0",
          status: "published",
          blocks_count: 3,
          required_tools: ["dns.resolve", "http.check"],
          missing_tools: ["http.check"],
          missing_params: [],
          can_run: false,
          readiness_label: "Нет инструментов",
          updated_at: null,
        },
      ],
    };
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(payload);
    postSupportOperationCancelMock.mockResolvedValue({
      status: "ok",
      target_operation_id: "op-running",
      cancel_operation_id: "op-cancel-1",
    });
    postSupportOperationRetryMock.mockResolvedValue({
      status: "accepted",
      operation_id: "op-retry-1",
      retry_of_operation_id: "op-failed",
      ticket_id: "ticket-1",
      device_id: "device-1",
      tool_name: "diagnose.website",
      poll_url: "/api/operations/op-retry-1",
    });

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByText("Проверить OLA очередь")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Запустить диагностику" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Инструменты" }));

    expect(await screen.findByText("Операции выполняются")).toBeInTheDocument();
    expect(screen.getByText("Выполняется")).toBeInTheDocument();
    expect(screen.getByText("Длительность: 1 s")).toBeInTheDocument();
    expect(screen.getByText("Повторы: 0/3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "\u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c" }));
    await waitFor(() => {
      expect(postSupportOperationRetryMock).toHaveBeenCalledWith("op-failed", {
        reason: "operator_requested_from_support_workspace",
      });
    });
    expect(screen.getByText("Trace: trace-ru...")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Детали операции" })[0]).toHaveAttribute("href", "/api/operations/op-running");
    fireEvent.click(screen.getByRole("button", { name: "Отменить операцию" }));
    await waitFor(() => {
      expect(postSupportOperationCancelMock).toHaveBeenCalledWith("op-running", {
        reason: "operator_requested_from_support_workspace",
      });
    });
    expect(screen.getAllByText("dns.resolve").length).toBeGreaterThan(0);
    expect(screen.getByText("Право: module.tool.run.low_risk")).toBeInTheDocument();
    expect(screen.getByText("Роли: support, admin")).toBeInTheDocument();
    expect(screen.getByText("Диагностика сайта")).toBeInTheDocument();
    expect(screen.getAllByText("Нет tool: http.check").length).toBeGreaterThan(0);
    expect(screen.getByText("Агент устройства offline")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Запустить" })).toBeDisabled();
  });

  it("persists the support workspace theme toggle", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(workspacePayload());

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByText("Проверить OLA очередь")).toBeInTheDocument();
    expect(screen.getByTestId("support-workspace-root")).toHaveAttribute("data-theme", "dark");

    fireEvent.click(screen.getByRole("button", { name: "Светлая тема" }));

    expect(window.localStorage.getItem("support-workspace-theme")).toBe("light");
    expect(screen.getByTestId("support-workspace-root")).toHaveAttribute("data-theme", "light");
    expect(screen.getByRole("button", { name: "Тёмная тема" })).toBeInTheDocument();
  });

  it("renders SLA/OLA timer edge states and passport readiness clearly", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        sla_ola: {
          first_response: {
            due_at: "2026-05-03T09:30:00+05:00",
            remaining_seconds: -120,
            target_seconds: 900,
            status: "breached",
          },
          resolution: {
            due_at: "2026-05-03T13:30:00+05:00",
            remaining_seconds: 1800,
            target_seconds: 14400,
            status: "at_risk",
          },
          ola_ack: { due_at: null, remaining_seconds: null, target_seconds: null, status: "unknown" },
          ola_processing: {
            due_at: "2026-05-03T11:30:00+05:00",
            remaining_seconds: 2400,
            target_seconds: 7200,
            status: "paused",
          },
        },
        passport_readiness: {
          ticket_id: "ticket-1",
          status: "ready",
          done: 4,
          total: 4,
          items: [
            { key: "problem_identified", label: "Проблема идентифицирована", status: "done" },
            { key: "cause_found", label: "Причина установлена", status: "done" },
            { key: "solution_applied", label: "Решение применено", status: "done" },
            { key: "verified_and_closed", label: "Проверка и закрытие", status: "done" },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByText("Проверить OLA очередь")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "SLA" }));

    expect(await screen.findByText("Нарушен")).toBeInTheDocument();
    expect(screen.getByText("Риск")).toBeInTheDocument();
    expect(screen.getByText("Пауза")).toBeInTheDocument();
    expect(screen.getAllByText("Нет срока").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Паспорт" }));

    expect(await screen.findByText("Готов")).toBeInTheDocument();
    expect(screen.getByText("Готовность 4/4")).toBeInTheDocument();
  });

  it("renders central closure blockers with actionable passport guidance", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 2,
          total: 3,
          evidence_candidate_count: 1,
          recommended_next_action: "Добавить evidence",
          blockers: [
            {
              key: "priority_evidence",
              label: "Доказательство для P0",
              met: false,
              detail: "Нужно приложить evidence.",
              source: "closure_requirement",
              action_kind: "attach_evidence",
              action_label: "Добавить evidence",
              severity: "blocking",
              candidate_count: 1,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByTestId("closure-plan-panel")).toBeInTheDocument();
    expect(screen.getByText("Перед закрытием")).toBeInTheDocument();
    expect(screen.getByText("Доказательство для P0")).toBeInTheDocument();
    expect(screen.getByText("Добавить evidence")).toBeInTheDocument();
  });

  it("keeps central closure blockers readable in the light theme", async () => {
    window.localStorage.setItem("support-workspace-theme", "light");
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 1,
          total: 3,
          evidence_candidate_count: 0,
          recommended_next_action: "Добавить evidence",
          blockers: [
            {
              key: "priority_evidence",
              label: "Доказательство для P0",
              met: false,
              detail: "Для этого приоритета нужно приложить evidence.",
              source: "closure_requirement",
              action_kind: "attach_evidence",
              action_label: "Добавить evidence",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    const closurePanel = await screen.findByTestId("closure-plan-panel");
    expect(within(closurePanel).getByTestId("closure-plan-title")).toHaveClass("text-slate-950");
    expect(within(closurePanel).getByTestId("closure-plan-summary")).toHaveClass("text-amber-900");
    expect(within(closurePanel).getByTestId("closure-blocker-card")).toHaveClass("bg-white/80");
    expect(within(closurePanel).getByText("Для этого приоритета нужно приложить evidence.")).toHaveClass(
      "text-amber-900/80",
    );
  });

  it("opens passport focus guidance from a closure blocker action", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketPassportEvidenceCandidatesMock.mockResolvedValue({ ticket_id: "ticket-1", candidates: [] });
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 1,
          total: 4,
          evidence_candidate_count: 1,
          recommended_next_action: "Добавить evidence",
          blockers: [
            {
              key: "priority_evidence",
              label: "Доказательство для P0",
              met: false,
              detail: "Нужно приложить evidence.",
              source: "closure_requirement",
              action_kind: "attach_evidence",
              action_label: "Добавить evidence",
              severity: "blocking",
              candidate_count: 1,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    const closurePanel = await screen.findByTestId("closure-plan-panel");
    fireEvent.click(within(closurePanel).getByRole("button", { name: "Добавить evidence" }));

    const focusCard = await screen.findByTestId("closure-focus-card");
    expect(focusCard).toBeInTheDocument();
    expect(screen.getByText("Фокус паспорта")).toBeInTheDocument();
    expect(screen.getAllByText("Доказательство для P0").length).toBeGreaterThan(1);
    expect(within(focusCard).getAllByText("Нужно приложить evidence.").length).toBeGreaterThan(0);
  });

  it("links an evidence candidate from the workspace closure guidance", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketPassportEvidenceCandidatesMock.mockResolvedValue({
      ticket_id: "ticket-1",
      candidates: [
        {
          candidate_id: "operation:op-1",
          source_kind: "operation",
          source_id: "op-1",
          source_ref: "operation:op-1",
          source_quality: "high",
          evidence_type: "diagnostic_result",
          required_fact: "evidence",
          section_key: "evidence",
          title: "HTTP диагностика",
          summary: "HTTP 502 Bad Gateway",
          visibility: "internal",
          captured_at: "2026-05-03T09:00:00+05:00",
          existing_evidence_id: null,
        },
      ],
    });
    linkSupportTicketPassportEvidenceMock.mockResolvedValue({} as Awaited<ReturnType<typeof linkSupportTicketPassportEvidence>>);
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 1,
          total: 4,
          evidence_candidate_count: 1,
          recommended_next_action: "Добавить evidence",
          blockers: [
            {
              key: "priority_evidence",
              label: "Доказательство для P0",
              met: false,
              detail: "Нужно приложить evidence.",
              source: "closure_requirement",
              action_kind: "attach_evidence",
              action_label: "Добавить evidence",
              severity: "blocking",
              candidate_count: 1,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    const closurePanel = await screen.findByTestId("closure-plan-panel");
    fireEvent.click(within(closurePanel).getByRole("button", { name: "Добавить evidence" }));

    expect(await screen.findByText("Кандидаты evidence")).toBeInTheDocument();
    expect(await screen.findByText("HTTP диагностика")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Привязать evidence" }));

    await waitFor(() => {
      expect(linkSupportTicketPassportEvidenceMock).toHaveBeenCalledWith("ticket-1", {
        source_kind: "operation",
        source_id: "op-1",
        required_fact: "evidence",
        visibility: "internal",
      });
    });
  });

  it("posts a worklog entry from the workspace closure guidance", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    postSupportTicketWorklogMock.mockResolvedValue({
      worklog_id: 5,
      actor_id: "support-test",
      spent_minutes: 20,
      note: "Проверил DNS",
    });
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 1,
          total: 4,
          evidence_candidate_count: 0,
          recommended_next_action: "Добавить worklog",
          blockers: [
            {
              key: "worklog",
              label: "Worklog",
              met: false,
              detail: "Добавьте запись о выполненной работе.",
              source: "closure_requirement",
              action_kind: "add_worklog",
              action_label: "Добавить worklog",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    const closurePanel = await screen.findByTestId("closure-plan-panel");
    fireEvent.click(within(closurePanel).getByRole("button", { name: "Добавить worklog" }));

    expect(await screen.findByText("Новый worklog")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Минуты"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("Что сделано"), { target: { value: "Проверил DNS" } });
    fireEvent.click(screen.getByRole("button", { name: "Записать worklog" }));

    await waitFor(() => {
      expect(postSupportTicketWorklogMock).toHaveBeenCalledWith("ticket-1", {
        spentMinutes: 20,
        note: "Проверил DNS",
      });
    });
  });

  it("shows action-specific passport guidance for resolution blockers", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 1,
          total: 4,
          evidence_candidate_count: 0,
          recommended_next_action: "Заполнить решение",
          blockers: [
            {
              key: "resolution_code",
              label: "Код решения",
              met: false,
              detail: "Укажите код решения из списка.",
              source: "closure_requirement",
              action_kind: "edit_resolution",
              action_label: "Заполнить решение",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    const closurePanel = await screen.findByTestId("closure-plan-panel");
    fireEvent.click(within(closurePanel).getByRole("button", { name: "Заполнить решение" }));

    const focusCard = await screen.findByTestId("closure-focus-card");
    expect(within(focusCard).getByText("Секция: Решение")).toBeInTheDocument();
    expect(within(focusCard).getByText("Следующий шаг")).toBeInTheDocument();
    expect(within(focusCard).getByText("Заполните код решения и итог для заявителя перед переводом тикета в решение.")).toBeInTheDocument();
    expect(within(screen.getByTestId("closure-focused-passport-item")).getByText("Решение применено")).toBeInTheDocument();
  });

  it("shows evidence-specific focus guidance for attachment blockers", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 1,
          total: 4,
          evidence_candidate_count: 2,
          recommended_next_action: "Добавить evidence",
          blockers: [
            {
              key: "priority_evidence",
              label: "Доказательство для P0",
              met: false,
              detail: "Нужно приложить evidence.",
              source: "closure_requirement",
              action_kind: "attach_evidence",
              action_label: "Добавить evidence",
              severity: "blocking",
              candidate_count: 2,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    const closurePanel = await screen.findByTestId("closure-plan-panel");
    fireEvent.click(within(closurePanel).getByRole("button", { name: "Добавить evidence" }));

    const focusCard = await screen.findByTestId("closure-focus-card");
    expect(within(focusCard).getByText("Секция: Evidence")).toBeInTheDocument();
    expect(within(focusCard).getByText("Целевое действие")).toBeInTheDocument();
    expect(within(focusCard).getByText("Приложить evidence")).toBeInTheDocument();
    expect(within(focusCard).getByText("Evidence candidates: 2")).toBeInTheDocument();
    expect(within(screen.getByTestId("closure-focused-passport-item")).getByText("Проверка и закрытие")).toBeInTheDocument();
  });

  it("shows worklog-specific focus guidance for worklog blockers", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 1,
          total: 4,
          evidence_candidate_count: 0,
          recommended_next_action: "Добавить worklog",
          blockers: [
            {
              key: "worklog",
              label: "Worklog",
              met: false,
              detail: "Добавьте запись о выполненной работе.",
              source: "closure_requirement",
              action_kind: "add_worklog",
              action_label: "Добавить worklog",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    const closurePanel = await screen.findByTestId("closure-plan-panel");
    fireEvent.click(within(closurePanel).getByRole("button", { name: "Добавить worklog" }));

    const focusCard = await screen.findByTestId("closure-focus-card");
    expect(within(focusCard).getByText("Секция: Worklog")).toBeInTheDocument();
    expect(within(focusCard).getByText("Целевое действие")).toBeInTheDocument();
    expect(within(focusCard).getByText("Зафиксировать worklog")).toBeInTheDocument();
    expect(within(screen.getByTestId("closure-focused-passport-item")).getByText("Проверка и закрытие")).toBeInTheDocument();
  });

  it("keeps evidence and worklog blockers discoverable when closure blockers overflow", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        closure_plan: {
          ticket_id: "ticket-1",
          ready_for_resolution: false,
          missing_count: 6,
          total: 7,
          evidence_candidate_count: 2,
          recommended_next_action: "Добавить evidence",
          blockers: [
            {
              key: "resolution_code",
              label: "Код решения",
              met: false,
              detail: "Укажите код решения из списка.",
              source: "closure_requirement",
              action_kind: "edit_resolution",
              action_label: "Заполнить решение",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
            {
              key: "public_summary",
              label: "Публичный итог для заявителя",
              met: false,
              detail: "Заполните итог, который увидит заявитель.",
              source: "closure_requirement",
              action_kind: "edit_resolution",
              action_label: "Заполнить решение",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
            {
              key: "internal_summary",
              label: "Внутренний итог решения",
              met: false,
              detail: "Заполните внутреннее описание причины и действий.",
              source: "closure_requirement",
              action_kind: "edit_resolution",
              action_label: "Заполнить решение",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
            {
              key: "official_passport",
              label: "Официальный паспорт решения",
              met: false,
              detail: "Откройте паспорт и проверьте обязательные поля.",
              source: "closure_requirement",
              action_kind: "open_passport",
              action_label: "Открыть паспорт",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
            {
              key: "priority_evidence",
              label: "Доказательство для P0",
              met: false,
              detail: "Для этого приоритета нужно приложить evidence.",
              source: "closure_requirement",
              action_kind: "attach_evidence",
              action_label: "Добавить evidence",
              severity: "blocking",
              candidate_count: 2,
              fact_key: null,
              blocking_for_closure: true,
            },
            {
              key: "worklog",
              label: "Worklog",
              met: false,
              detail: "Добавьте запись о выполненной работе.",
              source: "closure_requirement",
              action_kind: "add_worklog",
              action_label: "Добавить worklog",
              severity: "blocking",
              candidate_count: 0,
              fact_key: null,
              blocking_for_closure: true,
            },
          ],
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    const closurePanel = await screen.findByTestId("closure-plan-panel");
    expect(within(closurePanel).getByRole("button", { name: "Добавить evidence" })).toBeInTheDocument();
    expect(within(closurePanel).getByRole("button", { name: "Добавить worklog" })).toBeInTheDocument();
    expect(within(closurePanel).getByRole("button", { name: "Показать ещё 2" })).toBeInTheDocument();

    fireEvent.click(within(closurePanel).getByRole("button", { name: "Показать ещё 2" }));

    expect(within(closurePanel).getByText("Официальный паспорт решения")).toBeInTheDocument();
    expect(within(closurePanel).getByRole("button", { name: "Скрыть" })).toBeInTheDocument();

    fireEvent.click(within(closurePanel).getByRole("button", { name: "Добавить evidence" }));

    const focusCard = await screen.findByTestId("closure-focus-card");
    expect(within(focusCard).getByText("Секция: Evidence")).toBeInTheDocument();
    expect(within(focusCard).getByText("Приложить evidence")).toBeInTheDocument();
  });

  it("renders requester contact enrichment in the context sidebar", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(workspacePayload());

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByText("Александр Смирнов")).toBeInTheDocument();
    expect(screen.getByText("+7 (495) 123-45-67")).toBeInTheDocument();
    expect(screen.getByText("a.smirnov@example.test")).toBeInTheDocument();
    expect(screen.getByText("БЦ, 3 этаж, каб. 305")).toBeInTheDocument();
    expect(screen.getByText("Профиль: ручной ввод")).toBeInTheDocument();
    expect(screen.getByText("ПК")).toBeInTheDocument();
    expect(screen.getByText("asset-1")).toBeInTheDocument();
    expect(screen.getByText("Корпоративный сайт")).toBeInTheDocument();
    expect(screen.getByText("Web L2")).toBeInTheDocument();
    expect(screen.getByText("Источник услуги: реестр")).toBeInTheDocument();
    expect(screen.getByText("Похожие тикеты")).toBeInTheDocument();
  });

  it("renders knowledge suggestions from the aggregate workspace payload", async () => {
    fetchSupportQueueMock.mockResolvedValue(queuePayload());
    fetchSupportTicketWorkspaceMock.mockResolvedValue(
      workspacePayload({
        knowledge: {
          ticket_id: "ticket-1",
          similar_tickets: [
            {
              id: "ticket-1011",
              number: "T-001011",
              subject: "Ошибка 502 на портале",
              resolution_summary: "Перезапуск upstream устранил ошибку.",
            },
          ],
          articles: [{ id: "KB-502", title: "Ошибка 502 Bad Gateway", url: "/app/knowledge/KB-502" }],
          ai_summary: {
            text: "AI-рекомендация / Бета: проверьте связанные источники перед применением.",
            sources: ["KB-502", "T-001011"],
            confidence: "high",
            source_count: 2,
          },
          diagnostics: {
            provider: "support_knowledge_provider",
            provider_version: "local-v1",
            source_counts: { manual_kb: 1, catalog: 0, similar_ticket: 1 },
            query_signals: ["manual_link", "linked_ticket"],
            article_matches: {
              "KB-502": { source_type: "manual_kb", score: 100, match_reasons: ["manual_link"] },
            },
            similar_ticket_matches: {
              "ticket-1011": { source_type: "similar_ticket", score: 90, match_reasons: ["linked_ticket"] },
            },
          },
        },
      }),
    );

    renderTicketListPage("/app/tickets/ticket-1");

    await waitFor(() => {
      expect(fetchSupportTicketWorkspaceMock).toHaveBeenCalledWith("ticket-1");
    });
    fireEvent.click(screen.getByRole("button", { name: "Знания" }));

    expect(await screen.findByText("Ошибка 502 Bad Gateway")).toBeInTheDocument();
    expect(screen.getByText("Ошибка 502 на портале")).toBeInTheDocument();
    expect(screen.getAllByText(/AI-рекомендация \/ Бета/).length).toBeGreaterThan(0);
    expect(screen.getByText("Источник: support_knowledge_provider")).toBeInTheDocument();
    expect(screen.getByText("Доверие: high")).toBeInTheDocument();
    expect(screen.getByText("manual_link")).toBeInTheDocument();
    expect(screen.queryByText(/Knowledge suggestions/)).not.toBeInTheDocument();
  });
});
