import { fireEvent, render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "../features/auth/session-provider";
import { appRoutes } from "./router";
import { QueryProvider } from "./providers/query-provider";

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

  it("renders the support workspace when session bootstrap succeeds", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/api/web/session/me")) {
        return jsonResponse({
          status: "success",
          data: {
            user_login: "support1",
            actor_role: "support",
            auth_type: "ui_token"
          }
        });
      }

      if (url.endsWith("/api/web/support/bootstrap")) {
        return jsonResponse({
          status: "success",
          data: {
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
          }
        });
      }

      if (url.includes("/api/web/support/queue")) {
        return jsonResponse({
          status: "success",
          data: {
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
          }
        });
      }

      if (url.endsWith("/api/web/support/tickets/ticket-1")) {
        return jsonResponse({
          status: "success",
          data: {
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
                trace_count: 3,
                active_trace_count: 1,
                error_trace_count: 1,
                signature_count: 1,
                latest_trace_at: "2026-04-20T08:09:00+05:00"
              }
            }
          }
        });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    renderApp(["/app/support"], fetchMock as typeof fetch);

    expect(await screen.findByRole("link", { name: "Поддержка" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Администрирование" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Рабочее место поддержки" })).toBeInTheDocument();
    expect(await screen.findByText("Сбой синхронизации")).toBeInTheDocument();
    expect(await screen.findByText("/api/tickets/ticket-1/observer")).toBeInTheDocument();
  });

  it("logs in and returns the user to the requested admin workspace", async () => {
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
          data: {
            user_login: "support",
            actor_role: "support",
            auth_type: "ui_token"
          }
        });
      }

      if (url.endsWith("/api/web/admin/bootstrap")) {
        return jsonResponse({
          status: "success",
          data: {
            workspace: "admin",
            features: [
              "devices_inventory",
              "agent_rollout",
              "modules_workbench",
              "tech_panel"
            ],
            observer: {
              quick_endpoint: "/api/admin/tech/observer/quick",
              traces_endpoint: "/api/admin/tech/traces"
            }
          }
        });
      }

      if (url === "/api/web/admin/devices") {
        return jsonResponse({
          status: "success",
          data: {
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
          }
        });
      }

      if (url === "/api/web/admin/observer/quick?lookback_hours=24") {
        return jsonResponse({
          status: "success",
          data: {
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
              quick_endpoint: "/api/admin/tech/observer/quick",
              traces_endpoint: "/api/admin/tech/traces",
              runtime_endpoint: "/api/admin/tech/traces/runtime"
            }
          }
        });
      }

      if (url === "/api/web/admin/devices/device-1/updates") {
        return jsonResponse({
          status: "success",
          data: {
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
          }
        });
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

    expect(await screen.findByRole("heading", { name: "Рабочее место администрирования" })).toBeInTheDocument();
  });
});
