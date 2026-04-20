import { expect, test } from "playwright/test";


test("администратор открывает inventory устройств в /app/admin", async ({ page }) => {
  await page.goto("/app/admin");

  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.getByRole("heading", { name: "Вход в рабочие места" })).toBeVisible();

  await page.getByLabel("Логин").fill("admin");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/admin$/);
  await expect(page.getByRole("heading", { name: "Рабочее место администрирования" })).toBeVisible();
  await expect(page.getByText("Всего в inventory")).toBeVisible();
  await expect(page.getByText("Назначения rollout")).toBeVisible();
  await expect(page.getByRole("button", { name: /WS-01/i })).toBeVisible();
  await expect(page.getByText("Устройство на шаг позади rollout").first()).toBeVisible();

  await page.getByRole("button", { name: /LT-02/i }).click();

  await expect(page.getByText("Назначен rollout stable/2.3.9").first()).toBeVisible();
  await expect(page.getByText("/api/admin/tech/observer/quick")).toBeVisible();
});
