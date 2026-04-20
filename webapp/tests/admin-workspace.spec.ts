import { expect, test } from "playwright/test";


test("администратор открывает inventory, update workflow и observer drilldown в /app/admin", async ({ page }) => {
  await page.goto("/app/admin");

  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.getByRole("heading", { name: "Вход в рабочие места" })).toBeVisible();

  await page.getByLabel("Логин").fill("admin");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/\/app\/admin$/);
  await expect(page.getByRole("heading", { name: "Рабочее место администрирования" })).toBeVisible();
  await expect(page.getByText("Всего в инвентаре")).toBeVisible();
  await expect(page.getByText("Назначения rollout")).toBeVisible();
  await expect(page.getByRole("button", { name: /WS-01/i })).toBeVisible();
  await expect(page.getByText("Устройство на шаг позади rollout").first()).toBeVisible();
  await expect(page.getByText("Доступно обновление")).toBeVisible();
  await expect(page.getByText("Назначенный rollout новее текущей версии.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Реестр модулей" })).toBeVisible();
  await expect(page.getByRole("button", { name: /network_ping/i })).toBeVisible();
  await expect(page.getByText("Обновлять установленные устройства")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Быстрый срез трассировки" })).toBeVisible();
  await expect(page.getByText("Launcher signature mismatch")).toBeVisible();
  await expect(page.getByText("/api/web/admin/observer/traces", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Детальный разбор трасс" })).toBeVisible();
  await expect(page.getByText("trace-update-1").first()).toBeVisible();
  await expect(page.locator(".admin-observer-panel__runtime")).toHaveText("Норма");

  await page.getByLabel("Причина запуска").fill("canary после smoke");
  await page.getByRole("button", { name: "Запустить обновление" }).click();

  await expect(page.getByText(/Операция op-admin-update-\d+ поставлена в очередь\./)).toBeVisible();

  await page.getByRole("button", { name: /LT-02/i }).click();

  await expect(page.getByText("Платформа: linux_alt_x86_64")).toBeVisible();
  await expect(page.getByText("trace-linux-1").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Ожидает связи" })).toBeDisabled();

  await page.getByRole("button", { name: "72 часа" }).click();
  await expect(page.locator(".admin-observer-panel__runtime")).toHaveText("Есть отставание");
  await expect(page.getByText("Для выбранного устройства по текущим фильтрам трасс пока нет.")).toBeVisible();
});
