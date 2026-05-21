import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ServiceCatalogPanel } from "./service-catalog-panel";

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
        public_title: "Mail",
        short_description: "Corporate mail",
        lifecycle_status: "published",
        visibility: "public",
      },
      {
        code: "vpn",
        public_title: "VPN",
        short_description: "Remote access",
        lifecycle_status: "published",
        visibility: "public",
      },
    ],
    offerings: [
      {
        code: "new_box",
        full_code: "mail.new_box",
        public_title: "Mail box",
        service_code: "mail",
        lifecycle_status: "published",
        visibility: "public",
        request_template_key: "mailbox",
      },
      {
        code: "setup",
        full_code: "vpn.setup",
        public_title: "VPN setup",
        service_code: "vpn",
        lifecycle_status: "published",
        visibility: "public",
        request_template_key: "vpn_setup",
      },
    ],
  };
}

function registryPayload() {
  return {
    status: "success",
    data: {
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
        inheritance_order: [],
        policy_kinds: [],
      },
      request_templates: [],
      ticket_types: [],
      form_schemas: [],
      policies: [],
      smart_views: [],
    },
  };
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

function renderPanel(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <LocationProbe />
        <ServiceCatalogPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockServiceCatalogFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === "/api/web/admin/service-catalog") {
      return jsonResponse(catalogPayload());
    }
    if (url === "/api/web/admin/helpdesk-model/policies") {
      return jsonResponse(registryPayload());
    }
    if (url.includes("/validate")) {
      return jsonResponse({ validation: { status: "ok", issues: [], blocking: false } });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });
}

describe("ServiceCatalogPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("opens the service and offering requested by query params", async () => {
    mockServiceCatalogFetch();

    renderPanel("/app/admin/service-catalog?service=mail&offering=mail.new_box");

    const selectedOffering = await screen.findByRole("button", { name: /Mail box/i });
    expect(selectedOffering).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: /VPN setup/i })).not.toBeInTheDocument();
  });

  it("opens the service requested by query params", async () => {
    mockServiceCatalogFetch();

    renderPanel("/app/admin/service-catalog?service=vpn");

    expect(await screen.findByRole("button", { name: /VPN setup/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: /Mail box/i })).not.toBeInTheDocument();
  });

  it("does not break when offering query does not belong to the selected service", async () => {
    mockServiceCatalogFetch();

    renderPanel("/app/admin/service-catalog?service=mail&offering=vpn.setup");

    const fallbackOffering = await screen.findByRole("button", { name: /Mail box/i });
    expect(fallbackOffering).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: /VPN setup/i })).not.toBeInTheDocument();
    expect(screen.getByText("Вариант услуги из ссылки не найден или не относится к выбранной услуге.")).toBeInTheDocument();
  });

  it("shows a warning for an unknown service query without breaking the catalog", async () => {
    mockServiceCatalogFetch();

    renderPanel("/app/admin/service-catalog?service=unknown");

    expect(await screen.findByText("Услуга из ссылки не найдена.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Mail box/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows template context from query params", async () => {
    mockServiceCatalogFetch();

    renderPanel("/app/admin/service-catalog?service=mail&template=mailbox");

    expect(await screen.findByText("Контекст шаблона:")).toBeInTheDocument();
    expect(screen.getByText("mailbox")).toBeInTheDocument();
  });

  it("updates the URL when service changes", async () => {
    mockServiceCatalogFetch();

    renderPanel("/app/admin/service-catalog?service=mail&offering=mail.new_box");

    fireEvent.click(await screen.findByText("VPN"));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/app/admin/service-catalog?service=vpn");
    });
    expect(await screen.findByRole("button", { name: /VPN setup/i })).toHaveAttribute("aria-pressed", "true");
  });
});
