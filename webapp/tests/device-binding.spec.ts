import { expect, type Page, test } from "playwright/test";

const session = { user_login: "binding-fixture@example.test", actor_role: "user", auth_type: "web_session",
  default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };

async function fixture(page: Page, options: { anonymous?: boolean; complete?: boolean; conflict?: boolean } = {}) {
  let loggedIn = !options.anonymous;
  const redeemed: unknown[] = [];
  const requests: string[] = [];
  const errors: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/web/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = {};
    if (path === "/api/web/session/me") {
      if (!loggedIn) { await route.fulfill({ status: 401, json: { status: "error" } }); return; }
      data = session;
    } else if (path === "/api/web/session/login") { loggedIn = true; data = session;
    } else if (path === "/api/web/session/capabilities") { data = { self_registration_enabled: false };
    } else if (path === "/api/web/requester/profile" || path === "/api/web/requester/bootstrap") {
      data = { profile: options.complete === false ? null : { person_id: "fixture-person", display_name: "Тестовый пользователь" },
        profile_completion: { complete: options.complete !== false }, devices: [], feature_flags: {} };
    } else if (path === "/api/web/requester/devices/link") {
      redeemed.push(route.request().postDataJSON());
      data = { binding_status: options.conflict ? "pending_admin_review" : "active", devices: [], next_path: "/app/requester/devices" };
    } else if (path.endsWith("unread_count")) {
      await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return;
    }
    await route.fulfill({ json: { status: "success", data } });
  });
  return { redeemed, requests, errors };
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`device binding conflict wizard ${viewport.width}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page, { conflict: true });
    await page.goto("/app/requester/devices/link");
    await expect(page.getByRole("heading", { name: "Привязать компьютер" })).toBeVisible();
    await page.getByLabel("Код привязки").fill("123-456");
    const action = page.getByRole("button", { name: "Привязать устройство" });
    await expect(action).toBeInViewport(); await action.click();
    await expect(page.getByText(/Запрос на изменение владельца отправлен/)).toBeVisible();
    expect(state.redeemed).toEqual([{ code: "123456" }]);
    expect(state.errors).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`binding-conflict-${viewport.width}.png`), fullPage: true });
  });
}

test("fragment disappears before anonymous login and remains only in memory", async ({ page }) => {
  const state = await fixture(page, { anonymous: true, conflict: true });
  await page.goto("/app/requester/devices/link#code=123-456");
  await expect(page).toHaveURL(/\/app\/login\?next=/);
  expect(page.url()).not.toContain("123"); expect(page.url()).not.toContain("#");
  expect(state.redeemed).toEqual([]);
  await page.getByLabel("Логин", { exact: true }).fill("binding-fixture@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill("fixture-only-password");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByLabel("Код привязки")).toHaveValue("123456");
  const persisted = await page.evaluate(() => [JSON.stringify(localStorage), JSON.stringify(sessionStorage), document.cookie]);
  expect(persisted.join(" ")).not.toContain("123456");
  expect(persisted.join(" ")).not.toContain("123-456");
  expect(state.requests.filter((url) => new URL(url).pathname.startsWith("/api/")).every((url) => !url.includes("123456") && !url.includes("123-456"))).toBe(true);
  await page.getByRole("button", { name: "Привязать устройство" }).click();
  await expect(page.getByText(/Запрос на изменение владельца отправлен/)).toBeVisible();
  expect(state.redeemed).toEqual([{ code: "123456" }]); expect(state.errors).toEqual([]);
});

test("profile is required before redeem; disabled registration retains login", async ({ page }) => {
  const state = await fixture(page, { complete: false });
  await page.goto("/app/requester/devices/link#code=123-456");
  await expect(page.getByRole("link", { name: "Заполнить профиль" })).toBeVisible();
  expect(page.url()).not.toContain("#"); expect(state.redeemed).toEqual([]);
  await fixture(page, { anonymous: true });
  await page.goto("/app/register");
  await expect(page.getByText(/регистрация недоступна/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /Войти/i }).first()).toBeVisible();
});
