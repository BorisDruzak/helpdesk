import { expect, test } from "playwright/test";

test("администратор видит отдельные пункты admin-меню и открывает ключевые страницы", async ({ page }) => {
  await page.goto("/app/admin");

  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();

  await page.getByLabel("Логин").fill("admin");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/admin\/inventory$/);
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
  await expect(page.getByRole("heading", { name: "Observer" })).toBeVisible();
});
