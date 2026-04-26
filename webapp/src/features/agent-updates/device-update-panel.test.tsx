import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeviceUpdatePanel } from "./device-update-panel";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <DeviceUpdatePanel device={{ device_id: "linux-device-1", hostname: "ALT-01" }} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DeviceUpdatePanel", () => {
  it("shows Linux agent target, current version, rollout version and disabled offline action", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          status: "success",
          data: {
            device_id: "linux-device-1",
            device_label: "ALT-01",
            online: false,
            target: "linux_alt_x86_64",
            current_version: "3.2.0-linux.1",
            release_channel: "stable",
            is_release: true,
            summary: {
              status: "offline",
              label: "Ждёт связи",
              summary: "Linux agent is offline; update will be available after reconnect.",
            },
            recommendation: {
              update_available: true,
              recommendation_source: "assigned_rollout",
              recommendation_source_label: "Серверный rollout",
              comparison: "newer_release_available",
              comparison_label: "Назначена более новая Linux release-версия",
              recommended_reason: "assigned_rollout_newer",
              recommended_reason_label: "Для Linux агента назначен rollout stable/3.2.1-linux.1.",
              recommended_build: {
                target: "linux_alt_x86_64",
                channel: "stable",
                version: "3.2.1-linux.1",
              },
              assigned_rollout: {
                target: "linux_alt_x86_64",
                channel: "stable",
                version: "3.2.1-linux.1",
                updated_at: "2026-04-26T10:00:00+05:00",
                updated_by: "admin1",
              },
            },
            action: {
              enabled: false,
              label: "Ожидает связи",
              reason_required: true,
              endpoint: "/api/web/admin/devices/linux-device-1/updates/run",
            },
          },
        }),
      ),
    );

    renderPanel();

    expect(await screen.findByText("3.2.0-linux.1")).toBeInTheDocument();
    expect(await screen.findByText("linux_alt_x86_64")).toBeInTheDocument();
    expect(await screen.findByText("stable/3.2.1-linux.1")).toBeInTheDocument();
    expect(await screen.findByText("Для Linux агента назначен rollout stable/3.2.1-linux.1.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Ожидает связи" })).toBeDisabled();
  });
});
