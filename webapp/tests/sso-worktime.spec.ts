import { expect, test, type Page } from "playwright/test";

const portal = "https://endpoint.sosnadmin.local/employee";
const employee = {
  user_login: "employee", actor_role: "user", auth_type: "ui_token", login_method: "oidc",
  default_workspace: "requester", available_workspaces: ["requester"],
  permissions: ["workspace.requester.view"], worktime_portal_url: portal,
};

async function capabilities(page: Page, enabled: boolean) {
  await page.route("**/api/web/session/capabilities", route => route.fulfill({ json: {
    status: "success", data: { self_registration_enabled: false, sso_enabled: enabled },
  } }));
}

test("domain entry uses a fixed server document route and preserves password login", async ({ page }) => {
  await capabilities(page, true);
  await page.route("**/api/web/session/me", route => route.fulfill({ json: { status: "success", data: null } }));
  await page.route("**/api/web/session/oidc/login", route => route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset='utf-8'><h1>Доменный вход</h1>" }));
  await page.goto("/app/login?next=https://untrusted.test");
  await expect(page.getByLabel("Логин", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Войти", exact: true })).toBeVisible();
  const entry = page.getByRole("link", { name: "Войти с доменной учётной записью" });
  await expect(entry).toHaveAttribute("href", "/api/web/session/oidc/login");
  await entry.click();
  await expect(page.getByRole("heading", { name: "Доменный вход" })).toBeVisible();
  expect(new URL(page.url()).search).toBe("");
});

test("SSO policy failure retains ordinary login and offers no broken SSO entry", async ({ page }) => {
  await page.route("**/api/web/session/me", route => route.fulfill({ json: { status: "success", data: null } }));
  await page.route("**/api/web/session/capabilities", route => route.fulfill({ status: 503, json: { status: "error" } }));
  await page.goto("/app/login");
  await expect(page.getByRole("status")).toContainText("Самостоятельная регистрация недоступна");
  await expect(page.getByRole("link", { name: "Войти с доменной учётной записью" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Войти", exact: true })).toBeVisible();
});

for (const target of [portal, "https://endpoint-staging.sosnadmin.local/employee"]) {
test(`employee navigation links to ${new URL(target).hostname} and SSO logout posts as a document`, async ({ page }, testInfo) => {
  let authenticated = true;
  let logoutMethod = "";
  let logoutDocument = false;
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await capabilities(page, true);
  await page.route("**/api/web/session/me", route => route.fulfill({ json: { status: "success", data: authenticated ? { ...employee, worktime_portal_url: target } : null } }));
  await page.route("**/api/web/requester/tickets", route => route.fulfill({ json: { status: "success", data: { tickets: [] } } }));
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/session/oidc/logout", route => {
    authenticated = false;
    logoutMethod = route.request().method();
    logoutDocument = route.request().isNavigationRequest();
    return route.fulfill({ status: 303, headers: { location: "/app/login" } });
  });
  await page.goto("/app/requester/tickets");
  await expect(page.getByRole("heading", { name: "Мои обращения" })).toBeVisible();
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    const entry = page.getByRole("link", { name: "Рабочее время", exact: true }).filter({ visible: true });
    await expect(entry).toHaveAttribute("href", target);
    await entry.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (target.includes("endpoint-staging") && viewport.width !== 1920) {
      await page.screenshot({ path: testInfo.outputPath(`worktime-staging-${viewport.width}.png`), fullPage: true });
    }
  }
  let portalReferer: string | undefined;
  await page.route(target, route => {
    portalReferer = route.request().headers()["referer"];
    return route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset='utf-8'><h1>Рабочее время</h1>" });
  });
  await page.getByRole("link", { name: "Рабочее время", exact: true }).filter({ visible: true }).click();
  await expect(page.getByRole("heading", { name: "Рабочее время", exact: true })).toBeVisible();
  expect(page.url()).toBe(target);
  expect(portalReferer).toBeUndefined();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Мои обращения" })).toBeVisible();
  await page.getByRole("button", { name: "Выйти", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();
  expect(logoutMethod).toBe("POST");
  expect(logoutDocument).toBe(true);
  expect(errors).toEqual([]);
});
}
