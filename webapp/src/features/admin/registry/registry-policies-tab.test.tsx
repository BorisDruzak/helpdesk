import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RegistryPoliciesTab } from "./registry-policies-tab";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function policiesPayload() {
  return {
    defaults: {
      registration: {
        require_user_confirmation: true,
        require_admin_confirmation: false,
        auto_approve_first_binding: true,
        allow_shared_devices: true,
        allow_responsible_binding: true,
        max_primary_devices_per_person: 3,
        stale_after_days: 90,
        department_mode: "allow_pending_request",
        location_mode: "allow_pending_request",
      },
      account_sessions: {
        confirmed_binding_ttl_hours: null,
        verified_other_account_ttl_hours: 24,
        registration_pending_ttl_hours: 72,
        allow_other_account_login: true,
        other_account_requires_reason: true,
        other_account_requires_admin_approval: true,
        allow_other_account_on_shared_or_responsible: true,
      },
      ticket_visibility: {
        owner_can_see_historical_tickets: true,
        other_account_only_own_session_tickets: true,
      },
    },
    effective: {
      registration: {
        require_user_confirmation: true,
        require_admin_confirmation: false,
        auto_approve_first_binding: true,
        allow_shared_devices: true,
        allow_responsible_binding: true,
        max_primary_devices_per_person: 3,
        stale_after_days: 90,
        department_mode: "allow_pending_request",
        location_mode: "allow_pending_request",
      },
      account_sessions: {
        confirmed_binding_ttl_hours: null,
        verified_other_account_ttl_hours: 24,
        registration_pending_ttl_hours: 72,
        allow_other_account_login: true,
        other_account_requires_reason: true,
        other_account_requires_admin_approval: true,
        allow_other_account_on_shared_or_responsible: true,
      },
      ticket_visibility: {
        owner_can_see_historical_tickets: true,
        other_account_only_own_session_tickets: true,
      },
    },
    changed_from_defaults: {},
    warnings: [],
    validation: {
      "registration.max_primary_devices_per_person": { type: "integer", minimum: 1, maximum: 50, nullable: false },
      "registration.stale_after_days": { type: "integer", minimum: 1, maximum: 3650, nullable: false },
      "registration.department_mode": { type: "enum", values: ["allow_pending_request", "optional", "required_existing"] },
      "registration.location_mode": { type: "enum", values: ["allow_pending_request", "optional", "required_existing"] },
      "account_sessions.confirmed_binding_ttl_hours": { type: "integer", minimum: 1, maximum: 87600, nullable: true },
      "account_sessions.verified_other_account_ttl_hours": { type: "integer", minimum: 1, maximum: 8760, nullable: false },
      "account_sessions.registration_pending_ttl_hours": { type: "integer", minimum: 1, maximum: 8760, nullable: false },
    },
    requires_restart: false,
    restart_required_fields: [],
  };
}

function renderTab() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RegistryPoliciesTab />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RegistryPoliciesTab", () => {
  it("saves manual registration approval mode as an admin confirmation policy", async () => {
    let currentPayload = policiesPayload();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/admin/registry/policies" && (!init || !init.method)) {
        return jsonResponse({ status: "success", data: currentPayload });
      }
      if (url === "/api/web/admin/registry/policies" && init?.method === "PATCH") {
        const body = JSON.parse(String(init.body));
        currentPayload = { ...currentPayload, effective: body.policies };
        return jsonResponse({ status: "success", data: currentPayload });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderTab();

    fireEvent.click(await screen.findByLabelText("registration-approval-manual"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "switch to manual approval" } });
    fireEvent.click(screen.getByLabelText("save-registry-policies"));

    await waitFor(() => {
      const saveCall = fetchMock.mock.calls.find(
        ([input, init]) => String(input) === "/api/web/admin/registry/policies" && init?.method === "PATCH",
      );
      expect(saveCall).toBeTruthy();
      expect(JSON.parse(String((saveCall?.[1] as RequestInit).body))).toMatchObject({
        reason: "switch to manual approval",
        policies: {
          registration: {
            require_admin_confirmation: true,
            auto_approve_first_binding: false,
          },
        },
      });
    });
  });
});
