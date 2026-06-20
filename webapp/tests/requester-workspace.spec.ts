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
            can_confirm_solution: true,
            can_reopen: false,
            can_rate_solution: false,
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
        account_summary: {
          login: "requester@example.test",
          display_name: "Alex Requester",
          email: "requester@example.test",
          linked_profile: true,
        },
        profile_schema: { fields: [], custom_fields: [], required_fields: [] },
        profile_completion: { complete: true, required_fields: [], missing_fields: [] },
        profile_policy: { editable: true, editable_fields: ["full_name", "phone"], change_request_required: false },
        devices: [{ device_id: "device-1", hostname: "WORKSTATION-1", online: true }],
        active_bindings: [],
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
    fulfillJson(route, { status: "success", data: { ok: true, blockers: [], warnings: [], resolved_context: {} } }),
  );

  await page.route(`**/api/web/requester/tickets/${ticketCode}/message`, (route) =>
    fulfillJson(route, { status: "success", data: { ticket_id: ticketId } }),
  );

  await page.route(`**/api/web/requester/tickets/${ticketCode}/close`, (route) =>
    fulfillJson(route, { status: "success", data: { ticket_id: ticketId, status: "closed" } }),
  );

  await page.route(`**/api/web/requester/tickets/${ticketCode}/feedback`, (route) =>
    fulfillJson(route, { status: "success", data: { ticket_id: ticketId } }),
  );

  await page.route(`**/api/web/requester/tickets/${ticketCode}/reopen`, (route) =>
    fulfillJson(route, { status: "success", data: { ticket_id: ticketId, status: "in_progress" } }),
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

const routeMatrix: Array<{ name: string; path: string; text: string | RegExp; viewport?: { width: number; height: number } }> = [
  { name: "dashboard desktop", path: "/app/requester", text: "VPN access problem", viewport: { width: 1366, height: 768 } },
  { name: "dashboard mobile", path: "/app/requester", text: "VPN access problem", viewport: { width: 390, height: 844 } },
  { name: "tickets list", path: "/app/requester/tickets", text: "VPN access problem" },
  { name: "ticket detail", path: `/app/requester/tickets/${ticketCode}`, text: "Please confirm VPN error code." },
  { name: "profile", path: "/app/requester/profile", text: "Alex Requester" },
  { name: "devices", path: "/app/requester/devices", text: "WORKSTATION-1" },
  { name: "knowledge home", path: "/app/kb", text: "VPN guide" },
  { name: "ask fallback", path: "/app/kb/ask", text: /AI|Search|Поиск|помощник/i },
  { name: "requester not found", path: "/app/requester/unknown-section", text: "Раздел не найден" },
];

for (const scenario of routeMatrix) {
  test(`requester e2e route matrix: ${scenario.name}`, async ({ page }) => {
    if (scenario.viewport) {
      await page.setViewportSize(scenario.viewport);
    }
    await page.goto(scenario.path);
    await expect(page.getByText(scenario.text).first()).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await expectNoForbiddenRequesterTerms(page);
  });
}

test("requester create flow requires explicit category before preview and submit", async ({ page }) => {
  await page.goto("/app/requester/new");

  await page.getByLabel("Что случилось или что нужно?").fill("VPN stopped connecting after password change");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await page.getByRole("button", { name: "Продолжить оформление" }).click();

  await expect(page.getByLabel("Категория обращения")).toBeVisible();
  await page.getByLabel("Категория обращения").selectOption("form:vpn_access");
  await page.getByLabel("Impact").selectOption("me");
  await page.getByRole("button", { name: "К проверке" }).click();
  await page.getByRole("button", { name: "Проверить обращение" }).click();

  await expect(page.getByText("Безопасная проверка")).toBeVisible();
  await page.getByRole("button", { name: "Создать обращение" }).click();
  await expect(page).toHaveURL(/\/app\/requester\/tickets\/REQ-1002$/);
});

test("requester ticket message and close mutations stay available through policy actions", async ({ page }) => {
  await page.goto(`/app/requester/tickets/${ticketCode}`);

  const messageRequest = page.waitForRequest(`**/api/web/requester/tickets/${ticketCode}/message`);
  await page.getByLabel("Ответ заявителя").fill("The VPN error code is 720.");
  await page.getByRole("button", { name: "Отправить" }).click();
  await messageRequest;

  const closeRequest = page.waitForRequest(`**/api/web/requester/tickets/${ticketCode}/close`);
  await page.getByRole("button", { name: "Подтвердить решение" }).click();
  await closeRequest;
});

test("requester rating and reopen actions render from ticket policy capabilities", async ({ page }) => {
  await page.unroute(`**/api/web/requester/tickets/${ticketCode}`);
  await page.route(`**/api/web/requester/tickets/${ticketCode}`, (route) =>
    fulfillJson(route, {
      status: "success",
      data: {
        ticket: {
          ticket_id: ticketId,
          ticket_code: ticketCode,
          title: "VPN access problem",
          description: "VPN is unavailable from the requester laptop.",
          status: "resolved",
          requester_status_label: "Resolved",
          public_status_label: "Resolved",
          created_at: "2026-06-19T08:00:00Z",
          updated_at: "2026-06-19T08:20:00Z",
          actions: {
            can_send_message: false,
            can_confirm_solution: false,
            can_reopen: true,
            can_rate_solution: true,
          },
        },
        messages: [],
        events: [],
      },
    }),
  );

  await page.goto(`/app/requester/tickets/${ticketCode}`);
  await expect(page.getByLabel("Оценка обращения")).toBeVisible();
  await page.getByLabel("Оценка обращения").fill("2");
  await page.getByRole("textbox", { name: "Комментарий", exact: true }).fill("VPN still fails after reconnect.");

  const feedbackRequest = page.waitForRequest(`**/api/web/requester/tickets/${ticketCode}/feedback`);
  await page.getByRole("button", { name: "Отправить оценку" }).click();
  await feedbackRequest;

  const reopenRequest = page.waitForRequest(`**/api/web/requester/tickets/${ticketCode}/reopen`);
  await page.getByLabel("Комментарий для возврата в работу").fill("Please continue troubleshooting.");
  await page.getByRole("button", { name: "Вернуть в работу" }).click();
  await reopenRequest;
});
