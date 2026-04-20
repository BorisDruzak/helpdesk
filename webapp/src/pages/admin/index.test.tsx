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
  it("renders typed devices inventory and rollout summary on русском языке", async () => {
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
  });
});
