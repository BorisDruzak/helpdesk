import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  fetchSupportQueue,
  fetchSupportTicketTimeline,
  fetchSupportTicketWorkspace,
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
    fetchSupportTicketTimeline: vi.fn(),
    fetchSupportTicketWorkspace: vi.fn(),
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
const fetchSupportTicketTimelineMock = vi.mocked(fetchSupportTicketTimeline);
const fetchSupportTicketWorkspaceMock = vi.mocked(fetchSupportTicketWorkspace);
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
        finished_at: null,
        result_summary: null,
        error_message: null,
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

    renderTicketListPage("/app/tickets/ticket-1");

    expect(await screen.findByText("Проверить OLA очередь")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Запустить диагностику" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Инструменты" }));

    expect(await screen.findByText("Операции выполняются")).toBeInTheDocument();
    expect(screen.getByText("Выполняется")).toBeInTheDocument();
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
    expect(screen.queryByText(/Knowledge suggestions/)).not.toBeInTheDocument();
  });
});
