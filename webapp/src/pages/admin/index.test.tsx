import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminWorkspacePage } from "./index";

const realtimeClientMock = {
  subscribeTicket: vi.fn(() => () => {}),
  subscribeDevice: vi.fn(() => () => {}),
  dispose: vi.fn(),
};

vi.mock("../../shared/realtime/client", () => ({
  getSharedWebRealtimeClient: () => realtimeClientMock,
}));

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

type ModulesState = {
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

type FormsState = {
  summary: {
    pack_key: string;
    version: string;
    title: string;
    description: string;
    forms_count: number;
    fields_count: number;
    required_fields_count: number;
    last_published_at: string;
    last_published_by: string;
  };
  forms: Array<{
    key: string;
    request_kind: string;
    title: string;
    description: string;
    fields: Array<{
      key: string;
      label: string;
      type: string;
      type_label: string;
      required: boolean;
      placeholder: string;
      help_text: string;
      options: Array<{ value: string; label: string }>;
      visible_when: {
        field: string;
        equals: string | null;
        values: string[];
      } | null;
    }>;
  }>;
};

function getRolloutModeLabel(mode: string) {
  return mode === "installed_devices" ? "Обновлять установленные устройства" : "Только вручную";
}

function createModulesState(): ModulesState {
  return {
    rollout_settings: {
      preferred_version_rollout_mode: "installed_devices",
      preferred_version_rollout_mode_label: "Обновлять установленные устройства",
      sync_after_preferred_change: false,
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
            file_exists: true,
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
            file_exists: true,
          },
        ],
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
            file_exists: false,
          },
        ],
      },
    ],
  };
}

function cloneModulesPayload(state: ModulesState) {
  return {
    query: "",
    count: state.modules.length,
    rollout_settings: {
      ...state.rollout_settings,
    },
    modules: state.modules.map((moduleFamily) => ({
      ...moduleFamily,
      platforms: [...moduleFamily.platforms],
      tool_ids: [...moduleFamily.tool_ids],
      versions: moduleFamily.versions.map((version) => ({
        ...version,
        platforms: [...version.platforms],
        tool_ids: [...version.tool_ids],
      })),
    })),
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
    is_preferred: version !== null && item.version === version,
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
          2,
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

function createFormsState(): FormsState {
  return {
    summary: {
      pack_key: "request_forms",
      version: "1.0.3",
      title: "Каталог заявок",
      description: "Рабочий каталог",
      forms_count: 1,
      fields_count: 2,
      required_fields_count: 1,
      last_published_at: "2026-04-21T10:00:00+05:00",
      last_published_by: "admin1",
    },
    forms: [
      {
        key: "printer",
        request_kind: "printer",
        title: "Печать / принтер",
        description: "Проблемы печати",
        fields: [
          {
            key: "room",
            label: "Кабинет",
            type: "text",
            type_label: "Текст",
            required: true,
            placeholder: "",
            help_text: "",
            options: [],
            visible_when: null,
          },
          {
            key: "printer_model",
            label: "Модель",
            type: "text",
            type_label: "Текст",
            required: false,
            placeholder: "",
            help_text: "",
            options: [],
            visible_when: null,
          },
        ],
      },
    ],
  };
}

function cloneFormsCatalogPayload(state: FormsState) {
  return {
    summary: {
      ...state.summary,
    },
    capabilities: {
      current_endpoint: "/api/web/admin/forms/current",
      save_endpoint: "/api/web/admin/forms/save",
      preview_endpoint: "/api/web/admin/forms/route-preview",
      field_type_options: [
        { value: "text", label: "Текст" },
        { value: "textarea", label: "Большой текст" },
        { value: "select", label: "Список" },
        { value: "radio", label: "Переключатель" },
        { value: "checkbox", label: "Флажок" },
      ],
    },
    forms: state.forms.map((form) => ({
      ...form,
      fields: form.fields.map((field) => ({ ...field })),
    })),
  };
}

function cloneFormsVersionsPayload(state: FormsState) {
  return {
    status: "ok" as const,
    pack_key: "request_forms",
    current: {
      pack_key: "request_forms",
      version: state.summary.version,
      title: state.summary.title,
      description: state.summary.description,
      forms_count: state.summary.forms_count,
      fields_count: state.summary.fields_count,
      required_fields_count: state.summary.required_fields_count,
      created_at: state.summary.last_published_at,
      created_by: state.summary.last_published_by,
      is_preferred: true,
    },
    preferred: {
      pack_key: "request_forms",
      version: state.summary.version,
      updated_at: state.summary.last_published_at,
      updated_by: state.summary.last_published_by,
    },
    packs: [
      {
        pack_key: "request_forms",
        version: state.summary.version,
        title: state.summary.title,
        description: state.summary.description,
        forms_count: state.summary.forms_count,
        fields_count: state.summary.fields_count,
        required_fields_count: state.summary.required_fields_count,
        created_at: state.summary.last_published_at,
        created_by: state.summary.last_published_by,
        is_preferred: true,
      },
    ],
  };
}

function createTraceItem(params: {
  traceId: string;
  rootKind: string;
  rootKindLabel: string;
  status: string;
  statusLabel: string;
  ticketId: string | null;
  deviceId: string;
  operationId: string;
  durationMs: number;
  errorCount: number;
  spanCount: number;
  startedAt: string;
  finishedAt: string;
}) {
  return {
    trace_id: params.traceId,
    root_span_id: `root-${params.traceId}`,
    root_kind: params.rootKind,
    root_kind_label: params.rootKindLabel,
    status: params.status,
    status_label: params.statusLabel,
    ticket_id: params.ticketId,
    device_id: params.deviceId,
    operation_id: params.operationId,
    job_id: null,
    duration_ms: params.durationMs,
    error_count: params.errorCount,
    span_count: params.spanCount,
    started_at: params.startedAt,
    finished_at: params.finishedAt,
    attrs_json: {
      flow: params.rootKind,
    },
  };
}

function createObserverRuntimePayload() {
  return {
    status: "ok" as const,
    runtime: {
      enabled: true,
      running: true,
      stats: {
        queued_spans: 1,
        projected_traces: 12,
      },
      settings: {
        success_trace_sample_rate: 0.35,
      },
      health: {
        status: "ok",
        issues: [],
      },
    },
  };
}

function createObserverSettingsPayload() {
  return {
    status: "ok" as const,
    settings: {
      success_trace_sample_rate: 0.35,
      ok_trace_retention_hours: 24,
      error_trace_retention_hours: 168,
      historical_backfill_enabled: true,
      action_sync_enabled: true,
      action_sync_limit: 120,
      always_keep_root_kinds: ["ticket", "agent_update", "module_install", "consent"],
    },
  };
}

function renderAdminPage() {
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
      <AdminWorkspacePage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminWorkspacePage", () => {
  it("renders real admin workbench slices and keeps modules/forms/observer flows functional", async () => {
    const modulesState = createModulesState();
    const formsState = createFormsState();
    const saveCalls: unknown[] = [];

    const traceUpdate = createTraceItem({
      traceId: "trace-update-1",
      rootKind: "agent_update",
      rootKindLabel: "Обновление агента",
      status: "failed",
      statusLabel: "Ошибка",
      ticketId: "ticket-1",
      deviceId: "device-1",
      operationId: "op-update-1",
      durationMs: 6400,
      errorCount: 1,
      spanCount: 6,
      startedAt: "2026-04-20T11:24:00+05:00",
      finishedAt: "2026-04-20T11:24:06+05:00",
    });

    const traceLinux = createTraceItem({
      traceId: "trace-linux-1",
      rootKind: "tool_call",
      rootKindLabel: "Инструмент",
      status: "succeeded",
      statusLabel: "Успешно",
      ticketId: null,
      deviceId: "device-2",
      operationId: "op-linux-1",
      durationMs: 1200,
      errorCount: 0,
      spanCount: 2,
      startedAt: "2026-04-20T11:00:00+05:00",
      finishedAt: "2026-04-20T11:00:01+05:00",
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/bootstrap") {
          return jsonResponse({
            status: "success",
            data: {
              workspace: "admin",
              features: [
                "devices_inventory",
                "agent_rollout",
                "modules_workbench",
                "forms_builder",
                "tech_panel",
              ],
              observer: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
              },
            },
          });
        }

        if (url === "/api/web/admin/devices") {
          return jsonResponse({
            status: "success",
            data: {
              query: "",
              status_filter: "all",
              summary: {
                visible_count: 2,
                online_count: 1,
                rollout_targets: 2,
              },
              filters: {
                status_options: [
                  { value: "all", label: "Все устройства" },
                  { value: "online", label: "Только онлайн" },
                  { value: "offline", label: "Только оффлайн" },
                ],
              },
              rollout: [
                {
                  target: "windows_amd64",
                  channel: "stable",
                  version: "2.4.1",
                  updated_at: "2026-04-20T11:20:00+05:00",
                  updated_by: "admin1",
                },
                {
                  target: "linux_alt_x86_64",
                  channel: "stable",
                  version: "2.3.9",
                  updated_at: "2026-04-20T10:55:00+05:00",
                  updated_by: "admin1",
                },
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
                    summary: "Устройство на шаг позади rollout",
                  },
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
                    summary: "Назначен rollout stable/2.3.9",
                  },
                },
              ],
            },
          });
        }

        if (url === "/api/web/admin/modules/workbench" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...cloneModulesPayload(modulesState),
          });
        }

        if (url === "/api/web/admin/modules/workbench/network_ping/1.2.1" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...createWorkbenchDetailPayload(modulesState, "network_ping", "1.2.1"),
          });
        }

        if (url === "/api/web/admin/modules/workbench/network_ping/1.2.0" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...createWorkbenchDetailPayload(modulesState, "network_ping", "1.2.0"),
          });
        }

        if (url === "/api/web/admin/modules/workbench/observer_canary/0.9.0" && method === "GET") {
          return jsonResponse({
            status: "ok",
            ...createWorkbenchDetailPayload(modulesState, "observer_canary", "0.9.0"),
          });
        }

        if (url === "/api/web/admin/modules/rollout_settings" && method === "PATCH") {
          const payload = JSON.parse(String(init?.body ?? "{}")) as {
            preferred_version_rollout_mode?: string;
            sync_after_preferred_change?: boolean;
          };
          modulesState.rollout_settings.preferred_version_rollout_mode =
            payload.preferred_version_rollout_mode ??
            modulesState.rollout_settings.preferred_version_rollout_mode;
          modulesState.rollout_settings.preferred_version_rollout_mode_label = getRolloutModeLabel(
            modulesState.rollout_settings.preferred_version_rollout_mode,
          );
          modulesState.rollout_settings.sync_after_preferred_change =
            payload.sync_after_preferred_change ??
            modulesState.rollout_settings.sync_after_preferred_change;
          return jsonResponse({
            status: "ok",
            rollout_settings: {
              ...modulesState.rollout_settings,
            },
          });
        }

        if (url === "/api/web/admin/modules/network_ping/preferred" && method === "PATCH") {
          const payload = JSON.parse(String(init?.body ?? "{}")) as { version?: string | null };
          applyPreferredVersion(modulesState, "network_ping", payload.version ?? null);
          return jsonResponse({
            status: "ok",
            module_name: "network_ping",
            preferred_version: payload.version ?? null,
            updated_at: "2026-04-21T10:15:00+05:00",
            updated_by: "admin",
            message:
              payload.version === null
                ? "Preferred-версия снята для network_ping."
                : `Preferred-версия обновлена: network_ping → ${payload.version}.`,
            rollout_summary:
              payload.version === null
                ? {
                    mode: modulesState.rollout_settings.preferred_version_rollout_mode,
                    should_sync: modulesState.rollout_settings.sync_after_preferred_change,
                    desired_updates: 0,
                    sync_enqueued: 0,
                    refresh_enqueued: 0,
                  }
                : {
                    mode: modulesState.rollout_settings.preferred_version_rollout_mode,
                    should_sync: modulesState.rollout_settings.sync_after_preferred_change,
                    desired_updates: 2,
                    sync_enqueued: modulesState.rollout_settings.sync_after_preferred_change ? 2 : 0,
                    refresh_enqueued: modulesState.rollout_settings.sync_after_preferred_change ? 2 : 0,
                  },
          });
        }

        if (url === "/api/web/admin/forms/current" && method === "GET") {
          return jsonResponse({
            status: "success",
            data: cloneFormsCatalogPayload(formsState),
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms" && method === "GET") {
          return jsonResponse(cloneFormsVersionsPayload(formsState));
        }

        if (url === "/api/web/admin/forms/save" && method === "POST") {
          const payload = JSON.parse(String(init?.body ?? "{}")) as {
            title: string;
            description: string;
            forms: Array<{
              key: string;
              request_kind: string;
              title: string;
              description?: string;
              fields: Array<{
                key: string;
                label: string;
                type: string;
                required: boolean;
                placeholder?: string;
                help_text?: string;
                options?: Array<{ value: string; label: string }>;
                visible_when?: { field: string; equals?: string; values?: string[] };
              }>;
            }>;
          };
          saveCalls.push(payload);
          formsState.summary = {
            ...formsState.summary,
            version: "1.0.4",
            title: payload.title,
            description: payload.description,
            forms_count: payload.forms.length,
            fields_count: payload.forms.reduce((total, form) => total + form.fields.length, 0),
            required_fields_count: payload.forms.reduce(
              (total, form) => total + form.fields.filter((field) => field.required).length,
              0,
            ),
            last_published_at: "2026-04-21T12:30:00+05:00",
          };
          formsState.forms = payload.forms.map((form) => ({
            key: form.key,
            request_kind: form.request_kind,
            title: form.title,
            description: form.description ?? "",
            fields: form.fields.map((field) => ({
              key: field.key,
              label: field.label,
              type: field.type,
              type_label:
                field.type === "textarea"
                  ? "Большой текст"
                  : field.type === "select"
                    ? "Список"
                    : field.type === "radio"
                      ? "Переключатель"
                      : field.type === "checkbox"
                        ? "Флажок"
                        : "Текст",
              required: field.required,
              placeholder: field.placeholder ?? "",
              help_text: field.help_text ?? "",
              options: field.options ?? [],
              visible_when: field.visible_when
                ? {
                    field: field.visible_when.field,
                    equals: field.visible_when.equals ?? null,
                    values: field.visible_when.values ?? [],
                  }
                : null,
            })),
          }));
          return jsonResponse({
            status: "success",
            data: {
              ...cloneFormsCatalogPayload(formsState),
              message:
                "Каталог опубликован как версия 1.0.4. Изменения уже активны в /help и в интерфейсе агента.",
            },
          });
        }

        if (url === "/api/web/admin/observer/quick?device_id=device-1&lookback_hours=24") {
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                lookback_hours: 24,
                recent_trace_count: 9,
                hot_trace_count: 2,
                signature_count: 1,
                degradation_group_count: 1,
                dangerous_flow_count: 1,
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "ok",
                health_status_label: "Норма",
                pending_trace_count: 1,
                last_projected_at: "2026-04-20T11:28:00+05:00",
                issues: [],
              },
              hot_traces: [traceUpdate],
              top_signatures: [
                {
                  error_signature: "sig-1",
                  title: "Launcher signature mismatch",
                  tool_name: "update",
                  component: "agent_update",
                  occurrences_count: 4,
                  affected_devices_count: 2,
                  last_seen_at: "2026-04-20T11:25:00+05:00",
                },
              ],
              top_degradations: [
                {
                  operation_kind: "agent_update",
                  operation_kind_label: "Обновление агента",
                  tool_name: "update",
                  operations_count: 4,
                  timeout_count: 0,
                  retried_operations_count: 0,
                  slow_operations_count: 1,
                  max_duration_ms: 21800,
                  latest_operation_at: "2026-04-20T11:25:00+05:00",
                },
              ],
              dangerous_flows: [
                {
                  root_kind: "agent_update",
                  root_kind_label: "Обновление агента",
                  operations_count: 1,
                  error_count: 1,
                  timeout_count: 0,
                  retried_count: 0,
                  active_count: 0,
                  latest_operation_at: "2026-04-20T11:24:06+05:00",
                },
              ],
              links: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/web/admin/observer/runtime",
              },
            },
          });
        }

        if (url === "/api/web/admin/observer/quick?device_id=device-2&lookback_hours=24") {
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                lookback_hours: 24,
                recent_trace_count: 2,
                hot_trace_count: 1,
                signature_count: 0,
                degradation_group_count: 0,
                dangerous_flow_count: 0,
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "ok",
                health_status_label: "Норма",
                pending_trace_count: 0,
                last_projected_at: "2026-04-20T11:20:00+05:00",
                issues: [],
              },
              hot_traces: [traceLinux],
              top_signatures: [],
              top_degradations: [],
              dangerous_flows: [],
              links: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/web/admin/observer/runtime",
              },
            },
          });
        }

        if (url === "/api/web/admin/observer/quick?device_id=device-2&lookback_hours=72") {
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                lookback_hours: 72,
                recent_trace_count: 14,
                hot_trace_count: 3,
                signature_count: 2,
                degradation_group_count: 2,
                dangerous_flow_count: 2,
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "degraded",
                health_status_label: "Есть отставание",
                pending_trace_count: 6,
                last_projected_at: "2026-04-20T10:45:00+05:00",
                issues: ["pending_backlog"],
              },
              hot_traces: [traceLinux],
              top_signatures: [],
              top_degradations: [],
              dangerous_flows: [],
              links: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/web/admin/observer/runtime",
              },
            },
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-1&lookback_hours=24&limit=40") {
          return jsonResponse({
            status: "success",
            data: {
              query: {
                device_id: "device-1",
                lookback_hours: 24,
                status_filter: "all",
                root_kind_filter: "all",
                limit: 40,
              },
              summary: {
                visible_count: 1,
                active_count: 0,
                error_count: 1,
                selected_trace_id: "trace-update-1",
              },
              filters: {
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "failed", label: "Ошибки" },
                ],
                root_kind_options: [
                  { value: "all", label: "Все корни" },
                  { value: "agent_update", label: "Обновление агента" },
                ],
              },
              traces: [traceUpdate],
              links: {
                detail_endpoint_template: "/api/web/admin/observer/trace-detail/{trace_id}",
                runtime_endpoint: "/api/web/admin/observer/runtime",
              },
            },
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-2&lookback_hours=24&limit=40") {
          return jsonResponse({
            status: "success",
            data: {
              query: {
                device_id: "device-2",
                lookback_hours: 24,
                status_filter: "all",
                root_kind_filter: "all",
                limit: 40,
              },
              summary: {
                visible_count: 1,
                active_count: 0,
                error_count: 0,
                selected_trace_id: "trace-linux-1",
              },
              filters: {
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "succeeded", label: "Успешно" },
                ],
                root_kind_options: [
                  { value: "all", label: "Все корни" },
                  { value: "tool_call", label: "Инструмент" },
                ],
              },
              traces: [traceLinux],
              links: {
                detail_endpoint_template: "/api/web/admin/observer/trace-detail/{trace_id}",
                runtime_endpoint: "/api/web/admin/observer/runtime",
              },
            },
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-2&lookback_hours=72&limit=40") {
          return jsonResponse({
            status: "success",
            data: {
              query: {
                device_id: "device-2",
                lookback_hours: 72,
                status_filter: "all",
                root_kind_filter: "all",
                limit: 40,
              },
              summary: {
                visible_count: 1,
                active_count: 0,
                error_count: 0,
                selected_trace_id: "trace-linux-1",
              },
              filters: {
                status_options: [
                  { value: "all", label: "Все статусы" },
                  { value: "succeeded", label: "Успешно" },
                ],
                root_kind_options: [
                  { value: "all", label: "Все корни" },
                  { value: "tool_call", label: "Инструмент" },
                ],
              },
              traces: [traceLinux],
              links: {
                detail_endpoint_template: "/api/web/admin/observer/trace-detail/{trace_id}",
                runtime_endpoint: "/api/web/admin/observer/runtime",
              },
            },
          });
        }

        if (
          url === "/api/web/admin/observer/trace-detail/trace-update-1" ||
          url === "/api/web/admin/observer/trace-detail/trace-update-1?include_agent_actions=1&action_limit=120"
        ) {
          return jsonResponse({
            status: "ok",
            trace: traceUpdate,
            summary: {
              span_count: 6,
              error_count: 1,
              linked_trace_count: 1,
            },
            spans: [
              {
                span_id: "span-update-root",
                trace_id: "trace-update-1",
                parent_span_id: null,
                source_type: "operation",
                source_ref: "op-update-1",
                name: "agent.update.run",
                kind: "server",
                component: "agent_update",
                event_type: "operation.stage.failed",
                module_name: null,
                tool_name: "update",
                status: "failed",
                status_label: "Ошибка",
                started_at: "2026-04-20T11:24:00+05:00",
                finished_at: "2026-04-20T11:24:06+05:00",
                duration_ms: 6400,
                attrs_json: {},
              },
            ],
            span_links: [
              {
                id: 1,
                span_id: "span-update-root",
                linked_trace_id: "trace-runtime-audit-1",
                linked_span_id: "span-runtime-audit-1",
                reason: "operation_id_bridge",
                attrs_json: {},
                created_at: "2026-04-20T11:24:06+05:00",
              },
            ],
            error_occurrences: [
              {
                occurrence_id: "occ-1",
                trace_id: "trace-update-1",
                span_id: "span-update-root",
                error_signature: "sig-1",
                device_id: "device-1",
                ticket_id: "ticket-1",
                operation_id: "op-update-1",
                component: "agent_update",
                module_name: null,
                tool_name: "update",
                error_kind: "validation",
                exception_type: "RuntimeError",
                failure_stage: "download",
                severity: "error",
                severity_label: "Ошибка",
                message_norm: "Launcher signature mismatch",
                attrs_json: {},
                created_at: "2026-04-20T11:24:06+05:00",
              },
            ],
            agent_actions: [
              {
                kind: "agent_runtime_audit",
                status: "ok",
                summary: "handshake confirmed",
              },
            ],
            observer_settings: {
              action_sync_enabled: true,
              action_sync_limit: 120,
            },
          });
        }

        if (
          url === "/api/web/admin/observer/trace-detail/trace-linux-1" ||
          url === "/api/web/admin/observer/trace-detail/trace-linux-1?include_agent_actions=1&action_limit=120"
        ) {
          return jsonResponse({
            status: "ok",
            trace: traceLinux,
            summary: {
              span_count: 2,
              error_count: 0,
              linked_trace_count: 0,
            },
            spans: [
              {
                span_id: "span-linux-root",
                trace_id: "trace-linux-1",
                parent_span_id: null,
                source_type: "tool_call",
                source_ref: "op-linux-1",
                name: "system.collect",
                kind: "server",
                component: "tool_runtime",
                event_type: "tool_call_result",
                module_name: "system",
                tool_name: "collect",
                status: "succeeded",
                status_label: "Успешно",
                started_at: "2026-04-20T11:00:00+05:00",
                finished_at: "2026-04-20T11:00:01+05:00",
                duration_ms: 1200,
                attrs_json: {},
              },
            ],
            span_links: [],
            error_occurrences: [],
            agent_actions: [],
            observer_settings: {
              action_sync_enabled: true,
              action_sync_limit: 120,
            },
          });
        }

        if (
          url ===
          "/api/web/admin/observer/diagnostics/bundle?lookback_hours=24&limit=20&trace_id=trace-update-1&include_agent_actions=1&action_limit=80"
        ) {
          return jsonResponse({
            status: "ok",
            summary: {
              primary_trace_id: "trace-update-1",
              related_trace_count: 1,
              span_count: 6,
              error_count: 1,
              agent_action_count: 1,
              agent_audit_count: 1,
              recent_log_count: 2,
            },
            primary_trace: traceUpdate,
            related_traces: [traceUpdate],
            spans: [
              {
                span_id: "span-update-root",
                trace_id: "trace-update-1",
                parent_span_id: null,
                source_type: "operation",
                source_ref: "op-update-1",
                name: "agent.update.run",
                kind: "server",
                component: "agent_update",
                event_type: "operation.stage.failed",
                module_name: null,
                tool_name: "update",
                status: "failed",
                status_label: "РћС€РёР±РєР°",
                started_at: "2026-04-20T11:24:00+05:00",
                finished_at: "2026-04-20T11:24:06+05:00",
                duration_ms: 6400,
                attrs_json: {},
              },
            ],
            span_links: [
              {
                id: 1,
                span_id: "span-update-root",
                linked_trace_id: "trace-runtime-audit-1",
                linked_span_id: "span-runtime-audit-1",
                reason: "operation_id_bridge",
                attrs_json: {},
                created_at: "2026-04-20T11:24:06+05:00",
              },
            ],
            error_occurrences: [],
            agent_actions: [
              {
                action: "handshake.confirmed",
                source: "agent_runtime_audit",
                status: "ok",
                summary: "handshake confirmed",
                operation_id: "operation_id_bridge",
              },
            ],
            recommended_next_checks: ["РџСЂРѕРІРµСЂРёС‚СЊ rollout Рё РїРѕРґРїРёСЃСЊ launcher"],
            links: {
              trace_detail: "/api/web/admin/observer/trace-detail/trace-update-1",
            },
          });
        }

        if (url === "/api/web/admin/observer/signatures?device_id=device-1&lookback_hours=24&limit=40") {
          return jsonResponse({
            status: "ok",
            signatures: [
              {
                error_signature: "sig-1",
                title: "Launcher signature mismatch",
                component: "agent_update",
                module_name: null,
                tool_name: "update",
                occurrences_count: 4,
                affected_devices_count: 2,
                last_seen_at: "2026-04-20T11:25:00+05:00",
                first_seen_at: "2026-04-20T10:10:00+05:00",
              },
            ],
          });
        }

        if (url === "/api/web/admin/observer/signatures?device_id=device-2&lookback_hours=24&limit=40") {
          return jsonResponse({
            status: "ok",
            signatures: [],
          });
        }

        if (url === "/api/web/admin/observer/signatures?device_id=device-2&lookback_hours=72&limit=40") {
          return jsonResponse({
            status: "ok",
            signatures: [
              {
                error_signature: "sig-linux-1",
                title: "ALT agent timeout",
                component: "agent_runtime",
                module_name: null,
                tool_name: "sync",
                occurrences_count: 2,
                affected_devices_count: 1,
                last_seen_at: "2026-04-20T09:20:00+05:00",
                first_seen_at: "2026-04-20T09:10:00+05:00",
              },
            ],
          });
        }

        if (url === "/api/web/admin/observer/signatures/sig-1") {
          return jsonResponse({
            status: "ok",
            signature: {
              error_signature: "sig-1",
              title: "Launcher signature mismatch",
              component: "agent_update",
              module_name: null,
              tool_name: "update",
              occurrences_count: 4,
              affected_devices_count: 2,
              last_seen_at: "2026-04-20T11:25:00+05:00",
              first_seen_at: "2026-04-20T10:10:00+05:00",
            },
            occurrences: [
              {
                occurrence_id: "occ-1",
                trace_id: "trace-update-1",
                span_id: "span-update-root",
                device_id: "device-1",
                ticket_id: "ticket-1",
                operation_id: "op-update-1",
                component: "agent_update",
                module_name: null,
                tool_name: "update",
                error_kind: "validation",
                exception_type: "RuntimeError",
                failure_stage: "download",
                severity: "error",
                severity_label: "Ошибка",
                message_norm: "Launcher signature mismatch",
                created_at: "2026-04-20T11:24:06+05:00",
              },
            ],
          });
        }

        if (url === "/api/web/admin/observer/signatures/sig-linux-1") {
          return jsonResponse({
            status: "ok",
            signature: {
              error_signature: "sig-linux-1",
              title: "ALT agent timeout",
              component: "agent_runtime",
              module_name: null,
              tool_name: "sync",
              occurrences_count: 2,
              affected_devices_count: 1,
              last_seen_at: "2026-04-20T09:20:00+05:00",
              first_seen_at: "2026-04-20T09:10:00+05:00",
            },
            occurrences: [],
          });
        }

        if (url === "/api/web/admin/observer/degradations?device_id=device-1&lookback_hours=24&limit=40") {
          return jsonResponse({
            status: "ok",
            items: [
              {
                operation_kind: "agent_update",
                operation_kind_label: "Обновление агента",
                tool_name: "update",
                module_name: "agent_update",
                operations_count: 4,
                timeout_count: 0,
                timeout_rate: 0,
                retried_operations_count: 0,
                retry_rate: 0,
                slow_operations_count: 1,
                slow_rate: 0.25,
                avg_duration_ms: 9100,
                max_duration_ms: 21800,
                latest_operation_at: "2026-04-20T11:25:00+05:00",
                sample_trace_ids: ["trace-update-1"],
              },
            ],
          });
        }

        if (url === "/api/web/admin/observer/degradations?device_id=device-2&lookback_hours=24&limit=40") {
          return jsonResponse({
            status: "ok",
            items: [],
          });
        }

        if (url === "/api/web/admin/observer/degradations?device_id=device-2&lookback_hours=72&limit=40") {
          return jsonResponse({
            status: "ok",
            items: [
              {
                operation_kind: "tool_call",
                operation_kind_label: "Инструмент",
                tool_name: "sync",
                module_name: "agent_runtime",
                operations_count: 3,
                timeout_count: 1,
                timeout_rate: 0.33,
                retried_operations_count: 1,
                retry_rate: 0.33,
                slow_operations_count: 2,
                slow_rate: 0.66,
                avg_duration_ms: 4100,
                max_duration_ms: 12100,
                latest_operation_at: "2026-04-20T09:20:00+05:00",
                sample_trace_ids: ["trace-linux-1"],
              },
            ],
          });
        }

        if (url === "/api/web/admin/observer/runtime" && method === "GET") {
          return jsonResponse(createObserverRuntimePayload());
        }

        if (url === "/api/web/admin/observer/settings" && method === "GET") {
          return jsonResponse(createObserverSettingsPayload());
        }

        if (url === "/api/web/admin/devices/device-1/updates") {
          return jsonResponse({
            status: "success",
            data: {
              device_id: "device-1",
              device_label: "WS-01",
              online: true,
              target: "windows_amd64",
              current_version: "2.4.0",
              release_channel: "stable",
              is_release: true,
              summary: {
                status: "update_available",
                label: "Доступно обновление",
                summary: "Серверный rollout рекомендует stable/2.4.1.",
              },
              recommendation: {
                update_available: true,
                recommendation_source: "assigned_rollout",
                recommendation_source_label: "Серверный rollout",
                comparison: "newer_release_available",
                comparison_label: "Назначена более новая release-версия",
                recommended_reason: "assigned_rollout_newer",
                recommended_reason_label: "Назначенный rollout новее текущей версии.",
                recommended_build: {
                  target: "windows_amd64",
                  channel: "stable",
                  version: "2.4.1",
                },
                assigned_rollout: {
                  target: "windows_amd64",
                  channel: "stable",
                  version: "2.4.1",
                  updated_at: "2026-04-20T11:20:00+05:00",
                  updated_by: "admin1",
                },
              },
              action: {
                enabled: true,
                label: "Запустить обновление",
                reason_required: true,
                endpoint: "/api/web/admin/devices/device-1/updates/run",
              },
            },
          });
        }

        if (url === "/api/web/admin/devices/device-2/updates") {
          return jsonResponse({
            status: "success",
            data: {
              device_id: "device-2",
              device_label: "LT-02",
              online: false,
              target: "linux_alt_x86_64",
              current_version: "2.3.7",
              release_channel: "stable",
              is_release: true,
              summary: {
                status: "offline",
                label: "Ждёт связи",
                summary: "Запуск обновления доступен только когда агент онлайн и может принять команду.",
              },
              recommendation: {
                update_available: true,
                recommendation_source: "assigned_rollout",
                recommendation_source_label: "Серверный rollout",
                comparison: "newer_release_available",
                comparison_label: "Назначена более новая release-версия",
                recommended_reason: "assigned_rollout_newer",
                recommended_reason_label: "Назначенный rollout новее текущей версии.",
                recommended_build: {
                  target: "linux_alt_x86_64",
                  channel: "stable",
                  version: "2.3.9",
                },
                assigned_rollout: {
                  target: "linux_alt_x86_64",
                  channel: "stable",
                  version: "2.3.9",
                  updated_at: "2026-04-20T10:55:00+05:00",
                  updated_by: "admin1",
                },
              },
              action: {
                enabled: false,
                label: "Ожидает связи",
                reason_required: true,
                endpoint: "/api/web/admin/devices/device-2/updates/run",
              },
            },
          });
        }

        if (url === "/api/web/admin/devices/device-1/updates/run" && method === "POST") {
          return jsonResponse({
            status: "success",
            data: {
              device_id: "device-1",
              operation_id: "op-admin-update-001",
              status: "queued",
              message: "Операция op-admin-update-001 поставлена в очередь.",
              build_source: "assigned_rollout",
              poll_url: "/api/operations/op-admin-update-001",
              build: {
                target: "windows_amd64",
                channel: "stable",
                version: "2.4.1",
              },
            },
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      }),
    );

    renderAdminPage();

    expect(await screen.findByRole("heading", { name: "Рабочее место администрирования" })).toBeInTheDocument();
    expect(await screen.findByText("Всего в инвентаре")).toBeInTheDocument();
    expect((await screen.findAllByText("Назначения rollout")).length).toBeGreaterThan(0);
    expect(await screen.findByRole("button", { name: /WS-01/i })).toBeInTheDocument();
    expect((await screen.findAllByText("Устройство на шаг позади rollout")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Доступно обновление")).toBeInTheDocument();
    expect(await screen.findByText("Назначенный rollout новее текущей версии.")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Реестр модулей" })).toBeInTheDocument();
    expect(await screen.findByText("Рабочий реестр")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /network_ping/i })).toBeInTheDocument();
    expect((await screen.findAllByText("Обновлять установленные устройства")).length).toBeGreaterThan(0);

    expect(await screen.findByRole("heading", { name: "Observer для WS-01" })).toBeInTheDocument();
    expect((await screen.findAllByText("Горячие traces")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Launcher signature mismatch")).toBeInTheDocument();
    expect(await screen.findByText("Mass signatures и dangerous flows")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Конструктор форм заявок" })).toBeInTheDocument();

    fireEvent.click((await screen.findAllByRole("button", { name: "Открыть trace" }))[0]);
    expect(await screen.findByText("Список traces")).toBeInTheDocument();
    expect(await screen.findByText("Span timeline")).toBeInTheDocument();
    expect(await screen.findByText("Agent actions")).toBeInTheDocument();
    expect(await screen.findByText("operation_id_bridge")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Режим preferred-rollout" }), {
      target: { value: "manual" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить политику" }));

    expect(await screen.findByText("Политика preferred-rollout сохранена: Только вручную.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("Только вручную").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole("button", { name: "Сделать preferred для 1.2.1" }));
    expect(await screen.findByText(/Preferred-версия.*network_ping.*1\.2\.1/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/latest 1\.2\.1 .* preferred 1\.2\.1/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /observer_canary/i }));
    expect((await screen.findAllByText("Ошибка валидации")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/Архив отсутствует, нужен повторный upload/i)).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Новая форма" }));
    fireEvent.change(screen.getByLabelText("Название формы"), {
      target: { value: "Ремонт принтера" },
    });
    fireEvent.change(screen.getByLabelText("Ключ формы"), {
      target: { value: "printer_repair" },
    });
    fireEvent.change(screen.getByLabelText("request_kind"), {
      target: { value: "printer_repair" },
    });
    fireEvent.change(screen.getByLabelText("Название поля"), {
      target: { value: "Код поломки" },
    });
    fireEvent.change(screen.getByLabelText("Ключ поля"), {
      target: { value: "issue_code" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));

    expect(await screen.findByText(/Каталог опубликован как версия 1.0.4/)).toBeInTheDocument();
    expect(saveCalls).toHaveLength(1);

    fireEvent.change(screen.getByLabelText("Причина запуска"), {
      target: { value: "canary после smoke" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Запустить обновление" }));
    expect(await screen.findByText("Операция op-admin-update-001 поставлена в очередь.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /LT-02/i }));
    expect(await screen.findByText(/Платформа:/)).toBeInTheDocument();
    expect((await screen.findAllByText("linux_alt_x86_64")).length).toBeGreaterThan(0);
    expect(await screen.findByRole("button", { name: "Ожидает связи" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "72 часа" }));
    await waitFor(() => {
      expect(screen.getByText("Есть отставание")).toBeInTheDocument();
    });
  }, 10000);
});
