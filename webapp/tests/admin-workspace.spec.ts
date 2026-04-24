import { expect, type Page, test } from "playwright/test";

async function loginAsAdmin(page: Page) {
  await page.goto("/app/admin");
  if (page.url().includes("/app/admin/inventory")) {
    return;
  }
  const textboxes = page.getByRole("textbox");
  await textboxes.nth(0).fill("admin");
  await textboxes.nth(1).fill("secret");
  await page.getByRole("button").filter({ hasText: /Войти|Р’РѕР№С‚Рё/ }).click();
  await expect(page).toHaveURL(/\/app\/admin\/inventory/);
}

test("администратор видит отдельные пункты admin-меню и открывает ключевые страницы", async ({ page }) => {
  await page.goto("/app/admin");

  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();

  await page.getByLabel("Логин").fill("admin");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/admin\/inventory(?:\?.*)?$/);
  await expect(page.getByRole("heading", { name: "Инвентарь устройств" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Карточка устройства/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Модули/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Конструктор форм/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Observer/ })).toBeVisible();

  await page.getByRole("link", { name: /Карточка устройства/ }).click();
  await expect(page).toHaveURL(/\/app\/admin\/device$/);
  await expect(page.getByRole("heading", { name: "Карточка устройства" })).toBeVisible();

  await page.getByRole("link", { name: /Модули/ }).click();
  await expect(page).toHaveURL(/\/app\/admin\/modules$/);
  await expect(page.getByRole("heading", { name: "Модули" })).toBeVisible();

  await page.getByRole("link", { name: /Observer/ }).click();
  await expect(page).toHaveURL(/\/app\/admin\/observer$/);
  await expect(page.getByRole("heading", { name: "Observer", exact: true })).toBeVisible();
});

test("admin inventory tokens and notifications tab stay authenticated", async ({ page }) => {
  await loginAsAdmin(page);

  const tokensResponse = page.waitForResponse((response) =>
    response.url().includes("/api/web/admin/devices/device-1/tokens") && response.status() === 200
  );
  await page.goto("/app/admin/inventory?device=device-1");
  await tokensResponse;
  await expect(page.getByText("Токены устройства")).toBeVisible();
  await expect(page.getByText("tok-act")).toBeVisible();

  const revokeResponse = page.waitForResponse((response) =>
    response.url().includes("/api/web/admin/devices/device-1/tokens/revoke") && response.status() === 200
  );
  await page.getByRole("button", { name: "Отозвать" }).first().click();
  await revokeResponse;

  const prefsResponse = page.waitForResponse((response) =>
    response.url().includes("/api/notifications/preferences") && response.status() === 200
  );
  const alertsResponse = page.waitForResponse((response) =>
    response.url().includes("/api/admin/tech/alerts") && response.status() === 200
  );
  await page.goto("/app/admin/settings");
  await page.getByRole("button", { name: "Уведомления" }).click();
  await prefsResponse;
  await alertsResponse;
  await expect(page.getByText("env_uuid-дубли")).toBeVisible();
});
