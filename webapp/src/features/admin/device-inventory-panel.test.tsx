import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeviceInventoryPanel } from "./device-inventory-panel";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPanel(deviceId: string | null = "device-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DeviceInventoryPanel deviceId={deviceId} deviceLabel="pc-01" />
    </QueryClientProvider>
  );
}

function inventoryPayload() {
  return {
    status: "success",
    data: {
      device_id: "device-1",
      latest_snapshot: {
        id: "snapshot-1",
        source_tool: "inventory.collect",
        collected_at: "2026-05-18T10:00:00Z",
        status: "ok",
        summary: "pc-01",
        result: {
          identity: { hostname: "pc-01", current_user: "ivan" },
          agent: { version: "3.1.56" },
          platform: { os_name: "Windows", os_version: "11", uptime_seconds: 7200 },
          hardware: { manufacturer: "ACME", model: "DeskPro", serial_number: "SN-42" },
          resources: { cpu_percent: 12, memory_percent: 44, disks: [{ mount: "C:\\", used_percent: 77 }] },
          network: { primary_ip: "192.168.100.54", interfaces: [] },
          printers: {
            default_printer: "Office HP",
            items: [{ name: "Office HP", status: "idle", driver: "HP Universal", queue_length: 0 }],
          },
          software: {
            key_apps: [{ id: "libreoffice", name: "LibreOffice", present: true, version: "7.6", status: "ok" }],
          },
        },
        presentation_schema: {},
        effective_presentation_schema: {
          version: "1.0",
          kind: "tool_result",
          blocks: [
            { type: "field_grid", id: "hardware", title: "Железо", fields: [{ path: "hardware.model", label: "Модель" }] },
            {
              type: "table",
              id: "printers",
              title: "Принтеры",
              rows_path: "printers.items",
              columns: [{ path: "name", label: "Имя" }, { path: "driver", label: "Драйвер" }],
            },
            {
              type: "table",
              id: "software",
              title: "Ключевое ПО",
              rows_path: "software.key_apps",
              columns: [{ path: "name", label: "Приложение" }, { path: "version", label: "Версия" }],
            },
          ],
          fallback: { show_raw_json: true },
        },
        presentation_schema_source: "server_override",
        device_card_slots: ["identity", "network"],
      },
      history: [{ id: "snapshot-1", collected_at: "2026-05-18T10:00:00Z", status: "ok", summary: "pc-01" }],
      binding: {
        device_id: "device-1",
        building: "HQ",
        floor: "4",
        room: "401",
        department: "Support",
        responsible_user: "Ivan Petrov",
        responsible_user_login: "ipetrov",
        inventory_number: "INV-42",
        status: "active",
        tags: ["laptop", "shared"],
        notes: null,
        updated_at: "2026-05-18T09:00:00Z",
        updated_by: "admin",
      },
      binding_history: [
        {
          changed_at: "2026-05-18T09:00:00Z",
          changed_by: "admin",
          changed_fields: ["room"],
          old_binding: { room: "400" },
          new_binding: { room: "401" },
          reason: "move",
        },
      ],
      refresh_policy: {
        id: "policy-1",
        scope: "device",
        device_id: "device-1",
        enabled: true,
        interval_minutes: 1440,
        jitter_minutes: 30,
        last_requested_at: "2026-05-18T08:00:00Z",
        next_due_at: "2026-05-19T08:00:00Z",
        updated_at: "2026-05-18T08:00:00Z",
        updated_by: "admin",
      },
      refresh_runs: [
        {
          id: "run-1",
          device_id: "device-1",
          policy_id: "policy-1",
          requested_at: "2026-05-18T08:00:00Z",
          requested_by: "admin",
          status: "dispatched",
          job_id: "op-1",
          error: null,
          completed_at: null,
        },
      ],
      last_refresh_run: null,
    },
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("DeviceInventoryPanel", () => {
  it("renders v2 inventory, binding, schedule status and sends collect action", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/web/admin/devices/device-1/inventory" && !init?.method) {
        return jsonResponse(inventoryPayload());
      }
      if (url === "/api/web/admin/devices/device-1/inventory/collect" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            device_id: "device-1",
            tool_name: "inventory.collect",
            operation_id: "op-1",
            status: "accepted",
            message: "Команда inventory.collect отправлена",
            poll_url: "/api/operations/op-1",
          },
        });
      }
      return jsonResponse({ status: "error", error: `Unhandled ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();

    expect(await screen.findByText("Паспорт устройства")).toBeInTheDocument();
    expect(await screen.findByText("192.168.100.54")).toBeInTheDocument();
    expect(screen.getByText("INV-42")).toBeInTheDocument();
    expect(screen.getByText("refresh enabled")).toBeInTheDocument();
    expect(screen.getByText("server override")).toBeInTheDocument();
    expect(screen.getByText("77%")).toBeInTheDocument();
    expect(screen.getByText("DeskPro")).toBeInTheDocument();
    expect(screen.getByText("HP Universal")).toBeInTheDocument();
    expect(screen.getByText("LibreOffice")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /История/i }));
    expect(screen.getByText("Binding changes")).toBeInTheDocument();
    expect(screen.getByText("move")).toBeInTheDocument();
    expect(screen.getByText("Refresh runs")).toBeInTheDocument();
    expect(screen.getByText("dispatched")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Обновить инвентарь/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/devices/device-1/inventory/collect",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("saves binding and refresh policy from binding tab", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/web/admin/devices/device-1/inventory" && !init?.method) {
        return jsonResponse(inventoryPayload());
      }
      if (url === "/api/web/admin/devices/device-1/binding" && init?.method === "PUT") {
        return jsonResponse({ status: "success", data: { ...inventoryPayload().data.binding, room: "402" } });
      }
      if (url === "/api/web/admin/devices/device-1/inventory/refresh-policy" && init?.method === "PUT") {
        return jsonResponse({ status: "success", data: inventoryPayload().data.refresh_policy });
      }
      return jsonResponse({ status: "error", error: `Unhandled ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();

    fireEvent.click(await screen.findByRole("button", { name: "Привязка" }));
    const roomInput = screen.getByLabelText("Кабинет");
    fireEvent.change(roomInput, { target: { value: "402" } });
    fireEvent.click(screen.getByRole("button", { name: /Сохранить привязку/i }));
    fireEvent.click(screen.getByRole("button", { name: /Сохранить расписание/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/devices/device-1/binding",
        expect.objectContaining({ method: "PUT", body: expect.stringContaining("402") })
      );
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/devices/device-1/inventory/refresh-policy",
        expect.objectContaining({ method: "PUT", body: expect.stringContaining("1440") })
      );
    });
  });

  it("handles no inventory state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          status: "success",
          data: { device_id: "device-1", latest_snapshot: null, history: [], binding: null, refresh_policy: null },
        })
      )
    );

    renderPanel();

    expect(await screen.findByText(/Snapshot ещё не собран/i)).toBeInTheDocument();
  });
});
