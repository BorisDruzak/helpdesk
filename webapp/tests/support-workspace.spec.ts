import { expect, type Page, test } from "playwright/test";

async function loginSupport(page: Page) {
  await page.goto("/app/support");

  await expect(page).toHaveURL(/\/app\/login/);
  await expect(page.getByRole("heading", { name: "Добро пожаловать" })).toBeVisible();

  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();
}

test("оператор открывает tickets workspace через новый shell", async ({ page }) => {
  await loginSupport(page);

  await expect(page).toHaveURL(/\/app\/support$/);
  await page.getByRole("link", { name: "Тикеты" }).click();
  await expect(page).toHaveURL(/\/app\/tickets$/);
  await expect(page.getByRole("heading", { name: "Тикеты" })).toBeVisible();
  await expect(page.getByText("Service Desk")).toBeVisible();
  await expect(page.getByText("Мой рабочий список")).toBeVisible();
  await expect(page.getByRole("button", { name: /T-200001 Ошибка синхронизации/ })).toBeVisible();

  await page.getByRole("button", { name: /T-200001/ }).click();

  await expect(page).toHaveURL(/\/app\/tickets\/ticket-1$/);
  await expect(page.getByText(/T-200001 Ошибка синхронизации/)).toBeVisible();
  await expect(page.getByText("СЛЕДУЮЩЕЕ ДЕЙСТВИЕ")).toBeVisible();
  await expect(page.getByRole("button", { name: "Выполнить действие" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Инструменты" })).toBeVisible();

  await page.getByRole("button", { name: "Инструменты" }).click();
  await expect(page.getByText("Диагностика синхронизации профиля")).toBeVisible();
  await expect(page.getByText("Право: запуск безопасных инструментов")).toBeVisible();
});

test("оператор видит безопасное состояние диагностики Endpoint Platform", async ({ page }, testInfo) => {
  const consoleErrors: string[] = [];
  const failedDiagnosticsRequests: string[] = [];
  const knownFixtureFailures: string[] = [];
  const unexpectedFailedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      const failure = `${response.status()} ${response.request().method()} ${response.url()}`;
      if (response.url().includes("/diagnostics/")) {
        failedDiagnosticsRequests.push(failure);
      } else if (response.url().includes("/timeline?") || response.url().endsWith("/read")) {
        knownFixtureFailures.push(failure);
      } else {
        unexpectedFailedRequests.push(failure);
      }
    }
  });

  await loginSupport(page);
  await page.goto("/app/tickets/ticket-1");
  await expect(page.getByText(/T-200001 Ошибка синхронизации/)).toBeVisible();
  await page.getByRole("button", { name: "Инструменты", exact: true }).click();
  await page.getByRole("tab", { name: "Диагностика", exact: true }).click();

  await expect(page.getByText("Endpoint Platform", { exact: true })).toBeVisible();
  await expect(page.getByText("Поставлено в очередь Endpoint")).toBeVisible();
  await expect(page.getByText("Операция поставлена в очередь и будет доставлена при подключении агента.")).toBeVisible();
  await expect(page.getByText("Для обращения не определено устройство Endpoint Platform.")).toBeVisible();
  expect(failedDiagnosticsRequests).toEqual([]);
  expect(unexpectedFailedRequests).toEqual([]);
  expect(knownFixtureFailures).toEqual([
    "404 GET http://127.0.0.1:4173/api/web/support/tickets/ticket-1/timeline?filter=all",
    "404 POST http://127.0.0.1:4173/api/web/support/tickets/ticket-1/read",
  ]);
  expect(consoleErrors).toEqual([
    "Failed to load resource: the server responded with a status of 404 (Not Found)",
    "Failed to load resource: the server responded with a status of 404 (Not Found)",
  ]);

  await page.setViewportSize({ width: 1366, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(2);
  await page.screenshot({ path: testInfo.outputPath("endpoint-diagnostics-1366.png"), fullPage: true });

  await page.setViewportSize({ width: 1920, height: 1080 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(2);
  await page.screenshot({ path: testInfo.outputPath("endpoint-diagnostics-1920.png"), fullPage: true });
});

for (const width of [1366, 1440, 1920]) {
  test(`tickets workspace сохраняет читаемость на ${width}px в dark/light`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await loginSupport(page);

    await page.goto("/app/tickets/ticket-1");
    await expect(page.getByText(/T-200001 Ошибка синхронизации/)).toBeVisible();
    await expect(page.getByText("СЛЕДУЮЩЕЕ ДЕЙСТВИЕ")).toBeVisible();
    await expect(page.getByRole("button", { name: "Паспорт", exact: true })).toBeVisible();

    const root = page.getByTestId("support-workspace-root");
    await expect(root).toHaveAttribute("data-theme", "dark");

    await page.getByRole("button", { name: "Светлая тема" }).click();
    await expect(root).toHaveAttribute("data-theme", "light");
    await expect(page.getByRole("button", { name: "Выполнить действие" })).toBeVisible();

    const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(horizontalOverflow).toBeLessThanOrEqual(2);
  });
}
