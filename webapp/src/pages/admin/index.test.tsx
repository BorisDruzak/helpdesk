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

        if (url.startsWith("/api/web/admin/devices")) {
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

        return jsonResponse({ status: "error", error: `Unhandled URL: ${url}` }, 404);
      })
    );

    renderAdminPage();

    expect(await screen.findByRole("heading", { name: "Рабочее место администрирования" })).toBeInTheDocument();
    expect(await screen.findByText("Всего в inventory")).toBeInTheDocument();
    expect(await screen.findByText("Назначения rollout")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /WS-01/i })).toBeInTheDocument();
    expect((await screen.findAllByText("Устройство на шаг позади rollout")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /LT-02/i }));

    await waitFor(() => {
      expect(screen.getAllByText("Назначен rollout stable/2.3.9")).toHaveLength(2);
    });
  });
});
