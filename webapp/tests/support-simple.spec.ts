import { expect, test, type Page } from "playwright/test";

async function login(page: Page) {
  await page.goto("/app/login?next=/app/tickets");
  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Очередь обращений", exact: true })).toBeVisible();
}

test("unified queue keeps the full list reachable and restores the resizable inspector", async ({ page }, info) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/web/support/queue?*", async (route) => {
    const response = await route.fetch(); const payload = await response.json();
    payload.data.queue_mode = "unified";
    await route.fulfill({ json: payload });
  });
  await login(page);
  await page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "T-200001", exact: true }).click();
  await expect(page.getByTestId("support-inspector-panel")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Очередь", exact: true })).toHaveCount(0);
  const left = page.getByRole("separator", { name: "Ширина списка обращений" });
  const right = page.getByRole("separator", { name: "Ширина панели сведений" });
  const before = await right.getAttribute("aria-valuenow");
  await right.focus(); await page.keyboard.press("ArrowLeft");
  await expect(right).not.toHaveAttribute("aria-valuenow", before!);
  const handle = (await left.boundingBox())!;
  await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
  await page.mouse.down(); await page.mouse.move(handle.x + 70, handle.y + handle.height / 2); await page.mouse.up();
  expect(Number(await left.getAttribute("aria-valuenow"))).toBeGreaterThan(260);
  await page.getByRole("button", { name: "Open SLA inspector" }).click();
  await expect(page.getByTestId("simple-support-workspace")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Диалог", exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("unified-inspector-1920.png"), fullPage: true });
  await page.getByRole("button", { name: /Открыть всю очередь/ }).click();
  await expect(page.getByRole("heading", { name: "Очередь обращений", exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/app\/tickets$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});

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
    await page.getByRole("button", { name: /Описание и ответы сотрудника/ }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("205", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Закрыть описание", exact: true }).click();
    await expect(page.getByText("Расчёт SLA для теста")).toHaveCount(0);
    await expect(page.getByText("Проверить картридж — только для поддержки")).toHaveCount(0);
    await expect(page.getByText("Принтер не печатает", { exact: true })).toHaveCount(1);
    await expect(page.getByRole("link", { name: "Ошибка.png" })).toHaveAttribute("href", "/api/artifacts/fixture-attachment/download");
    await expect(reply).toBeInViewport();
    await expect(page.getByRole("button", { name: "Отправить", exact: true })).toBeInViewport();
    expect((await page.getByRole("tabpanel", { name: "Диалог", exact: true }).boundingBox())?.height).toBeGreaterThan(width < 760 ? 110 : 180);
    await page.screenshot({ path: info.outputPath(`ticket-before-take-${width}.png`), fullPage: true });
    await take.click();
    await expect(reply).toBeEnabled();
    await reply.fill("Бумага добавлена. Проверьте печать.");
    await reply.press("Control+Enter");
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

test("queue and card explain an unavailable take before sending a command", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 768 });
  await page.route("**/api/web/support/tickets/ticket-1/timeline?*", (route) => route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", filter: "all", items: [], total: 0, limit: 200 } } }));
  const reason = "Вы не состоите в очереди обращения. Назначить исполнителем можно участника этой очереди.";
  const availability = { allowed: false, reason_code: "ASSIGNEE_NOT_IN_QUEUE", reason };
  let commands = 0;
  await page.route("**/api/web/support/queue?*", async (route) => {
    const response = await route.fetch(); const payload = await response.json();
    for (const ticket of payload.data.tickets) ticket.take_in_work = availability;
    await route.fulfill({ response, json: payload });
  });
  await page.route("**/api/web/support/tickets/ticket-1/workspace", async (route) => {
    const response = await route.fetch(); const payload = await response.json();
    payload.data.detail.actions.take_in_work = availability;
    await route.fulfill({ response, json: payload });
  });
  await page.route("**/api/web/support/tickets/ticket-1/status", (route) => { commands++; return route.abort(); });
  await login(page);
  const row = page.getByRole("row", { name: /T-200001/ });
  await expect(row.getByRole("button", { name: "Взять в работу", exact: true })).toHaveCount(0);
  await expect(row.getByText("Не состоите в очереди", { exact: true })).toBeVisible();
  await row.getByRole("button", { name: "T-200001" }).click();
  await expect(page.getByRole("button", { name: "Взять в работу", exact: true })).toHaveCount(0);
  await expect(page.getByText(reason, { exact: true }).first()).toBeVisible();
  await expect(page.locator('textarea[aria-label="Сообщение сотруднику"]')).toBeDisabled();
  expect((await page.getByRole("tabpanel", { name: "Диалог", exact: true }).boundingBox())?.height).toBeGreaterThan(110);
  await page.getByRole("tab", { name: "Внутренние заметки", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Внутренняя заметка", exact: true })).toBeEnabled();
  expect(commands).toBe(0);
});

test("a stale take refreshes availability and shows the specific server error", async ({ page }) => {
  let rejected = false;
  const reason = "Достигнут лимит активных обращений (3). Завершите работу с одной из текущих заявок.";
  await page.route("**/api/web/support/tickets/ticket-1/workspace", async (route) => {
    const response = await route.fetch(); const payload = await response.json();
    payload.data.detail.actions.take_in_work = rejected
      ? { allowed: false, reason_code: "ASSIGNEE_CAPACITY_REACHED", reason }
      : { allowed: true, reason_code: null, reason: null };
    await route.fulfill({ response, json: payload });
  });
  await page.route("**/api/web/support/tickets/ticket-1/status", (route) => {
    rejected = true;
    return route.fulfill({ status: 409, json: { status: "error", error: reason, error_code: "ASSIGNEE_CAPACITY_REACHED" } });
  });
  await login(page);
  await page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "T-200001" }).click();
  await page.getByRole("button", { name: "Взять в работу", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: reason })).toBeVisible();
  await expect(page.getByRole("button", { name: "Взять в работу", exact: true })).toHaveCount(0);
  await expect(page.locator('textarea[aria-label="Сообщение сотруднику"]')).toBeDisabled();
});
