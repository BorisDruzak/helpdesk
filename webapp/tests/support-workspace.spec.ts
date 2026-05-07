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

  await expect(page).toHaveURL(/\/app\/tickets$/);
  await expect(page.getByRole("heading", { name: "Тикеты" })).toBeVisible();
  await expect(page.getByText("Service Desk")).toBeVisible();
  await expect(page.getByText("РАБОЧИЕ СРЕЗЫ")).toBeVisible();
  await expect(page.getByText("ТИКЕТЫ В ОЧЕРЕДИ")).toBeVisible();

  await page.getByRole("button", { name: /T-200001/ }).click();

  await expect(page).toHaveURL(/\/app\/tickets\/ticket-1$/);
  await expect(page.getByText(/T-200001 Ошибка синхронизации/)).toBeVisible();
  await expect(page.getByText("СЛЕДУЮЩЕЕ ДЕЙСТВИЕ")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ответить" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Инструменты" })).toBeVisible();

  await page.getByRole("button", { name: "Инструменты" }).click();
  await expect(page.getByText("Диагностика синхронизации профиля")).toBeVisible();
  await expect(page.getByText("Право: запуск безопасных инструментов")).toBeVisible();
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
    await expect(page.getByText("РАБОЧИЕ СРЕЗЫ")).toBeVisible();
    await expect(page.getByRole("button", { name: "Ответить" })).toBeVisible();

    const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(horizontalOverflow).toBeLessThanOrEqual(2);
  });
}
