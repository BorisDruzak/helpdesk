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

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("DeviceInventoryPanel", () => {
  it("renders latest inventory through presentation schema and sends collect action", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/web/admin/devices/device-1/inventory" && !init?.method) {
        return jsonResponse({
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
                resources: { cpu_percent: 12, memory_percent: 44, disks: [{ mount: "C:\\", used_percent: 77 }] },
                network: { primary_ip: "192.168.100.54", interfaces: [] },
              },
              presentation_schema: {},
              effective_presentation_schema: {
                version: "1.0",
                kind: "tool_result",
                blocks: [{ type: "field_grid", title: "Device", fields: [{ path: "identity.hostname", label: "Host" }] }],
                fallback: { show_raw_json: true },
              },
              presentation_schema_source: "server_override",
              device_card_slots: ["identity", "network"],
            },
            history: [{ id: "snapshot-1", collected_at: "2026-05-18T10:00:00Z", status: "ok", summary: "pc-01" }],
          },
        });
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

    expect(await screen.findByText("Инвентарь устройства")).toBeInTheDocument();
    expect(await screen.findByText("192.168.100.54")).toBeInTheDocument();
    expect(screen.getAllByText("pc-01").length).toBeGreaterThan(0);
    expect(screen.getByText("server override")).toBeInTheDocument();
    expect(screen.getAllByText("Host").length).toBeGreaterThan(0);
    expect(screen.getByText("77%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Обновить инвентарь/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/devices/device-1/inventory/collect",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("handles no inventory state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          status: "success",
          data: { device_id: "device-1", latest_snapshot: null, history: [] },
        })
      )
    );

    renderPanel();

    expect(await screen.findByText(/Snapshot ещё не собран/i)).toBeInTheDocument();
  });
});
