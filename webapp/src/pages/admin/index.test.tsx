import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminWorkspacePage } from "./index";


function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
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

function getRolloutModeLabel(mode: string) {
  return mode === "installed_devices" ? "Обновлять установленные устройства" : "Только вручную";
}

function createModulesState(): ModulesState {
  return {
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
  const modules = state.modules.map((moduleFamily) => ({
    ...moduleFamily,
    platforms: [...moduleFamily.platforms],
    tool_ids: [...moduleFamily.tool_ids],
    versions: moduleFamily.versions.map((version) => ({
      ...version,
      platforms: [...version.platforms],
      tool_ids: [...version.tool_ids]
    }))
  }));

  return {
    query: "",
    summary: {
      visible_count: modules.length,
      preferred_count: modules.filter((item) => item.preferred_assigned).length,
      invalid_count: modules.filter((item) =>
        ["warning", "failed"].includes(item.validation_status)
      ).length,
      missing_files_count: modules.filter((item) => item.has_missing_files).length
    },
    rollout_settings: {
      ...state.rollout_settings
    },
    modules
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

function renderAdminPage() {
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
      <AdminWorkspacePage />
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminWorkspacePage", () => {
  it("renders typed inventory, observer drilldown and modules actions in Russian", async () => {
    const modulesState = createModulesState();
    const formsState: {
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
    } = {
      summary: {
        pack_key: "request_forms",
        version: "1.0.3",
        title: "Каталог заявок",
        description: "Рабочий каталог",
        forms_count: 1,
        fields_count: 2,
        required_fields_count: 1,
        last_published_at: "2026-04-21T10:00:00+05:00",
        last_published_by: "admin1"
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
              visible_when: null
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
              visible_when: null
            }
          ]
        }
      ]
    };

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
              features: ["devices_inventory", "agent_rollout", "modules_workbench", "forms_builder", "tech_panel"],
              observer: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces"
              }
            }
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
                rollout_targets: 2
              },
              filters: {
                status_options: [
                  { value: "all", label: "Все устройства" },
                  { value: "online", label: "Только онлайн" },
                  { value: "offline", label: "Только оффлайн" }
                ]
              },
              rollout: [
                {
                  target: "windows_amd64",
                  channel: "stable",
                  version: "2.4.1",
                  updated_at: "2026-04-20T11:20:00+05:00",
                  updated_by: "admin1"
                },
                {
                  target: "linux_alt_x86_64",
                  channel: "stable",
                  version: "2.3.9",
                  updated_at: "2026-04-20T10:55:00+05:00",
                  updated_by: "admin1"
                }
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
                    summary: "Устройство на шаг позади rollout"
                  }
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
                    summary: "Назначен rollout stable/2.3.9"
                  }
                }
              ]
            }
          });
        }

        if (url === "/api/web/admin/modules" && method === "GET") {
          return jsonResponse({
            status: "success",
            data: cloneModulesPayload(modulesState)
          });
        }

        if (url === "/api/web/admin/modules/rollout_settings" && method === "PATCH") {
          const payload = JSON.parse(String(init?.body ?? "{}")) as {
            preferred_version_rollout_mode?: string;
            sync_after_preferred_change?: boolean;
          };
          modulesState.rollout_settings.preferred_version_rollout_mode =
            payload.preferred_version_rollout_mode ?? modulesState.rollout_settings.preferred_version_rollout_mode;
          modulesState.rollout_settings.preferred_version_rollout_mode_label = getRolloutModeLabel(
            modulesState.rollout_settings.preferred_version_rollout_mode
          );
          modulesState.rollout_settings.sync_after_preferred_change =
            payload.sync_after_preferred_change ?? modulesState.rollout_settings.sync_after_preferred_change;
          return jsonResponse({
            status: "success",
            data: {
              ...modulesState.rollout_settings
            }
          });
        }

        if (url === "/api/web/admin/modules/network_ping/preferred" && method === "PATCH") {
          const payload = JSON.parse(String(init?.body ?? "{}")) as { version?: string | null };
          applyPreferredVersion(modulesState, "network_ping", payload.version ?? null);
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
              rollout_summary: {
                mode: modulesState.rollout_settings.preferred_version_rollout_mode,
                should_sync: modulesState.rollout_settings.sync_after_preferred_change,
                desired_updates: payload.version === null ? 0 : 2,
                sync_enqueued:
                  payload.version !== null && modulesState.rollout_settings.sync_after_preferred_change ? 2 : 0,
                refresh_enqueued:
                  payload.version !== null && modulesState.rollout_settings.sync_after_preferred_change ? 2 : 0
              }
            }
          });
        }

        if (url === "/api/web/admin/forms/current" && method === "GET") {
          return jsonResponse({
            status: "success",
            data: {
              summary: { ...formsState.summary },
              capabilities: {
                current_endpoint: "/api/web/admin/forms/current",
                save_endpoint: "/api/web/admin/forms/save",
                field_type_options: [
                  { value: "text", label: "Текст" },
                  { value: "textarea", label: "Большой текст" },
                  { value: "select", label: "Список" },
                  { value: "radio", label: "Переключатель" },
                  { value: "checkbox", label: "Флажок" }
                ]
              },
              forms: formsState.forms.map((form) => ({
                ...form,
                fields: form.fields.map((field) => ({ ...field }))
              }))
            }
          });
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

          formsState.summary = {
            ...formsState.summary,
            version: "1.0.4",
            title: payload.title,
            description: payload.description,
            forms_count: payload.forms.length,
            fields_count: payload.forms.reduce((total, form) => total + form.fields.length, 0),
            required_fields_count: payload.forms.reduce(
              (total, form) => total + form.fields.filter((field) => field.required).length,
              0
            )
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
                    values: field.visible_when.values ?? []
                  }
                : null
            }))
          }));

          return jsonResponse({
            status: "success",
            data: {
              summary: { ...formsState.summary },
              forms: formsState.forms.map((form) => ({
                ...form,
                fields: form.fields.map((field) => ({ ...field }))
              })),
              message: "Каталог опубликован как версия 1.0.4. Изменения уже активны в /help и в интерфейсе агента."
            }
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
                dangerous_flow_count: 1
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "ok",
                health_status_label: "Норма",
                pending_trace_count: 1,
                last_projected_at: "2026-04-20T11:28:00+05:00",
                issues: []
              },
              hot_traces: [
                {
                  trace_id: "trace-update-1",
                  root_span_id: "span-root-1",
                  root_kind: "agent_update",
                  root_kind_label: "Обновление агента",
                  status: "failed",
                  status_label: "Ошибка",
                  ticket_id: "ticket-1",
                  device_id: "device-1",
                  operation_id: "op-update-1",
                  job_id: null,
                  duration_ms: 6400,
                  error_count: 1,
                  span_count: 6,
                  started_at: "2026-04-20T11:24:00+05:00",
                  finished_at: "2026-04-20T11:24:06+05:00",
                  attrs_json: {
                    flow: "agent_update"
                  }
                }
              ],
              top_signatures: [
                {
                  error_signature: "sig-1",
                  title: "Launcher signature mismatch",
                  tool_name: "update",
                  component: "agent_update",
                  occurrences_count: 4,
                  affected_devices_count: 2,
                  last_seen_at: "2026-04-20T11:25:00+05:00"
                }
              ],
              top_degradations: [],
              dangerous_flows: [],
              links: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
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
                dangerous_flow_count: 0
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "ok",
                health_status_label: "Норма",
                pending_trace_count: 0,
                last_projected_at: "2026-04-20T11:20:00+05:00",
                issues: []
              },
              hot_traces: [
                {
                  trace_id: "trace-linux-1",
                  root_span_id: "span-root-2",
                  root_kind: "tool_call",
                  root_kind_label: "Инструмент",
                  status: "succeeded",
                  status_label: "Успешно",
                  ticket_id: null,
                  device_id: "device-2",
                  operation_id: "op-linux-1",
                  job_id: null,
                  duration_ms: 1200,
                  error_count: 0,
                  span_count: 2,
                  started_at: "2026-04-20T11:00:00+05:00",
                  finished_at: "2026-04-20T11:00:01+05:00",
                  attrs_json: {}
                }
              ],
              top_signatures: [],
              top_degradations: [],
              dangerous_flows: [],
              links: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
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
                dangerous_flow_count: 2
              },
              runtime: {
                enabled: true,
                running: true,
                health_status: "degraded",
                health_status_label: "Есть отставание",
                pending_trace_count: 6,
                last_projected_at: "2026-04-20T10:45:00+05:00",
                issues: ["pending_backlog"]
              },
              hot_traces: [],
              top_signatures: [],
              top_degradations: [],
              dangerous_flows: [],
              links: {
                quick_endpoint: "/api/web/admin/observer/quick",
                traces_endpoint: "/api/web/admin/observer/traces",
                runtime_endpoint: "/api/admin/tech/traces/runtime"
              }
            }
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-1&lookback_hours=24&status=all&root_kind=all&limit=12") {
          return jsonResponse({
            status: "success",
            data: {
              filters: {
                device_id: "device-1",
                lookback_hours: 24,
                status: "all",
                root_kind: "all",
                limit: 12
              },
              summary: {
                total_count: 1,
                active_count: 0,
                failed_count: 1
              },
              traces: [
                {
                  trace_id: "trace-update-1",
                  root_kind: "agent_update",
                  root_kind_label: "Обновление агента",
                  status: "failed",
                  status_label: "Ошибка",
                  ticket_id: "ticket-1",
                  device_id: "device-1",
                  operation_id: "op-update-1",
                  duration_ms: 6400,
                  error_count: 1,
                  span_count: 6,
                  started_at: "2026-04-20T11:24:00+05:00",
                  finished_at: "2026-04-20T11:24:06+05:00"
                }
              ]
            }
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-2&lookback_hours=24&status=all&root_kind=all&limit=12") {
          return jsonResponse({
            status: "success",
            data: {
              filters: {
                device_id: "device-2",
                lookback_hours: 24,
                status: "all",
                root_kind: "all",
                limit: 12
              },
              summary: {
                total_count: 1,
                active_count: 0,
                failed_count: 0
              },
              traces: [
                {
                  trace_id: "trace-linux-1",
                  root_kind: "tool_call",
                  root_kind_label: "Инструмент",
                  status: "succeeded",
                  status_label: "Успешно",
                  ticket_id: null,
                  device_id: "device-2",
                  operation_id: "op-linux-1",
                  duration_ms: 1200,
                  error_count: 0,
                  span_count: 2,
                  started_at: "2026-04-20T11:00:00+05:00",
                  finished_at: "2026-04-20T11:00:01+05:00"
                }
              ]
            }
          });
        }

        if (url === "/api/web/admin/observer/traces?device_id=device-2&lookback_hours=72&status=all&root_kind=all&limit=12") {
          return jsonResponse({
            status: "success",
            data: {
              filters: {
                device_id: "device-2",
                lookback_hours: 72,
                status: "all",
                root_kind: "all",
                limit: 12
              },
              summary: {
                total_count: 0,
                active_count: 0,
                failed_count: 0
              },
              traces: []
            }
          });
        }

        if (url === "/api/web/admin/observer/traces/trace-update-1") {
          return jsonResponse({
            status: "success",
            data: {
              trace_id: "trace-update-1",
              root_kind: "agent_update",
              root_kind_label: "Обновление агента",
              status: "failed",
              status_label: "Ошибка",
              started_at: "2026-04-20T11:24:00+05:00",
              finished_at: "2026-04-20T11:24:06+05:00",
              duration_ms: 6400,
              operation_id: "op-update-1",
              ticket_id: "ticket-1",
              device_id: "device-1",
              spans: [],
              events: [],
              dangerous_flow: null
            }
          });
        }

        if (url === "/api/web/admin/observer/traces/trace-linux-1") {
          return jsonResponse({
            status: "success",
            data: {
              trace_id: "trace-linux-1",
              root_kind: "tool_call",
              root_kind_label: "Инструмент",
              status: "succeeded",
              status_label: "Успешно",
              started_at: "2026-04-20T11:00:00+05:00",
              finished_at: "2026-04-20T11:00:01+05:00",
              duration_ms: 1200,
              operation_id: "op-linux-1",
              ticket_id: null,
              device_id: "device-2",
              spans: [],
              events: [],
              dangerous_flow: null
            }
          });
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
                summary: "Серверный rollout рекомендует stable/2.4.1."
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
                  version: "2.4.1"
                },
                assigned_rollout: {
                  target: "windows_amd64",
                  channel: "stable",
                  version: "2.4.1",
                  updated_at: "2026-04-20T11:20:00+05:00",
                  updated_by: "admin1"
                }
              },
              action: {
                enabled: true,
                label: "Запустить обновление",
                reason_required: true,
                endpoint: "/api/web/admin/devices/device-1/updates/run"
              }
            }
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
                summary: "Запуск обновления доступен только когда агент онлайн и может принять команду."
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
                  version: "2.3.9"
                },
                assigned_rollout: {
                  target: "linux_alt_x86_64",
                  channel: "stable",
                  version: "2.3.9",
                  updated_at: "2026-04-20T10:55:00+05:00",
                  updated_by: "admin1"
                }
              },
              action: {
                enabled: false,
                label: "Ожидает связи",
                reason_required: true,
                endpoint: "/api/web/admin/devices/device-2/updates/run"
              }
            }
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
                version: "2.4.1"
              }
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderAdminPage();

    expect(await screen.findByRole("heading", { name: "Рабочее место администрирования" })).toBeInTheDocument();
    expect(await screen.findByText("Всего в инвентаре")).toBeInTheDocument();
    expect(await screen.findByText("Назначения rollout")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /WS-01/i })).toBeInTheDocument();
    expect((await screen.findAllByText("Устройство на шаг позади rollout")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Доступно обновление")).toBeInTheDocument();
    expect(await screen.findByText("Назначенный rollout новее текущей версии.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Реестр модулей" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /network_ping/i })).toBeInTheDocument();
    expect((await screen.findAllByText("Обновлять установленные устройства")).length).toBeGreaterThan(0);
    expect(await screen.findByRole("heading", { name: "Быстрый срез трассировки" })).toBeInTheDocument();
    expect(await screen.findByText("Launcher signature mismatch")).toBeInTheDocument();
    expect(await screen.findByText("/api/web/admin/observer/traces", { exact: true })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Детальный разбор трасс" })).toBeInTheDocument();
    expect((await screen.findAllByText("trace-update-1")).length).toBeGreaterThan(0);
    expect(await screen.findByRole("heading", { name: "Конструктор форм заявок" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Режим preferred-rollout" }), {
      target: { value: "manual" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить политику" }));

    expect(await screen.findByText("Политика раскатки сохранена: Только вручную.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Сделать preferred для 1.2.1" }));

    expect(await screen.findByText("Preferred-версия для network_ping обновлена на 1.2.1.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Preferred:\s*1\.2\.1/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Новая форма" }));
    fireEvent.change(screen.getByLabelText("Название формы"), {
      target: { value: "Ремонт принтера" }
    });
    fireEvent.change(screen.getByLabelText("Ключ формы"), {
      target: { value: "printer_repair" }
    });
    fireEvent.change(screen.getByLabelText("Request kind"), {
      target: { value: "printer_repair" }
    });
    fireEvent.change(screen.getByLabelText("Название поля"), {
      target: { value: "Код поломки" }
    });
    fireEvent.change(screen.getByLabelText("Ключ поля"), {
      target: { value: "issue_code" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));

    expect(await screen.findByText(/Каталог опубликован как версия 1.0.4/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Причина запуска"), {
      target: { value: "canary после smoke" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Запустить обновление" }));

    expect(await screen.findByText("Операция op-admin-update-001 поставлена в очередь.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /LT-02/i }));

    expect(await screen.findByText("Платформа")).toBeInTheDocument();
    expect((await screen.findAllByText("linux_alt_x86_64")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("trace-linux-1")).length).toBeGreaterThan(0);
    expect(await screen.findByRole("button", { name: "Ожидает связи" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "72 часа" }));
    await waitFor(() => {
      expect(screen.getByText("Есть отставание")).toBeInTheDocument();
    });
  });
});
