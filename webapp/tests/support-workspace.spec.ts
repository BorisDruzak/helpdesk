import { expect, test } from "playwright/test";


test("оператор проходит support workflow на русском языке", async ({ page }) => {
  await page.goto("/app/support");

  await expect(page).toHaveURL(/\/app\/login/);
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page).toHaveTitle("pc_client — рабочие места");
  await expect(page.getByRole("heading", { name: "Вход в рабочие места" })).toBeVisible();

  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/support$/);
  await expect(page.getByRole("heading", { name: "Рабочее место поддержки" })).toBeVisible();
  await expect(page.getByText("trace-support-root")).toBeVisible();

  await page.getByRole("button", { name: /T-200002/i }).click();
  await expect(page.getByRole("heading", { name: "Нужно уточнить статус печати" })).toBeVisible();

  await page.getByRole("button", { name: /T-200001/i }).click();
  await expect(page.getByRole("heading", { name: "Ошибка синхронизации профиля" })).toBeVisible();

  await page.getByLabel("Ответ оператору").fill("Проверка начата, остаёмся на связи и собираем сетевой снимок.");
  await page.getByRole("button", { name: "Отправить ответ" }).click();
  await expect(page.getByText("Проверка начата, остаёмся на связи и собираем сетевой снимок.")).toBeVisible();

  await page.getByRole("button", { name: "Взять в работу" }).click();
  await expect(page.locator(".support-ticket-detail__stats")).toContainText("В работе");

  await page.getByRole("button", { name: /network\.diagnostics/i }).click();
  await page.getByLabel("Хост").fill("fileserver.local");
  await page.getByRole("button", { name: "Запустить инструмент" }).click();

  await expect(page.getByText("Операция op-support-tool-1 поставлена в очередь выполнения.")).toBeVisible();
  await expect(page.getByText("Сетевой маршрут проверен успешно.").first()).toBeVisible();
  await expect(page.getByText("Инструмент завершён")).toBeVisible();
  await expect(page.locator(".support-operations__list")).toContainText("network.diagnostics");
});
