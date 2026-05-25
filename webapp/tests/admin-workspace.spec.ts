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
  await expect(page).toHaveURL(/\/app\/admin$/);
}

test("администратор видит отдельные пункты admin-меню и открывает ключевые страницы", async ({ page }) => {
  await page.goto("/app/admin");

  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();

  await page.getByLabel("Логин").fill("admin");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/admin$/);
  await expect(page.getByRole("heading", { name: "Центр администрирования" })).toBeVisible();
  await page.goto("/app/admin/inventory");
  const adminNav = page.getByRole("navigation", { name: "Навигация администрирования" });
  await expect(page.getByRole("heading", { name: "Агенты" })).toBeVisible();
  await expect(adminNav.getByRole("link", { name: /Инвентарь устройств/ })).toBeVisible();
  await expect(adminNav.getByRole("link", { name: /Карточка устройства/ })).toBeVisible();
  await expect(adminNav.getByRole("link", { name: /Observer/ })).toBeVisible();

  await adminNav.getByRole("link", { name: /Карточка устройства/ }).click();
  await expect(page).toHaveURL(/\/app\/admin\/device$/);
  await expect(page.getByRole("heading", { name: "Карточка устройства" })).toBeVisible();

  await page.getByRole("button", { name: /Автоматизация/ }).click();
  await page.getByRole("link", { name: /Модули/ }).click();
  await expect(page).toHaveURL(/\/app\/admin\/modules$/);
  await expect(page.getByRole("heading", { name: "Модули" })).toBeVisible();

  await page.getByRole("button", { name: /Каталог и заявки/ }).click();
  await page.getByRole("link", { name: /Конструктор форм/ }).click();
  await expect(page).toHaveURL(/\/app\/admin\/forms$/);

  await page.goto("/app/admin/observer");
  await expect(page).toHaveURL(/\/app\/admin\/observer$/);
  await expect(page.getByRole("heading", { name: "Observer", exact: true })).toBeVisible();
});

test("admin inventory tokens and notifications tab stay authenticated", async ({ page }) => {
  await loginAsAdmin(page);

  const tokensResponse = page.waitForResponse((response) =>
    response.url().includes("/api/web/admin/devices/device-1/tokens") && response.status() === 200
  );
  await page.goto("/app/admin/inventory?device=device-1&panel=tokens");
  await tokensResponse;
  await expect(page.getByRole("button", { name: "Токены" })).toBeVisible();
  await expect(page.getByText("tok-act")).toBeVisible();

  const revokeResponse = page.waitForResponse((response) =>
    response.url().includes("/api/web/admin/devices/device-1/tokens/revoke") && response.status() === 200
  );
  await page.getByRole("button", { name: "Отозвать" }).first().click();
  await revokeResponse;

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
