import { expect, type Page, test } from "playwright/test";
import { endpointDeviceId, mockEndpointFleet } from "./fixtures/endpoint-context";

async function loginAsAdmin(page: Page) {
  await page.goto("/app/admin");
  if (page.url().includes("/app/admin/inventory")) {
    return;
  }
  const textboxes = page.getByRole("textbox");
  await textboxes.nth(0).fill("admin");
  await textboxes.nth(1).fill("secret");
  await page.getByRole("button").filter({ hasText: /Войти|Р’РѕР№С‚Рё/ }).click();
  await expect(page).toHaveURL(/\/app\/admin$/);
}

test("администратор видит отдельные пункты admin-меню и открывает ключевые страницы", async ({ page }) => {
  await mockEndpointFleet(page);
  await page.goto("/app/admin");

  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();

  await page.getByLabel("Логин").fill("admin");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/admin$/);
  await expect(page.getByRole("heading", { name: "Центр администрирования" })).toBeVisible();
  await page.goto("/app/admin/inventory");
  const adminNav = page.getByRole("navigation", { name: "Навигация администрирования" });
  await expect(page.getByRole("heading", { name: "Устройства", exact: true })).toBeVisible();
  await expect(adminNav.getByRole("link", { name: /Устройства/ })).toBeVisible();
  await expect(adminNav.getByRole("link", { name: /Карточка устройства/ })).toBeVisible();
  await expect(adminNav.getByRole("link", { name: /Observer/ })).toBeVisible();

  await adminNav.getByRole("link", { name: /Карточка устройства/ }).click();
  await expect(page).toHaveURL(/\/app\/admin\/device(?:\?.*)?$/);
  await expect(page.getByRole("heading", { name: "Укажите корректный идентификатор устройства" })).toBeVisible();

  await page.goto("/app/admin/capabilities");
  await expect(page).toHaveURL(/\/app\/admin\/capabilities$/);
  await expect(page.getByRole("heading", { name: "Capabilities" })).toBeVisible();

  await page.goto("/app/admin/forms");
  await expect(page).toHaveURL(/\/app\/admin\/forms$/);

  await page.goto("/app/admin/observer");
  await expect(page).toHaveURL(/\/app\/admin\/observer$/);
  await expect(page.getByRole("heading", { name: "Observer", exact: true })).toBeVisible();
});

test("admin opens the exact Endpoint device without retired API traffic and keeps notifications authenticated", async ({ page }) => {
  await mockEndpointFleet(page);
  const retiredRequests: string[] = [];
  page.on("request", request => {
    const path = new URL(request.url()).pathname;
    if (/^\/api\/web\/admin\/(devices|inventory|device-tokens)(\/|$)/.test(path)) retiredRequests.push(path);
  });
  await loginAsAdmin(page);
  await page.goto("/app/admin/inventory");
  for (const label of ["Платформа", "Расположение", "Связь с Registry", "Связь пользователя", "Актуальность inventory", "Lifecycle устройства", "Порог актуальности inventory"]) {
    await expect(page.getByLabel(label, {exact: true})).toBeVisible();
  }
  await page.getByLabel("Поиск на странице", {exact: true}).fill(endpointDeviceId);
  await page.getByLabel("Актуальность inventory", {exact: true}).selectOption("missing");
  await page.getByRole("link", { name: "Windows fixture", exact: true }).click();
  await expect(page).toHaveURL(`/app/admin/device?device=${endpointDeviceId}`);
  await expect(page.getByRole("heading", { name: "Windows fixture" })).toBeVisible();
  await expect(page.getByText("Связь с Registry не подтверждена. Устройство доступно в Endpoint.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Токены", exact: true })).toHaveCount(0);
  expect(retiredRequests).toEqual([]);

  const prefsResponse = page.waitForResponse((response) =>
    response.url().includes("/api/web/notifications/preferences") && response.status() === 200
  );
  const alertsResponse = page.waitForResponse((response) =>
    response.url().includes("/api/web/admin/tech/alerts") && response.status() === 200
  );
  await page.goto("/app/admin/settings");
  await page.getByRole("main").getByRole("button", { name: "Уведомления" }).click();
  await prefsResponse;
  await alertsResponse;
  await expect(page.getByText("env_uuid-дубли")).toBeVisible();
});

for (const viewport of [{width: 1366, height: 768}, {width: 1920, height: 1080}]) {
  test(`fleet offers boolean row states and degrades on refresh failure at ${viewport.width}`, async ({page}, testInfo) => {
    await page.setViewportSize(viewport);
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    const badResponses: string[] = [];
    page.on("pageerror", error => pageErrors.push(error.message));
    page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
    page.on("response", response => {
      if (response.status() >= 400 && !(response.status() === 503 && response.url().includes("/api/web/admin/endpoint/devices?"))) {
        badResponses.push(`${response.status()} ${new URL(response.url()).pathname}`);
      }
    });
    // The shared fixture omits this shell read; supply its current contract.
    await page.route("**/api/web/notifications/unread_count", route => route.fulfill({
      json: {status: "success", unread_count: 0},
    }));
    await mockEndpointFleet(page);
    await loginAsAdmin(page);
    await page.goto("/app/admin/inventory");
    await expect(page.getByRole("link", {name: "Windows fixture", exact: true})).toBeVisible();
    const filter = page.getByLabel("Статус устройства", {exact: true});
    await expect(filter.locator("option")).toHaveText(["Все статусы", "ONLINE", "OFFLINE"]);
    await expect(page.getByText("UNKNOWN", {exact: true})).toHaveCount(0);
    await filter.selectOption("offline");
    await expect(page.getByRole("link", {name: "Windows fixture", exact: true})).toHaveCount(0);
    await filter.selectOption("online");
    await expect(page.getByRole("link", {name: "Windows fixture", exact: true})).toBeVisible();
    const refresh = page.getByRole("button", {name: "Обновить список"});
    expect((await refresh.boundingBox())!.y).toBeLessThan(viewport.height);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
    await page.screenshot({path: testInfo.outputPath("fleet-success.png"), fullPage: true});
    await page.route("**/api/web/admin/endpoint/devices?*", route => route.fulfill({
      status: 503, json: {status: "error", error: {code: "endpoint_unavailable", message: "Endpoint unavailable"}},
    }));
    await refresh.click();
    await expect(page.getByRole("alert")).toContainText("UNKNOWN");
    await expect(page.getByRole("alert")).toContainText("Endpoint недоступен");
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.locator("p").filter({hasText: /^OFFLINE$/}).locator("..")).toContainText("UNKNOWN");
    await page.screenshot({path: testInfo.outputPath("fleet-degraded.png"), fullPage: true});
    expect(pageErrors).toEqual([]);
    expect(badResponses).toEqual([]);
    expect(consoleErrors.filter(message => !message.includes("503"))).toEqual([]);
    await testInfo.attach("console-errors", {body: JSON.stringify(consoleErrors), contentType: "application/json"});
  });
}
