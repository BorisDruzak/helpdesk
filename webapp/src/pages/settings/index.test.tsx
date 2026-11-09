import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ServiceSettingsPage as SettingsPage } from "./service-settings-page";
import type { WebSettingsPayload } from "../../features/settings/api";

import {createSettingsPayload, jsonResponse} from "./settings-test-fixtures";

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
    fireEvent.change(screen.getByLabelText("Действие согласования"), {
      target: { value: "create_request" },
    });
    fireEvent.change(screen.getByLabelText("Поля журнала"), {
      target: { value: "resolution_code, custom_fields.routing_decision.queue" },
    });
    fireEvent.change(screen.getByLabelText("Событие запуска"), {
      target: { value: "requester_replied" },
    });
    fireEvent.click(screen.getByLabelText("Автоматический переход"));
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
      log_fields: ["resolution_code", "custom_fields.routing_decision.queue"],
      trigger: "requester_replied",
      auto: true,
      actions: {
        notify: ["assignee", "queue_lead"],
        sla: "pause",
        approval: "create_request",
      },
    });
  });
});
