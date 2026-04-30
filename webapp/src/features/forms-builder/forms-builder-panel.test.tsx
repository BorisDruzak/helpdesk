import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AdminFormsPayload } from "./api";
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
      field_type_options: [
        { value: "text", label: "Текст" },
        { value: "textarea", label: "Большой текст" },
        { value: "select", label: "Список" },
        { value: "radio", label: "Переключатель" },
        { value: "checkbox", label: "Флажок" }
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
}

function createHelpdeskModelRegistryPayload() {
  return {
    summary: {
      request_templates_count: 0,
      active_request_templates_count: 0,
      policies_count: 0,
      active_policies_count: 0,
      smart_views_count: 0,
      active_smart_views_count: 0,
    },
    capabilities: {
      registry_endpoint: "/api/web/admin/helpdesk-model/policies",
      publish_from_form_endpoint: "/api/web/admin/helpdesk-model/request-templates/publish-from-form",
      publish_policy_endpoint: "/api/web/admin/helpdesk-model/policies/publish",
      inheritance_order: ["system", "ticket_type", "category", "request_template"],
      policy_kinds: ["approval", "closure", "diagnostic", "notification", "priority", "routing", "visibility"],
    },
    request_templates: [],
    policies: {
      approval: [],
      closure: [],
      diagnostic: [],
      notification: [],
      priority: [],
      routing: [],
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
    expect(screen.getAllByRole("button", { name: /Опубликовать новую версию|Сохранить изменения/ })[0]).toBeDisabled();
  });

  it("показывает каталог форм и публикует новую версию", async () => {
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

        if (url === "/api/web/admin/forms/save" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
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

    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));

    await waitFor(() => {
      expect(screen.getByText(/Каталог опубликован как версия 1.0.4/)).toBeInTheDocument();
    });

    expect(saveCalls).toHaveLength(1);
    const savedPrinterRepair = (
      saveCalls[0] as {
        forms: Array<{
          key: string;
          fields?: Array<{ key: string }>;
          field_roles?: Record<string, string[]>;
          priority_policy?: Record<string, unknown>;
        }>;
      }
    ).forms.find((form) => form.key === "printer_repair");
    expect(savedPrinterRepair?.fields?.some((field) => field.key === "impact_scope")).toBe(true);
    expect(savedPrinterRepair?.field_roles?.impact_scope).toContain("priority_field");
    expect(savedPrinterRepair?.priority_policy).toMatchObject({
      impact_field: "impact_scope",
      urgency_field: "work_continuity",
      importance_field: "business_importance",
    });
    expect(saveCalls[0]).toMatchObject({
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
    expect(screen.getByRole("button", { name: "Сохранить изменения" })).toBeDisabled();
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

        if (url === "/api/web/admin/forms/save" && method === "POST") {
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

    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));

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

        if (url === "/api/web/admin/forms/save" && method === "POST") {
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

    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));

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

        if (url === "/api/web/admin/forms/save" && method === "POST") {
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

    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));

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
});
