import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminRequestTemplateStudioPage } from "./request-template-studio-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function catalogPayload() {
  return {
    status: "ok",
    services: [
      {
        code: "mail",
        public_title: "Почта",
        short_description: "Корпоративная почта",
        lifecycle_status: "published",
        visibility: "public",
        owner_queue_id: 7,
      },
      {
        code: "it",
        public_title: "ИТ поддержка",
        lifecycle_status: "published",
        visibility: "public",
      },
    ],
    offerings: [
      {
        code: "new_box",
        full_code: "mail.new_box",
        public_title: "Новый ящик",
        service_code: "mail",
        lifecycle_status: "published",
        visibility: "public",
        request_template_key: "mailbox",
        routing_policy_code: "route_l1",
      },
      {
        code: "password_reset",
        full_code: "it.password_reset",
        public_title: "Сброс пароля",
        service_code: "it",
        lifecycle_status: "published",
        visibility: "public",
        request_template_key: "password_reset",
      },
    ],
  };
}

function registryPayload() {
  return {
    summary: {
      request_templates_count: 1,
      active_request_templates_count: 1,
      ticket_types_count: 1,
      active_ticket_types_count: 1,
      form_schemas_count: 1,
      active_form_schemas_count: 1,
      policies_count: 3,
      active_policies_count: 3,
      smart_views_count: 0,
      active_smart_views_count: 0,
    },
    capabilities: {
      registry_endpoint: "/api/web/admin/helpdesk-model/policies",
      publish_from_form_endpoint: "/api/web/admin/helpdesk-model/request-templates/publish-from-form",
      publish_policy_endpoint: "/api/web/admin/helpdesk-model/policies/publish",
      publish_ticket_type_endpoint: "/api/web/admin/helpdesk-model/ticket-types/publish",
      publish_form_schema_endpoint: "/api/web/admin/helpdesk-model/form-schemas/publish",
      publish_smart_view_endpoint: "/api/web/admin/helpdesk-model/smart-views/publish",
      inheritance_order: ["system", "ticket_type", "request_template"],
      policy_kinds: ["priority", "routing", "sla", "closure"],
    },
    request_templates: [
      {
        template_code: "mailbox",
        version: "1.0.0",
        public_title: "Почтовый ящик",
        internal_name: null,
        description: "Создание почтового ящика",
        ticket_type: "service_request",
        category_id: null,
        service_id: null,
        subcategory_id: null,
        form_schema_id: "mailbox_form",
        workflow_profile_id: "service_request_default",
        priority_policy_code: "priority_default",
        routing_policy_code: "route_l1",
        sla_policy_id: null,
        sla_policy_code: "sla_p2",
        ola_policy_code: null,
        approval_policy_code: null,
        diagnostic_policy_code: null,
        closure_policy_code: "closure_basic",
        visibility_policy_code: "visibility_default",
        notification_policy_code: null,
        reporting_policy_code: null,
        config: {},
        overrides: {},
        is_active: true,
        published_at: "2026-05-19T10:00:00+05:00",
        created_at: "2026-05-19T10:00:00+05:00",
        created_by: "admin",
        updated_at: "2026-05-19T10:00:00+05:00",
        updated_by: "admin",
      },
    ],
    ticket_types: [],
    form_schemas: [
      {
        schema_id: "mailbox_form",
        version: "1.0.0",
        title: "Форма почтового ящика",
        description: "Поля заявки на почтовый ящик",
        form_key: "mailbox",
        request_template_code: "mailbox",
        ticket_type: "service_request",
        fields: [
          {
            key: "employee",
            label: "Сотрудник",
            type: "user_picker",
            required: true,
            options: [],
            validation: {},
            process_mapping: { role: "requester" },
            visibility: {},
            sort_order: 1,
          },
          {
            key: "quota",
            label: "Квота",
            type: "select",
            required: false,
            options: [{ value: "standard", label: "Стандартная" }],
            validation: {},
            process_mapping: {},
            visibility: { field: "employee" },
            sort_order: 2,
          },
        ],
        conditions: [],
        config: {},
        is_active: true,
        published_at: "2026-05-19T10:00:00+05:00",
        created_at: "2026-05-19T10:00:00+05:00",
        created_by: "admin",
        updated_at: "2026-05-19T10:00:00+05:00",
        updated_by: "admin",
      },
    ],
    policies: {
      priority: [{ kind: "priority", table: "priority_policies", code: "priority_default", version: "1.0.0", title: "Приоритет по умолчанию", description: null, scope_level: "system", scope_ref: null, config: {}, is_active: true, published_at: null, created_at: null, created_by: null, updated_at: null, updated_by: null }],
      routing: [{ kind: "routing", table: "routing_policies", code: "route_l1", version: "1.0.0", title: "Маршрут L1", description: null, scope_level: "request_template", scope_ref: "mailbox", config: {}, is_active: true, published_at: null, created_at: null, created_by: null, updated_at: null, updated_by: null }],
      sla: [{ kind: "sla", table: "sla_policies", code: "sla_p2", version: "1.0.0", title: "SLA P2", description: null, scope_level: "system", scope_ref: null, config: {}, is_active: true, published_at: null, created_at: null, created_by: null, updated_at: null, updated_by: null }],
      closure: [{ kind: "closure", table: "closure_policies", code: "closure_basic", version: "1.0.0", title: "Базовое закрытие", description: null, scope_level: "system", scope_ref: null, config: {}, is_active: true, published_at: null, created_at: null, created_by: null, updated_at: null, updated_by: null }],
      visibility: [{ kind: "visibility", table: "visibility_policies", code: "visibility_default", version: "1.0.0", title: "Видимость", description: null, scope_level: "system", scope_ref: null, config: {}, is_active: true, published_at: null, created_at: null, created_by: null, updated_at: null, updated_by: null }],
    },
    smart_views: [],
  };
}

function formsPayload() {
  return {
    summary: {
      pack_key: "request_forms",
      version: "1.0.0",
      title: "Каталог заявок",
      description: null,
      forms_count: 0,
      fields_count: 0,
      required_fields_count: 0,
      last_published_at: null,
      last_published_by: null,
    },
    capabilities: {
      current_endpoint: "/api/web/admin/forms/current",
      save_endpoint: "/api/web/admin/forms/save",
      preview_endpoint: "/api/web/admin/forms/route-preview",
      field_type_options: [],
      field_role_options: [],
    },
    forms: [],
  };
}

function healthPayload() {
  return {
    status: "ok",
    summary: { total: 1, ok: 1, warning: 0, error: 0 },
    templates: [
      {
        template_id: "mailbox",
        template_code: "mailbox",
        template_name: "Почтовый ящик",
        version: "1.0.0",
        status: "published",
        owner: "admin",
        health_status: "ok",
        health_score: 100,
        conflict_count: 0,
        issue_count: 0,
        issues_by_severity: { critical: 0, error: 0, warning: 0, info: 0 },
        checks: {
          priority: { status: "ok", reference: "priority_default", policy_title: "Приоритет по умолчанию" },
          routing: { status: "ok", reference: "route_l1", resolved_queue: "servicedesk_l1" },
          sla: { status: "ok", reference: "sla_p2" },
          closure: { status: "ok", reference: "closure_basic" },
          visibility: { status: "ok", reference: "visibility_default" },
        },
        issues: [],
        last_checked_at: "2026-05-19T10:00:00+05:00",
      },
    ],
  };
}

function simulationResult() {
  return {
    template_code: "mailbox",
    routing: { status: "ok", policy_code: "route_l1", target_queue_name: "Service Desk L1" },
    priority: { status: "ok", policy_code: "priority_default", priority: "P2" },
    sla: { status: "ok", policy_code: "sla_p2", sla_target: "8h" },
    ola: { status: "not_configured" },
    approval: { status: "ok", required: "нет" },
    closure: { status: "ok", policy_code: "closure_basic", required: "resolution_code" },
    visibility: { status: "ok", policy_code: "visibility_default", public_status: "В работе" },
    diagnostic: { status: "not_configured" },
    warnings: ["OLA policy не задана"],
    would_create_ticket: false,
  };
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{`${location.pathname}${location.search}`}</span>;
}

function renderPage(initialEntry = "/app/admin/request-template-studio?service=mail&offering=mail.new_box&template=mailbox") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={queryClient}>
        <LocationProbe />
        <AdminRequestTemplateStudioPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminRequestTemplateStudioPage", () => {
  it("opens create wizard and creates a dirty no-code draft", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/admin/service-catalog") {
          return jsonResponse(catalogPayload());
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: registryPayload() });
        }
        if (url === "/api/web/admin/helpdesk/policy-health") {
          return jsonResponse(healthPayload());
        }
        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: formsPayload() });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderPage();

    await screen.findByRole("heading", { name: "Студия обращений" });
    fireEvent.click(screen.getByRole("button", { name: "Создать обращение" }));
    fireEvent.click(screen.getByRole("button", { name: "Заявка на доступ" }));
    fireEvent.change(screen.getByLabelText("Раздел"), { target: { value: "it" } });
    fireEvent.change(screen.getAllByLabelText("Название для пользователей")[0], { target: { value: "Доступ к CRM" } });
    fireEvent.change(screen.getAllByLabelText("Краткое описание")[0], { target: { value: "Запрос прав в CRM" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать черновик" }));

    expect(await screen.findByText("Есть несохранённые изменения")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("template=crm");
    expect(screen.getAllByText("В какую систему?").length).toBeGreaterThan(0);
  });

  it("edits form, process blocks, auto-fixes safe policies and saves a durable draft", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/admin/service-catalog") {
        return jsonResponse(catalogPayload());
      }
      if (url === "/api/web/admin/helpdesk-model/policies") {
        return jsonResponse({ status: "success", data: registryPayload() });
      }
      if (url === "/api/web/admin/helpdesk/policy-health") {
        return jsonResponse(healthPayload());
      }
      if (url === "/api/web/admin/forms/current") {
        return jsonResponse({ status: "success", data: formsPayload() });
      }
      if (url === "/api/web/admin/forms/save-draft" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            draft_id: "draft-1",
            pack_key: "request_forms",
            base_version: "1.0.0",
            status: "draft",
            summary: formsPayload().summary,
            published_version: "1.0.0",
            preferred_version: "1.0.0",
            message: "Черновик сохранён",
          },
        });
      }
      if (url === "/api/web/admin/service-catalog/offerings/save-draft" && init?.method === "POST") {
        return jsonResponse({ status: "ok", offering: catalogPayload().offerings[0] });
      }
      if (url === "/api/web/admin/helpdesk/policy-health/simulate" && init?.method === "POST") {
        return jsonResponse(simulationResult());
      }
      throw new Error(`Unexpected fetch: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    await screen.findByRole("button", { name: "Добавить поле" });
    fireEvent.click(screen.getByRole("button", { name: "Добавить поле" }));
    fireEvent.change(screen.getByLabelText("Название поля"), { target: { value: "Обоснование" } });
    fireEvent.change(screen.getByLabelText("Ключ поля"), { target: { value: "business_reason" } });
    fireEvent.click(screen.getByLabelText("Обязательное поле"));
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[3]);
    fireEvent.change(screen.getByLabelText("Кто выполняет заявку?"), { target: { value: "route_l1" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[4]);
    fireEvent.change(screen.getByLabelText("Срок выполнения"), { target: { value: "sla_p2" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[5]);
    fireEvent.click(screen.getByLabelText("Согласование не требуется"));
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[7]);
    fireEvent.change(screen.getByLabelText("Правила закрытия"), { target: { value: "closure_basic" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[8]);
    fireEvent.change(screen.getByLabelText("Уведомления"), { target: { value: "__unused__" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Исправить автоматически" })[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Применить всё" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[9]);
    expect(screen.getByText("Сначала сохраните черновик.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/forms/save-draft", expect.objectContaining({ method: "POST" })));
    const saveFormsCall = fetchMock.mock.calls.find(([url]) => String(url) === "/api/web/admin/forms/save-draft");
    const formBody = JSON.parse(String(saveFormsCall?.[1]?.body ?? "{}"));
    expect(formBody.forms[0]).toMatchObject({
      key: "mailbox",
      routing_policy_ref: "route_l1",
      sla_policy_ref: "sla_p2",
      closure_policy_ref: "closure_basic",
      notification_policy_ref: null,
    });
    expect(formBody.forms[0].fields).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: "business_reason", label: "Обоснование", required: true }),
      ]),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/service-catalog/offerings/save-draft", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("Черновик сохранён. Запустите проверку.")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[9]);
    expect(screen.getByText("Теперь можно запустить проверку.")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Запустить проверку" })[0]);
    expect(await screen.findByText("Проверка выполнена.")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[1]);
    fireEvent.change(screen.getByLabelText("Название поля"), { target: { value: "Бизнес-обоснование" } });
    expect(await screen.findByText("Проверка устарела, запустите повторно.")).toBeInTheDocument();
  });

  it("keeps raw technical policy refs hidden in basic mode and exposes Studio publish", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/admin/service-catalog") {
          return jsonResponse(catalogPayload());
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: registryPayload() });
        }
        if (url === "/api/web/admin/helpdesk/policy-health") {
          return jsonResponse(healthPayload());
        }
        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: formsPayload() });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderPage();

    await screen.findByRole("button", { name: "Добавить поле" });
    expect(screen.getAllByRole("link", { name: "Полный каталог услуг" })[0]).toHaveAttribute(
      "href",
      "/app/admin/service-catalog?service=mail&offering=mail.new_box&template=mailbox",
    );
    expect(screen.getByRole("button", { name: "Опубликовать из Studio" })).toBeInTheDocument();
    expect(screen.getByText("Публикация через Studio доступна после проверки draft и подтверждения safe publish preview.")).toBeInTheDocument();
    expect(screen.queryByText("routing_policy_code")).not.toBeInTheDocument();
    expect(screen.queryByText("route_l1")).not.toBeInTheDocument();
  });

  it("shows a publish success banner after confirmed Studio publish", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/admin/service-catalog") {
        return jsonResponse(catalogPayload());
      }
      if (url === "/api/web/admin/helpdesk-model/policies") {
        return jsonResponse({ status: "success", data: registryPayload() });
      }
      if (url === "/api/web/admin/helpdesk/policy-health") {
        return jsonResponse(healthPayload());
      }
      if (url === "/api/web/admin/forms/current") {
        return jsonResponse({ status: "success", data: formsPayload() });
      }
      if (url === "/api/web/admin/request-studio/publish-preview" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            validation: { status: "ok", can_publish: true, issues: [], confirmation_token: "token-1" },
            steps: [
              { key: "form_schema", label: "Форма пользователя", status: "will_publish", details: "Будет опубликована." },
              { key: "request_template", label: "Тип обращения", status: "will_publish", details: "Будет опубликован." },
            ],
            confirmation_token: "token-1",
            expires_at: "2099-01-01T00:00:00+00:00",
            summary: { creates: 0, updates: 2, noops: 1, blocked: 0, warnings: 0 },
            diffs: [
              {
                object_type: "form_schema",
                object_code: "mailbox_form",
                action: "update",
                title: "Форма пользователя",
                warnings: [],
                changes: [
                  {
                    path: "title",
                    label: "Название формы",
                    from_value: "Старая форма",
                    to_value: "Форма почтового ящика",
                    change_type: "changed",
                    severity: "info",
                  },
                ],
              },
              {
                object_type: "request_template",
                object_code: "mailbox",
                action: "noop",
                title: "Тип обращения",
                warnings: [],
                changes: [],
              },
            ],
            message: "Проверка пройдена. Подтвердите публикацию текущего draft.",
          },
        });
      }
      if (url === "/api/web/admin/request-studio/publish" && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}"));
        expect(body.confirmation_token).toBe("token-1");
        return jsonResponse({
          status: "success",
          data: {
            validation: { status: "ok", can_publish: true, issues: [], confirmation_token: "token-1" },
            request_template: registryPayload().request_templates[0],
            form_schema: registryPayload().form_schemas[0],
            service: catalogPayload().services[0],
            offering: catalogPayload().offerings[0],
            message: "Тип обращения опубликован из Studio.",
          },
        });
      }
      throw new Error(`Unexpected fetch: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    const publishButton = await screen.findByRole("button", { name: "Опубликовать из Studio" });
    await waitFor(() => expect(publishButton).toBeEnabled());
    fireEvent.click(publishButton);

    await waitFor(
      () => {
        expect(fetchMock).toHaveBeenCalledWith(
          "/api/web/admin/request-studio/publish-preview",
          expect.objectContaining({ method: "POST" }),
        );
      },
      { timeout: 5000 },
    );
    expect(await screen.findByText("Safe publish preview", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getAllByText("Будет обновлено").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Название формы").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Без изменений").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить публикацию" }));

    expect(await screen.findByText("Тип обращения опубликован из Studio.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/web/admin/request-studio/publish", expect.objectContaining({ method: "POST" }));
  });

  it("disables publish confirmation when preview is blocked", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/admin/service-catalog") {
        return jsonResponse(catalogPayload());
      }
      if (url === "/api/web/admin/helpdesk-model/policies") {
        return jsonResponse({ status: "success", data: registryPayload() });
      }
      if (url === "/api/web/admin/helpdesk/policy-health") {
        return jsonResponse(healthPayload());
      }
      if (url === "/api/web/admin/forms/current") {
        return jsonResponse({ status: "success", data: formsPayload() });
      }
      if (url === "/api/web/admin/request-studio/publish-preview" && init?.method === "POST") {
        return jsonResponse({
          status: "success",
          data: {
            validation: {
              status: "error",
              can_publish: false,
              issues: [{ severity: "error", code: "sla_missing", message: "Не выбран срок выполнения.", path: "form.sla_policy_ref", suggested_fix: null }],
              confirmation_token: null,
            },
            steps: [{ key: "request_template", label: "Тип обращения", status: "blocked", details: "Публикация заблокирована." }],
            confirmation_token: null,
            expires_at: null,
            summary: { creates: 0, updates: 0, noops: 0, blocked: 2, warnings: 0 },
            diffs: [{ object_type: "request_template", object_code: "mailbox", action: "blocked", title: "Тип обращения", changes: [], warnings: [] }],
            message: "Публикация заблокирована. Исправьте ошибки в Studio.",
          },
        });
      }
      throw new Error(`Unexpected fetch: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    const publishButton = await screen.findByRole("button", { name: /Studio/ });
    await waitFor(() => expect(publishButton).toBeEnabled());
    fireEvent.click(publishButton);

    const confirmButton = await screen.findByRole("button", { name: /публикацию|publish/i });
    expect(confirmButton).toBeDisabled();
    expect(screen.getAllByText("Заблокировано").length).toBeGreaterThan(0);
    expect(fetchMock).not.toHaveBeenCalledWith("/api/web/admin/request-studio/publish", expect.anything());
  });

  it("renders the primary workflow with selectors, form preview, policies, simulation and publication gates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/admin/service-catalog") {
          return jsonResponse(catalogPayload());
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: registryPayload() });
        }
        if (url === "/api/web/admin/helpdesk/policy-health") {
          return jsonResponse(healthPayload());
        }
        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: formsPayload() });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderPage();

    expect(await screen.findByRole("heading", { name: "Студия обращений" })).toBeInTheDocument();
    expect((await screen.findAllByText("Форма почтового ящика")).length).toBeGreaterThan(0);
    expect(screen.getByText("Карта настройки обращения")).toBeInTheDocument();
    expect(screen.getAllByText("Форма пользователя").length).toBeGreaterThan(0);
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[9]);
    expect(screen.getByText("Проверка и симуляция")).toBeInTheDocument();
    expect(screen.getByText("Готовность к публикации")).toBeInTheDocument();
    expect(screen.getByText("Как увидит пользователь")).toBeInTheDocument();
    expect(screen.getAllByText("Сотрудник").length).toBeGreaterThan(0);
    expect(screen.getByText("Типы обращений")).toBeInTheDocument();
  });

  it("resets an offering that does not belong to the selected service", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/admin/service-catalog") {
          return jsonResponse(catalogPayload());
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: registryPayload() });
        }
        if (url === "/api/web/admin/helpdesk/policy-health") {
          return jsonResponse(healthPayload());
        }
        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: formsPayload() });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderPage("/app/admin/request-template-studio?service=mail&offering=it.password_reset&template=mailbox");

    expect(await screen.findByText("Вариант услуги не относится к выбранному разделу и был сброшен.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/app/admin/request-template-studio?service=mail&template=mailbox");
    });
  });

  it("sends guided simulation with top-level catalog context and renders human-readable result cards", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/admin/service-catalog") {
        return jsonResponse(catalogPayload());
      }
      if (url === "/api/web/admin/helpdesk-model/policies") {
        return jsonResponse({ status: "success", data: registryPayload() });
      }
      if (url === "/api/web/admin/helpdesk/policy-health") {
        return jsonResponse(healthPayload());
      }
      if (url === "/api/web/admin/forms/current") {
        return jsonResponse({ status: "success", data: formsPayload() });
      }
      if (url === "/api/web/admin/helpdesk/policy-health/simulate" && init?.method === "POST") {
        return jsonResponse(simulationResult());
      }
      throw new Error(`Unexpected fetch: ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    await screen.findByRole("heading", { name: "Студия обращений" });
    await screen.findAllByText("Форма почтового ящика");
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть блок" })[9]);
    fireEvent.change(screen.getByPlaceholderText("Инициатор"), { target: { value: "ivanov" } });
    fireEvent.change(screen.getByPlaceholderText("Краткое содержание/ответы формы"), { target: { value: "Нужен новый ящик" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Запустить проверку" })[0]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/web/admin/helpdesk/policy-health/simulate",
        expect.objectContaining({ method: "POST" }),
      );
    });
    const simulateCall = fetchMock.mock.calls.find(([url]) => String(url) === "/api/web/admin/helpdesk/policy-health/simulate");
    const body = JSON.parse(String(simulateCall?.[1]?.body ?? "{}"));
    expect(body).toMatchObject({
      template_code: "mailbox",
      service_code: "mail",
      offering_code: "new_box",
      offering_full_code: "mail.new_box",
      requester_context: { requester_id: "ivanov" },
      request_form_data: { summary: "Нужен новый ящик" },
    });

    expect(await screen.findByText("Результат тестового прогона")).toBeInTheDocument();
    expect(screen.getAllByText("Service Desk L1").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Расширенный" }));
    expect(screen.getByText("Экспертный JSON запрос")).toBeInTheDocument();
    expect(screen.getByTestId("studio-simulation-payload")).toHaveTextContent('"service_code": "mail"');
  });

  it("preserves context in deep links to expert screens", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/admin/service-catalog") {
          return jsonResponse(catalogPayload());
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: registryPayload() });
        }
        if (url === "/api/web/admin/helpdesk/policy-health") {
          return jsonResponse(healthPayload());
        }
        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: formsPayload() });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    renderPage();

    await screen.findByRole("heading", { name: "Студия обращений" });
    await screen.findAllByText("Форма почтового ящика");
    expect(screen.getAllByRole("link", { name: /Редактировать форму|Полный конструктор форм/ })[0]).toHaveAttribute(
      "href",
      "/app/admin/forms?service=mail&offering=mail.new_box&template=mailbox",
    );
    expect(screen.getAllByRole("link", { name: /Открыть публикацию|Полный каталог услуг/ }).at(-1)).toHaveAttribute(
      "href",
      "/app/admin/service-catalog?service=mail&offering=mail.new_box&template=mailbox",
    );
    expect(screen.getAllByRole("link", { name: "Проверка политик" }).at(-1)).toHaveAttribute(
      "href",
      "/app/admin/policy-health?service=mail&offering=mail.new_box&template=mailbox",
    );
  });
});
