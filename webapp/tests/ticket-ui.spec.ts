import { expect, test, type Page } from "playwright/test";

async function prepareSupport(page: Page) {
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/support/tickets/*/timeline?*", route => route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", filter: "all", items: [] } } }));
  await page.route("**/api/web/support/tickets/*/read", route => route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", last_read_event_id: 1 } } }));
  await page.goto("/app/login");
  await page.getByLabel("Логин").fill("admin");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page).not.toHaveURL(/\/app\/login/);
}

for (const width of [1366, 1920]) {
  test(`shared tickets shell, completed SLA and requester profile at ${width}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 1366 ? 768 : 1080 });
    await prepareSupport(page);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    await page.route("**/api/web/support/tickets/*/workspace", async route => {
      const response = await route.fetch();
      const payload = await response.json();
      payload.data.detail.snapshot.registry = { status: "available", person_id: "person-1", person_display_name: "Тестовый заявитель", person_email: "person@example.test", person_phone: "1234", person_source: "local_authoritative", department_name: "Отдел поддержки", location_display_name: "Кабинет 101" };
      payload.data.sla_ola.first_response = { due_at: null, remaining_seconds: null, target_seconds: 900, status: "completed", completed_at: "2026-10-11T08:22:00Z", completed_within_target: true };
      await route.fulfill({ response, json: payload });
    });
    await page.goto("/app/tickets/ticket-1");
    await expect(page.getByRole("navigation", { name: "Навигация поддержки" })).toBeVisible();
    await expect(page.getByTestId("support-workspace-root")).toHaveAttribute("data-theme", "light");
    await expect(page.getByRole("button", { name: "Выполнить действие" })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`tickets-${width}.png`) });
    await page.getByTestId("support-command-strip").getByRole("button", { name: "Контекст", exact: true }).click();
    await expect(page.getByTestId("support-inspector-panel")).toBeVisible();
    await page.getByText("Тестовый заявитель", { exact: true }).scrollIntoViewIfNeeded();
    await expect(page.getByText("person@example.test", { exact: true })).toBeVisible();
    await expect(page.getByText("1234", { exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`profile-${width}.png`) });
    await page.getByRole("button", { name: "SLA", exact: true }).last().click();
    await page.getByText("Ответ получен", { exact: true }).scrollIntoViewIfNeeded();
    await expect(page.getByText("Ответ получен", { exact: true })).toBeVisible();
    await expect(page.getByText("Выполнено", { exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`sla-${width}.png`) });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(2);
    const returnToChat = page.getByRole("button", { name: "Вернуться к переписке", exact: true });
    if (await returnToChat.isVisible()) await returnToChat.click();
    await expect(page.getByLabel("Сообщение в тикет")).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("quality dashboard uses Russian labels while mutation codes stay unchanged", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await prepareSupport(page);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
  const policy = { scope_type: "global", low_csat_threshold: 3, reopen_review_enabled: true, sla_breach_review_enabled: true, high_priority_review_enabled: true, missing_evidence_review_enabled: true, random_sample_percent: 0, qa_due_hours: 72 };
  let created: Record<string, unknown> | null = null;
  await page.route("**/api/web/quality/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let payload: object = {};
    if (path.endsWith("/summary")) payload = { summary: { avg_csat: null, feedback_count: 2, negative_csat_count: 1, reopen_count: 1, sla_breach_count: 1, qa_review_count: 1, improvement_action_count: 1 } };
    if (path.endsWith("/service-quality")) payload = { rows: [], last_computed_at: "2026-10-11T08:00:00Z" };
    if (path.endsWith("/reviews")) payload = { reviews: [{ review_id: "review-1", ticket_id: "ticket-1", review_type: "low_csat", severity: "high", status: "open", created_at: "2026-10-11T08:00:00Z" }] };
    if (path.endsWith("/improvement-actions")) {
      if (route.request().method() === "POST") {
        created = route.request().postDataJSON();
        payload = { action: { action_id: "action-2", ...created } };
      } else payload = { actions: [{ action_id: "action-1", source_kind: "manual", action_type: "process_review", title: "Улучшить ответы", status: "in_progress", priority: "medium" }] };
    }
    if (path.endsWith("/policies") || path.endsWith("/policies/save")) payload = { policy };
    await route.fulfill({ json: { status: "ok", ...payload } });
  });
  await page.goto("/app/admin/quality");
  await expect(page.getByRole("heading", { name: "Управление качеством" })).toBeVisible();
  await expect(page.getByText("Низкая оценка пользователя", { exact: true })).toBeVisible();
  await expect(page.getByText("В работе", { exact: true })).toBeVisible();
  await expect(page.getByText("Нет данных", { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("quality-ru.png"), fullPage: true });
  await page.getByPlaceholder("Название задачи").fill("Проверить процесс ответов");
  await page.getByRole("button", { name: "Создать", exact: true }).click();
  await expect.poll(() => created).toMatchObject({ source_kind: "manual", action_type: "process_review", priority: "medium", title: "Проверить процесс ответов" });
  expect(errors).toEqual([]);
});
