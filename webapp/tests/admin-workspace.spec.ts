import { expect, test } from "playwright/test";


test("администратор открывает inventory, modules actions и observer drilldown в /app/admin", async ({
  page
}) => {
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
  await expect(
    page.locator(".support-snapshot-card").filter({ hasText: "Rollout policy" }).getByText("Обновлять установленные устройства")
  ).toBeVisible();

  await page.getByRole("combobox", { name: "Режим preferred-rollout" }).selectOption("manual");
  await page.getByRole("button", { name: "Сохранить политику" }).click();
  await expect(page.getByText("Политика раскатки сохранена: Только вручную.")).toBeVisible();

  await page.getByRole("button", { name: "Сделать preferred для 1.2.1" }).click();
  await expect(page.getByText("Preferred-версия для network_ping обновлена на 1.2.1.")).toBeVisible();
  await expect(page.getByText(/Preferred:\s*1\.2\.1/)).toBeVisible();

  await expect(page.getByRole("heading", { name: "Быстрый срез трассировки" })).toBeVisible();
  await expect(page.getByText("Launcher signature mismatch")).toBeVisible();
  await expect(page.getByText("/api/web/admin/observer/traces", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Детальный разбор трасс" })).toBeVisible();
  await expect(page.getByText("trace-update-1").first()).toBeVisible();
  await expect(page.locator(".admin-observer-panel__runtime")).toHaveText("Норма");

  await expect(page.getByRole("heading", { name: "Конструктор форм заявок" })).toBeVisible();
  await expect(page.getByText("Активная версия")).toBeVisible();
  await expect(page.getByRole("button", { name: "Новая форма" })).toBeVisible();
  await page.getByRole("button", { name: "Новая форма" }).click();
  await page.getByLabel("Название формы").fill("Ремонт принтера");
  await page.getByLabel("Ключ формы").fill("printer_repair");
  await page.getByLabel("Request kind").fill("printer_repair");
  await page.getByLabel("Название поля").fill("Код поломки");
  await page.getByLabel("Ключ поля").fill("issue_code");
  await page.getByRole("button", { name: "Сохранить изменения" }).click();
  await expect(page.getByText(/Каталог опубликован как версия 1.0.4/)).toBeVisible();

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
