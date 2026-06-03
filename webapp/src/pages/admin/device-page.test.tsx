import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAdminDevices } from "../../features/admin/api";
import { AdminDevicePage } from "./device-page";

vi.mock("../../features/admin/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/admin/api")>();
  return {
    ...actual,
    fetchAdminDevices: vi.fn(),
  };
});

vi.mock("../../features/agent-updates/device-update-panel", () => ({
  DeviceUpdatePanel: () => <section data-testid="device-update-panel">update panel</section>,
}));

vi.mock("../../features/admin/device-inventory-panel", () => ({
  DeviceInventoryPanel: () => <section data-testid="device-inventory-panel">inventory panel</section>,
}));

vi.mock("../../features/tech/observer-quick-panel", () => ({
  ObserverQuickPanel: () => <section data-testid="observer-quick-panel">observer panel</section>,
}));

const fetchAdminDevicesMock = vi.mocked(fetchAdminDevices);

function renderDevicePage(initialEntry = "/app/admin/device?device=device-1") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/app/admin/device" element={<AdminDevicePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AdminDevicePage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps device identity dominant and moves secondary context into a rail", async () => {
    fetchAdminDevicesMock.mockResolvedValue({
      query: "",
      status_filter: "all",
      summary: {
        visible_count: 1,
        online_count: 0,
        rollout_targets: 1,
        duplicate_hosts: 0,
        cleanup_candidates: 0,
      },
      filters: {
        status_options: [
          { value: "all", label: "Все" },
          { value: "online", label: "Онлайн" },
          { value: "offline", label: "Оффлайн" },
        ],
      },
      rollout: [],
      devices: [
        {
          device_id: "device-1",
          hostname: "ADMIN-2",
          os: "Windows",
          target: "windows_amd64",
          agent_version: "3.1.61",
          online: false,
          connection_status_label: "Оффлайн",
          last_seen_at: "2026-06-02T13:26:00+05:00",
          latest_update: {
            status: "waiting",
            label: "Ждёт связи",
            summary: "Waiting for agent connection",
          },
          identity_summary: {
            machine_id: "machine-1",
            install_id: "install-1",
            machine_id_source: "registry",
            identity_scheme: "stable",
            source_label: "Stable machine",
            is_stable: true,
          },
          duplicate_warning: null,
        },
      ],
    } satisfies Awaited<ReturnType<typeof fetchAdminDevices>>);

    renderDevicePage();

    const identity = await screen.findByTestId("device-primary-identity");
    expect(identity).toHaveTextContent("ADMIN-2");
    expect(identity).toHaveAttribute("aria-label", "Основная идентификация и статус устройства");
    expect(screen.getByTestId("device-secondary-rail")).toHaveAttribute("aria-label", "Вторичный контекст устройства");
    expect(screen.getByTestId("device-page-layout")).toHaveAttribute("data-audit-layout", "identity-first");
    expect(screen.getByTestId("device-drilldown-tabs")).toHaveAttribute("data-layout", "tabbed-drilldown");
    expect(screen.getByTestId("device-drilldown-panel")).toHaveAttribute("data-active-tab", "status");
  });
});
