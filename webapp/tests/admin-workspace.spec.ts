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
