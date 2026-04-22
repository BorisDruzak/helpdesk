import { expect, test } from "playwright/test";

test("оператор открывает tickets workspace через новый shell", async ({ page }) => {
  await page.goto("/app/support");

  await expect(page).toHaveURL(/\/app\/login/);
  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();

  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/tickets$/);
  await expect(page.getByRole("heading", { name: "Тикеты" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Рабочая панель" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Тикеты/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Выйти" })).toBeVisible();

  await page.getByText("T-200001").click();

  await expect(page).toHaveURL(/\/app\/tickets\/ticket-1$/);
  await expect(page.getByRole("heading", { name: "Тикет #T-200001" })).toBeVisible();
  await expect(page.getByText("Информация о тикете")).toBeVisible();
  await expect(page.getByRole("button", { name: "Отправить" })).toBeVisible();
});
