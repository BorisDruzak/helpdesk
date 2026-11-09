import { expect, test, type Page } from "playwright/test";

async function prepare(page: Page) {
  await page.addInitScript(() => localStorage.setItem("helpdesk-notification-intro-v1:support", "1"));
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/support/command-center*", async route => {
    const payload = { status: "success", data: { generated_at: "2026-11-09T12:00:00Z", scope: "team", metadata: {}, filters: {}, summary: {}, sections: [] as unknown[] } };
    const query = new URL(route.request().url()).searchParams.get("query")?.toLowerCase() ?? "";
    const item = (id: string, title: string) => ({ id, ticket_id: id, ticket_number: id === "ticket-1" ? "T-200001" : "T-200002", title, status: "queued", priority: "P1", queue: "servicedesk_l1", requester_name: "Оператор проверки", assignee: null, reason: "Нужно ответить сотруднику", href: `/app/tickets/${id}`, requires_operator_action: true, unread_user_messages: 1, sla: { state: "breached", due_at: "2026-11-09T08:00:00Z" } });
    const items = [item("ticket-1", "Настроить VPN"), item("ticket-2", "Проверить принтер")].filter(item => item.title.toLowerCase().includes(query));
    const section = (key: string, title: string, values: typeof items) => ({ key, title, severity: "warning", count: values.length, items: values, description: title, action: { label: "Открыть очередь", href: "/app/tickets" } });
    payload.data.sections = [section("sla_risk", "SLA risk", items.filter(item => item.ticket_id === "ticket-1")), section("unread_user_messages", "Сообщения пользователей", items)];
    await route.fulfill({ json: payload });
  });
  await page.goto("/app/login?next=/app/tickets");
  await page.getByLabel("Логин", { exact: true }).fill("support");
  await page.getByLabel("Пароль", { exact: true }).fill("secret");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Очередь обращений", exact: true })).toBeVisible();
}

for (const width of [390, 1366, 1920]) {
  test(`actions share the primary queue and search at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : width === 1920 ? 1080 : 768 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await prepare(page);
    await page.goto("/app/support/advanced");
    await expect(page).toHaveURL(/\/app\/tickets\?view=actions$/);
    await expect(page.getByRole("tab", { name: "Действия", exact: true })).toHaveAttribute("aria-selected", "true");
    const actions = page.getByRole("region", { name: "Действия очереди", exact: true });
    await expect(actions.locator(".support-action-row")).toHaveCount(2);
    const refreshed = page.waitForResponse(response => new URL(response.url()).pathname === "/api/web/support/command-center");
    await page.getByRole("button", { name: "Обновить очередь", exact: true }).click();
    await refreshed;
    await expect(page.getByRole("searchbox", { name: "Поиск обращений", exact: true })).toHaveCount(1);
    await expect(page.getByRole("link", { name: "Расширенный центр", exact: true })).toHaveCount(0);
    await expect(actions.getByText("queued", { exact: true })).toHaveCount(0);
    await expect(actions.getByText("SLA risk", { exact: true })).toHaveCount(0);
    await expect(actions.getByRole("link", { name: "Открыть обращение", exact: true })).toHaveAttribute("href", "/app/tickets/ticket-1");
    const filters = page.getByRole("region", { name: "Фильтры действий", exact: true });
    await filters.getByRole("button", { name: /Риск SLA/ }).click();
    await expect(actions.locator(".support-action-row")).toHaveCount(1);
    await filters.getByRole("button", { name: /Все действия/ }).click();
    await page.getByRole("searchbox", { name: "Поиск обращений", exact: true }).fill("принтер");
    await expect(actions.locator(".support-action-row")).toHaveCount(1);
    await expect(actions.getByRole("link", { name: "Открыть обращение", exact: true })).toHaveAttribute("href", "/app/tickets/ticket-2");
    await page.getByRole("searchbox", { name: "Поиск обращений", exact: true }).fill("");
    await expect(actions.locator(".support-action-row")).toHaveCount(2);
    await actions.getByRole("button", { name: "Доска", exact: true }).click();
    await expect(actions.getByRole("heading", { name: "Операции и диагностика", exact: true })).toBeVisible();
    await actions.getByRole("button", { name: "Список", exact: true }).click();
    await expect(actions.locator(".support-action-row")).toHaveCount(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    const filtersBox = await filters.boundingBox();
    const searchBox = await page.getByRole("searchbox", { name: "Поиск обращений", exact: true }).boundingBox();
    expect(searchBox!.x).toBeGreaterThanOrEqual(0);
    expect(searchBox!.x + searchBox!.width).toBeLessThanOrEqual(width);
    expect(filtersBox!.x + filtersBox!.width).toBeLessThanOrEqual(width);
    await page.screenshot({ path: info.outputPath(`queue-actions-${width}.png`), fullPage: true });
    expect(await page.locator(".simple-queue__heading--unified").evaluate(element => getComputedStyle(element).display)).toBe("grid");
    await page.getByRole("button", { name: "Тёмная тема", exact: true }).click();
    const contrast = async (selector: string) => page.locator(selector).first().evaluate(element => {
      const style = getComputedStyle(element);
      const luminance = (color: string) => {
        const values = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(v => v / 255).map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
        return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
      };
      const first = luminance(style.color), second = luminance(style.backgroundColor);
      return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
    });
    expect(await contrast(".support-action-brief .support-action-badge")).toBeGreaterThanOrEqual(4.5);
    await actions.getByRole("button", { name: "Доска", exact: true }).click();
    expect(await contrast(".support-action-board-card")).toBeGreaterThanOrEqual(4.5);
    await page.screenshot({ path: info.outputPath(`queue-actions-dark-${width}.png`), fullPage: true });
    await actions.getByRole("button", { name: "Список", exact: true }).click();
    await page.getByRole("button", { name: "Светлая тема", exact: true }).click();
    await actions.getByRole("link", { name: "Открыть обращение", exact: true }).click();
    await expect(page.locator(".simple-ticket")).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("failed action refresh retains loaded cards and first load failure never claims zero", async ({ page }) => {
  await prepare(page);
  await page.getByRole("tab", { name: "Действия", exact: true }).click();
  const actions = page.getByRole("region", { name: "Действия очереди", exact: true });
  await expect(actions.locator(".support-action-row")).toHaveCount(2);
  await page.route("**/api/web/support/command-center*", route => route.fulfill({ status: 503, json: { status: "error", error_code: "DB_UNAVAILABLE", error: "Недоступно" } }));
  await actions.getByRole("button", { name: "Обновить действия", exact: true }).click();
  await expect(actions.getByRole("alert")).toContainText("Показаны ранее загруженные данные");
  await expect(actions.locator(".support-action-row")).toHaveCount(2);
  await page.reload();
  await expect(actions.getByRole("alert")).toContainText("Не удалось загрузить действия");
  await expect(actions.getByText("Нет срочных действий", { exact: true })).toHaveCount(0);
  await expect(actions.getByRole("region", { name: "Фильтры действий" })).toHaveCount(0);
});
