import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

type ModulesState = {
  summary: {
    visible_count: number;
    preferred_count: number;
    invalid_count: number;
    missing_files_count: number;
  };
  rollout_settings: {
    preferred_version_rollout_mode: string;
    preferred_version_rollout_mode_label: string;
    sync_after_preferred_change: boolean;
  };
  modules: Array<{
    module_name: string;
    preferred_version: string | null;
    preferred_assigned: boolean;
    latest_version: string | null;
    owner_scope: string | null;
    module_api_version: string | null;
    validation_status: string;
    validation_status_label: string;
    version_count: number;
    tools_count: number;
    platforms: string[];
    tool_ids: string[];
    warnings_count: number;
    has_missing_files: boolean;
    versions: Array<{
      version: string;
      created_at: string | null;
      uploaded_by: string | null;
      manifest_version: number | null;
      module_api_version: string | null;
      owner_scope: string | null;
      validation_status: string;
      validation_status_label: string;
      preflight_status: string;
      preflight_status_label: string;
      is_preferred: boolean;
      tools_count: number;
      platforms: string[];
      tool_ids: string[];
      warnings_count: number;
      file_exists: boolean;
    }>;
  }>;
};

function getRolloutModeLabel(mode: string) {
  return mode === "installed_devices" ? "Обновлять установленные устройства" : "Только вручную";
}

function createModulesState(): ModulesState {
  return {
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
  };
}

function cloneModulesPayload(state: ModulesState) {
  return {
    query: "",
    summary: {
      visible_count: state.modules.length,
      preferred_count: state.modules.filter((item) => item.preferred_assigned).length,
      invalid_count: state.modules.filter((item) =>
        ["warning", "failed"].includes(item.validation_status)
      ).length,
      missing_files_count: state.modules.filter((item) => item.has_missing_files).length
    },
    rollout_settings: {
      ...state.rollout_settings
    },
    modules: state.modules.map((moduleFamily) => ({
      ...moduleFamily,
      platforms: [...moduleFamily.platforms],
      tool_ids: [...moduleFamily.tool_ids],
      versions: moduleFamily.versions.map((version) => ({
        ...version,
        platforms: [...version.platforms],
        tool_ids: [...version.tool_ids]
      }))
    }))
  };
}

function applyPreferredVersion(state: ModulesState, moduleName: string, version: string | null) {
  const family = state.modules.find((item) => item.module_name === moduleName);
  if (!family) {
    throw new Error(`Unexpected module ${moduleName}`);
  }

  family.preferred_version = version;
  family.preferred_assigned = version !== null;
  family.versions = family.versions.map((item) => ({
    ...item,
    is_preferred: version !== null && item.version === version
  }));
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
  it("renders typed module registry in Russian and updates rollout/preferred actions", async () => {
    const state = createModulesState();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/modules" && method === "GET") {
          return jsonResponse({
            status: "success",
            data: cloneModulesPayload(state)
          });
        }

        if (url === "/api/web/admin/modules/rollout_settings" && method === "PATCH") {
          const payload = JSON.parse(String(init?.body ?? "{}")) as {
            preferred_version_rollout_mode?: string;
            sync_after_preferred_change?: boolean;
          };
          state.rollout_settings.preferred_version_rollout_mode =
            payload.preferred_version_rollout_mode ?? state.rollout_settings.preferred_version_rollout_mode;
          state.rollout_settings.preferred_version_rollout_mode_label = getRolloutModeLabel(
            state.rollout_settings.preferred_version_rollout_mode
          );
          state.rollout_settings.sync_after_preferred_change =
            payload.sync_after_preferred_change ?? state.rollout_settings.sync_after_preferred_change;
          return jsonResponse({
            status: "success",
            data: {
              ...state.rollout_settings
            }
          });
        }

        if (url === "/api/web/admin/modules/network_ping/preferred" && method === "PATCH") {
          const payload = JSON.parse(String(init?.body ?? "{}")) as { version?: string | null };
          applyPreferredVersion(state, "network_ping", payload.version ?? null);
          return jsonResponse({
            status: "success",
            data: {
              module_name: "network_ping",
              preferred_version: payload.version ?? null,
              updated_at: "2026-04-21T10:15:00+05:00",
              updated_by: "admin",
              message:
                payload.version === null
                  ? "Preferred-версия для network_ping снята."
                  : `Preferred-версия для network_ping обновлена на ${payload.version}.`,
              rollout_summary:
                payload.version === null
                  ? {
                      mode: state.rollout_settings.preferred_version_rollout_mode,
                      should_sync: state.rollout_settings.sync_after_preferred_change,
                      desired_updates: 0,
                      sync_enqueued: 0,
                      refresh_enqueued: 0
                    }
                  : {
                      mode: state.rollout_settings.preferred_version_rollout_mode,
                      should_sync: state.rollout_settings.sync_after_preferred_change,
                      desired_updates: 2,
                      sync_enqueued: state.rollout_settings.sync_after_preferred_change ? 2 : 0,
                      refresh_enqueued: state.rollout_settings.sync_after_preferred_change ? 2 : 0
                    }
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderModulesPanel();

    expect(await screen.findByRole("heading", { name: "Реестр модулей" })).toBeInTheDocument();
    expect(await screen.findByText("Семейств в срезе")).toBeInTheDocument();
    expect((await screen.findAllByText("network_ping")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Обновлять установленные устройства")).length).toBeGreaterThan(0);

    fireEvent.change(screen.getByRole("combobox", { name: "Режим preferred-rollout" }), {
      target: { value: "manual" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить политику" }));

    expect(await screen.findByText("Политика раскатки сохранена: Только вручную.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("Только вручную").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole("button", { name: "Сделать preferred для 1.2.1" }));

    expect(await screen.findByText("Preferred-версия для network_ping обновлена на 1.2.1.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Preferred:\s*1\.2\.1/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /observer_canary/i }));

    expect((await screen.findAllByText("Ошибка валидации")).length).toBeGreaterThan(0);
    expect(
      await screen.findByText("Архив отсутствует, нужен повторный upload")
    ).toBeInTheDocument();
  });
});
