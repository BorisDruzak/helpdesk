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
  it("renders typed inventory, update workflow and observer drilldown in Russian", async () => {
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
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces"
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

        if (url === "/api/web/admin/observer/quick?device_id=device-1&lookback_hours=24") {
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
                  root_span_id: "span-root-1",
                  root_kind: "agent_update",
                  root_kind_label: "Обновление агента",
                  status: "failed",
                  status_label: "Ошибка",
                  ticket_id: "ticket-1",
                  device_id: "device-1",
                  operation_id: "op-update-1",
                  job_id: null,
                  duration_ms: 6400,
                  error_count: 1,
                  span_count: 6,
                  started_at: "2026-04-20T11:24:00+05:00",
                  finished_at: "2026-04-20T11:24:06+05:00",
                  attrs_json: {
                    flow: "agent_update"
                  }
                },
                {
                  trace_id: "trace-tool-1",
                  root_span_id: "span-root-2",
                  root_kind: "tool_call",
                  root_kind_label: "Инструмент",
                  status: "running",
                  status_label: "В работе",
                  ticket_id: "ticket-2",
                  device_id: "device-1",
                  operation_id: "op-tool-1",
                  job_id: null,
                  duration_ms: 1800,
                  error_count: 0,
                  span_count: 4,
                  started_at: "2026-04-20T11:26:00+05:00",
                  finished_at: null,
                  attrs_json: {}
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
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-1&lookback_hours=24&limit=12") {
          return jsonResponse({
            status: "success",
            data: {
              query: {
                device_id: "device-1",
                lookback_hours: 24,
                status_filter: "all",
                root_kind_filter: "all",
                limit: 12
              },
              summary: {
                visible_count: 2,
                active_count: 1,
                error_count: 1,
                selected_trace_id: "trace-update-1"
              },
              filters: {
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "running", label: "В работе" },
                  { value: "failed", label: "С ошибкой" }
                ],
                root_kind_options: [
                  { value: "all", label: "Все потоки" },
                  { value: "agent_update", label: "Обновление агента" },
                  { value: "tool_call", label: "Инструмент" }
                ]
              },
              traces: [
                {
                  trace_id: "trace-update-1",
                  root_span_id: "span-root-1",
                  root_kind: "agent_update",
                  root_kind_label: "Обновление агента",
                  status: "failed",
                  status_label: "Ошибка",
                  ticket_id: "ticket-1",
                  device_id: "device-1",
                  operation_id: "op-update-1",
                  job_id: null,
                  duration_ms: 6400,
                  error_count: 1,
                  span_count: 6,
                  started_at: "2026-04-20T11:24:00+05:00",
                  finished_at: "2026-04-20T11:24:06+05:00",
                  attrs_json: {
                    flow: "agent_update"
                  }
                },
                {
                  trace_id: "trace-tool-1",
                  root_span_id: "span-root-2",
                  root_kind: "tool_call",
                  root_kind_label: "Инструмент",
                  status: "running",
                  status_label: "В работе",
                  ticket_id: "ticket-2",
                  device_id: "device-1",
                  operation_id: "op-tool-1",
                  job_id: null,
                  duration_ms: 1800,
                  error_count: 0,
                  span_count: 4,
                  started_at: "2026-04-20T11:26:00+05:00",
                  finished_at: null,
                  attrs_json: {}
                }
              ],
              links: {
                detail_endpoint_template: "/api/web/admin/observer/traces/{trace_id}",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
          });
        }

        if (url === "/api/web/admin/observer/traces/trace-update-1") {
          return jsonResponse({
            status: "success",
            data: {
              trace: {
                trace_id: "trace-update-1",
                root_span_id: "span-root-1",
                root_kind: "agent_update",
                root_kind_label: "Обновление агента",
                status: "failed",
                status_label: "Ошибка",
                ticket_id: "ticket-1",
                device_id: "device-1",
                operation_id: "op-update-1",
                job_id: null,
                duration_ms: 6400,
                error_count: 1,
                span_count: 3,
                started_at: "2026-04-20T11:24:00+05:00",
                finished_at: "2026-04-20T11:24:06+05:00",
                attrs_json: {
                  flow: "agent_update"
                }
              },
              summary: {
                span_count: 3,
                error_count: 1,
                linked_trace_count: 1
              },
              spans: [
                {
                  span_id: "span-root-1",
                  trace_id: "trace-update-1",
                  parent_span_id: null,
                  source_type: "operation",
                  source_ref: "op-update-1",
                  name: "operation.agent_update",
                  kind: "internal",
                  component: "operation",
                  event_type: "agent_update",
                  module_name: null,
                  tool_name: null,
                  status: "failed",
                  status_label: "Ошибка",
                  started_at: "2026-04-20T11:24:00+05:00",
                  finished_at: "2026-04-20T11:24:06+05:00",
                  duration_ms: 6400,
                  attrs_json: {}
                }
              ],
              span_links: [
                {
                  id: 11,
                  span_id: "span-root-1",
                  linked_trace_id: "trace-followup-1",
                  linked_span_id: "span-followup-1",
                  reason: "child_trace",
                  attrs_json: {
                    edge: "child"
                  },
                  created_at: "2026-04-20T11:24:07+05:00"
                }
              ],
              error_occurrences: [
                {
                  occurrence_id: "occ-1",
                  trace_id: "trace-update-1",
                  span_id: "span-root-1",
                  error_signature: "sig-1",
                  device_id: "device-1",
                  ticket_id: "ticket-1",
                  operation_id: "op-update-1",
                  component: "agent_update",
                  module_name: null,
                  tool_name: null,
                  error_kind: "runtime_error",
                  exception_type: "RuntimeError",
                  failure_stage: "delivery",
                  severity: "error",
                  severity_label: "Ошибка",
                  message_norm: "update delivery failed",
                  stack_hash: "stack-1",
                  attrs_json: {
                    code: "DELIVERY_FAILED"
                  },
                  created_at: "2026-04-20T11:24:06+05:00"
                }
              ]
            }
          });
        }

        if (url === "/api/web/admin/observer/quick?device_id=device-2&lookback_hours=24") {
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                lookback_hours: 24,
                recent_trace_count: 2,
                hot_trace_count: 1,
                signature_count: 0,
                degradation_group_count: 0,
                dangerous_flow_count: 0
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "ok",
                health_status_label: "Норма",
                pending_trace_count: 0,
                last_projected_at: "2026-04-20T09:10:00+05:00",
                issues: []
              },
              hot_traces: [
                {
                  trace_id: "trace-linux-1",
                  root_span_id: "span-linux-1",
                  root_kind: "tool_call",
                  root_kind_label: "Инструмент",
                  status: "succeeded",
                  status_label: "Успешно",
                  ticket_id: null,
                  device_id: "device-2",
                  operation_id: "op-linux-1",
                  job_id: null,
                  duration_ms: 1200,
                  error_count: 0,
                  span_count: 2,
                  started_at: "2026-04-20T08:55:00+05:00",
                  finished_at: "2026-04-20T08:55:01+05:00",
                  attrs_json: {}
                }
              ],
              top_signatures: [],
              top_degradations: [],
              dangerous_flows: [],
              links: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-2&lookback_hours=24&limit=12") {
          return jsonResponse({
            status: "success",
            data: {
              query: {
                device_id: "device-2",
                lookback_hours: 24,
                status_filter: "all",
                root_kind_filter: "all",
                limit: 12
              },
              summary: {
                visible_count: 1,
                active_count: 0,
                error_count: 0,
                selected_trace_id: "trace-linux-1"
              },
              filters: {
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "running", label: "В работе" },
                  { value: "failed", label: "С ошибкой" }
                ],
                root_kind_options: [
                  { value: "all", label: "Все потоки" },
                  { value: "agent_update", label: "Обновление агента" },
                  { value: "tool_call", label: "Инструмент" }
                ]
              },
              traces: [
                {
                  trace_id: "trace-linux-1",
                  root_span_id: "span-linux-1",
                  root_kind: "tool_call",
                  root_kind_label: "Инструмент",
                  status: "succeeded",
                  status_label: "Успешно",
                  ticket_id: null,
                  device_id: "device-2",
                  operation_id: "op-linux-1",
                  job_id: null,
                  duration_ms: 1200,
                  error_count: 0,
                  span_count: 2,
                  started_at: "2026-04-20T08:55:00+05:00",
                  finished_at: "2026-04-20T08:55:01+05:00",
                  attrs_json: {}
                }
              ],
              links: {
                detail_endpoint_template: "/api/web/admin/observer/traces/{trace_id}",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
          });
        }

        if (url === "/api/web/admin/observer/traces/trace-linux-1") {
          return jsonResponse({
            status: "success",
            data: {
              trace: {
                trace_id: "trace-linux-1",
                root_span_id: "span-linux-1",
                root_kind: "tool_call",
                root_kind_label: "Инструмент",
                status: "succeeded",
                status_label: "Успешно",
                ticket_id: null,
                device_id: "device-2",
                operation_id: "op-linux-1",
                job_id: null,
                duration_ms: 1200,
                error_count: 0,
                span_count: 2,
                started_at: "2026-04-20T08:55:00+05:00",
                finished_at: "2026-04-20T08:55:01+05:00",
                attrs_json: {}
              },
              summary: {
                span_count: 2,
                error_count: 0,
                linked_trace_count: 0
              },
              spans: [
                {
                  span_id: "span-linux-1",
                  trace_id: "trace-linux-1",
                  parent_span_id: null,
                  source_type: "operation",
                  source_ref: "op-linux-1",
                  name: "operation.tool_call",
                  kind: "internal",
                  component: "operation",
                  event_type: "tool_call",
                  module_name: "network_ping",
                  tool_name: "network_ping.ping",
                  status: "succeeded",
                  status_label: "Успешно",
                  started_at: "2026-04-20T08:55:00+05:00",
                  finished_at: "2026-04-20T08:55:01+05:00",
                  duration_ms: 1200,
                  attrs_json: {}
                }
              ],
              span_links: [],
              error_occurrences: []
            }
          });
        }

        if (url === "/api/web/admin/observer/quick?device_id=device-2&lookback_hours=72") {
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
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-2&lookback_hours=72&limit=12") {
          return jsonResponse({
            status: "success",
            data: {
              query: {
                device_id: "device-2",
                lookback_hours: 72,
                status_filter: "all",
                root_kind_filter: "all",
                limit: 12
              },
              summary: {
                visible_count: 0,
                active_count: 0,
                error_count: 0,
                selected_trace_id: null
              },
              filters: {
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "running", label: "В работе" },
                  { value: "failed", label: "С ошибкой" }
                ],
                root_kind_options: [
                  { value: "all", label: "Все потоки" },
                  { value: "agent_update", label: "Обновление агента" },
                  { value: "tool_call", label: "Инструмент" }
                ]
              },
              traces: [],
              links: {
                detail_endpoint_template: "/api/web/admin/observer/traces/{trace_id}",
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
    expect(await screen.findByText("Всего в инвентаре")).toBeInTheDocument();
    expect(await screen.findByText("Назначения rollout")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /WS-01/i })).toBeInTheDocument();
    expect(await screen.findByText("Доступно обновление")).toBeInTheDocument();
    expect(await screen.findByText("Назначенный rollout новее текущей версии.")).toBeInTheDocument();
    expect(await screen.findByText("Быстрый срез трассировки")).toBeInTheDocument();
    expect(await screen.findByText("Launcher signature mismatch")).toBeInTheDocument();
    expect(await screen.findByText("/api/web/admin/observer/traces")).toBeInTheDocument();
    expect(await screen.findByText("Детальный разбор трасс")).toBeInTheDocument();
    expect(await screen.findByText("Trace ID")).toBeInTheDocument();
    expect((await screen.findAllByText("trace-update-1")).length).toBeGreaterThan(0);
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
      expect(screen.getByText("Платформа: linux_alt_x86_64")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("trace-linux-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "72 часа" }));

    await waitFor(() => {
      expect(screen.getByText("Есть отставание")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Для выбранного устройства по текущим фильтрам трасс пока нет.")).toBeInTheDocument();
    });
  });
});
