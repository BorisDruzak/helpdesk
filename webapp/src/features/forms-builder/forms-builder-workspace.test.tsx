import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AdminFormsPayload, AdminHelpdeskModelPayload } from "./api";
import { FormsBuilderWorkspace } from "./forms-builder-workspace";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function createFormsPayload(title = "Печать / принтер"): AdminFormsPayload {
  return {
    summary: {
      pack_key: "request_forms",
      version: "1.0.3",
      title: "Каталог заявок",
      description: "Рабочий каталог",
      forms_count: 1,
      fields_count: 1,
      required_fields_count: 1,
      last_published_at: "2026-04-21T10:00:00+05:00",
      last_published_by: "admin",
    },
    capabilities: {
      current_endpoint: "/api/web/admin/forms/current",
      save_endpoint: "/api/web/admin/forms/save",
      preview_endpoint: "/api/web/admin/forms/route-preview",
      process_preview_endpoint: "/api/web/admin/forms/process-preview",
      field_type_options: [{ value: "text", label: "Текст" }],
      field_role_options: [{ value: "routing_field", label: "Routing field" }],
    },
    forms: [
      {
        key: "printer",
        request_kind: "printer",
        title,
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
            process_mapping: {},
          },
        ],
      },
    ],
  };
}

function createRegistryPayload(): AdminHelpdeskModelPayload {
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
      smart_views_count: 1,
      active_smart_views_count: 1,
    },
    capabilities: {
      registry_endpoint: "/api/web/admin/helpdesk-model/policies",
      publish_from_form_endpoint: "/api/web/admin/helpdesk-model/request-templates/publish-from-form",
      publish_policy_endpoint: "/api/web/admin/helpdesk-model/policies/publish",
      policy_diff_endpoint: "/api/web/admin/helpdesk-model/policies/diff",
      policy_deactivate_endpoint: "/api/web/admin/helpdesk-model/policies/deactivate",
      policy_rollback_endpoint: "/api/web/admin/helpdesk-model/policies/rollback",
      publish_ticket_type_endpoint: "/api/web/admin/helpdesk-model/ticket-types/publish",
      publish_form_schema_endpoint: "/api/web/admin/helpdesk-model/form-schemas/publish",
      publish_smart_view_endpoint: "/api/web/admin/helpdesk-model/smart-views/publish",
      inheritance_order: ["system", "ticket_type", "category", "request_template"],
      policy_kinds: ["routing"],
    },
    request_templates: [],
    ticket_types: [],
    form_schemas: [],
    policies: { routing: [] },
    smart_views: [
      {
        code: "sla_risk_custom",
        version: "1.0.0",
        title: "Риск SLA",
        description: "Контроль сроков",
        scope_level: "system",
        scope_ref: null,
        filter: { status: { not_in: ["Closed", "Cancelled"] } },
        sort: [{ field: "resolution_due_at", direction: "asc" }],
        columns: ["ticket_id", "title", "status"],
        is_active: true,
        published_at: "2026-04-21T10:00:00+05:00",
        created_at: "2026-04-21T10:00:00+05:00",
        created_by: "admin",
        updated_at: "2026-04-21T10:00:00+05:00",
        updated_by: "admin",
      },
    ],
  };
}

function packListPayload() {
  return {
    status: "ok",
    pack_key: "request_forms",
    current: {
      pack_key: "request_forms",
      version: "1.0.3",
      title: "Каталог заявок",
      description: "Рабочий каталог",
      forms_count: 1,
      fields_count: 1,
      required_fields_count: 1,
      created_at: "2026-04-21T10:00:00+05:00",
      created_by: "admin",
      is_preferred: true,
    },
    preferred: {
      pack_key: "request_forms",
      version: "1.0.3",
      updated_at: "2026-04-21T10:00:00+05:00",
      updated_by: "admin",
    },
    packs: [
      {
        pack_key: "request_forms",
        version: "1.0.3",
        title: "Каталог заявок",
        description: "Рабочий каталог",
        forms_count: 1,
        fields_count: 1,
        required_fields_count: 1,
        created_at: "2026-04-21T10:00:00+05:00",
        created_by: "admin",
        is_preferred: true,
      },
      {
        pack_key: "request_forms",
        version: "1.0.4",
        title: "Каталог заявок",
        description: "Рабочий каталог",
        forms_count: 1,
        fields_count: 1,
        required_fields_count: 1,
        created_at: "2026-04-22T10:00:00+05:00",
        created_by: "admin",
        is_preferred: false,
      },
    ],
  };
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{`${location.pathname}${location.search}`}</span>;
}

function renderWorkspace(initialEntry: string) {
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
        <FormsBuilderWorkspace permissions={["admin.forms.publish"]} />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("FormsBuilderWorkspace", () => {
  it("accepts underscored mode aliases and runs smart view preview with URL feedback", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/admin/forms/current") {
        return jsonResponse({ status: "success", data: createFormsPayload() });
      }
      if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
        return jsonResponse(packListPayload());
      }
      if (url === "/api/web/admin/helpdesk-model/policies") {
        return jsonResponse({ status: "success", data: createRegistryPayload() });
      }
      if (url === "/api/web/support/queue?scope=all&smart_view=sla_risk_custom") {
        return jsonResponse({
          status: "success",
          data: {
            scope: "all",
            query: "",
            status_filter: "all",
            smart_view: "sla_risk_custom",
            summary: {
              visible_count: 1,
              selected_ticket_id: null,
              scope_counts: [],
              status_counts: [],
              smart_view_counts: [],
              queue_counts: [],
            },
            filters: { scope_options: [], status_options: [], smart_view_options: [] },
            tickets: [
              {
                ticket_id: "1",
                ticket_code: "TKT-1",
                title: "Нет доступа",
                status: "open",
                status_label: "Открыта",
                queue_code: "servicedesk_l1",
                assignee_id: null,
                assignee_display_name: "Линия 1",
                requester_display_name: "Иван",
                device_id: null,
                updated_at: null,
                created_at: null,
                requires_operator_action: true,
                unread_user_messages: 0,
              },
            ],
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWorkspace("/app/admin/forms?mode=smart_views&view=sla_risk_custom");

    expect(await screen.findByRole("heading", { name: "Риск SLA" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/web/support/queue?scope=all&smart_view=sla_risk_custom", expect.anything());
    });
    expect(await screen.findByText(/найдено 1 заявок/)).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/app/admin/forms?mode=smart-views&view=sla_risk_custom");
  });

  it("blocks catalog publish until validation preflight has passed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/web/admin/forms/current") {
          return jsonResponse({ status: "success", data: createFormsPayload() });
        }
        if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
          return jsonResponse(packListPayload());
        }
        if (url === "/api/web/admin/helpdesk-model/policies") {
          return jsonResponse({ status: "success", data: createRegistryPayload() });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      })
    );

    renderWorkspace("/app/admin/forms?mode=versions");

    expect(await screen.findByText(/Сначала выполните проверку публикации/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Опубликовать" })).toBeDisabled();
  });

  it("opens and compares selected catalog versions instead of rendering no-op actions", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/admin/forms/current") {
        return jsonResponse({ status: "success", data: createFormsPayload() });
      }
      if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
        return jsonResponse(packListPayload());
      }
      if (url === "/api/web/admin/helpdesk-model/policies") {
        return jsonResponse({ status: "success", data: createRegistryPayload() });
      }
      if (url === "/api/ticket_forms/packs/request_forms/1.0.3") {
        return jsonResponse({ status: "ok", pack: createFormsPayload("Печать / принтер").forms.length ? { ...createFormsPayload("Печать / принтер"), title: "Каталог заявок" } : {} });
      }
      if (url === "/api/ticket_forms/packs/request_forms/1.0.4") {
        return jsonResponse({ status: "ok", pack: { ...createFormsPayload("Печать / принтер v4"), title: "Каталог заявок" } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWorkspace("/app/admin/forms?mode=versions&version=1.0.4");

    await screen.findByRole("heading", { name: "1.0.4" });
    fireEvent.click(screen.getAllByRole("button", { name: "Сравнить" })[0]);
    expect(await screen.findByText("Сравнение версий: 1.0.3 → 1.0.4.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Открыть в редакторе" }));
    expect(await screen.findByRole("heading", { name: "Редактор шаблона обращения: Печать / принтер v4" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/app/admin/forms?mode=template&version=1.0.4&template=printer");
  });

  it("saves on-behalf policy from the template process step", async () => {
    const draftCalls: unknown[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/web/admin/forms/current") {
        return jsonResponse({ status: "success", data: createFormsPayload() });
      }
      if (url === "/api/ticket_forms/packs?pack_key=request_forms") {
        return jsonResponse(packListPayload());
      }
      if (url === "/api/web/admin/helpdesk-model/policies") {
        return jsonResponse({ status: "success", data: createRegistryPayload() });
      }
      if (url === "/api/web/admin/forms/save-draft" && method === "POST") {
        draftCalls.push(JSON.parse(String(init?.body ?? "{}")));
        return jsonResponse({
          status: "success",
          data: {
            draft_id: "draft-on-behalf",
            pack_key: "request_forms",
            base_version: "1.0.3",
            status: "draft",
            summary: createFormsPayload().summary,
            published_version: null,
            preferred_version: "1.0.3",
            message: "Черновик сохранён.",
          },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWorkspace("/app/admin/forms?mode=template&template=printer");

    expect(await screen.findByRole("heading", { name: "Редактор шаблона обращения: Печать / принтер" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Процесс/ }));
    fireEvent.click(await screen.findByLabelText("Разрешить создание обращения за другого сотрудника"));
    fireEvent.click(screen.getByLabelText("Требовать причину обращения за другого сотрудника"));
    fireEvent.click(screen.getByLabelText("Сотрудник с проблемой обязателен"));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    await waitFor(() => {
      expect(draftCalls).toHaveLength(1);
    });
    const savedPrinter = (
      draftCalls[0] as {
        forms: Array<{ key: string; on_behalf_policy?: Record<string, unknown> }>;
      }
    ).forms.find((form) => form.key === "printer");
    expect(savedPrinter?.on_behalf_policy).toMatchObject({
      allowed: true,
      reason_required: true,
      affected_person_required: true,
      diagnostic_target: "affected_person_primary_agent",
    });
  });
});
