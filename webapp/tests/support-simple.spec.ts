import { expect, test, type Page } from "playwright/test";

async function login(page: Page) {
  await page.goto("/app/login?next=/app/tickets");
  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Очередь обращений", exact: true })).toBeVisible();
}

for (const width of [1366, 1920, 390]) {
  test(`simple support lifecycle without agent at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 768 });
    const pageErrors: string[] = []; const failures: string[] = []; const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
    page.on("response", (response) => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    page.on("requestfailed", (request) => failures.push(`${request.method()} ${new URL(request.url()).pathname}`));
    await page.route("**/api/web/notifications/unread_count", (route) => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
    let currentStatus = "new";
    let currentAssignee: string | null = null;
    let history = [
      { message_id: "public-one", event_id: 9001, event_type: "chat_message", visibility: "public", text: "Принтер не печатает", from_role: "user", sender_display_name: "Тестовый сотрудник", ts: "2026-10-19T09:00:00+05:00", attachments: [{ artifact_id: "fixture-attachment", name: "Ошибка.png", url: "/api/artifacts/fixture-attachment/download" }] },
      { message_id: "internal-one", event_id: 9002, event_type: "chat_message", visibility: "internal", text: "Проверить картридж — только для поддержки", from_role: "support", ts: "2026-10-19T09:01:00+05:00", attachments: [] },
      { message_id: null, event_id: 9003, event_type: "sla_started", visibility: "system", text: "Расчёт SLA для теста", from_role: "system", ts: "2026-10-19T09:02:00+05:00", attachments: [] },
    ];
    await page.route("**/api/web/support/tickets/ticket-1/timeline?*", (route) => route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", filter: "all", items: [...history, history[0]], total: history.length, limit: 200 } } }));
    await page.route("**/api/web/support/tickets/*/read", (route) => route.fulfill({ json: { status: "success", data: { last_read_event_id: 9003 } } }));
    await page.route("**/api/web/support/tickets/ticket-1/workspace", async (route) => {
      const response = await route.fetch(); const payload = await response.json(); const detail = payload.data.detail;
      detail.ticket.status = currentStatus;
      detail.ticket.status_label = ({ new: "Новая", in_progress: "В работе", resolved: "Решена" } as Record<string, string>)[currentStatus];
      detail.ticket.assignee_id = currentAssignee;
      detail.ticket.device_id = null; detail.snapshot.device.device_id = null; detail.snapshot.device.hostname = null;
      detail.request_form = { rows: [{ key: "room", label: "Кабинет", value: "205" }] };
      await route.fulfill({ response, json: payload });
    });
    await page.route("**/api/web/support/tickets/ticket-1/status", async (route) => {
      currentStatus = route.request().postDataJSON().to_status;
      if (currentStatus === "in_progress") currentAssignee = "support";
      if (currentStatus === "resolved") history.push({ message_id: "confirmation", event_id: 9010, event_type: "chat_message", visibility: "public", text: "Подтвердите решение", from_role: "support", ts: "2026-10-19T09:10:00+05:00", attachments: [] });
      await route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", status: currentStatus, status_label: currentStatus } } });
    });
    await page.route("**/api/web/support/tickets/ticket-1/messages", async (route) => {
      const response = await route.fetch(); const payload = await response.json();
      if (response.ok()) history = [...history, { ...payload.data.message }];
      await route.fulfill({ response, json: payload });
    });
    await login(page);
    await expect(page.getByRole("heading", { name: "Очередь обращений" })).toBeVisible();
    await expect(page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "Взять в работу", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Завершённые", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath(`queue-${width}.png`), fullPage: true });
    await page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "T-200001" }).click();
    const reply = page.getByRole("textbox", { name: "Сообщение сотруднику" });
    await expect(reply).toBeDisabled();
    const take = page.getByRole("button", { name: "Взять в работу", exact: true });
    await expect(take).toBeInViewport();
    await expect(page.getByText("205", { exact: true })).toBeVisible();
    await expect(page.getByText("Расчёт SLA для теста")).toHaveCount(0);
    await expect(page.getByText("Проверить картридж — только для поддержки")).toHaveCount(0);
    await expect(page.getByText("Принтер не печатает", { exact: true })).toHaveCount(1);
    await expect(page.getByRole("link", { name: "↗ Ошибка.png" })).toHaveAttribute("href", "/api/artifacts/fixture-attachment/download");
    await page.screenshot({ path: info.outputPath(`ticket-before-take-${width}.png`), fullPage: true });
    await take.click();
    await expect(reply).toBeEnabled();
    await reply.fill("Бумага добавлена. Проверьте печать.");
    await page.getByRole("button", { name: "Отправить", exact: true }).click();
    await expect(page.getByText("Бумага добавлена. Проверьте печать.", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Внутренние заметки", exact: true }).click();
    await expect(page.getByText("Проверить картридж — только для поддержки")).toBeVisible();
    await page.getByRole("textbox", { name: "Внутренняя заметка", exact: true }).fill("Черновик внутренней заметки");
    await page.getByRole("tab", { name: "Диалог", exact: true }).click();
    await expect(reply).toHaveValue("");
    await page.getByRole("tab", { name: "История", exact: true }).click();
    await expect(page.getByText("Расчёт SLA для теста")).toBeVisible();
    await page.getByRole("tab", { name: "Диалог", exact: true }).click();
    await page.getByRole("button", { name: "Решить обращение", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Решить обращение", exact: true })).toBeVisible();
    await page.getByLabel("Итог для сотрудника").fill("Печать восстановлена, бумага добавлена.");
    await page.getByRole("dialog").getByRole("button", { name: "Решить обращение", exact: true }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(reply).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath(`ticket-resolved-${width}.png`), fullPage: true });
    expect(pageErrors).toEqual([]); expect(failures).toEqual([]); expect(consoleErrors).toEqual([]);
  });
}
