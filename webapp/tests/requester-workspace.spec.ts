import { expect, type Page, type Route, test } from "playwright/test";

const ticketId = "550e8400-e29b-41d4-a716-446655440001";
const ticketCode = "REQ-1001";

async function fulfillJson(route: Route, payload: unknown) {
  await route.fulfill({
    body: JSON.stringify(payload),
    contentType: "application/json",
    status: 200,
  });
}

async function installRequesterMocks(page: Page) {
  const ticket = {
    ticket_id: ticketId,
    ticket_code: ticketCode,
    title: "VPN access problem",
    description: "VPN is unavailable from the requester laptop.",
    status: "waiting_on_user",
    requester_status_label: "Needs your reply",
    public_status_label: "Needs your reply",
    created_at: "2026-06-19T08:00:00Z",
    updated_at: "2026-06-19T08:20:00Z",
    next_action_label: "Reply to support",
  };

  await page.route("**/api/web/session/me", (route) =>
    fulfillJson(route, {
      status: "success",
      data: {
        user_login: "requester@example.test",
        actor_role: "user",
        auth_type: "web_session",
        default_workspace: "requester",
        available_workspaces: ["requester"],
        permissions: ["workspace.requester.view"],
      },
    }),
  );

  await page.route("**/api/web/notifications/unread_count", (route) =>
    fulfillJson(route, { status: "ok", unread_count: 0 }),
  );

  await page.route("**/api/web/requester/bootstrap", (route) =>
    fulfillJson(route, {
      status: "success",
      data: {
        workspace: "requester",
        profile: {
          person_id: "person-1",
          display_name: "Alex Requester",
          full_name: "Alex Requester",
          email: "requester@example.test",
          department_id: "dept-it",
          location_id: "loc-ekb",
          status: "active",
        },
        profile_completion: {
          complete: true,
          status: "complete",
          setup_path: "/app/requester/profile/setup",
          required_fields: [],
          missing_fields: [],
          blocks: {
            ticket_create: false,
            ticket_preview: false,
            device_binding_confirmation: false,
          },
        },
        profile_schema: { schema_key: "requester_profile", fields: [], custom_fields: [], required_fields: [] },
        requester_context: {
          profile: { display_name: "Alex Requester", department: "IT", location: "HQ" },
          device: { device_id: "device-1", hostname: "WORKSTATION-1" },
          form_prefill: { title: "VPN access problem" },
          routing_facts: {},
          summary: ["IT", "WORKSTATION-1"],
        },
        devices: [{ device_id: "device-1", hostname: "WORKSTATION-1", os: "Windows", agent_version: "3.1.71", online: true }],
        primary_device: { device_id: "device-1", hostname: "WORKSTATION-1", os: "Windows", agent_version: "3.1.71", online: true },
        primary_device_resolution: { status: "available", reason_code: null, source: "fixture" },
        active_bindings: [],
        pending_registration_claims: [],
        open_ticket_count: 1,
        tickets_requiring_user_action_count: 1,
        pending_consent_count: 0,
        recent_tickets: [ticket],
        feature_flags: {
          requester_ticket_create: true,
          requester_no_device_create: true,
          requester_owned_device_create: true,
        },
        policies: { device_selection_required: false },
      },
    }),
  );

  await page.route("**/api/web/requester/consents**", (route) =>
    fulfillJson(route, { status: "success", data: { consents: [] } }),
  );

  await page.route("**/api/web/requester/tickets", (route) => {
    if (route.request().method() === "POST") {
      return fulfillJson(route, {
        status: "success",
        data: {
          ticket_id: "550e8400-e29b-41d4-a716-446655440002",
          ticket_code: "REQ-1002",
          ticket: {
            ticket_id: "550e8400-e29b-41d4-a716-446655440002",
            ticket_code: "REQ-1002",
          },
        },
      });
    }
    return fulfillJson(route, { status: "success", data: { tickets: [ticket] } });
  });

  await page.route(`**/api/web/requester/tickets/${ticketCode}`, (route) =>
    fulfillJson(route, {
      status: "success",
      data: {
        ticket: {
          ...ticket,
          actions: {
            can_send_message: true,
            can_close: true,
            can_reopen: false,
            can_rate: false,
          },
        },
        messages: [
          {
            message_id: "msg-1",
            from_role: "support",
            text: "Please confirm VPN error code.",
            created_at: "2026-06-19T08:15:00Z",
            attachments: [],
          },
        ],
        events: [],
      },
    }),
  );

  await page.route("**/api/web/requester/profile", (route) =>
    fulfillJson(route, {
      status: "success",
      data: {
        profile: {
          person_id: "person-1",
          display_name: "Alex Requester",
          full_name: "Alex Requester",
          email: "requester@example.test",
          department_id: "dept-it",
          location_id: "loc-ekb",
          phone: "+1 555 0100",
          custom_fields: {},
        },
        profile_schema: { fields: [], custom_fields: [], required_fields: [] },
        profile_completion: { complete: true, required_fields: [], missing_fields: [] },
        edit_policy: { can_edit: true },
        devices: [{ device_id: "device-1", hostname: "WORKSTATION-1", online: true }],
        active_bindings: [],
        identity_aliases: [],
        pending_registration_claims: [],
      },
    }),
  );

  await page.route("**/api/registry/options", (route) =>
    fulfillJson(route, {
      status: "success",
      data: {
        departments: [{ value: "dept-it", label: "IT" }],
        locations: [{ value: "loc-ekb", label: "HQ" }],
      },
    }),
  );

  await page.route("**/api/web/requester/devices/device-1", (route) =>
    fulfillJson(route, {
      status: "success",
      data: {
        device: { device_id: "device-1", hostname: "WORKSTATION-1", os: "Windows", online: true, agent_version: "3.1.71" },
        relationship: { label: "Primary device" },
        open_ticket_count: 1,
        recent_tickets: [ticket],
        available_actions: [],
      },
    }),
  );

  await page.route("**/public_api/ticket_forms/current?pack_key=request_forms", (route) =>
    fulfillJson(route, {
      status: "ok",
      pack: {
        key: "request_forms",
        version: "e2e",
        forms: [
          {
            key: "vpn_access",
            title: "VPN access",
            fields: [{ key: "impact", label: "Impact", type: "select", required: true, options: [{ value: "me", label: "Only me" }] }],
            availability_policy: { available_without_agent_binding: true },
          },
        ],
      },
    }),
  );

  await page.route("**/api/service-catalog/current", (route) =>
    fulfillJson(route, { status: "ok", catalog_version: "e2e", services: [], offerings: [], categories: [] }),
  );

  await page.route("**/api/knowledge/suggest", (route) =>
    fulfillJson(route, { status: "ok", suggestions: [], known_errors: [], workarounds: [] }),
  );

  await page.route("**/api/web/requester/tickets/preview", (route) =>
    fulfillJson(route, { status: "success", data: { blockers: [], warnings: [], resolved_context: {} } }),
  );

  await page.route("**/api/knowledge/portal/home", (route) =>
    fulfillJson(route, {
      status: "ok",
      display_message: "Portal loaded",
      spaces: [{ space_id: "space-it", code: "it", title: "IT", description: "IT help", visibility: "requester", lifecycle_status: "active" }],
      featured_articles: [{ item_id: "article-vpn", slug: "vpn-guide", title: "VPN guide", summary: "How to restore VPN access", visibility: "requester", tags: ["vpn"] }],
      popular_articles: [],
      recent_articles: [],
    }),
  );

  await page.route("**/api/knowledge/ask", (route) =>
    fulfillJson(route, {
      status: "ok",
      answer_status: "ai_disabled",
      display_message: "Search fallback",
      retrieval_results: [{ slug: "vpn-guide", title: "VPN guide", snippet: "Check VPN settings" }],
      citations: [],
    }),
  );
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(2);
}

async function expectNoForbiddenRequesterTerms(page: Page) {
  const body = await page.locator("body").innerText();
  expect(body).not.toMatch(/Requester workspace|binding_id|claim_id|pairing_id|account_session_id|registry person/);
}

test.beforeEach(async ({ page }) => {
  await installRequesterMocks(page);
});

test("requester split routes render without legacy workspace leakage", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });

  await page.goto("/app/requester");
  await expect(page.getByText("VPN access problem")).toBeVisible();
  await expect(page.getByText("WORKSTATION-1")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoForbiddenRequesterTerms(page);

  await page.goto("/app/requester/tickets");
  await expect(page.getByText("VPN access problem")).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto(`/app/requester/tickets/${ticketCode}`);
  await expect(page.getByText("Please confirm VPN error code.")).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto("/app/requester/profile");
  await expect(page.getByText("Alex Requester").first()).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto("/app/requester/devices");
  await expect(page.getByText("WORKSTATION-1").first()).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto("/app/kb");
  await expect(page.getByText("VPN guide").first()).toBeVisible();

  await page.goto("/app/kb/ask");
  await expect(page.locator("textarea, input").first()).toBeVisible();
  await expectNoForbiddenRequesterTerms(page);
});
