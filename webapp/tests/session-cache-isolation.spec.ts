import { expect, test } from "playwright/test";

test("logout and a new requester login never reuse private profile data", async ({ page }, testInfo) => {
  const jsErrors: string[] = [];
  const failedRequests: string[] = [];
  const unexpectedResponses: string[] = [];
  const consoleErrors: string[] = [];
  const unexpectedCalls: string[] = [];
  page.on("pageerror", (error) => jsErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("403 (Forbidden)")) consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    if (request.failure()?.errorText !== "net::ERR_ABORTED") failedRequests.push(request.url());
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && !(response.status() === 403 && response.url().endsWith("/requester/profile"))) {
      unexpectedResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  let actor: string | null = "requester-a";
  let releaseForbiddenRead!: () => void;
  const forbiddenRead = new Promise<void>((resolve) => { releaseForbiddenRead = resolve; });
  let nextProfileRequested = false;
  const session = () => actor ? {
    user_login: actor, actor_role: "user", auth_type: "web_session",
    default_workspace: "requester", available_workspaces: ["requester"],
    permissions: ["workspace.requester.view"]
  } : null;

  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const requestKey = `${route.request().method()} ${path}`;
    const allowedCalls = new Set([
      "GET /api/web/session/me",
      "GET /api/web/session/capabilities",
      "POST /api/web/session/login",
      "POST /api/web/session/logout",
      "GET /api/web/requester/profile",
      "GET /api/registry/options",
      "GET /api/web/requester/bootstrap",
      "GET /api/web/requester/tickets",
      "GET /api/web/requester/consents",
      "GET /api/web/notifications/unread_count"
    ]);
    if (!allowedCalls.has(requestKey)) {
      unexpectedCalls.push(requestKey);
      await route.fulfill({ status: 501, contentType: "application/json", body: JSON.stringify({ status: "error", error: "Unexpected fixture API call" }) });
      return;
    }
    let data: unknown = {};
    if (path === "/api/web/session/logout") actor = null;
    if (path === "/api/web/session/login") actor = JSON.parse(route.request().postData() ?? "{}").login;
    if (["GET /api/web/session/me", "POST /api/web/session/login", "POST /api/web/session/logout", "GET /api/web/session/capabilities"].includes(requestKey)) {
      data = path.endsWith("/capabilities") ? { self_registration_enabled: false } : session();
    } else if (path === "/api/web/requester/profile") {
      if (actor === "requester-b") {
        nextProfileRequested = true;
        await forbiddenRead;
        await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ status: "error", error_code: "FORBIDDEN" }) });
        return;
      }
      data = {
        profile: { person_id: "person-a", full_name: "Private Person A", display_name: "Private Person A", email: "private-a@example.test", custom_fields: {} },
        account_summary: { login: "requester-a", display_name: "Private Person A", linked_profile: true },
        profile_schema: { fields: [], custom_fields: [], required_fields: [] },
        profile_completion: { complete: true, required_fields: [], missing_fields: [] },
        profile_policy: { editable: true, editable_fields: [], change_request_required: false },
        devices: [], active_bindings: [], pending_registration_claims: []
      };
    } else if (path === "/api/registry/options") {
      data = { departments: [], locations: [] };
    } else if (path === "/api/web/requester/bootstrap") {
      data = {
        profile: null, profile_completion: { complete: true }, devices: [], recent_tickets: [],
        primary_device: null, feature_flags: {}, policies: {}, open_ticket_count: 0,
        tickets_requiring_user_action_count: 0, pending_consent_count: 0
      };
    } else if (path === "/api/web/requester/tickets") {
      data = { tickets: [], total: 0 };
    } else if (path === "/api/web/requester/consents") {
      data = { consents: [] };
    } else if (path === "/api/web/notifications/unread_count") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: "ok", unread_count: 0 }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: "success", data }) });
  });

  await page.goto("/app/requester/profile");
  await expect(page.getByText("Private Person A").first()).toBeVisible();
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await expect(page.getByLabel("Логин", { exact: true })).toBeVisible();
  await page.getByLabel("Логин", { exact: true }).fill("requester-b");
  await page.getByLabel("Пароль", { exact: true }).fill("fixture-only");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByText("requester-b", { exact: true })).toBeVisible();
  if (!new URL(page.url()).pathname.endsWith("/requester/profile")) {
    await page.locator('a[href="/app/requester/profile"]').first().click();
  }
  await expect.poll(() => nextProfileRequested).toBe(true);
  await expect(page.getByText("Загружаем профиль...")).toBeVisible();
  await expect(page.getByText("Private Person A")).toHaveCount(0);
  await expect(page.getByText("private-a@example.test")).toHaveCount(0);
  releaseForbiddenRead();
  await expect(page.getByRole("alert")).toBeVisible();
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    await expect(page.getByText("Private Person A")).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`session-isolation-${viewport.width}.png`) });
  }
  expect(jsErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
  expect(unexpectedResponses).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(unexpectedCalls).toEqual([]);
});
