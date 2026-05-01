import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "./index";
import type { WebSettingsPayload } from "../../features/settings/api";

function jsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    headers: {
      "content-type": "application/json",
    },
  });
}

function createSettingsPayload(): WebSettingsPayload {
  return {
    capabilities: {
      can_write: true,
      actor_role: "admin",
    },
    overview: {
      queues_count: 1,
      active_queues_count: 1,
      routing_rules_count: 1,
      active_routing_rules_count: 1,
      sla_policies_count: 1,
      calendars_count: 1,
      resolution_codes_count: 1,
      audit_records_count: 0,
    },
    routing_builder: {
      operators: [{ value: "eq", label: "равно" }],
      fields: [{ field: "request_kind", label: "Тип обращения", source: "ticket", form_key: null, form_title: null, field_type: "text" }],
      forms: [],
    },
    ticket_settings: {
      internal_statuses: [
        {
          value: "new",
          label: "Новая",
          requester_status: "accepted",
          requester_label: "Заявка принята",
          next_action_owner: "support",
          stage: "intake",
          waits: false,
          terminal: false,
        },
        {
          value: "waiting_on_user",
          label: "Ожидает пользователя",
          requester_status: "needs_requester",
          requester_label: "Нужен ваш ответ",
          next_action_owner: "requester",
          stage: "waiting",
          waits: true,
          terminal: false,
        },
        {
          value: "resolved",
          label: "Решена",
          requester_status: "review_solution",
          requester_label: "Проверьте решение",
          next_action_owner: "requester",
          stage: "review",
          waits: false,
          terminal: true,
        },
      ],
      requester_statuses: [
        { value: "accepted", label: "Заявка принята", internal_statuses: ["new"] },
        { value: "needs_requester", label: "Нужен ваш ответ", internal_statuses: ["waiting_on_user"] },
        { value: "review_solution", label: "Проверьте решение", internal_statuses: ["resolved"] },
      ],
      next_action_owners: [
        { value: "support", label: "Поддержка", internal_statuses: ["new"] },
        { value: "requester", label: "Пользователь", internal_statuses: ["waiting_on_user", "resolved"] },
      ],
      workflow_profiles: [
        {
          ticket_type: "incident",
          label: "Инцидент",
          purpose: "restore_service",
          suggested_path: ["new", "queued", "in_progress", "resolved", "closed"],
          allowed_statuses: ["new", "queued", "in_progress", "resolved", "closed"],
          required_create_fields: [],
          required_resolve_fields: ["resolution_code"],
          requires_approval: false,
          requires_change_plan: false,
          requires_action_log: false,
          evidence_required_for_priorities: ["P0", "P1"],
          transitions: {
            new: ["queued"],
            queued: ["in_progress"],
            in_progress: ["resolved"],
            resolved: ["closed"],
            closed: [],
          },
        },
      ],
      ticket_types: [],
      request_templates: [
        {
          id: "breakage",
          public_title: "Поломка",
          internal_name: "incident / breakage",
          active: true,
          version: "1.0.0",
          classification: { ticket_type: "incident", request_kind: "breakage" },
          form: { form_schema_id: "breakage_form", fields_count: 6, required_fields_count: 2 },
          workflow: { workflow_profile_id: "incident" },
          priority: { policy_id: "inline:breakage:priority_policy" },
          routing: { policy_id: null },
          sla: { policy_id: null },
          ola: { policy_id: null },
          approvals: { policy_id: null },
          diagnostics: { suggested_playbook_id: null },
          closure: { policy_id: null },
          visibility: { policy_id: null },
          notifications: { policy_id: null },
          field_roles: {},
          policies_missing: ["routing_policy", "sla_policy", "closure_policy"],
        },
      ],
      process_schema: [
        {
          key: "request_template",
          label: "Шаблон обращения",
          meaning: "Каталог обращений собирает факты и порождает процессный контекст",
          source: "request_forms",
          ui_surface: "/app/admin/forms",
          status: "active",
        },
        {
          key: "ticket_type_workflow_profile",
          label: "Тип процесса и маршрут",
          meaning: "Тип заявки выбирает профиль workflow",
          source: "workflow_profiles",
          ui_surface: "/app/settings",
          status: "active",
        },
        {
          key: "priority",
          label: "Приоритет",
          meaning: "Приоритет рассчитывается из impact, urgency и importance",
          source: "priority_policy",
          ui_surface: "/app/settings",
          status: "active",
        },
        {
          key: "routing",
          label: "Маршрутизация",
          meaning: "Роутинг выбирает очередь",
          source: "routing_rules",
          ui_surface: "/app/settings",
          status: "active",
        },
        {
          key: "sla",
          label: "Сроки ответа и решения",
          meaning: "Показывает, за какое время пользователю должны ответить и решить обращение",
          source: "sla_policies",
          ui_surface: "/app/settings",
          status: "active",
        },
      ],
      support_lines: [
        { code: "L1", label: "L1", competence_depth: "Первичная диагностика", routing_role: "triage", status: "planned" },
        { code: "L2", label: "L2", competence_depth: "Профильная диагностика", routing_role: "specialist", status: "planned" },
        { code: "L3", label: "L3", competence_depth: "Глубокая экспертиза", routing_role: "engineering", status: "planned" },
      ],
      priority_model: {
        direct_user_priority_choice: false,
        impact_levels: ["minimal", "low", "medium", "high"],
        urgency_levels: ["minimal", "low", "medium", "high"],
        importance_sources: ["service_criticality", "deadline", "security", "public_service"],
        modifiers: ["critical_service", "deadline_today", "security"],
      },
      governance: {
        fsm_mode: "soft",
        legacy_role_fields: true,
        auto_close_hours: 72,
        resolution_validation_mode: "warn",
        require_root_cause_priorities: ["P1", "P2"],
        evidence_gate_enabled: true,
        passport_enabled: true,
        requester_confirmation_required: true,
      },
      operational_flags: {
        admin_config_api_enabled: true,
        admin_config_write_enabled: false,
        auditor_role_enabled: false,
        sla_calendar_enabled: true,
        ola_enabled: true,
        retention_enabled: false,
        retention_dry_run: true,
        events_hot_retention_days: 180,
        admin_audit_hot_retention_days: 365,
        take_queue_mode: "common",
        take_queue_common_code: "servicedesk_l1",
        take_queue_test_code: "servicedesk_test",
      },
    },
    queues: [
      {
        id: 1,
        code: "servicedesk_l1",
        name: "ServiceDesk L1",
        is_triage: true,
        is_active: true,
        auto_assign_enabled: true,
        open_tickets_count: 2,
        enabled_routing_rules_count: 1,
        members: [],
        ola_targets: [],
      },
    ],
    routing_rules: [],
    sla_policies: [],
    calendars: [],
    resolution_codes: [],
    audit: [],
  };
}

function renderSettingsPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SettingsPage", () => {
  it("renders ticket lifecycle settings tab from typed payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/settings") {
          return jsonResponse({
            status: "success",
            data: createSettingsPayload(),
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderSettingsPage();

    fireEvent.click(await screen.findByRole("button", { name: "Тикеты" }));

    expect(screen.getByText("Жизненный цикл тикета")).toBeInTheDocument();
    expect(screen.getByText("Канонические внутренние статусы, пользовательское отображение и ответственный за следующий шаг.")).toBeInTheDocument();
    expect(screen.getByText("Ожидает пользователя")).toBeInTheDocument();
    expect(screen.getAllByText("Нужен ваш ответ").length).toBeGreaterThan(0);
    expect(screen.getByText("Паспорт решения")).toBeInTheDocument();
    expect(screen.getByText("Evidence gate: Включено")).toBeInTheDocument();
    expect(screen.getByText("Правила закрытия")).toBeInTheDocument();
    expect(screen.getByText("Take-self queue mode")).toBeInTheDocument();
    expect(screen.getByText("Схема service desk")).toBeInTheDocument();
    expect(screen.getByText("Шаблон обращения → форма → процесс → приоритет → сроки → очередь → паспорт")).toBeInTheDocument();
    expect(screen.getByText("Тип заявки выбирает профиль workflow")).toBeInTheDocument();
    expect(screen.getByText("Роутинг выбирает очередь")).toBeInTheDocument();
    expect(screen.getByText("Показывает, за какое время пользователю должны ответить и решить обращение")).toBeInTheDocument();
    expect(screen.getByText("Модель приоритета")).toBeInTheDocument();
    expect(screen.getByText("Пользователь не выбирает P0/P1/P2/P3 напрямую")).toBeInTheDocument();
    expect(screen.getByText("Линии поддержки")).toBeInTheDocument();
    expect(screen.getByText("Первичная диагностика")).toBeInTheDocument();
  });

  it("uses bounded settings editors instead of raw JSON textareas", async () => {
    const payload = createSettingsPayload();
    payload.routing_rules = [
      {
        id: 10,
        enabled: true,
        priority_order: 10,
        target_queue_id: 1,
        target_queue_name: "ServiceDesk L1",
        condition_json: { field: "request_kind", op: "eq", value: "access" },
      },
    ];
    payload.sla_policies = [
      {
        id: 20,
        name: "Стандартная",
        timezone: "Asia/Yekaterinburg",
        calendar_id: 30,
        calendar_name: "Будни",
        is_default: true,
        is_active: true,
        open_tickets_count: 0,
        business_hours_json: { mode: "calendar" },
        targets: [],
        priority_matrix: [],
      },
    ];
    payload.calendars = [
      {
        id: 30,
        code: "weekday_ru",
        name: "Будни",
        timezone: "Asia/Yekaterinburg",
        is_active: true,
        weekly_hours_json: { mon: [["09:00", "18:00"]] },
        holidays_json: { dates: ["2026-01-01"] },
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/settings") {
          return jsonResponse({
            status: "success",
            data: payload,
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    const { container } = renderSettingsPage();

    fireEvent.click(await screen.findByRole("button", { name: "Маршрутизация" }));
    expect(screen.getByText("Собранное условие")).toBeInTheDocument();
    expect(screen.queryByText("Condition JSON")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Сроки" }));
    expect(screen.getByLabelText("Режим рабочих часов")).toBeInTheDocument();
    expect(screen.queryByText("Business hours JSON")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Календари" }));
    expect(screen.getByText("Рабочая неделя")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Добавить дату" })).toBeInTheDocument();
    expect(screen.getByLabelText("Дата праздника или исключения")).toHaveValue("2026-01-01");
    expect(screen.getByText("Собирается для API")).toBeInTheDocument();
    expect(container.querySelector("textarea")).not.toBeInTheDocument();
    expect(screen.queryByText("Weekly hours JSON")).not.toBeInTheDocument();
    expect(screen.queryByText("Holidays JSON")).not.toBeInTheDocument();
  });

  it("shows split permission reasons for read-only queue and routing actions", async () => {
    const payload = createSettingsPayload();
    Object.assign(payload.capabilities as Record<string, unknown>, {
      can_write: true,
      can_manage_queues: false,
      can_manage_routing: false,
      manage_queues_denial_reason: "Недостаточно прав: settings.manage_queues",
      manage_routing_denial_reason: "Недостаточно прав: settings.manage_routing",
    });
    payload.routing_rules = [
      {
        id: 10,
        enabled: true,
        priority_order: 10,
        target_queue_id: 1,
        target_queue_name: "ServiceDesk L1",
        condition_json: { field: "request_kind", op: "eq", value: "access" },
      },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/settings") {
          return jsonResponse({
            status: "success",
            data: payload,
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderSettingsPage();

    fireEvent.click(await screen.findByRole("button", { name: "Очереди" }));
    expect(screen.getByText("Недостаточно прав: settings.manage_queues")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сохранить очередь" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Добавить / обновить участника" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Сохранить внутренние сроки" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Маршрутизация" }));
    expect(screen.getByText("Недостаточно прав: settings.manage_routing")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сохранить правило" })).toBeDisabled();
  });

  it("builds workflow transition guards and actions without hand-editing JSON", async () => {
    const payload = createSettingsPayload();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/settings" && (!init?.method || init.method === "GET")) {
        return jsonResponse({
          status: "success",
          data: payload,
        });
      }
      if (url === "/api/web/settings/workflow_profiles" && init?.method === "PUT") {
        return jsonResponse({
          status: "success",
          data: { workflow_profiles: payload.ticket_settings.workflow_profiles },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSettingsPage();

    fireEvent.click(await screen.findByRole("button", { name: "Тикеты" }));
    fireEvent.change(screen.getByLabelText("Откуда"), { target: { value: "in_progress" } });
    fireEvent.change(screen.getByLabelText("Куда"), { target: { value: "resolved" } });
    fireEvent.change(screen.getByLabelText("Роли, которые могут перевести"), {
      target: { value: "assignee, queue_lead" },
    });
    fireEvent.change(screen.getByLabelText("Поля, обязательные перед переходом"), {
      target: { value: "resolution_code" },
    });
    fireEvent.change(screen.getByLabelText("Какой комментарий нужен"), {
      target: { value: "public" },
    });
    fireEvent.click(screen.getByLabelText("Нужно согласование"));
    fireEvent.click(screen.getByLabelText("Нужно доказательство"));
    fireEvent.change(screen.getByLabelText("Кого уведомить"), {
      target: { value: "assignee, queue_lead" },
    });
    fireEvent.change(screen.getByLabelText("Что сделать со сроками ответа"), {
      target: { value: "pause" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Применить правило перехода" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить профили процесса" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/settings/workflow_profiles",
        expect.objectContaining({ method: "PUT" }),
      );
    });
    const putCall = fetchMock.mock.calls.find(([input, init]) => String(input) === "/api/web/settings/workflow_profiles" && init?.method === "PUT");
    const body = JSON.parse(String(putCall?.[1]?.body ?? "{}"));
    expect(body.workflow_profiles[0].transitions.in_progress[0]).toEqual({
      to: "resolved",
      allowed_roles: ["assignee", "queue_lead"],
      required_fields: ["resolution_code"],
      required_comment: "public",
      require_approval: true,
      require_evidence: true,
      actions: {
        notify: ["assignee", "queue_lead"],
        sla: "pause",
      },
    });
  });
});
