import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AdminFormsPayload, AdminHelpdeskModelPayload } from "./api";
import { FormsBuilderPanel } from "./forms-builder-panel";


function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json"
    }
  });
}


function createFormsPayload(): AdminFormsPayload {
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
      last_published_by: "admin1"
    },
    capabilities: {
      current_endpoint: "/api/web/admin/forms/current",
      save_endpoint: "/api/web/admin/forms/save",
      preview_endpoint: "/api/web/admin/forms/route-preview",
      process_preview_endpoint: "/api/web/admin/forms/process-preview",
      field_type_options: [
        { value: "text", label: "Текст" },
        { value: "textarea", label: "Большой текст" },
        { value: "select", label: "Список" },
        { value: "radio", label: "Переключатель" },
        { value: "checkbox", label: "Флажок" }
      ],
      field_role_options: [
        { value: "routing_field", label: "Routing field" },
        { value: "priority_impact", label: "Priority impact" },
        { value: "priority_urgency", label: "Priority urgency" },
        { value: "priority_importance", label: "Priority importance" },
        { value: "diagnostic_input", label: "Diagnostic input" },
        { value: "approval_subject", label: "Approval subject" },
        { value: "closure_evidence", label: "Closure evidence" },
        { value: "reporting_dimension", label: "Reporting dimension" },
        { value: "passport_fact", label: "Passport fact" },
        { value: "visibility_public", label: "Requester-visible fact" },
        { value: "display_only", label: "Display only" }
      ]
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
            validation: {},
            process_mapping: {}
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
            validation: {},
            process_mapping: {}
          }
        ]
      }
    ]
  };
}

function createHelpdeskModelRegistryPayload(): AdminHelpdeskModelPayload {
  return {
    summary: {
      request_templates_count: 0,
      active_request_templates_count: 0,
      ticket_types_count: 0,
      active_ticket_types_count: 0,
      form_schemas_count: 0,
      active_form_schemas_count: 0,
      policies_count: 0,
      active_policies_count: 0,
      smart_views_count: 0,
      active_smart_views_count: 0,
    },
    capabilities: {
      registry_endpoint: "/api/web/admin/helpdesk-model/policies",
      publish_from_form_endpoint: "/api/web/admin/helpdesk-model/request-templates/publish-from-form",
      publish_policy_endpoint: "/api/web/admin/helpdesk-model/policies/publish",
      policy_diff_endpoint: "/api/web/admin/helpdesk-model/policies/diff",
      policy_deactivate_endpoint: "/api/web/admin/helpdesk-model/policies/deactivate",
      policy_rollback_endpoint: "/api/web/admin/helpdesk-model/policies/rollback",
      publish_ticket_type_endpoint: "/api/web/admin/helpdesk-model/ticket-types/publish",
      ticket_type_deactivate_endpoint: "/api/web/admin/helpdesk-model/ticket-types/deactivate",
      ticket_type_rollback_endpoint: "/api/web/admin/helpdesk-model/ticket-types/rollback",
      publish_form_schema_endpoint: "/api/web/admin/helpdesk-model/form-schemas/publish",
      publish_smart_view_endpoint: "/api/web/admin/helpdesk-model/smart-views/publish",
      inheritance_order: ["system", "ticket_type", "category", "request_template"],
      policy_kinds: ["approval", "closure", "diagnostic", "notification", "ola", "priority", "reporting", "routing", "sla", "visibility"],
    },
    request_templates: [],
    ticket_types: [],
    form_schemas: [],
    policies: {
      approval: [],
      closure: [],
      diagnostic: [],
      notification: [],
      ola: [],
      priority: [],
      reporting: [],
      routing: [],
      sla: [],
      visibility: [],
    },
    smart_views: [],
  };
}


function renderFormsBuilder(props?: { permissions?: string[] }) {
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
      <FormsBuilderPanel {...props} />
    </QueryClientProvider>
  );
}


afterEach(() => {
  vi.unstubAllGlobals();
});

describe("FormsBuilderPanel", () => {
  it("shows a read-only reason and blocks publish without admin.forms.publish", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.view"] });

    expect(await screen.findByText("Недостаточно прав: admin.forms.publish")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Сохранить черновик|Опубликовать/ })[0]).toBeDisabled();
  });

  it("shows inline field role conflicts near affected fields", async () => {
    const payload = createFormsPayload();
    payload.forms[0] = {
      ...payload.forms[0],
      diagnostic_policy: {
        auto_run: { enabled: true },
        suggested_playbooks: ["diagnose.printer"]
      },
      field_roles: {
        room: ["priority_impact", "diagnostic_input"],
        printer_model: ["priority_impact"]
      }
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: payload
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    await waitFor(() => {
      expect(screen.getAllByText("Печать / принтер").length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText("Role priority_impact can be assigned to only one field.").length).toBeGreaterThan(0);
    expect(screen.getByText("Diagnostic input needs a playbook parameter mapping.")).toBeInTheDocument();
  });

  it("сохраняет черновик, запускает проверку и публикует отдельными действиями", async () => {
    const draftCalls: unknown[] = [];
    const validateCalls: unknown[] = [];
    const publishCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: {
              pack_key: "request_forms",
              version: "1.0.3",
              title: "Каталог заявок",
              description: "Рабочий каталог",
              forms_count: 1,
              fields_count: 2,
              required_fields_count: 1,
              created_at: "2026-04-21T10:00:00+05:00",
              created_by: "admin1",
              is_preferred: true
            },
            preferred: {
              pack_key: "request_forms",
              version: "1.0.3",
              updated_at: "2026-04-21T10:00:00+05:00",
              updated_by: "admin1"
            },
            packs: [
              {
                pack_key: "request_forms",
                version: "1.0.3",
                title: "Каталог заявок",
                description: "Рабочий каталог",
                forms_count: 1,
                fields_count: 2,
                required_fields_count: 1,
                created_at: "2026-04-21T10:00:00+05:00",
                created_by: "admin1",
                is_preferred: true
              }
            ]
          });
        }

        if (url === "/api/web/admin/forms/save-draft" && method === "POST") {
          draftCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              draft_id: "draft-1",
              pack_key: "request_forms",
              base_version: "1.0.3",
              status: "draft",
              summary: createFormsPayload().summary,
              published_version: null,
              preferred_version: "1.0.3",
              message: "Черновик сохранён. Активная версия не изменилась."
            }
          });
        }

        if (url === "/api/web/admin/forms/validate" && method === "POST") {
          validateCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              status: "validated",
              summary: {
                errors_count: 0,
                warnings_count: 0,
                can_publish: true
              },
              errors: [],
              warnings: [],
              message: "Проверка завершена: публикация разрешена."
            }
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          publishCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4",
                forms_count: 2,
                fields_count: 3
              },
              forms: [
                ...createFormsPayload().forms,
                {
                  key: "new_form_2",
                  request_kind: "printer_repair",
                  title: "Ремонт принтера",
                  description: "",
                  fields: [
                    {
                      key: "issue_code",
                      label: "Код поломки",
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
              ],
              published_version: "1.0.4",
              preferred_version: "1.0.4",
              made_preferred: true,
              message: "Каталог опубликован как версия 1.0.4. Изменения уже активны в /help и в интерфейсе агента."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    expect(await screen.findByText("Активная версия")).toBeInTheDocument();
    expect((await screen.findAllByText("1.0.3")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Новая форма" }));
    await waitFor(() => {
      expect(screen.getByLabelText("Ключ формы")).toHaveValue("new_form_2");
    });
    fireEvent.change(screen.getByLabelText("Название формы"), {
      target: { value: "Ремонт принтера" }
    });
    fireEvent.change(screen.getByLabelText("Ключ формы"), {
      target: { value: "printer_repair" }
    });
    fireEvent.change(screen.getByLabelText("request_kind"), {
      target: { value: "printer_repair" }
    });
    fireEvent.change(screen.getByLabelText("Название поля"), {
      target: { value: "Код поломки" }
    });
    fireEvent.change(screen.getByLabelText("Ключ поля"), {
      target: { value: "issue_code" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Добавить вопросы" }));
    expect(screen.getByText("Priority impact")).toBeInTheDocument();
    expect(screen.queryByText("priority_field")).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Сохранить черновик" })[0]);

    await waitFor(() => {
      expect(screen.getByText(/Черновик сохранён/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Проверить публикацию" }));

    await waitFor(() => {
      expect(screen.getAllByText(/Проверка завершена/).length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(screen.getByText(/Каталог опубликован как версия 1.0.4/)).toBeInTheDocument();
    });

    expect(draftCalls).toHaveLength(1);
    expect(validateCalls).toHaveLength(1);
    expect(publishCalls).toHaveLength(1);
    const savedPrinterRepair = (
      publishCalls[0] as {
        forms: Array<{
          key: string;
          fields?: Array<{ key: string }>;
          field_roles?: Record<string, string[]>;
          priority_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer_repair");
    expect(savedPrinterRepair?.fields?.some((field) => field.key === "impact_scope")).toBe(true);
    expect(savedPrinterRepair?.field_roles?.impact_scope).toContain("priority_impact");
    expect(savedPrinterRepair?.priority_policy).toMatchObject({
      impact_field: "impact_scope",
      urgency_field: "work_continuity",
      importance_field: "business_importance",
    });
    expect(validateCalls[0]).toMatchObject({
      draft_id: "draft-1"
    });
    expect(publishCalls[0]).toMatchObject({
      draft_id: "draft-1",
      make_preferred: true,
      title: "Каталог заявок",
      forms: [
        expect.objectContaining({
          key: "printer",
          ticket_type: "incident",
          title: "Печать / принтер"
        }),
        expect.objectContaining({
          key: "printer_repair",
          request_kind: "printer_repair",
          title: "Ремонт принтера",
          fields: expect.arrayContaining([
            expect.objectContaining({
              key: "issue_code",
              label: "Код поломки"
            })
          ])
        })
      ]
    });
  });

  it("строит preview маршрута по текущей форме", async () => {
    const previewCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: {
              pack_key: "request_forms",
              version: "1.0.3",
              title: "Каталог заявок",
              description: "Рабочий каталог",
              forms_count: 1,
              fields_count: 2,
              required_fields_count: 1,
              created_at: "2026-04-21T10:00:00+05:00",
              created_by: "admin1",
              is_preferred: true
            },
            preferred: {
              pack_key: "request_forms",
              version: "1.0.3",
              updated_at: "2026-04-21T10:00:00+05:00",
              updated_by: "admin1"
            },
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/route-preview" && method === "POST") {
          previewCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              ticket_type: "printer",
              request_kind: "printer",
              target_queue_id: 17,
              target_queue_name: "Printer 214",
              fallback_applied: false,
              matched_rule: {
                id: 5,
                priority_order: 10,
                target_queue_id: 17,
                target_queue_name: "Printer 214",
                condition_json: {
                  field: "request_form_data.room",
                  op: "eq",
                  value: "214"
                }
              },
              summary_rows: [
                { key: "room", label: "Кабинет", value: "214" },
                { key: "printer_model", label: "Модель", value: "HP LaserJet" }
              ]
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    await screen.findByLabelText("Кабинет");
    fireEvent.change(screen.getByLabelText("Кабинет"), {
      target: { value: "214" }
    });
    fireEvent.change(screen.getByLabelText("Модель"), {
      target: { value: "HP LaserJet" }
    });

    fireEvent.click(screen.getByRole("button", { name: "Проверить" }));

    expect(await screen.findByText("Printer 214")).toBeInTheDocument();
    expect(screen.getByText("Условие правила")).toBeInTheDocument();
    expect(screen.getByText("request_form_data.room = 214")).toBeInTheDocument();
    expect(screen.queryByText(/Condition JSON/)).not.toBeInTheDocument();
    expect(previewCalls).toHaveLength(1);
    expect(previewCalls[0]).toMatchObject({
      form: {
        key: "printer",
        request_kind: "printer"
      },
      form_payload: {
        room: "214",
        printer_model: "HP LaserJet"
      }
    });
  });

  it("строит полный process preview по текущей форме", async () => {
    const processPreviewCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/process-preview" && method === "POST") {
          processPreviewCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              ticket_type: "incident",
              request_kind: "printer",
              priority: {
                priority_class: "P2",
                priority_source: "request_template.priority_policy"
              },
              routing: {
                source: "request_template.routing_policy",
                target_queue_id: 17,
                target_queue_name: "Printer 214",
                matched_rule_code: "printer_room_214"
              },
              sla: {
                policy_code: "incident_sla",
                first_response_min: 15,
                resolution_min: 240
              },
              ola: {
                policy_code: "printer_ola",
                ack_min: 10,
                processing_min: 120
              },
              approval: {
                required: false,
                mode: "none"
              },
              diagnostics: {
                suggested_playbooks: ["printer.quick_diag"],
                auto_run_enabled: true,
                consent_required: false
              },
              closure: {
                requires_resolution_code: true,
                requires_evidence: false
              },
              visibility: {
                public_status_mapping: {}
              },
              notifications: {
                events: ["ticket_created"]
              },
              summary_rows: [{ key: "room", label: "Кабинет", value: "214" }],
              validation_report: {
                summary: { can_publish: true },
                errors: [],
                warnings: []
              },
              preview_metadata: {
                source: "draft",
                side_effects: []
              }
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    fireEvent.change(await screen.findByLabelText("Кабинет"), {
      target: { value: "214" }
    });
    fireEvent.change(screen.getByLabelText("Модель"), {
      target: { value: "HP LaserJet" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Проверить процесс" }));

    expect(await screen.findByText("При таких ответах будет создан")).toBeInTheDocument();
    expect(screen.getByText("Printer 214")).toBeInTheDocument();
    expect(screen.getByText("P2")).toBeInTheDocument();
    expect(screen.getByText(/incident_sla/)).toBeInTheDocument();
    expect(screen.getByText("printer.quick_diag")).toBeInTheDocument();
    expect(screen.getByText("printer_room_214")).toBeInTheDocument();
    expect(processPreviewCalls).toHaveLength(1);
    expect(processPreviewCalls[0]).toMatchObject({
      form: {
        key: "printer",
        request_kind: "printer"
      },
      form_payload: {
        room: "214",
        printer_model: "HP LaserJet"
      }
    });
  });

  it("показывает проверку публикации и блокирует hard-invalid форму", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: {
              pack_key: "request_forms",
              version: "1.0.3",
              title: "Каталог заявок",
              description: "Рабочий каталог",
              forms_count: 1,
              fields_count: 2,
              required_fields_count: 1,
              created_at: "2026-04-21T10:00:00+05:00",
              created_by: "admin1",
              is_preferred: true
            },
            preferred: {
              pack_key: "request_forms",
              version: "1.0.3",
              updated_at: "2026-04-21T10:00:00+05:00",
              updated_by: "admin1"
            },
            packs: []
          });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    await waitFor(() => {
      expect(screen.getAllByText("Печать / принтер").length).toBeGreaterThan(0);
    });
    fireEvent.change(screen.getByLabelText("Тип поля"), {
      target: { value: "select" }
    });
    fireEvent.change(screen.getByLabelText("Ключ поля"), {
      target: { value: "" }
    });
    fireEvent.click(screen.getByLabelText("Включить"));

    expect(screen.getByText("Проверка публикации")).toBeInTheDocument();
    expect(screen.getByText("У поля «Кабинет» нужен ключ.")).toBeInTheDocument();
    expect(screen.getByText("Укажите ключ плейбука или выключите автозапуск.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Опубликовать" })[0]).toBeDisabled();
  });

  it("показывает end-to-end preview запуска плейбука вместе с маршрутом", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          const payload = createFormsPayload();
          payload.forms[0].playbook_triggers = [
            {
              event: "ticket_created",
              playbook_key: "printer.quick_diag",
              module_kind: "diagnostic",
              enabled: true
            }
          ];
          return jsonResponse({
            status: "success",
            data: payload
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/route-preview" && method === "POST") {
          return jsonResponse({
            status: "success",
            data: {
              ticket_type: "printer",
              request_kind: "printer",
              target_queue_id: 17,
              target_queue_name: "Printer 214",
              fallback_applied: false,
              matched_rule: null,
              summary_rows: [{ key: "room", label: "Кабинет", value: "214" }]
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    fireEvent.change(await screen.findByLabelText("Кабинет"), {
      target: { value: "214" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Проверить" }));

    expect(await screen.findByText("Printer 214")).toBeInTheDocument();
    expect(screen.getByText("Автозапуск плейбука")).toBeInTheDocument();
    expect(screen.getAllByText("printer.quick_diag").length).toBeGreaterThan(0);
    expect(screen.getByText("Факты формы будут приложены к запуску после создания тикета.")).toBeInTheDocument();
  });

  it("не отправляет route preview, если обязательные preview-поля пустые", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url === "/api/web/admin/forms/current") {
        return jsonResponse({
          status: "success",
          data: createFormsPayload()
        });
      }

      if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
        return jsonResponse({
          status: "ok",
          pack_key: "request_forms",
          current: null,
          preferred: null,
          packs: []
        });
      }

      if (url === "/api/web/admin/forms/route-preview" && init?.method === "POST") {
        throw new Error("route preview should not be called with invalid sample data");
      }

      throw new Error(`Unexpected fetch: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    await screen.findByLabelText("Кабинет");
    fireEvent.click(screen.getByRole("button", { name: "Проверить" }));

    expect(await screen.findByText("Заполните обязательные поля preview.")).toBeInTheDocument();
    expect(screen.getByText("Заполните поле «Кабинет».")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input, init]) => String(input) === "/api/web/admin/forms/route-preview" && init?.method === "POST")
    ).toBe(false);
  });

  it("обновляет и очищает visible_when ссылки при rename/delete поля", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          const payload = createFormsPayload();
          payload.forms[0].fields[1].visible_when = {
            field: "room",
            equals: "214",
            values: []
          };
          return jsonResponse({
            status: "success",
            data: payload
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: {
              pack_key: "request_forms",
              version: "1.0.3",
              title: "Каталог заявок",
              description: "Рабочий каталог",
              forms_count: 1,
              fields_count: 2,
              required_fields_count: 1,
              created_at: "2026-04-21T10:00:00+05:00",
              created_by: "admin1",
              is_preferred: true
            },
            preferred: {
              pack_key: "request_forms",
              version: "1.0.3",
              updated_at: "2026-04-21T10:00:00+05:00",
              updated_by: "admin1"
            },
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    await screen.findByLabelText("Ключ поля");
    fireEvent.change(screen.getByLabelText("Ключ поля"), {
      target: { value: "office_room" }
    });

    fireEvent.click(screen.getByRole("button", { name: /Модель/ }));
    await waitFor(() => {
      expect(screen.getByLabelText("Поле условия")).toHaveValue("office_room");
    });

    fireEvent.click(screen.getByRole("button", { name: /Кабинет/ }));
    fireEvent.click(screen.getByRole("button", { name: "Удалить" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Поле условия")).toHaveValue("");
    });

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });
    expect(saveCalls[0]).toMatchObject({
      forms: [
        {
          key: "printer",
          fields: [
            {
              key: "printer_model",
              label: "Модель"
            }
          ]
        }
      ]
    });
    expect((saveCalls[0] as { forms: Array<{ fields: Array<{ visible_when?: unknown }> }> }).forms[0].fields[0]).not.toHaveProperty(
      "visible_when"
    );
  });

  it("редактирует options и условия видимости через контролы, а не технический textarea", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          const payload = createFormsPayload();
          payload.forms[0].fields[0] = {
            key: "issue_type",
            label: "Тип проблемы",
            type: "select",
            type_label: "Список",
            required: true,
            placeholder: "",
            help_text: "",
            options: [
              { value: "printer", label: "Принтер" },
              { value: "network", label: "Сеть" },
            ],
            visible_when: null,
            validation: {},
            process_mapping: {},
          };
          payload.forms[0].fields[1].visible_when = {
            field: "issue_type",
            equals: "printer",
            values: [],
          };
          return jsonResponse({
            status: "success",
            data: payload,
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: [],
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.5",
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.5.",
            },
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    fireEvent.click(await screen.findByRole("button", { name: /Тип проблемы/ }));

    expect(screen.getByText("Варианты ответа")).toBeInTheDocument();
    expect(screen.queryByText("visible_when.field")).not.toBeInTheDocument();
    expect(screen.queryByText("visible_when.equals")).not.toBeInTheDocument();
    expect(screen.queryByText("visible_when.values")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Название варианта 1"), {
      target: { value: "Печать" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Добавить вариант" }));
    fireEvent.change(screen.getByLabelText("Значение варианта 3"), {
      target: { value: "software" },
    });
    fireEvent.change(screen.getByLabelText("Название варианта 3"), {
      target: { value: "ПО" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Модель/ }));
    expect(screen.getByText("Условие показа")).toBeInTheDocument();
    expect(screen.getByLabelText("Поле условия")).toHaveValue("issue_type");
    expect(screen.getByLabelText("Значение условия")).toHaveValue("printer");
    fireEvent.change(screen.getByLabelText("Значение условия"), {
      target: { value: "network" },
    });

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });
    expect(saveCalls[0]).toMatchObject({
      forms: [
        {
          fields: [
            expect.objectContaining({
              key: "issue_type",
              options: [
                { value: "printer", label: "Печать" },
                { value: "network", label: "Сеть" },
                { value: "software", label: "ПО" },
              ],
            }),
            expect.objectContaining({
              key: "printer_model",
              visible_when: {
                field: "issue_type",
                equals: "network",
              },
            }),
          ],
        },
      ],
    });
  });

  it("показывает readiness запуска плейбука без ручного JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByRole("heading", { name: "Конструктор форм заявок" });
    await screen.findByText("Плейбук при создании тикета");
    expect(screen.getByText("Цепочка запуска")).toBeInTheDocument();
    expect(screen.getAllByText("Форма").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Роутинг").length).toBeGreaterThan(0);
    expect(screen.getByText("Плейбук")).toBeInTheDocument();
    expect(screen.getByText("Запуск выключен")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Включить"));
    expect(screen.getByText("Нужен ключ плейбука")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Ключ плейбука"), {
      target: { value: "printer_diagnostic" }
    });
    expect(screen.getByText("Готов к запуску после создания тикета")).toBeInTheDocument();
    expect(screen.getByText("ticket_created")).toBeInTheDocument();
    expect(screen.getAllByText("diagnostic").length).toBeGreaterThan(0);
  });

  it("собирает политики шаблона через визуальный конструктор и сохраняет их в catalog pack", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Сроки")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить OLA" }));
    fireEvent.click(screen.getAllByText("Диагностика")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить диагностику" }));
    fireEvent.click(screen.getAllByText("Уведомления")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить уведомления" }));

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          diagnostic_policy?: Record<string, unknown>;
          notification_policy?: Record<string, unknown>;
          ola_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.diagnostic_policy).toMatchObject({
      attach_results: {
        as_evidence: true,
        to_passport: true,
      },
    });
    expect(savedPrinter?.notification_policy).toMatchObject({
      on_created: {
        requester: true,
        queue: true,
      },
    });
    expect(savedPrinter?.ola_policy).toMatchObject({
      targets: {
        ack: {
          P0: "10m",
        },
      },
    });
  });

  it("показывает карту экранов мастера шаблона обращения", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    expect(screen.getByText("Карта экранов мастера")).toBeInTheDocument();
    [
      "Основное",
      "Классификация",
      "Форма",
      "Процесс",
      "Приоритет",
      "Роутинг",
      "SLA / OLA",
      "Согласования",
      "Диагностика",
      "Закрытие",
      "Видимость / Уведомления",
      "Паспорт / Отчётность",
    ].forEach((label) => {
      expect(screen.getAllByRole("button", { name: new RegExp(label.replace("/", "\\/")) }).length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole("button", { name: /Паспорт \/ Отчётность/ }));
    expect(screen.getAllByText("Паспорт решения и отчётность").length).toBeGreaterThan(0);
  });

  it("настраивает OLA цели и escalation actions без ручного JSON", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Сроки")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить OLA" }));

    fireEvent.change(screen.getByLabelText("Принять P0"), { target: { value: "7m" } });
    fireEvent.click(screen.getByLabelText("Уведомить исполнителя"));
    fireEvent.click(screen.getByLabelText("Эскалировать руководителю очереди"));
    fireEvent.click(screen.getByLabelText("Канал email"));

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          ola_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.ola_policy).toMatchObject({
      targets: {
        ack: {
          P0: "7m",
        },
      },
      breach_actions: {
        notify: ["assignee"],
        escalate_to_queue_lead: true,
        channels: {
          email: true,
        },
      },
    });
  });

  it("настраивает routing policy в шаблоне без ручного JSON", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Роутинг")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить роутинг" }));

    const templateControl = (label: string) => {
      const controls = screen.getAllByLabelText(label);
      return controls[controls.length - 1];
    };

    fireEvent.change(templateControl("Очередь по умолчанию"), { target: { value: "servicedesk_l2" } });
    fireEvent.change(templateControl("Поле условия роутинга"), { target: { value: "request_form_data.problem_area" } });
    fireEvent.change(templateControl("Значения условия"), { target: { value: "website, dns" } });
    fireEvent.change(templateControl("Куда направить"), { target: { value: "networks" } });
    fireEvent.change(templateControl("Повысить приоритет на"), { target: { value: "2" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          routing_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.routing_policy).toMatchObject({
      default_queue: "servicedesk_l2",
      rules: [
        {
          when: {
            field: "request_form_data.problem_area",
            op: "in",
            values: ["website", "dns"],
          },
          then: {
            queue: "networks",
            priority_boost: 2,
          },
        },
      ],
      fallback: {
        queue: "servicedesk_l2",
      },
    });
  });

  it("настраивает approval policy в шаблоне без ручного JSON", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Согласования")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить согласование" }));

    const templateControl = (label: string) => {
      const controls = screen.getAllByLabelText(label);
      return controls[controls.length - 1];
    };

    fireEvent.change(templateControl("Источник согласующего"), { target: { value: "form_field" } });
    fireEvent.change(templateControl("Поле согласующего"), { target: { value: "manager_user_id" } });
    fireEvent.change(templateControl("Режим согласования"), { target: { value: "sequential" } });
    fireEvent.change(templateControl("Напомнить через"), { target: { value: "2h" } });
    fireEvent.change(templateControl("Эскалировать через"), { target: { value: "1d" } });
    fireEvent.click(templateControl("Комментарий при отказе"));

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          approval_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.approval_policy).toMatchObject({
      required: true,
      approver_source: {
        type: "form_field",
        field: "manager_user_id",
      },
      approval_mode: "sequential",
      timeout: {
        reminder_after: "2h",
        escalate_after: "1d",
      },
      require_comment_on_reject: false,
      log_to_passport: true,
    });
  });

  it("настраивает closure policy в шаблоне без ручного JSON", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Закрытие")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить закрытие" }));

    const templateControl = (label: string) => {
      const controls = screen.getAllByLabelText(label);
      return controls[controls.length - 1];
    };

    fireEvent.click(templateControl("Внутренний итог обязателен"));
    fireEvent.click(templateControl("Worklog обязателен"));
    fireEvent.click(templateControl("Evidence для P2"));
    fireEvent.click(templateControl("Подтверждение пользователя"));
    fireEvent.change(templateControl("Автозакрытие через дней"), { target: { value: "5" } });
    fireEvent.click(templateControl("Открывать при отрицательном отзыве"));
    fireEvent.change(templateControl("Коды решения"), { target: { value: "fixed_remote, duplicate, cannot_reproduce" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          closure_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.closure_policy).toMatchObject({
      before_resolved: {
        require_resolution_code: true,
        require_public_summary: true,
        require_internal_summary: true,
        require_worklog: true,
      },
      evidence: {
        require_evidence_for_priorities: ["P0", "P1", "P2"],
        require_operation_log_if_module_used: true,
        require_approval_if_approval_policy_used: true,
      },
      requester_confirmation: {
        required: false,
        auto_close_after_days: 5,
        reopen_on_negative_feedback: false,
      },
      allowed_resolution_codes: ["fixed_remote", "duplicate", "cannot_reproduce"],
    });
  });

  it("настраивает diagnostic policy в шаблоне без ручного JSON", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Диагностика")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить диагностику" }));

    const templateControl = (label: string) => {
      const controls = screen.getAllByLabelText(label);
      return controls[controls.length - 1];
    };

    fireEvent.change(templateControl("Плейбуки"), { target: { value: "diagnose.website, diagnose.dns.basic" } });
    fireEvent.click(templateControl("Автозапуск"));
    fireEvent.change(templateControl("Автозапуск для приоритетов"), { target: { value: "P0, P1" } });
    fireEvent.click(templateControl("Нужно согласие пользователя"));
    fireEvent.click(templateControl("Согласие для high-risk tools"));
    fireEvent.click(templateControl("Прикладывать к timeline"));
    fireEvent.click(templateControl("Считать доказательством"));
    fireEvent.change(templateControl("DNS_FAIL очередь"), { target: { value: "networks_l2" } });
    fireEvent.change(templateControl("HTTP_500 очередь"), { target: { value: "apps" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          diagnostic_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.diagnostic_policy).toMatchObject({
      suggested_playbooks: ["diagnose.website", "diagnose.dns.basic"],
      auto_run: {
        enabled: true,
        only_for_priorities: ["P0", "P1"],
      },
      consent: {
        required_for_requester_device: false,
        required_for_high_risk_tools: false,
      },
      attach_results: {
        to_timeline: false,
        to_passport: true,
        as_evidence: false,
      },
      reroute_by_result: {
        DNS_FAIL: "networks_l2",
        HTTP_500: "apps",
      },
    });
  });

  it("настраивает visibility policy в шаблоне без ручного JSON", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Видимость")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить видимость" }));

    const templateControl = (label: string) => {
      const controls = screen.getAllByLabelText(label);
      return controls[controls.length - 1];
    };

    fireEvent.change(templateControl("Новая публично"), { target: { value: "Заявка принята" } });
    fireEvent.change(templateControl("В работе публично"), { target: { value: "Заявка в работе" } });
    fireEvent.change(templateControl("Ожидает пользователя публично"), { target: { value: "Нужен ваш ответ" } });
    fireEvent.change(templateControl("Решена публично"), { target: { value: "Проверьте решение" } });
    fireEvent.change(templateControl("Закрыта публично"), { target: { value: "Закрыта" } });
    fireEvent.change(templateControl("Скрыть от заявителя"), { target: { value: "internal_notes, ola_details, raw_diagnostics" } });
    fireEvent.change(templateControl("Показывать заявителю"), { target: { value: "public_messages, public_status, expected_due_at" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          visibility_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.visibility_policy).toMatchObject({
      public_status_mapping: {
        new: "Заявка принята",
        in_progress: "Заявка в работе",
        waiting_user: "Нужен ваш ответ",
        resolved: "Проверьте решение",
        closed: "Закрыта",
      },
      hide_from_requester: ["internal_notes", "ola_details", "raw_diagnostics"],
      show_to_requester: ["public_messages", "public_status", "expected_due_at"],
    });
  });

  it("настраивает notification policy в шаблоне без ручного JSON", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Уведомления")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить уведомления" }));

    const templateControl = (label: string) => {
      const controls = screen.getAllByLabelText(label);
      return controls[controls.length - 1];
    };

    fireEvent.click(templateControl("Создание: очереди"));
    fireEvent.click(templateControl("Ответ пользователя: исполнителю"));
    fireEvent.click(templateControl("Ответ пользователя: очередь без исполнителя"));
    fireEvent.click(templateControl("Нарушение срока: руководителю"));
    fireEvent.click(templateControl("Канал: Telegram"));
    fireEvent.click(templateControl("Канал: VK Teams"));

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          notification_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.notification_policy).toMatchObject({
      on_created: {
        requester: true,
        queue: false,
      },
      on_requester_replied: {
        assignee: false,
        queue_if_no_assignee: false,
      },
      on_sla_breach: {
        queue_lead: false,
      },
      channels: {
        web: true,
        email: true,
        telegram: true,
        vk_teams: true,
      },
    });
  });

  it("показывает preview requester/support видимости и каналов до публикации", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Видимость")[0]);

    const visibilityPreview = screen.getByTestId("visibility-policy-preview");
    expect(visibilityPreview).toHaveTextContent("Предпросмотр видимости");
    expect(visibilityPreview).toHaveTextContent("Заявитель");
    expect(visibilityPreview).toHaveTextContent("Support");
    expect(visibilityPreview).toHaveTextContent("raw_diagnostics");
    expect(visibilityPreview).toHaveTextContent("expected_due_at");

    fireEvent.click(screen.getAllByText("Уведомления")[0]);

    const notificationPreview = screen.getByTestId("notification-policy-preview");
    expect(notificationPreview).toHaveTextContent("Предпросмотр уведомлений");
    expect(notificationPreview).toHaveTextContent("Создание: requester, queue");
    expect(notificationPreview).toHaveTextContent("email");
    expect(notificationPreview).toHaveTextContent("web");
  });

  it("настраивает reporting policy в шаблоне без ручного JSON", async () => {
    const saveCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/forms/publish" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              summary: {
                ...createFormsPayload().summary,
                version: "1.0.4"
              },
              forms: createFormsPayload().forms,
              message: "Каталог опубликован как версия 1.0.4."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder();

    await screen.findByText("Визуальный конструктор шаблона обращения");
    fireEvent.click(screen.getAllByText("Паспорт")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Вставить паспорт" }));

    const templateControl = (label: string) => {
      const controls = screen.getAllByLabelText(label);
      return controls[controls.length - 1];
    };

    fireEvent.change(templateControl("Разделы паспорта"), {
      target: { value: "problem, evidence, user_result, action_package" }
    });
    fireEvent.change(templateControl("Теги отчёта"), {
      target: { value: "standard_passport, knowledge_candidate" }
    });
    fireEvent.change(templateControl("Скрыть из экспорта"), {
      target: { value: "internal_result, raw_diagnostics" }
    });
    fireEvent.change(templateControl("Типы доказательств для evidence"), {
      target: { value: "screenshot, file_attachment, diagnostic_result" }
    });
    fireEvent.click(templateControl("Включать журнал действий"));
    fireEvent.click(templateControl("Включать связанные объекты"));
    fireEvent.click(templateControl("Включать внутренние заметки"));
    fireEvent.click(templateControl("Требовать официальный паспорт"));
    fireEvent.click(templateControl("Подсказки для базы знаний"));

    fireEvent.click(screen.getAllByRole("button", { name: "Опубликовать" })[0]);

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });

    const savedPrinter = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          reporting_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer");

    expect(savedPrinter?.reporting_policy).toMatchObject({
      required_sections: ["problem", "evidence", "user_result", "action_package"],
      evidence_package: {
        include_action_log: false,
        include_related_objects: false,
      },
      export_visibility: {
        hide_sections: ["internal_result", "raw_diagnostics"],
      },
      required_evidence_types: {
        evidence: ["screenshot", "file_attachment", "diagnostic_result"],
      },
      report_tags: ["standard_passport", "knowledge_candidate"],
      include_internal_notes: true,
      require_official_passport: true,
      knowledge_draft_hints: {
        enabled: true,
      },
    });
  });

  it("публикует выбранный шаблон и политики в отдельный реестр целевой модели", async () => {
    const publishCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({
            status: "success",
            data: createHelpdeskModelRegistryPayload()
          });
        }

        if (url === "/api/web/admin/helpdesk-model/request-templates/publish-from-form" && method === "POST") {
          publishCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              request_template: {
                template_code: "printer",
                version: "1.0.1",
                public_title: "Печать / принтер",
                internal_name: "incident / printer",
                description: "Проблемы печати",
                ticket_type: "incident",
                category_id: null,
                service_id: null,
                subcategory_id: null,
                form_schema_id: "printer_form",
                workflow_profile_id: "incident",
                priority_policy_code: "printer_priority_policy",
                routing_policy_code: null,
                sla_policy_id: null,
                ola_policy_code: null,
                approval_policy_code: null,
                diagnostic_policy_code: null,
                closure_policy_code: null,
                visibility_policy_code: null,
                notification_policy_code: null,
                config: {},
                overrides: {},
                is_active: true,
                published_at: "2026-04-30T18:00:00+05:00",
                created_at: "2026-04-30T18:00:00+05:00",
                created_by: "admin1",
                updated_at: "2026-04-30T18:00:00+05:00",
                updated_by: "admin1"
              },
              form_schema: {
                schema_id: "printer_form",
                version: "1.0.1",
                title: "Печать / принтер",
                description: "Проблемы печати",
                form_key: "printer",
                request_template_code: "printer",
                ticket_type: "incident",
                fields: [],
                conditions: [],
                config: {},
                is_active: true,
                published_at: "2026-04-30T18:00:00+05:00",
                created_at: "2026-04-30T18:00:00+05:00",
                created_by: "admin1",
                updated_at: "2026-04-30T18:00:00+05:00",
                updated_by: "admin1"
              },
              policies: {
                priority: {
                  kind: "priority",
                  table: "priority_policies",
                  code: "printer_priority_policy",
                  version: "1.0.1",
                  title: "Печать / принтер: приоритет",
                  description: null,
                  scope_level: "request_template",
                  scope_ref: "printer",
                  config: { impact_field: "impact_scope" },
                  is_active: true,
                  published_at: "2026-04-30T18:00:00+05:00",
                  created_at: "2026-04-30T18:00:00+05:00",
                  created_by: "admin1",
                  updated_at: "2026-04-30T18:00:00+05:00",
                  updated_by: "admin1"
                }
              },
              message: "Шаблон обращения printer опубликован в реестр как версия 1.0.1. Политик опубликовано: 1."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.publish"] });

    await screen.findByText("Реестр целевой модели");
    const publishButton = screen.getByRole("button", { name: "Опубликовать в реестр" });
    await waitFor(() => {
      expect(publishButton).not.toBeDisabled();
    });
    fireEvent.click(publishButton);

    await waitFor(() => {
      expect(publishCalls).toHaveLength(1);
    });

    const payload = publishCalls[0] as {
      form: {
        key: string;
        fields: Array<{ key: string }>;
        priority_policy?: Record<string, unknown>;
      };
      publish_policies: boolean;
    };
    expect(payload.form.key).toBe("printer");
    expect(payload.form.fields.map((field) => field.key)).toContain("room");
    expect(payload.publish_policies).toBe(true);
    expect(await screen.findByText(/Шаблон обращения printer опубликован/)).toBeInTheDocument();
  });

  it("показывает policy refs как основной режим и сохраняет выбранный ref в draft", async () => {
    const draftCalls: unknown[] = [];
    const registryPayload = createHelpdeskModelRegistryPayload();
    registryPayload.request_templates = [
      {
        template_code: "site_unavailable",
        version: "1.0.1",
        public_title: "Не открывается сайт",
        internal_name: "Incident / Website unavailable",
        description: "Проблемы доступа к сайту",
        ticket_type: "incident",
        category_id: 10,
        service_id: null,
        subcategory_id: null,
        form_schema_id: "site_form",
        workflow_profile_id: "incident_default",
        priority_policy_code: null,
        routing_policy_code: "website_routing_v5",
        sla_policy_id: null,
        sla_policy_code: null,
        ola_policy_code: null,
        approval_policy_code: null,
        diagnostic_policy_code: null,
        closure_policy_code: null,
        visibility_policy_code: null,
        notification_policy_code: null,
        reporting_policy_code: null,
        config: {},
        overrides: {},
        is_active: true,
        published_at: "2026-05-02T18:00:00+05:00",
        created_at: "2026-05-02T18:00:00+05:00",
        created_by: "admin1",
        updated_at: "2026-05-02T18:00:00+05:00",
        updated_by: "admin1"
      }
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: createFormsPayload() });
        }
        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({ status: "ok", pack_key: "request_forms", current: null, preferred: null, packs: [] });
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: registryPayload });
        }
        if (url === "/api/web/admin/forms/save-draft" && method === "POST") {
          draftCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              draft_id: "draft-policy-ref",
              pack_key: "request_forms",
              base_version: "1.0.3",
              status: "draft",
              summary: createFormsPayload().summary,
              published_version: null,
              preferred_version: "1.0.3",
              message: "Черновик сохранён. Активная версия не изменилась."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.publish"] });

    expect(await screen.findByText("Policy refs")).toBeInTheDocument();
    expect(screen.getByText("Advanced inline policy JSON")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Routing policy ref"), {
      target: { value: "website_routing_v5" }
    });

    expect(await screen.findByText("Affects active templates: Не открывается сайт")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Сохранить черновик" })[0]);

    await waitFor(() => {
      expect(draftCalls).toHaveLength(1);
    });

    expect(draftCalls[0]).toMatchObject({
      forms: [
        {
          key: "printer",
          routing_policy_ref: "website_routing_v5"
        }
      ]
    });
  });
  it("публикует отдельную routing policy из редактора политик", async () => {
    const publishCalls: unknown[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({
            status: "success",
            data: createFormsPayload()
          });
        }

        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({
            status: "ok",
            pack_key: "request_forms",
            current: null,
            preferred: null,
            packs: []
          });
        }

        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({
            status: "success",
            data: createHelpdeskModelRegistryPayload()
          });
        }

        if (url === "/api/web/admin/helpdesk-model/policies/publish" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          publishCalls.push(body);
          return jsonResponse({
            status: "success",
            data: {
              policy: {
                kind: "routing",
                table: "routing_policies",
                code: body.code,
                version: "1.0.1",
                title: body.title,
                description: body.description,
                scope_level: body.scope_level,
                scope_ref: body.scope_ref,
                config: body.config,
                is_active: true,
                published_at: "2026-04-30T18:30:00+05:00",
                created_at: "2026-04-30T18:30:00+05:00",
                created_by: "admin1",
                updated_at: "2026-04-30T18:30:00+05:00",
                updated_by: "admin1"
              },
              message: "Политика printer_routing_policy опубликована в реестр как версия 1.0.1."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.publish"] });

    await screen.findByText("Редакторы политик");
    const publishPolicyButton = screen.getByRole("button", { name: "Опубликовать политику" });
    await waitFor(() => {
      expect(publishPolicyButton).not.toBeDisabled();
      expect(screen.getByLabelText("Код политики")).toHaveValue("printer_routing_policy");
    });
    fireEvent.change(screen.getByLabelText("Куда направить"), {
      target: { value: "networks" }
    });
    fireEvent.click(publishPolicyButton);

    await waitFor(() => {
      expect(publishCalls).toHaveLength(1);
    });
    expect(publishCalls[0]).toMatchObject({
      kind: "routing",
      code: "printer_routing_policy",
      scope_level: "request_template",
      scope_ref: "printer",
      config: {
        rules: [
          expect.objectContaining({
            then: expect.objectContaining({
              queue: "networks"
            })
          })
        ]
      }
    });
    expect(await screen.findByText(/Политика printer_routing_policy опубликована/)).toBeInTheDocument();
  });

  it("показывает предпросмотр влияния перед публикацией политики", async () => {
    const registryPayload = createHelpdeskModelRegistryPayload();
    registryPayload.request_templates = [
      {
        template_code: "printer",
        version: "1.0.1",
        public_title: "Печать / принтер",
        internal_name: "Incident / Printer",
        description: "Проблемы печати",
        ticket_type: "incident",
        category_id: 10,
        service_id: null,
        subcategory_id: null,
        form_schema_id: "printer_form",
        workflow_profile_id: "incident_default",
        priority_policy_code: null,
        routing_policy_code: "printer_routing_policy",
        sla_policy_id: null,
        sla_policy_code: null,
        ola_policy_code: null,
        approval_policy_code: null,
        diagnostic_policy_code: null,
        closure_policy_code: null,
        visibility_policy_code: null,
        notification_policy_code: null,
        reporting_policy_code: null,
        config: {},
        overrides: {},
        is_active: true,
        published_at: "2026-05-02T18:00:00+05:00",
        created_at: "2026-05-02T18:00:00+05:00",
        created_by: "admin1",
        updated_at: "2026-05-02T18:00:00+05:00",
        updated_by: "admin1"
      },
      {
        template_code: "site_unavailable",
        version: "1.0.1",
        public_title: "Не открывается сайт",
        internal_name: "Incident / Website unavailable",
        description: "Проблемы доступа к сайту",
        ticket_type: "incident",
        category_id: 10,
        service_id: null,
        subcategory_id: null,
        form_schema_id: "site_form",
        workflow_profile_id: "incident_default",
        priority_policy_code: null,
        routing_policy_code: "printer_routing_policy",
        sla_policy_id: null,
        sla_policy_code: null,
        ola_policy_code: null,
        approval_policy_code: null,
        diagnostic_policy_code: null,
        closure_policy_code: null,
        visibility_policy_code: null,
        notification_policy_code: null,
        reporting_policy_code: null,
        config: {},
        overrides: {},
        is_active: true,
        published_at: "2026-05-02T18:00:00+05:00",
        created_at: "2026-05-02T18:00:00+05:00",
        created_by: "admin1",
        updated_at: "2026-05-02T18:00:00+05:00",
        updated_by: "admin1"
      },
    ];
    registryPayload.ticket_types = [
      {
        code: "incident",
        version: "1.0.1",
        title: "Инцидент",
        description: null,
        default_workflow_profile_id: "incident_default",
        default_priority_policy_code: null,
        default_routing_policy_code: "printer_routing_policy",
        default_sla_policy_id: null,
        default_sla_policy_code: null,
        default_ola_policy_code: null,
        default_approval_policy_code: null,
        default_diagnostic_policy_code: null,
        default_closure_policy_code: null,
        default_visibility_policy_code: null,
        default_notification_policy_code: null,
        default_reporting_policy_code: null,
        feature_flags: {},
        config: {},
        is_active: true,
        published_at: "2026-05-02T18:00:00+05:00",
        created_at: "2026-05-02T18:00:00+05:00",
        created_by: "admin1",
        updated_at: "2026-05-02T18:00:00+05:00",
        updated_by: "admin1"
      },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: createFormsPayload() });
        }
        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({ status: "ok", pack_key: "request_forms", current: null, preferred: null, packs: [] });
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: registryPayload });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.publish"] });

    await screen.findByText("Редакторы политик");
    expect(await screen.findByText("Предпросмотр влияния публикации")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Шаблонов: 2")).toBeInTheDocument();
      expect(screen.getByText("Типов тикетов: 1")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Печать / принтер").length).toBeGreaterThan(0);
    expect(screen.getByText("Не открывается сайт")).toBeInTheDocument();
    expect(screen.getAllByText("Инцидент").length).toBeGreaterThan(0);
  });

  it("публикует reporting policy для паспорта решения", async () => {
    const publishCalls: Record<string, unknown>[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: createFormsPayload() });
        }
        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({ status: "ok", pack_key: "request_forms", current: null, preferred: null, packs: [] });
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: createHelpdeskModelRegistryPayload() });
        }
        if (url === "/api/web/admin/helpdesk-model/policies/publish" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          publishCalls.push(body);
          return jsonResponse({
            status: "success",
            data: {
              policy: {
                kind: "reporting",
                table: "reporting_policies",
                code: body.code,
                version: "1.0.1",
                title: body.title,
                description: body.description,
                scope_level: body.scope_level,
                scope_ref: body.scope_ref,
                config: body.config,
                is_active: true,
                published_at: "2026-04-30T18:30:00+05:00",
                created_at: "2026-04-30T18:30:00+05:00",
                created_by: "admin1",
                updated_at: "2026-04-30T18:30:00+05:00",
                updated_by: "admin1"
              },
              message: "Политика printer_reporting_policy опубликована в реестр как версия 1.0.1."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.publish"] });

    await screen.findByText("Редакторы политик");
    fireEvent.click(screen.getByRole("button", { name: /Политика: Паспорт решения/ }));
    await waitFor(() => {
      expect(screen.getByLabelText("Код политики")).toHaveValue("printer_reporting_policy");
    });
    fireEvent.change(screen.getByLabelText("Разделы паспорта"), {
      target: { value: "problem, evidence, user_result" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Опубликовать политику" }));

    await waitFor(() => {
      expect(publishCalls).toHaveLength(1);
    });
    expect(publishCalls[0]).toMatchObject({
      kind: "reporting",
      code: "printer_reporting_policy",
      config: {
        required_sections: ["problem", "evidence", "user_result"],
        evidence_package: {
          include_action_log: true,
          include_related_objects: true
        }
      }
    });
  });

  it("публикует smart view из структурированных полей без ручного JSON", async () => {
    const publishCalls: Record<string, unknown>[] = [];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: createFormsPayload() });
        }
        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({ status: "ok", pack_key: "request_forms", current: null, preferred: null, packs: [] });
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: createHelpdeskModelRegistryPayload() });
        }
        if (url === "/api/web/admin/helpdesk-model/smart-views/publish" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          publishCalls.push(body);
          return jsonResponse({
            status: "success",
            data: {
              smart_view: {
                code: body.code,
                version: "1.0.1",
                title: body.title,
                description: body.description,
                scope_level: body.scope_level,
                scope_ref: body.scope_ref,
                filter: body.filter,
                sort: body.sort,
                columns: body.columns,
                is_active: true,
                published_at: "2026-05-02T18:30:00+05:00",
                created_at: "2026-05-02T18:30:00+05:00",
                created_by: "admin1",
                updated_at: "2026-05-02T18:30:00+05:00",
                updated_by: "admin1"
              },
              message: "Smart view ola_risk_ops опубликован в реестр как версия 1.0.1."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.publish"] });

    await screen.findByText("Редактор smart views");
    const smartViewControl = (label: string) => {
      const controls = screen.getAllByLabelText(label);
      return controls[controls.length - 1];
    };

    fireEvent.change(smartViewControl("Код"), { target: { value: "ola_risk_ops" } });
    fireEvent.change(smartViewControl("Название"), { target: { value: "OLA риск" } });
    fireEvent.change(smartViewControl("Статусы исключить"), { target: { value: "closed, canceled, resolved" } });
    fireEvent.change(smartViewControl("Срок до, часов"), { target: { value: "6" } });
    fireEvent.change(smartViewControl("Поля сроков"), { target: { value: "ola_ack_due_at, ola_processing_due_at" } });
    fireEvent.change(smartViewControl("Сортировать по"), { target: { value: "ola_processing_due_at" } });
    fireEvent.change(smartViewControl("Направление сортировки"), { target: { value: "desc" } });
    fireEvent.change(smartViewControl("Колонки"), {
      target: { value: "ticket_id,title,status,queue_id,ola_processing_due_at" }
    });

    fireEvent.click(screen.getByRole("button", { name: "Опубликовать smart view" }));

    await waitFor(() => {
      expect(publishCalls).toHaveLength(1);
    });
    expect(publishCalls[0]).toMatchObject({
      code: "ola_risk_ops",
      title: "OLA риск",
      scope_level: "system",
      scope_ref: null,
      filter: {
        status_not_in: ["closed", "canceled", "resolved"],
        due_before_hours: 6,
        due_fields: ["ola_ack_due_at", "ola_processing_due_at"],
      },
      sort: [{ field: "ola_processing_due_at", direction: "desc" }],
      columns: ["ticket_id", "title", "status", "queue_id", "ola_processing_due_at"],
    });
  });

  it("скрывает JSON и lifecycle-действия политики до открытия advanced режима", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: createFormsPayload() });
        }
        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({ status: "ok", pack_key: "request_forms", current: null, preferred: null, packs: [] });
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: createHelpdeskModelRegistryPayload() });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.publish"] });

    await screen.findByText("Редакторы политик");
    expect(screen.queryByRole("button", { name: "Сравнить версии" })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "JSON конфигурации политики" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Расширенный JSON и версии" }));

    expect(screen.getByRole("button", { name: "Сравнить версии" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "JSON конфигурации политики" })).toBeInTheDocument();
  });

  it("вызывает diff, deactivate и rollback для версий политики", async () => {
    const lifecycleCalls: Array<{ url: string; body: Record<string, unknown> }> = [];
    const registryPayload = createHelpdeskModelRegistryPayload();
    registryPayload.policies.routing = [
      {
        kind: "routing",
        table: "routing_policies",
        code: "printer_routing_policy",
        version: "1.0.1",
        title: "Routing policy",
        description: null,
        scope_level: "request_template",
        scope_ref: "printer",
        config: { default_queue: "servicedesk_l1" },
        is_active: false,
        published_at: "2026-04-30T10:00:00+05:00",
        created_at: "2026-04-30T10:00:00+05:00",
        created_by: "admin1",
        updated_at: "2026-04-30T10:00:00+05:00",
        updated_by: "admin1"
      },
      {
        kind: "routing",
        table: "routing_policies",
        code: "printer_routing_policy",
        version: "1.0.2",
        title: "Routing policy v2",
        description: null,
        scope_level: "request_template",
        scope_ref: "printer",
        config: { default_queue: "networks" },
        is_active: true,
        published_at: "2026-04-30T11:00:00+05:00",
        created_at: "2026-04-30T11:00:00+05:00",
        created_by: "admin1",
        updated_at: "2026-04-30T11:00:00+05:00",
        updated_by: "admin1"
      }
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: createFormsPayload() });
        }
        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse({ status: "ok", pack_key: "request_forms", current: null, preferred: null, packs: [] });
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: registryPayload });
        }
        if (url === "/api/web/admin/helpdesk-model/policies/diff" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          lifecycleCalls.push({ url, body });
          return jsonResponse({
            status: "success",
            data: {
              kind: "routing",
              code: "printer_routing_policy",
              from_policy: registryPayload.policies.routing[0],
              to_policy: registryPayload.policies.routing[1],
              changes: [{ path: "config.default_queue", from: "servicedesk_l1", to: "networks" }]
            }
          });
        }
        if (url === "/api/web/admin/helpdesk-model/policies/deactivate" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          lifecycleCalls.push({ url, body });
          return jsonResponse({
            status: "success",
            data: {
              policy: { ...registryPayload.policies.routing[1], is_active: false },
              message: "Политика printer_routing_policy версии 1.0.2 деактивирована."
            }
          });
        }
        if (url === "/api/web/admin/helpdesk-model/policies/rollback" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          lifecycleCalls.push({ url, body });
          return jsonResponse({
            status: "success",
            data: {
              policy: { ...registryPayload.policies.routing[0], version: "1.0.3", is_active: true },
              message: "Политика printer_routing_policy откатана к версии 1.0.1; новая активная версия 1.0.3."
            }
          });
        }

        throw new Error(`Unexpected fetch: ${method} ${url}`);
      })
    );

    renderFormsBuilder({ permissions: ["admin.forms.publish"] });

    await screen.findByText("Редакторы политик");
    await waitFor(() => {
      expect(screen.getByLabelText("Код политики")).toHaveValue("printer_routing_policy");
    });

    fireEvent.click(screen.getByRole("button", { name: "Расширенный JSON и версии" }));

    fireEvent.click(screen.getByRole("button", { name: "Сравнить версии" }));
    expect(await screen.findByText("config.default_queue")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Деактивировать выбранную версию" }));
    expect(await screen.findByText(/деактивирована/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Откатить к выбранной версии" }));
    expect(await screen.findByText(/откатана к версии 1.0.1/)).toBeInTheDocument();

    expect(lifecycleCalls).toEqual([
      {
        url: "/api/web/admin/helpdesk-model/policies/diff",
        body: { kind: "routing", code: "printer_routing_policy", from_version: "1.0.1", to_version: "1.0.2" }
      },
      {
        url: "/api/web/admin/helpdesk-model/policies/deactivate",
        body: { kind: "routing", code: "printer_routing_policy", version: "1.0.2" }
      },
      {
        url: "/api/web/admin/helpdesk-model/policies/rollback",
        body: { kind: "routing", code: "printer_routing_policy", target_version: "1.0.1" }
      }
    ]);
  });
});
