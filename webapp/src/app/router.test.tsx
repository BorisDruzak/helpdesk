import { fireEvent, render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "../features/auth/session-provider";
import { QueryProvider } from "./providers/query-provider";
import { appRoutes } from "./router";

const realtimeClientMock = {
  subscribeTicket: vi.fn(() => () => {}),
  subscribeDevice: vi.fn(() => () => {}),
  dispose: vi.fn(),
};

vi.mock("../shared/realtime/client", () => ({
  getSharedWebRealtimeClient: () => realtimeClientMock,
}));


function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}


function renderApp(initialEntries: string[], fetchMock: typeof fetch) {
  vi.stubGlobal("fetch", fetchMock);

  const router = createMemoryRouter(appRoutes, {
    initialEntries
  });

  render(
    <QueryProvider>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryProvider>
  );

  return { router };
}


function createSupportSession() {
  return {
    user_login: "support1",
    actor_role: "support",
    auth_type: "ui_token",
    default_workspace: "support",
    available_workspaces: ["support"]
  };
}


function createAdminSession() {
  return {
    user_login: "admin1",
    actor_role: "admin",
    auth_type: "ui_token",
    default_workspace: "admin",
    available_workspaces: ["admin", "support"]
  };
}


function createSupportBootstrap() {
  return {
    workspace: "support",
    features: [
      "queue_overview",
      "ticket_workspace",
      "observer_trace",
      "tool_actions"
    ],
    observer: {
      ticket_summary_endpoint: "/api/tickets/{ticket_id}/observer",
      drawer_tab: "trace"
    }
  };
}


function createSupportQueue() {
  return {
    scope: "all",
    query: "",
    status_filter: "all",
    summary: {
      visible_count: 1,
      selected_ticket_id: "ticket-1"
    },
    filters: {
      scope_options: [
        { value: "all", label: "Все доступные" },
        { value: "mine", label: "Только мои" }
      ],
      status_options: [
        { value: "all", label: "Все статусы" },
        { value: "new", label: "Новые" }
      ]
    },
    tickets: [
      {
        ticket_id: "ticket-1",
        ticket_code: "T-100001",
        title: "Сбой синхронизации",
        status: "new",
        status_label: "Новая",
        queue_code: "servicedesk_l1",
        assignee_id: null,
        requester_display_name: "Алексей",
        device_id: "device-1",
        updated_at: "2026-04-20T08:10:00+05:00",
        created_at: "2026-04-20T07:55:00+05:00",
        requires_operator_action: true,
        unread_user_messages: 2
      }
    ]
  };
}


function createSupportDetail() {
  return {
    ticket: {
      ticket_id: "ticket-1",
      ticket_code: "T-100001",
      title: "Сбой синхронизации",
      description: "Нужно переподключить агент и проверить канал.",
      status: "new",
      status_label: "Новая",
      requester_display_name: "Алексей",
      device_id: "device-1",
      queue: {
        id: 11,
        code: "servicedesk_l1",
        name: "ServiceDesk L1"
      },
      assignee_id: null,
      updated_at: "2026-04-20T08:10:00+05:00",
      created_at: "2026-04-20T07:55:00+05:00",
      queue_members: []
    },
    observer: {
      ticket_summary_endpoint: "/api/tickets/ticket-1/observer",
      summary: {
        ticket_id: "ticket-1",
        root_trace_id: "trace-ticket-1",
        trace_count: 3,
        active_trace_count: 1,
        error_trace_count: 1,
        signature_count: 1,
        latest_trace_at: "2026-04-20T08:09:00+05:00"
      }
    },
    timeline: [
      {
        event_id: 1,
        event_type: "chat_message",
        ts: "2026-04-20T08:00:00+05:00",
        from_role: "support",
        sender_display_name: "Оператор",
        text: "Проверяем подключение.",
        visibility: "public",
        message_id: "msg-1"
      }
    ],
    snapshot: {
      presence: {
        agent_online: true,
        requester_online: false,
        support_online: true
      },
      device: {
        device_id: "device-1",
        hostname: "WS-01",
        os: "Windows 11",
        agent_version: "2.4.0",
        last_seen_at: "2026-04-20T08:05:00+05:00"
      },
      latest_operations: [],
      notification_unread: 0
    },
    actions: {
      status_options: [
        {
          value: "in_progress",
          label: "Взять в работу"
        }
      ]
    }
  };
}


function createSupportTools() {
  return {
    ticket_id: "ticket-1",
    device_id: "device-1",
    tools: [
      {
        tool_name: "network_ping",
        title: "Проверка сети",
        description: "Быстрая проверка доступности узла.",
        presets: [],
        params_schema: [
          {
            name: "host",
            label: "Хост",
            type: "string",
            required: true,
            default: "8.8.8.8",
            description: "Имя узла или IP-адрес"
          }
        ]
      }
    ]
  };
}


function createAdminBootstrap() {
  return {
    workspace: "admin",
    features: [
      "devices_inventory",
      "agent_rollout",
      "modules_workbench",
      "forms_builder",
      "tech_panel"
    ],
    observer: {
      quick_endpoint: "/api/web/admin/observer/quick",
      traces_endpoint: "/api/web/admin/observer/traces"
    }
  };
}


function createAdminDevices() {
  return {
    query: "",
    status_filter: "all",
    summary: {
      visible_count: 1,
      online_count: 1,
      rollout_targets: 1
    },
    filters: {
      status_options: [
        { value: "all", label: "Все устройства" },
        { value: "online", label: "Только онлайн" },
        { value: "offline", label: "Только офлайн" }
      ]
    },
    rollout: [
      {
        target: "windows_amd64",
        channel: "stable",
        version: "2.4.1",
        updated_at: "2026-04-20T11:20:00+05:00",
        updated_by: "admin1"
      }
    ],
    devices: [
      {
        device_id: "device-1",
        hostname: "WS-01",
        os: "Windows 11",
        agent_version: "2.4.0",
        target: "windows_amd64",
        online: true,
        last_seen_at: "2026-04-20T11:25:00+05:00",
        connection_status_label: "Онлайн",
        latest_update: {
          status: "healthy",
          label: "Готово к действиям",
          summary: "Устройство уже видно в typed inventory."
        }
      }
    ]
  };
}


function createAdminObserverQuick() {
  return {
    summary: {
      lookback_hours: 24,
      recent_trace_count: 3,
      hot_trace_count: 1,
      signature_count: 1,
      degradation_group_count: 1,
      dangerous_flow_count: 1
    },
    runtime: {
      enabled: true,
      running: true,
      health_status: "ok",
      health_status_label: "Норма",
      pending_trace_count: 0,
      last_projected_at: "2026-04-20T11:20:00+05:00",
      issues: []
    },
    hot_traces: [],
    top_signatures: [],
    top_degradations: [],
    dangerous_flows: [],
    links: {
      quick_endpoint: "/api/web/admin/observer/quick",
      traces_endpoint: "/api/web/admin/observer/traces",
      runtime_endpoint: "/api/admin/tech/traces/runtime"
    }
  };
}


function createAdminDeviceUpdates() {
  return {
    device_id: "device-1",
    device_label: "WS-01",
    online: true,
    target: "windows_amd64",
    current_version: "2.4.0",
    release_channel: "stable",
    is_release: true,
    summary: {
      status: "update_available",
      label: "Доступно обновление",
      summary: "Серверный rollout рекомендует stable/2.4.1."
    },
    recommendation: {
      update_available: true,
      recommendation_source: "assigned_rollout",
      recommendation_source_label: "Серверный rollout",
      comparison: "newer_release_available",
      comparison_label: "Назначена более новая release-версия",
      recommended_reason: "assigned_rollout_newer",
      recommended_reason_label: "Назначенный rollout новее текущей версии.",
      recommended_build: {
        target: "windows_amd64",
        channel: "stable",
        version: "2.4.1"
      },
      assigned_rollout: {
        target: "windows_amd64",
        channel: "stable",
        version: "2.4.1",
        updated_at: "2026-04-20T11:20:00+05:00",
        updated_by: "admin1"
      }
    },
    action: {
      enabled: true,
      label: "Запустить обновление",
      reason_required: true,
      endpoint: "/api/web/admin/devices/device-1/updates/run"
    }
  };
}


function createAdminModules() {
  return {
    query: "",
    summary: {
      family_count: 1,
      version_count: 1,
      registry_health_label: "Норма"
    },
    rollout_settings: {
      mode: "preferred_only",
      label: "Только preferred"
    },
    families: [
      {
        module_name: "network_ping",
        title: "network_ping",
        preferred_version: "1.2.0",
        versions: [
          {
            version: "1.2.0",
            channel: "stable",
            is_preferred: true,
            published_at: "2026-04-20T11:00:00+05:00",
            summary: "Typed registry entry"
          }
        ]
      }
    ]
  };
}


function createAdminForms() {
  return {
    summary: {
      pack_key: "request_forms",
      version: "7",
      title: "Каталог форм",
      description: "Актуальный набор форм заявок",
      forms_count: 1,
      fields_count: 1,
      required_fields_count: 1,
      last_published_at: "2026-04-20T11:30:00+05:00",
      last_published_by: "admin1"
    },
    capabilities: {
      current_endpoint: "/api/web/admin/forms/current",
      save_endpoint: "/api/web/admin/forms/save",
      field_type_options: [
        { value: "text", label: "Текст" },
        { value: "textarea", label: "Большой текст" },
        { value: "select", label: "Список" },
        { value: "radio", label: "Переключатели" },
        { value: "checkbox", label: "Флажок" }
      ]
    },
    forms: [
      {
        key: "printer",
        request_kind: "printer",
        title: "Принтер",
        description: "Проблемы с печатью",
        fields: [
          {
            key: "cabinet",
            label: "Кабинет",
            type: "text",
            type_label: "Текст",
            required: true,
            placeholder: "101",
            help_text: "Укажите кабинет",
            options: [],
            visible_when: null
          }
        ]
      }
    ]
  };
}


function createSupportFetchMock(session = createSupportSession()) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/api/web/session/me")) {
      return jsonResponse({
        status: "success",
        data: session
      });
    }

    if (url.endsWith("/api/web/support/bootstrap")) {
      return jsonResponse({
        status: "success",
        data: createSupportBootstrap()
      });
    }

    if (url.includes("/api/web/support/queue")) {
      return jsonResponse({
        status: "success",
        data: createSupportQueue()
      });
    }

    if (url.endsWith("/api/web/support/tickets/ticket-1")) {
      return jsonResponse({
        status: "success",
        data: createSupportDetail()
      });
    }

    if (url.endsWith("/api/web/support/tickets/ticket-1/tools")) {
      return jsonResponse({
        status: "success",
        data: createSupportTools()
      });
    }

    throw new Error(`Unexpected fetch: ${url}`);
  });
}


function createAdminFetchMock() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/api/web/session/me")) {
      return jsonResponse({
        status: "success",
        data: createAdminSession()
      });
    }

    if (url.endsWith("/api/web/admin/bootstrap")) {
      return jsonResponse({
        status: "success",
        data: createAdminBootstrap()
      });
    }

    if (url === "/api/web/admin/devices") {
      return jsonResponse({
        status: "success",
        data: createAdminDevices()
      });
    }

    if (url === "/api/web/admin/observer/quick?lookback_hours=24") {
      return jsonResponse({
        status: "success",
        data: createAdminObserverQuick()
      });
    }

    if (url === "/api/web/admin/devices/device-1/updates") {
      return jsonResponse({
        status: "success",
        data: createAdminDeviceUpdates()
      });
    }

    if (url === "/api/web/admin/modules") {
      return jsonResponse({
        status: "success",
        data: createAdminModules()
      });
    }

    if (url === "/api/web/admin/forms/current") {
      return jsonResponse({
        status: "success",
        data: createAdminForms()
      });
    }

    throw new Error(`Unexpected fetch: ${url}`);
  });
}


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("appRoutes", () => {
  it("redirects unauthenticated users to the Russian login page", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        status: "success",
        data: null
      })
    );

    renderApp(["/app/support"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Вход в рабочие места" })).toBeInTheDocument();
    expect(screen.getByLabelText("Логин")).toBeInTheDocument();
    expect(screen.getByLabelText("Пароль")).toBeInTheDocument();
  });

  it("renders the support workspace and hides the admin nav for support role", async () => {
    renderApp(["/app/support"], createSupportFetchMock() as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Рабочее место поддержки" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Поддержка" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Администрирование" })).not.toBeInTheDocument();
    expect(await screen.findByText("Сбой синхронизации")).toBeInTheDocument();
    expect(await screen.findByText("/api/tickets/ticket-1/observer")).toBeInTheDocument();
  });

  it("returns support user to the default workspace when requested admin route is forbidden", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: null
        });
      }

      if (url.endsWith("/api/web/session/login")) {
        expect(init?.method).toBe("POST");
        expect(init?.body).toBe(JSON.stringify({ login: "support", password: "secret" }));
        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      if (url.endsWith("/api/web/support/bootstrap")) {
        return jsonResponse({
          status: "success",
          data: createSupportBootstrap()
        });
      }

      if (url.includes("/api/web/support/queue")) {
        return jsonResponse({
          status: "success",
          data: createSupportQueue()
        });
      }

      if (url.endsWith("/api/web/support/tickets/ticket-1")) {
        return jsonResponse({
          status: "success",
          data: createSupportDetail()
        });
      }

      if (url.endsWith("/api/web/support/tickets/ticket-1/tools")) {
        return jsonResponse({
          status: "success",
          data: createSupportTools()
        });
      }

      if (url.includes("/api/web/admin/")) {
        throw new Error(`Forbidden admin fetch should not happen: ${url}`);
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Вход в рабочие места" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Логин"), {
      target: { value: "support" }
    });
    fireEvent.change(screen.getByLabelText("Пароль"), {
      target: { value: "secret" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByRole("heading", { name: "Рабочее место поддержки" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Администрирование" })).not.toBeInTheDocument();
  });

  it("redirects /app to the admin workspace for admin role", async () => {
    renderApp(["/app"], createAdminFetchMock() as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Рабочее место администрирования" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Поддержка" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Администрирование" })).toBeInTheDocument();
    expect(await screen.findByText("Реестр модулей")).toBeInTheDocument();
    expect(await screen.findByText("Конструктор форм заявок")).toBeInTheDocument();
  });

  it("redirects support role away from /app/admin before admin bootstrap is requested", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: createSupportSession()
        });
      }

      if (url.endsWith("/api/web/support/bootstrap")) {
        return jsonResponse({
          status: "success",
          data: createSupportBootstrap()
        });
      }

      if (url.includes("/api/web/support/queue")) {
        return jsonResponse({
          status: "success",
          data: createSupportQueue()
        });
      }

      if (url.endsWith("/api/web/support/tickets/ticket-1")) {
        return jsonResponse({
          status: "success",
          data: createSupportDetail()
        });
      }

      if (url.endsWith("/api/web/support/tickets/ticket-1/tools")) {
        return jsonResponse({
          status: "success",
          data: createSupportTools()
        });
      }

      if (url.includes("/api/web/admin/")) {
        throw new Error(`Admin bootstrap must stay untouched for support role: ${url}`);
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/admin"], fetchMock as typeof fetch);

    expect(await screen.findByRole("heading", { name: "Рабочее место поддержки" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Администрирование" })).not.toBeInTheDocument();
  });
});
