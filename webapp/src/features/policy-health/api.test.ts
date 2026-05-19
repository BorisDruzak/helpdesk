import { afterEach, describe, expect, it, vi } from "vitest";

import { simulatePolicyHealth, type PolicySimulationPayload } from "./api";

describe("policy health API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts Studio simulation catalog context as top-level fields", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          template_code: "password_reset_request",
          routing: {},
          priority: {},
          sla: {},
          ola: {},
          approval: {},
          closure: {},
          visibility: {},
          diagnostic: {},
          warnings: [],
          would_create_ticket: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    const payload: PolicySimulationPayload = {
      template_code: "password_reset_request",
      service_code: "it-support",
      offering_code: "password-reset",
      offering_full_code: "it-support.password-reset",
      request_form_data: { summary: "Не могу войти" },
      custom_fields: { additional: true },
      device_metadata: { device_id: "device-1" },
      requester_context: { requester_id: "ivanov" },
    };

    await simulatePolicyHealth(payload);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/web/admin/helpdesk/policy-health/simulate",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });
});
