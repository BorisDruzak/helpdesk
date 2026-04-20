import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModulesPanel } from "./modules-panel";


function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}


function renderModulesPanel() {
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
      <ModulesPanel />
    </QueryClientProvider>
  );
}


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("ModulesPanel", () => {
  it("renders typed module registry in Russian and switches family detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.startsWith("/api/web/admin/modules")) {
          return jsonResponse({
            status: "success",
            data: {
              query: "",
              summary: {
                visible_count: 2,
                preferred_count: 1,
                invalid_count: 1,
                missing_files_count: 1
              },
              rollout_settings: {
                preferred_version_rollout_mode: "installed_devices",
                preferred_version_rollout_mode_label: "Обновлять установленные устройства",
                sync_after_preferred_change: false
              },
              modules: [
                {
                  module_name: "network_ping",
                  preferred_version: "1.2.0",
                  preferred_assigned: true,
                  latest_version: "1.2.1",
                  owner_scope: "vendor",
                  module_api_version: "2.0.0",
                  validation_status: "warning",
                  validation_status_label: "Есть предупреждения",
                  version_count: 2,
                  tools_count: 2,
                  platforms: ["windows_amd64", "linux_alt_x86_64"],
                  tool_ids: ["network_ping.ping", "network_ping.trace"],
                  warnings_count: 1,
                  has_missing_files: false,
                  versions: [
                    {
                      version: "1.2.1",
                      created_at: "2026-04-20T11:10:00+05:00",
                      uploaded_by: "admin",
                      manifest_version: 2,
                      module_api_version: "2.0.0",
                      owner_scope: "vendor",
                      validation_status: "warning",
                      validation_status_label: "Есть предупреждения",
                      preflight_status: "passed",
                      preflight_status_label: "Проверен",
                      is_preferred: false,
                      tools_count: 2,
                      platforms: ["windows_amd64", "linux_alt_x86_64"],
                      tool_ids: ["network_ping.ping", "network_ping.trace"],
                      warnings_count: 1,
                      file_exists: true
                    },
                    {
                      version: "1.2.0",
                      created_at: "2026-04-19T10:00:00+05:00",
                      uploaded_by: "admin",
                      manifest_version: 2,
                      module_api_version: "2.0.0",
                      owner_scope: "vendor",
                      validation_status: "passed",
                      validation_status_label: "Проверен",
                      preflight_status: "passed",
                      preflight_status_label: "Проверен",
                      is_preferred: true,
                      tools_count: 2,
                      platforms: ["windows_amd64", "linux_alt_x86_64"],
                      tool_ids: ["network_ping.ping", "network_ping.trace"],
                      warnings_count: 0,
                      file_exists: true
                    }
                  ]
                },
                {
                  module_name: "observer_canary",
                  preferred_version: null,
                  preferred_assigned: false,
                  latest_version: "0.9.0",
                  owner_scope: "internal",
                  module_api_version: "1.0.0",
                  validation_status: "failed",
                  validation_status_label: "Ошибка валидации",
                  version_count: 1,
                  tools_count: 1,
                  platforms: ["windows_amd64"],
                  tool_ids: ["observer.canary"],
                  warnings_count: 2,
                  has_missing_files: true,
                  versions: [
                    {
                      version: "0.9.0",
                      created_at: "2026-04-18T09:00:00+05:00",
                      uploaded_by: "admin",
                      manifest_version: 2,
                      module_api_version: "1.0.0",
                      owner_scope: "internal",
                      validation_status: "failed",
                      validation_status_label: "Ошибка валидации",
                      preflight_status: "failed",
                      preflight_status_label: "Ошибка валидации",
                      is_preferred: false,
                      tools_count: 1,
                      platforms: ["windows_amd64"],
                      tool_ids: ["observer.canary"],
                      warnings_count: 2,
                      file_exists: false
                    }
                  ]
                }
              ]
            }
          });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderModulesPanel();

    expect(await screen.findByRole("heading", { name: "Реестр модулей" })).toBeInTheDocument();
    expect(await screen.findByText("Семейств в срезе")).toBeInTheDocument();
    expect((await screen.findAllByText("network_ping")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Обновлять установленные устройства")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /observer_canary/i }));

    expect((await screen.findAllByText("Ошибка валидации")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Архив отсутствует, нужен повторный upload")).toBeInTheDocument();
  });
});
