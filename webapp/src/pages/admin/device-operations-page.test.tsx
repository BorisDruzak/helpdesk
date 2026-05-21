import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { collectAdminDeviceInventory } from "../../features/admin/api";
import { fetchDeviceOperations } from "../../features/device-operations/api";
import type { DeviceOperationsPayload } from "../../features/device-operations/types";
import { AdminDeviceOperationsPage } from "./device-operations-page";

vi.mock("../../features/device-operations/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/device-operations/api")>();
  return {
    ...actual,
    fetchDeviceOperations: vi.fn(),
  };
});

vi.mock("../../features/admin/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/admin/api")>();
  return {
    ...actual,
    collectAdminDeviceInventory: vi.fn(),
  };
});

function payload(overrides: Partial<DeviceOperationsPayload> = {}): DeviceOperationsPayload {
  return {
    generated_at: "2026-05-21T08:00:00Z",
    device: {
      device_id: "device-1",
      hostname: "pc-support-01",
      display_name: "PC Support 01",
      platform: "windows",
      os_name: "Windows 11",
      os_version: "23H2",
      arch: "x64",
      first_seen_at: "2026-05-20T08:00:00Z",
      last_seen_at: "2026-05-21T07:55:00Z",
      source: "agent",
      status: "active",
    },
    binding: {
      responsible_person: "Иван Петров",
      department: "Support",
      building: "HQ",
      room: "401",
      inventory_number: "INV-001",
      status: "active",
      tags: ["support"],
      updated_at: "2026-05-21T07:00:00Z",
      updated_by: "admin",
    },
    agent: {
      connection_state: "online",
      last_seen_at: "2026-05-21T07:55:00Z",
      version: "2.4.1",
      protocol: "ws_ticket_v3",
      capabilities_count: 12,
      toolset_hash: "toolset-a",
      desired_revision: "rev-2",
      current_revision: "rev-1",
      config_status: "outdated",
      update_status: "pending",
      update_available: true,
      pending_restart: false,
    },
    provisioning: {
      state: "approved",
      auth_state: "ok",
      last_error: null,
      last_error_at: null,
      token_status: "active",
      connection_request_id: "conn-1",
      can_approve: false,
      can_reject: false,
    },
    inventory: {
      latest_snapshot_id: "snap-1",
      collected_at: "2026-05-21T07:40:00Z",
      age_seconds: 1200,
      freshness: "fresh",
      summary: { cpu: "Intel", ram_gb: 32 },
      presentation: null,
      refresh_policy: { enabled: true, interval_minutes: 120, next_due_at: "2026-05-21T09:40:00Z" },
      latest_refresh_run: { id: "run-1", status: "completed", requested_at: "2026-05-21T07:35:00Z", completed_at: "2026-05-21T07:40:00Z", error_summary: null },
      can_request_refresh: true,
    },
    modules: {
      reconcile_state: "outdated",
      module_count: 2,
      missing_count: 1,
      outdated_count: 1,
      failed_count: 0,
      items: [
        {
          module_id: "inventory.collect",
          name: "Inventory Collect",
          installed_version: "1.0.0",
          desired_version: "1.1.0",
          state: "outdated",
          last_error: null,
          last_seen_at: "2026-05-21T07:40:00Z",
        },
      ],
    },
    outbox: {
      pending_count: 1,
      failed_count: 0,
      last_ack_at: "2026-05-21T07:35:00Z",
      items: [
        {
          id: "outbox-1",
          command_type: "collect_inventory",
          status: "pending",
          created_at: "2026-05-21T07:30:00Z",
          sent_at: null,
          ack_at: null,
          error_summary: null,
          ticket_id: null,
          operation_id: "op-1",
        },
      ],
    },
    operations: {
      recent_failed_count: 1,
      recent_running_count: 0,
      items: [
        {
          id: "op-1",
          ticket_id: "ticket-1",
          tool_name: "inventory.collect",
          status: "failed",
          started_at: "2026-05-21T07:20:00Z",
          finished_at: "2026-05-21T07:21:00Z",
          duration_ms: 60_000,
          error_summary: "timeout",
          trace_id: "trace-1",
        },
      ],
    },
    observer: {
      trace_count: 1,
      latest_trace_at: "2026-05-21T07:21:00Z",
      items: [
        {
          trace_id: "trace-1",
          title: "Inventory failure",
          status: "failed",
          started_at: "2026-05-21T07:20:00Z",
          finished_at: "2026-05-21T07:21:00Z",
          ticket_id: "ticket-1",
          operation_id: "op-1",
          root_span: "collect",
          error_summary: "timeout",
        },
      ],
    },
    remote_assist: {
      availability: "available",
      reason: "Агент online; запуск доступен из тикета с consent workflow.",
      active_session_id: null,
      pending_consent_id: null,
      last_session_at: null,
      can_request: false,
    },
    signals: {
      agent_offline: false,
      stale_inventory: false,
      missing_inventory: false,
      update_available: true,
      provisioning_error: false,
      auth_error: false,
      module_reconcile_failed: false,
      outbox_backlog: true,
      failed_recent_operation: true,
      observer_errors: true,
      remote_assist_unavailable: false,
    },
    links: {
      inventory: "/app/admin/inventory?device=device-1",
      device_card: "/app/admin/device?device=device-1",
      agent_updates: "/app/admin/agent-updates?device=device-1",
      modules: "/app/admin/modules?device=device-1",
      observer: "/app/admin/observer?device_id=device-1",
      tickets: "/app/tickets?search=device-1",
      remote_assist: "/app/tickets?search=device-1",
    },
    ...overrides,
  };
}

function renderPage(initialEntry = "/app/admin/device-operations?device_id=device-1") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AdminDeviceOperationsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminDeviceOperationsPage", () => {
  it("renders Russian workspace, health cards and expert links", async () => {
    vi.mocked(fetchDeviceOperations).mockResolvedValue(payload());

    renderPage();

    expect(await screen.findByRole("heading", { name: "Операции устройства" })).toBeInTheDocument();
    expect((await screen.findAllByText("PC Support 01")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Агент").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Инвентаризация").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Remote Assist").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Открыть Inventory/ })).toHaveAttribute("href", "/app/admin/inventory?device=device-1");
    expect(screen.getByRole("link", { name: /Открыть карточку устройства/ })).toHaveAttribute("href", "/app/admin/device?device=device-1");
    expect(screen.getByRole("link", { name: /Открыть Observer/ })).toHaveAttribute("href", "/app/admin/observer?device_id=device-1");
  });

  it("renders missing inventory and offline agent states without fake actions", async () => {
    vi.mocked(fetchDeviceOperations).mockResolvedValue(
      payload({
        agent: { ...payload().agent, connection_state: "offline" },
        inventory: { ...payload().inventory, freshness: "missing", latest_snapshot_id: null, collected_at: null, summary: null, can_request_refresh: false },
        remote_assist: {
          availability: "offline",
          reason: "Агент устройства offline.",
          active_session_id: null,
          pending_consent_id: null,
          last_session_at: null,
          can_request: false,
        },
        signals: { ...payload().signals, agent_offline: true, missing_inventory: true, stale_inventory: false, remote_assist_unavailable: true },
      }),
    );

    renderPage();

    expect((await screen.findAllByText("Офлайн")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Инвентаризация" }));
    expect(screen.getByText("Инвентаризация ещё не получена.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Запросить инвентаризацию" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remote Assist" }));
    expect(screen.getByText("Запуск Remote Assist доступен только из тикета с реальным consent workflow.")).toBeInTheDocument();
  });

  it("requests inventory refresh only when backend allows it", async () => {
    vi.mocked(fetchDeviceOperations).mockResolvedValue(payload());
    vi.mocked(collectAdminDeviceInventory).mockResolvedValue({
      device_id: "device-1",
      tool_name: "inventory.collect",
      operation_id: "op-refresh",
      status: "accepted",
      message: "accepted",
      poll_url: null,
    });

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Запросить инвентаризацию" }));

    await waitFor(() => {
      expect(collectAdminDeviceInventory).toHaveBeenCalledWith("device-1");
    });
  });
});
