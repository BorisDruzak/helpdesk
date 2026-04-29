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

    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));

    await waitFor(() => {
      expect(screen.getByText(/Каталог опубликован как версия 1.0.4/)).toBeInTheDocument();
    });

    expect(saveCalls).toHaveLength(1);
    expect(saveCalls[0]).toMatchObject({
      title: "Каталог заявок",
      forms: [
        expect.objectContaining({
          key: "printer",
          title: "Печать / принтер"
        }),
        expect.objectContaining({
          key: "printer_repair",
          request_kind: "printer_repair",
          title: "Ремонт принтера",
          fields: [
            expect.objectContaining({
              key: "issue_code",
              label: "Код поломки"
            })
          ]
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
    expect(screen.getByText("Форма")).toBeInTheDocument();
    expect(screen.getByText("Роутинг")).toBeInTheDocument();
    expect(screen.getByText("Плейбук")).toBeInTheDocument();
    expect(screen.getByText("Запуск выключен")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Включить"));
    expect(screen.getByText("Нужен ключ плейбука")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Ключ плейбука"), {
      target: { value: "printer_diagnostic" }
    });
    expect(screen.getByText("Готов к запуску после создания тикета")).toBeInTheDocument();
    expect(screen.getByText("ticket_created")).toBeInTheDocument();
    expect(screen.getByText("diagnostic")).toBeInTheDocument();
  });
});
