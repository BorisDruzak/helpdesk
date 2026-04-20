import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminWorkspacePage } from "./index";


function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}

function renderAdminPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false
      }
    }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <AdminWorkspacePage />
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminWorkspacePage", () => {
  it("renders typed devices inventory, update panel and observer quick in Russian", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/bootstrap") {
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
                visible_count: 2,
                online_count: 1,
                rollout_targets: 2
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
                },
                {
                  target: "linux_alt_x86_64",
                  channel: "stable",
                  version: "2.3.9",
                  updated_at: "2026-04-20T10:55:00+05:00",
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
                    status: "completed",
                    label: "Обновление завершено",
                    summary: "Устройство на шаг позади rollout"
                  }
                },
                {
                  device_id: "device-2",
                  hostname: "LT-02",
                  os: "ALT Linux",
                  agent_version: "2.3.7",
                  target: "linux_alt_x86_64",
                  online: false,
                  last_seen_at: "2026-04-20T09:10:00+05:00",
                  connection_status_label: "Оффлайн",
                  latest_update: {
                    status: "pending",
                    label: "Ожидает rollout",
                    summary: "Назначен rollout stable/2.3.9"
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
                recent_trace_count: 9,
                hot_trace_count: 2,
                signature_count: 1,
                degradation_group_count: 1,
                dangerous_flow_count: 1
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "ok",
                health_status_label: "Норма",
                pending_trace_count: 1,
                last_projected_at: "2026-04-20T11:28:00+05:00",
                issues: []
              },
              hot_traces: [
                {
                  trace_id: "trace-update-1",
                  root_kind: "agent_update",
                  root_kind_label: "Обновление агента",
                  status: "failed",
                  status_label: "Ошибка",
                  ticket_id: "ticket-1",
                  device_id: "device-1",
                  duration_ms: 6400,
                  error_count: 1,
                  span_count: 6,
                  started_at: "2026-04-20T11:24:00+05:00",
                  finished_at: "2026-04-20T11:24:06+05:00"
                },
                {
                  trace_id: "trace-tool-1",
                  root_kind: "tool_call",
                  root_kind_label: "Инструмент",
                  status: "running",
                  status_label: "В работе",
                  ticket_id: "ticket-2",
                  device_id: "device-1",
                  duration_ms: 1800,
                  error_count: 0,
                  span_count: 4,
                  started_at: "2026-04-20T11:26:00+05:00",
                  finished_at: null
                }
              ],
              top_signatures: [
                {
                  error_signature: "sig-1",
                  title: "Launcher signature mismatch",
                  tool_name: "update",
                  component: "agent_update",
                  occurrences_count: 4,
                  affected_devices_count: 2,
                  last_seen_at: "2026-04-20T11:25:00+05:00"
                }
              ],
              top_degradations: [
                {
                  operation_kind: "tool_call",
                  operation_kind_label: "Инструмент",
                  tool_name: "network_ping.ping",
                  operations_count: 7,
                  timeout_count: 2,
                  retried_operations_count: 3,
                  slow_operations_count: 1,
                  max_duration_ms: 9000,
                  latest_operation_at: "2026-04-20T11:23:00+05:00"
                }
              ],
              dangerous_flows: [
                {
                  root_kind: "agent_update",
                  root_kind_label: "Обновление агента",
                  operations_count: 5,
                  error_count: 2,
                  timeout_count: 1,
                  retried_count: 1,
                  active_count: 0,
                  latest_operation_at: "2026-04-20T11:24:00+05:00"
                }
              ],
              links: {
                quick_endpoint: "/api/admin/tech/observer/quick",
                traces_endpoint: "/api/admin/tech/traces",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
          });
        }

        if (url === "/api/web/admin/observer/quick?lookback_hours=72") {
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                lookback_hours: 72,
                recent_trace_count: 14,
                hot_trace_count: 3,
                signature_count: 2,
                degradation_group_count: 2,
                dangerous_flow_count: 2
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "degraded",
                health_status_label: "Есть отставание",
                pending_trace_count: 6,
                last_projected_at: "2026-04-20T10:10:00+05:00",
                issues: ["pending_backlog"]
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

        if (url === "/api/web/admin/devices/device-2/updates") {
          return jsonResponse({
            status: "success",
            data: {
              device_id: "device-2",
              device_label: "LT-02",
              online: false,
              target: "linux_alt_x86_64",
              current_version: "2.3.7",
              release_channel: "stable",
              is_release: true,
              summary: {
                status: "offline",
                label: "Ждёт связи",
                summary: "Запуск обновления доступен только когда агент онлайн и может принять команду."
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
                  target: "linux_alt_x86_64",
                  channel: "stable",
                  version: "2.3.9"
                },
                assigned_rollout: {
                  target: "linux_alt_x86_64",
                  channel: "stable",
                  version: "2.3.9",
                  updated_at: "2026-04-20T10:55:00+05:00",
                  updated_by: "admin1"
                }
              },
              action: {
                enabled: false,
                label: "Ожидает связи",
                reason_required: true,
                endpoint: "/api/web/admin/devices/device-2/updates/run"
              }
            }
          });
        }

        if (url === "/api/web/admin/devices/device-1/updates/run") {
          return jsonResponse(
            {
              status: "success",
              data: {
                device_id: "device-1",
                operation_id: "op-admin-1",
                status: "queued",
                message: "Операция op-admin-1 поставлена в очередь.",
                build_source: "assigned_rollout",
                poll_url: "/api/operations/op-admin-1",
                build: {
                  target: "windows_amd64",
                  channel: "stable",
                  version: "2.4.1"
                }
              }
            },
            202
          );
        }

        return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
      })
    );

    renderAdminPage();

    expect(await screen.findByRole("heading", { name: "Рабочее место администрирования" })).toBeInTheDocument();
    expect(await screen.findByText("Всего в inventory")).toBeInTheDocument();
    expect(await screen.findByText("Назначения rollout")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /WS-01/i })).toBeInTheDocument();
    expect((await screen.findAllByText("Устройство на шаг позади rollout")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Доступно обновление")).toBeInTheDocument();
    expect(await screen.findByText("Назначенный rollout новее текущей версии.")).toBeInTheDocument();
    expect(await screen.findByText("Observer quick")).toBeInTheDocument();
    expect(await screen.findByText("Launcher signature mismatch")).toBeInTheDocument();
    expect(await screen.findByText("/api/admin/tech/traces/runtime")).toBeInTheDocument();
    expect(await screen.findByText("Норма")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Причина запуска"), {
      target: { value: "canary после smoke" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Запустить обновление" }));

    await waitFor(() => {
      expect(screen.getByText("Операция op-admin-1 поставлена в очередь.")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /LT-02/i }));

    await waitFor(() => {
      expect(screen.getAllByText("Назначен rollout stable/2.3.9")).toHaveLength(2);
    });

    fireEvent.click(screen.getByRole("button", { name: "72 часа" }));

    await waitFor(() => {
      expect(screen.getByText("Есть отставание")).toBeInTheDocument();
    });
  });
});
