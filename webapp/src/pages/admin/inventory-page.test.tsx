import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminInventoryPage } from "./inventory-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderInventory(initialPath = "/app/admin/inventory") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AdminInventoryPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function installFetchMock(options: { omitSummary?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";

    if (url.startsWith("/api/web/admin/devices?") || url === "/api/web/admin/devices") {
      return jsonResponse({
        status: "success",
        data: {
          query: "",
          status_filter: "all",
          ...(options.omitSummary
            ? {}
            : {
                summary: {
                  visible_count: 2,
                  online_count: 1,
                  rollout_targets: 1,
                  duplicate_hosts: 0,
                  cleanup_candidates: 0,
                },
              }),
          filters: {
            status_options: [
              { value: "all", label: "Все устройства" },
              { value: "online", label: "Только онлайн" },
              { value: "offline", label: "Только офлайн" },
            ],
          },
          rollout: [
            {
              target: "linux_alt_x86_64",
              channel: "stable",
              version: "1.2.3",
              updated_at: "2026-04-27T10:00:00Z",
              updated_by: "admin",
            },
          ],
          devices: [
            {
              device_id: "11111111-1111-4111-8111-111111111111",
              hostname: "web-server-01",
              os: "Ubuntu 22.04",
              agent_version: "1.2.3",
              target: "linux_alt_x86_64",
              online: true,
              last_seen_at: "2026-04-27T10:00:00Z",
              connection_status_label: "Онлайн",
              latest_update: {
                status: "ok",
                label: "Обновлено",
                summary: null,
              },
              identity_summary: {
                machine_id: "11111111-1111-4111-8111-111111111111",
                install_id: null,
                machine_id_source: "linux_machine_id",
                identity_scheme: "machine_id",
                source_label: "Linux machine-id",
                is_stable: true,
              },
              duplicate_warning: null,
            },
            {
              device_id: "22222222-2222-4222-8222-222222222222",
              hostname: "win-workstation-12",
              os: "Windows 11",
              agent_version: "1.2.2",
              target: "windows_amd64",
              online: false,
              last_seen_at: "2026-04-27T09:00:00Z",
              connection_status_label: "Офлайн",
              latest_update: {
                status: "failed",
                label: "Ошибка",
                summary: null,
              },
              identity_summary: {
                machine_id: "22222222-2222-4222-8222-222222222222",
                install_id: null,
                machine_id_source: "windows_machine_guid",
                identity_scheme: "machine_id",
                source_label: "Windows MachineGuid",
                is_stable: true,
              },
              duplicate_warning: null,
            },
          ],
        },
      });
    }

    if (url === "/api/web/admin/connection_policy") {
      if (method === "PATCH") {
        return jsonResponse({ status: "ok", policy: "manual" });
      }
      return jsonResponse({ status: "ok", policy: "manual" });
    }

    if (url === "/api/web/admin/connection_requests") {
      return jsonResponse({
        status: "ok",
        count: 1,
        connection_requests: [
          {
            device_id: "33333333-3333-4333-8333-333333333333",
            status: "pending",
            ip_address: "192.168.100.11",
            hostname: "AD-MAIN",
            created_at: "2026-04-27T10:05:00Z",
            metadata: {
              os: "Windows 11",
              agent_version: "1.2.0",
              machine_id: "33333333-3333-4333-8333-333333333333",
            },
          },
        ],
      });
    }

    if (url.startsWith("/api/web/admin/inventory/dashboard")) {
      return jsonResponse({
        status: "success",
        data: {
          totals: {
            devices: 2,
            with_inventory: 1,
            stale_inventory: 1,
            missing_inventory: 1,
            missing_binding: 1,
          },
          freshness: { fresh_days: 7, stale_count: 1, missing_count: 1 },
          by_os: [{ label: "Windows 11", count: 1 }],
          by_building: [{ label: "HQ", count: 1 }],
          by_department: [{ label: "Support", count: 1 }],
          binding_gaps: {
            missing_room: 1,
            missing_department: 1,
            missing_responsible_user: 1,
            missing_inventory_number: 1,
          },
          health: {
            high_disk_usage: 1,
            missing_key_apps: [{ device_id: "22222222-2222-4222-8222-222222222222", hostname: "win-workstation-12", name: "LibreOffice" }],
          },
          refresh: { enabled: true, due_devices: 1 },
        },
      });
    }

    if (url === "/api/web/admin/inventory/bindings/import" && method === "POST") {
      return jsonResponse({
        status: "success",
        data: {
          dry_run: true,
          total_rows: 1,
          valid_rows: 1,
          error_rows: 0,
          changes: [
            {
              row: 2,
              device_id: "11111111-1111-4111-8111-111111111111",
              hostname: "web-server-01",
              action: "update",
              changed_fields: ["room"],
              errors: [],
            },
          ],
        },
      });
    }

    if (url.includes("/api/web/admin/connection_requests/") && url.endsWith("/approve")) {
      return jsonResponse({ status: "ok", device_id: "33333333-3333-4333-8333-333333333333" });
    }

    if (url.includes("/api/web/admin/connection_requests/") && url.endsWith("/reject")) {
      return jsonResponse({ status: "ok", device_id: "33333333-3333-4333-8333-333333333333" });
    }

    if (url.includes("/api/web/admin/devices/") && url.endsWith("/tokens")) {
      return jsonResponse({
        status: "success",
        data: {
          device_id: "11111111-1111-4111-8111-111111111111",
          summary: {
            total_count: 1,
            active_count: 1,
            revoked_count: 0,
          },
          tokens: [
            {
              token_hash: "hash-1",
              token_prefix: "pc_123",
              created_at: "2026-04-27T10:00:00Z",
              expires_at: null,
              revoked_at: null,
              last_used_at: "2026-04-27T10:00:00Z",
              is_active: true,
            },
          ],
        },
      });
    }

    return jsonResponse({ status: "error", error: `Unhandled test request ${method} ${url}` }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AdminInventoryPage", () => {
  it("renders agents, connection requests and approves a pending agent", async () => {
    const fetchMock = installFetchMock();

    renderInventory("/app/admin/inventory?panel=requests");

    expect(await screen.findByRole("heading", { name: "Агенты" })).toBeInTheDocument();
    expect((await screen.findAllByText("AD-MAIN")).length).toBeGreaterThan(0);
    expect(screen.getByText("192.168.100.11 / 1.2.0")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Одобрить/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/connection_requests/33333333-3333-4333-8333-333333333333/approve",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("keeps token and rollout panels available for the selected agent", async () => {
    installFetchMock();

    renderInventory();

    expect((await screen.findAllByText("web-server-01")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /Токены/i }));
    expect(await screen.findByText("pc_123")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Rollout/i }));
    expect((await screen.findAllByText("linux_alt_x86_64")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("1.2.3").length).toBeGreaterThan(0);
  });

  it("renders when the devices payload has no summary block", async () => {
    installFetchMock({ omitSummary: true });

    renderInventory();

    expect((await screen.findAllByText("web-server-01")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
  });

  it("renders fleet inventory dashboard and dry-run import preview", async () => {
    const fetchMock = installFetchMock();

    renderInventory("/app/admin/inventory?panel=fleet");

    expect(await screen.findByText("Сводка парка")).toBeInTheDocument();
    expect(screen.getByText("CSV инвентарь")).toBeInTheDocument();
    expect(screen.getByText("CSV привязки")).toBeInTheDocument();
    expect(await screen.findByText(/LibreOffice/)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/device_id,hostname/i), {
      target: { value: "device_id,hostname,room\n11111111-1111-4111-8111-111111111111,web-server-01,401" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Dry run/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/inventory/bindings/import",
        expect.objectContaining({ method: "POST", body: expect.stringContaining("dry_run") })
      );
    });
    expect(await screen.findByText("update")).toBeInTheDocument();
    expect(screen.getByText("room")).toBeInTheDocument();
  });
});
