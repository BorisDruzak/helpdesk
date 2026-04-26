import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "./index";

function jsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    headers: {
      "content-type": "application/json",
    },
  });
}

function createSettingsPayload() {
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

  render(
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
  });
});
