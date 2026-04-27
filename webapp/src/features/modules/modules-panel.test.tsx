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
    count: state.modules.length,
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

function createWorkbenchDetailPayload(state: ModulesState, moduleName: string, version: string) {
  const family = state.modules.find((item) => item.module_name === moduleName);
  const versionRecord = family?.versions.find((item) => item.version === version);
  if (!family || !versionRecord) {
    throw new Error(`Unexpected workbench detail request for ${moduleName} ${version}`);
  }

  return {
    module: {
      ...versionRecord,
      module_name: moduleName,
      sha256: `${moduleName}-${version}-sha256`,
      size: 2048,
      warnings: versionRecord.warnings_count ? ["warning"] : [],
      manifest_json: {
        module_name: moduleName,
        version,
      },
      validation_json: {
        status: versionRecord.validation_status,
      },
      tools: versionRecord.tool_ids.map((toolId) => ({ tool_name: toolId })),
      requirements: [],
      optional_requirements: [],
    },
    editable_spec: {
      module_name: moduleName,
      version,
      module_api_version: versionRecord.module_api_version ?? "1.0.0",
      owner_scope: versionRecord.owner_scope ?? "vendor",
      description: `${moduleName} ${version}`,
      platforms: [...versionRecord.platforms],
      requirements: [],
      optional_requirements: [],
      min_agent_version: null,
      entrypoint: "module:register",
      tools: versionRecord.tool_ids.map((toolId, index) => ({
        tool_name: toolId,
        aliases: [],
        method_name: `tool_${index + 1}`,
        description: "",
        params_schema: {
          type: "object",
          properties: {},
          required: [],
        },
        output_schema: {
          type: "object",
          properties: {},
        },
        presets: [],
        capabilities: [],
        metadata: {
          risk_level: "safe_read",
          tool_kind: "diagnostic",
          timeout_sec: 30,
          platforms: [...versionRecord.platforms],
          allow_roles: ["admin"],
          scopes: [],
          requires_consent: false,
          idempotent: true,
          side_effects: false,
        },
        contract_version: "1.0.0",
        dependencies: {},
        lifecycle: "stable",
        error_codes: [],
        artifact_types: [],
        redaction: {},
        resources: {
          max_runtime_sec: 30,
          max_stdout_bytes: 65536,
          max_stderr_bytes: 65536,
          max_artifact_count: 2,
          max_artifact_bytes: 5242880,
          max_subprocess_count: 2,
          allowed_filesystem_scope: [],
          allowed_external_hosts: [],
        },
        user_function_body: "return {}",
        reconstruction_strategy: "draft",
      })),
      warnings: versionRecord.warnings_count ? ["warning"] : [],
      source: {
        manifest_json_text: JSON.stringify(
          {
            module_name: moduleName,
            version,
          },
          null,
          2
        ),
        module_py_text: "def register():\n    return {}\n",
        files: [
          {
            path: "module.py",
            size_bytes: 32,
            language: "python",
            content: "def register():\n    return {}\n",
            detected_tools: [],
            parse_errors: [],
          },
        ],
        decomposition: {
          resolved_tools: versionRecord.tool_ids.length,
          unresolved_tools: [],
          available_methods: ["register"],
          available_tool_names: [...versionRecord.tool_ids],
        },
      },
    },
  };
}

function createLiveTestCandidatesPayload(moduleName = "network_ping", version = "1.2.1", platform = "win32") {
  return {
    status: "ok",
    module_name: moduleName,
    version,
    platform,
    module_platforms: ["win32", "linux"],
    min_agent_version: "1.0.0",
    candidates: [
      {
        device_id: `${platform}-agent-1`,
        hostname: platform === "linux" ? "linux-lab-01" : "win-lab-01",
        platform,
        raw_os: platform === "linux" ? "Linux" : "Windows",
        agent_version: "1.3.0",
        online: true,
        compatible: true,
        reasons: [],
        last_seen_at: "2026-04-21T10:10:00+05:00",
        last_handshake_at: "2026-04-21T10:10:00+05:00",
      },
      {
        device_id: `${platform}-agent-old`,
        hostname: `${platform}-old`,
        platform,
        raw_os: platform,
        agent_version: "0.9.0",
        online: true,
        compatible: false,
        reasons: ["AGENT_VERSION_TOO_OLD"],
        last_seen_at: "2026-04-21T09:10:00+05:00",
        last_handshake_at: "2026-04-21T09:10:00+05:00",
      },
    ],
  };
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
  it("warns that Windows drafts need a lab-agent live test before preferred rollout", async () => {
    const state = createModulesState();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url === "/api/modules/workbench" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...cloneModulesPayload(state)
          });
        }
        if (url.includes("/live_test_candidates") && method === "GET") {
          return jsonResponse(createLiveTestCandidatesPayload());
        }
        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderModulesPanel();

    fireEvent.click(await screen.findByRole("button", { name: /Новый модуль/i }));
    fireEvent.change(screen.getByRole("textbox", { name: "Platforms" }), {
      target: { value: "win32" }
    });

    expect(await screen.findByText(/Не проверено на Windows agent/i)).toBeInTheDocument();
  });

  it("lets support choose a Linux or Windows lab agent and run a module live test", async () => {
    const state = createModulesState();
    const postBodies: unknown[] = [];

    const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url === "/api/modules/workbench" && method === "GET") {
        return jsonResponse({
          status: "ok",
          ...cloneModulesPayload(state)
        });
      }

      if (url === "/api/modules/workbench/network_ping/1.2.1" && method === "GET") {
        const detail = createWorkbenchDetailPayload(state, "network_ping", "1.2.1");
        const { tool_ids: _toolIds, ...moduleWithoutToolIds } = detail.module;
        return jsonResponse({
          status: "ok",
          ...detail,
          module: moduleWithoutToolIds
        });
      }

      if (url.includes("/live_test_candidates") && method === "GET") {
        const platform = url.includes("platform=linux") ? "linux" : "win32";
        return jsonResponse(createLiveTestCandidatesPayload("network_ping", "1.2.1", platform));
      }

      if (url === "/api/modules/network_ping/1.2.1/live_tests" && method === "POST") {
        postBodies.push(JSON.parse(String(init?.body ?? "{}")));
        return jsonResponse({
          status: "ok",
          live_test: {
            status: "success",
            stage: "run",
            module_name: "network_ping",
            version: "1.2.1",
            tool_name: "network_ping.ping",
            device_id: "linux-agent-1",
            platform: "linux",
            agent_version: "1.3.0",
            trace_id: "trace-live-test-1",
            install_operation_id: "install-op-1",
            run_operation_id: "run-op-1",
            tested_at: "2026-04-21T10:20:00+05:00"
          }
        });
      }

      throw new Error(`Unexpected fetch: ${method} ${url}`);
    });

    vi.stubGlobal("fetch", fetchSpy);

    renderModulesPanel();

    expect(await screen.findByText("Lab test agent")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Test platform" }), {
      target: { value: "linux" }
    });

    expect((await screen.findAllByText(/linux-lab-01/i)).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /Запустить live test/i }));

    expect((await screen.findAllByText(/trace-live-test-1/i)).length).toBeGreaterThan(0);
    expect(postBodies).toEqual([
      {
        device_id: "linux-agent-1",
        tool_name: "network_ping.ping",
        params: {}
      }
    ]);
  });

  it("renders typed module registry in Russian and updates rollout/preferred actions", async () => {
    const state = createModulesState();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/modules/workbench" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...cloneModulesPayload(state)
          });
        }

        if (url === "/api/modules/workbench/network_ping/1.2.1" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...createWorkbenchDetailPayload(state, "network_ping", "1.2.1")
          });
        }

        if (url === "/api/modules/workbench/network_ping/1.2.0" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...createWorkbenchDetailPayload(state, "network_ping", "1.2.0")
          });
        }

        if (url === "/api/modules/workbench/observer_canary/0.9.0" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...createWorkbenchDetailPayload(state, "observer_canary", "0.9.0")
          });
        }

        if (url.includes("/live_test_candidates") && method === "GET") {
          const platform = url.includes("platform=linux") ? "linux" : "win32";
          const parts = url.split("/");
          return jsonResponse(createLiveTestCandidatesPayload(parts[3] ?? "network_ping", parts[4] ?? "1.2.1", platform));
        }

        if (url === "/api/modules/rollout_settings" && method === "PATCH") {
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
            status: "ok",
            rollout_settings: {
              ...state.rollout_settings
            }
          });
        }

        if (url === "/api/modules/network_ping/preferred" && method === "PATCH") {
          const payload = JSON.parse(String(init?.body ?? "{}")) as { version?: string | null };
          applyPreferredVersion(state, "network_ping", payload.version ?? null);
          return jsonResponse({
            status: "ok",
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

    expect(await screen.findByText("Политика preferred-rollout сохранена: Только вручную.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("Только вручную").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole("button", { name: "Сделать preferred для 1.2.1" }));

    expect(await screen.findByText(/Preferred-.*network_ping.*1\.2\.1/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/latest 1\.2\.1 .* preferred 1\.2\.1/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /observer_canary/i }));

    expect((await screen.findAllByText("Ошибка валидации")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/archive missing|Архив отсутствует/i)).length).toBeGreaterThan(0);
  });
});
