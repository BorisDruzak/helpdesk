import { expect, test, type Page } from "playwright/test";

// The fixture's workspace owns its current timeline; these two live routes are
// absent from that fixture. Keep the browser exercising the real filtered reads.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("helpdesk-notification-intro-v1:support", "1"));
  await page.route("**/api/web/problems?ticket_id=*", route => route.fulfill({ json: { status: "ok", items: [] } }));
  await page.route("**/api/web/support/tickets/*/read", route => route.fulfill({ json: { status: "success", data: { last_read_event_id: 0 } } }));
  await page.route("**/api/web/support/tickets/*/timeline?*", async route => {
    const url = new URL(route.request().url());
    const response = await route.fetch({ url: url.origin + url.pathname.replace(/\/timeline$/, "/workspace") });
    const payload = await response.json();
    const filter = url.searchParams.get("filter");
    const items = (payload.data.detail.timeline ?? []).filter((item: { event_type: string; visibility: string }) => filter === "all" ||
      (filter === "messages" ? item.event_type === "chat_message" && item.visibility === "public" : filter === "internal" ? item.visibility === "internal" : item.event_type !== "chat_message"));
    await route.fulfill({ json: { status: "success", data: { items, total: items.length, limit: 200, filter } } });
  });
});

test("inspector becomes a drawer when expanded navigation narrows the workspace at 1280", async ({ page }, info) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await login(page);
  await page.getByRole("button", { name: "Закрепить панель", exact: true }).click();
  await page.getByRole("button", { name: "T-200001", exact: true }).click();
  const toggle = page.getByRole("button", { name: "Сведения", exact: true });
  const facts = page.getByRole("complementary", { name: "Сведения об обращении", exact: true });
  await expect(toggle).toBeVisible();
  await expect(facts).toBeHidden();
  await toggle.click();
  await expect(facts).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(facts).toBeHidden();
  await expect(page.getByRole("button", { name: "Взять в работу", exact: true })).toBeInViewport();
  const main = await page.locator(".simple-ticket__main").boundingBox();
  const composer = await page.locator(".simple-composer").boundingBox();
  expect(composer!.x + composer!.width).toBeLessThanOrEqual(main!.x + main!.width);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: info.outputPath("unified-ticket-drawer-1280.png"), fullPage: true });
});

for (const width of [1366, 1920]) {
  test(`legacy work requires an explicit self-claim before resolution at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 768 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let owner: string | null = null;
    const claims: unknown[] = [];
    await page.route("**/api/web/notifications/unread_count", (route) => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
    await page.route("**/api/web/support/tickets/ticket-1/workspace", async (route) => {
      const response = await route.fetch(); const payload = await response.json();
      payload.data.detail.ticket.status = "in_progress";
      payload.data.detail.ticket.status_label = "В работе";
      payload.data.detail.ticket.assignee_id = owner;
      payload.data.detail.actions.take_in_work = { allowed: !owner, reason_code: null, reason: null };
      payload.data.detail.actions.can_send_public_message = Boolean(owner);
      payload.data.detail.actions.status_options = [{ value: "resolved", label: "Решить" }];
      await route.fulfill({ response, json: payload });
    });
    await page.route("**/api/web/support/tickets/ticket-1/assign", async (route) => {
      const body = route.request().postDataJSON(); claims.push(body);
      expect(body).toMatchObject({ assignee_id: "support", claim: true, expected_assignee_id: null });
      owner = "support";
      await route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", action: "assign", status: "in_progress" } } });
    });
    await login(page); await page.goto("/app/tickets/ticket-1");
    const take = page.getByRole("button", { name: "Взять себе", exact: true });
    await expect(take).toBeInViewport();
    await expect(page.getByRole("button", { name: /Решить/ })).toHaveCount(0);
    await expect(page.getByRole("textbox", { name: "Сообщение сотруднику" })).toBeDisabled();
    await page.screenshot({ path: info.outputPath(`legacy-before-claim-${width}.png`), fullPage: true });
    await take.click();
    await expect(page.getByRole("button", { name: /Решить/ })).toBeInViewport();
    await expect(page.getByText("Исполнитель: вы", { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Сообщение сотруднику" })).toBeEnabled();
    expect(claims).toHaveLength(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath(`legacy-after-claim-${width}.png`), fullPage: true });
    expect(errors).toEqual([]);
  });
}

async function login(page: Page) {
  await page.goto("/app/login?next=/app/tickets");
  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Очередь обращений", exact: true })).toBeVisible();
}

async function openContext(page: Page) {
  const toggle = page.getByRole("button", { name: "Сведения", exact: true });
  await page.locator(".simple-ticket").waitFor();
  if (await toggle.isVisible()) await toggle.click();
  return page.getByRole("region", { name: "Контекст обращения", exact: true });
}

async function closeContext(page: Page) {
  const close = page.getByRole("button", { name: "Закрыть сведения", exact: true });
  if (await close.isVisible()) await close.click();
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
  await expect(page.getByRole("complementary", { name: "Сведения об обращении", exact: true })).toBeVisible();
  await expect(page.getByTestId("support-inspector-panel")).toBeVisible();
  await expect(page.getByRole("region", { name: "Следующее действие", exact: true })).toBeVisible();
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
  await expect(page.getByRole("button", { name: "Дополнительные возможности", exact: true })).toHaveCount(0);
  const navigation = page.getByRole("navigation", { name: "Разделы правой панели" });
  await navigation.getByRole("button", { name: "SLA", exact: true }).click();
  await expect(page.getByRole("tab", { name: "История сроков", exact: true })).toBeVisible();
  await navigation.getByRole("button", { name: "Качество", exact: true }).click();
  await expect(page.getByText("Оценка обслуживания", { exact: true })).toBeVisible();
  await expect(page.getByText("Experience signals", { exact: true })).toHaveCount(0);
  await navigation.getByRole("button", { name: "Контекст", exact: true }).click();
  await page.getByRole("button", { name: "Скрыть список заявок", exact: true }).click();
  await expect(page.getByRole("button", { name: "Показать список заявок", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Показать список заявок", exact: true }).click();
  await expect(page.getByRole("tab", { name: "SLA риск", exact: true })).toHaveCount(0);
  await page.getByRole("tab", { name: "Новые", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Новые", exact: true })).toHaveAttribute("aria-selected", "true");
  await page.screenshot({ path: info.outputPath("unified-inspector-1920.png"), fullPage: true });
  await expect(page.getByTestId("simple-support-workspace")).toBeVisible();
  await page.getByRole("button", { name: /Открыть всю очередь/ }).click();
  await expect(page.getByRole("heading", { name: "Очередь обращений", exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/app\/tickets\/ticket-1$/);
  await page.getByRole("button", { name: /Вернуться к обращению/ }).click();
  await expect(page.locator(".simple-ticket")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});

for (const width of [1366, 1440, 1920, 390]) {
  test(`simple support lifecycle without agent at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : width === 1440 ? 900 : 768 });
    const pageErrors: string[] = []; const failures: string[] = []; const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
    page.on("response", (response) => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    page.on("requestfailed", (request) => failures.push(`${request.method()} ${new URL(request.url()).pathname}`));
    await page.route("**/api/web/notifications/unread_count", (route) => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
    await page.route("**/api/artifacts/fixture-attachment/download", route => route.fulfill({contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOC8AAAAASUVORK5CYII=", "base64")}));
    let currentStatus = "new";
    let currentAssignee: string | null = null;
    let publicResult = "";
    const completionCommands: unknown[] = [];
    const problem = "Задания остаются в очереди принтера в кабинете 205.";
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
      detail.ticket.status_label = ({ new: "Новая", in_progress: "В работе", closed: "Закрыта" } as Record<string, string>)[currentStatus];
      detail.ticket.assignee_id = currentAssignee;
      detail.ticket.description = problem;
      detail.ticket.requester_resolution_summary = publicResult || null;
      detail.ticket.device_id = null; detail.snapshot.device.device_id = null; detail.snapshot.device.hostname = null;
      detail.actions.can_resolve_and_close = currentStatus === "in_progress";
      detail.actions.status_options = currentStatus === "closed" ? [] : [{ value: "in_progress", label: "В работе" }, { value: "resolved", label: "Решена" }];
      detail.actions.closure_requirements = [{ key: "public_summary", label: "Итог для сотрудника", met: Boolean(publicResult) }];
      detail.request_form = { rows: [{ key: "room", label: "Кабинет", value: "205" }] };
      await route.fulfill({ response, json: payload });
    });
    await page.route("**/api/web/support/tickets/ticket-1/status", async (route) => {
      const command = route.request().postDataJSON();
      expect(route.request().method()).toBe("POST");
      currentStatus = command.to_status;
      if (currentStatus === "in_progress") currentAssignee = "support";
      if (currentStatus === "resolved") {
        completionCommands.push(command);
        expect(command).toMatchObject({ to_status: "resolved", close_after_resolve: true, requester_resolution_summary: "Печать восстановлена, бумага добавлена." });
        expect(command).not.toHaveProperty("resolution_code");
        publicResult = command.requester_resolution_summary;
        currentStatus = "closed";
      }
      await route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", status: currentStatus, status_label: currentStatus } } });
    });
    await page.route("**/api/web/support/tickets/ticket-1/messages", async (route) => {
      const response = await route.fetch(); const payload = await response.json();
      if (response.ok()) history = [...history, { ...payload.data.message }];
      await route.fulfill({ response, json: payload });
    });
    await login(page);
    await expect(page.getByRole("heading", { name: "Очередь обращений" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Действие", exact: true })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Завершённые", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath(`queue-${width}.png`), fullPage: true });
    await page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "T-200001" }).click();
    const reply = page.getByRole("textbox", { name: "Сообщение сотруднику" });
    await expect(reply).toBeDisabled();
    const take = page.getByRole("button", { name: "Взять в работу", exact: true });
    await expect(take).toBeInViewport();
    const summary = await openContext(page);
    await expect(summary.getByText(problem, { exact: true })).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByText("205", { exact: true })).toBeVisible();
    await page.screenshot({path: info.outputPath(`context-${width}.png`), fullPage: true});
    await closeContext(page);
    await expect(page.getByText("Расчёт SLA для теста")).toHaveCount(0);
    await expect(page.getByText("Проверить картридж — только для поддержки")).toHaveCount(0);
    await expect(page.getByText("Принтер не печатает", { exact: true })).toHaveCount(1);
    await expect(page.getByRole("link", { name: "Скачать Ошибка.png" })).toHaveAttribute("href", "/api/artifacts/fixture-attachment/download");
    const preview = page.getByRole("button", {name: "Открыть изображение Ошибка.png"});
    await preview.scrollIntoViewIfNeeded();
    await expect(page.getByRole("img", {name: "Миниатюра: Ошибка.png"})).toHaveJSProperty("naturalWidth", 1);
    let downloads = 0; page.on("download", () => downloads++);
    await preview.click();
    await expect(page.getByRole("dialog", {name: "Просмотр изображения: Ошибка.png"})).toBeVisible();
    const viewerBounds = (await page.getByRole("dialog").boundingBox())!;
    expect(Math.abs(viewerBounds.x + viewerBounds.width / 2 - width / 2)).toBeLessThan(2);
    expect(viewerBounds.y).toBeGreaterThan(0);
    await page.screenshot({path: info.outputPath(`image-viewer-${width}.png`), fullPage: true});
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(preview).toBeFocused();
    expect(downloads).toBe(0);
    await expect(reply).toBeInViewport();
    await expect(page.getByRole("button", { name: "Отправить", exact: true })).toBeInViewport();
    expect((await page.getByRole("tabpanel", { name: "Диалог", exact: true }).boundingBox())?.height).toBeGreaterThan(width < 760 ? 110 : 180);
    await page.screenshot({ path: info.outputPath(`ticket-before-take-${width}.png`), fullPage: true });
    await take.click();
    await expect(reply).toBeEnabled();
    await reply.fill("Черновик сохранён при просмотре изображения");
    await preview.click();
    await page.getByRole("button", {name: "Закрыть просмотр изображения"}).click();
    await expect(reply).toHaveValue("Черновик сохранён при просмотре изображения");
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
    await page.getByRole("button", { name: "Решить и закрыть", exact: true }).click();
    const resolution = page.getByRole("dialog", { name: "Решить и закрыть", exact: true });
    await expect(resolution).toBeVisible();
    await expect(resolution.getByRole("textbox", { name: /Код решения/ })).toHaveCount(0);
    await expect(resolution.getByRole("button", { name: "Решить и закрыть", exact: true })).toBeDisabled();
    await page.getByLabel("Итог для сотрудника").fill("Печать восстановлена, бумага добавлена.");
    await resolution.getByRole("button", { name: "Решить и закрыть", exact: true }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByText("Обращение закрыто. Переписка и история доступны для просмотра.", { exact: true })).toBeVisible();
    await openContext(page);
    await expect(summary.getByRole("heading", { name: "Результат решения", exact: true })).toBeVisible();
    await expect(summary.getByText("Печать восстановлена, бумага добавлена.", { exact: true })).toBeVisible();
    await closeContext(page);
    expect(completionCommands).toHaveLength(1);
    await expect(page.getByText("Подтвердите решение", { exact: true })).toHaveCount(0);
    await expect(reply).toHaveCount(0);
    await page.getByRole("tab", { name: "Внутренние заметки", exact: true }).click();
    const internalNote = page.getByRole("textbox", { name: "Внутренняя заметка", exact: true });
    await expect(internalNote).toBeEnabled();
    await expect(internalNote).toHaveValue("Черновик внутренней заметки");
    await page.getByRole("tab", { name: "Диалог", exact: true }).click();
    await expect(reply).toHaveCount(0);
    await expect(page.getByText("Проверить картридж — только для поддержки", { exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath(`ticket-closed-${width}.png`), fullPage: true });
    expect(pageErrors).toEqual([]); expect(failures).toEqual([]); expect(consoleErrors).toEqual([]);
  });
}

test("explicit confirmation policy keeps separate resolution without a completion flag", async ({ page }) => {
  let currentStatus = "in_progress";
  const commands: unknown[] = [];
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/support/tickets/ticket-1/workspace", async route => {
    const response = await route.fetch(); const payload = await response.json(); const detail = payload.data.detail;
    detail.ticket.status = currentStatus; detail.ticket.status_label = currentStatus === "resolved" ? "Решена" : "В работе";
    detail.ticket.assignee_id = "support";
    detail.actions.can_resolve_and_close = false;
    detail.actions.status_options = currentStatus === "resolved" ? [] : [{ value: "resolved", label: "Решена" }];
    detail.actions.closure_requirements = [{ key: "public_summary", label: "Итог для сотрудника", met: false }];
    await route.fulfill({ response, json: payload });
  });
  await page.route("**/api/web/support/tickets/ticket-1/status", async route => {
    const command = route.request().postDataJSON(); commands.push(command);
    expect(command).toMatchObject({ to_status: "resolved", close_after_resolve: false, requester_resolution_summary: "Решение ожидает подтверждения сотрудника." });
    expect(command).not.toHaveProperty("resolution_code");
    currentStatus = "resolved";
    await route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", status: "resolved", status_label: "Решена" } } });
  });
  await login(page);
  await page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "T-200001", exact: true }).click();
  await expect(page.getByRole("button", { name: "Решить и закрыть", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Решить обращение", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Решить обращение", exact: true });
  await dialog.getByLabel("Итог для сотрудника").fill("Решение ожидает подтверждения сотрудника.");
  await dialog.getByRole("button", { name: "Решить обращение", exact: true }).click();
  await expect(page.getByText("Решение отправлено сотруднику. Закрытие выполняется по действующей политике.", { exact: true })).toBeVisible();
  await expect(page.getByText("Обращение закрыто. Переписка и история доступны для просмотра.", { exact: true })).toHaveCount(0);
  expect(commands).toHaveLength(1);
});

test("legacy code-only requirements allow completion without manual code entry", async ({ page }) => {
  let closed = false;
  const commands: unknown[] = [];
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/support/tickets/ticket-1/workspace", async route => {
    const response = await route.fetch(); const payload = await response.json(); const detail = payload.data.detail;
    detail.ticket.status = closed ? "closed" : "in_progress"; detail.ticket.status_label = closed ? "Закрыта" : "В работе"; detail.ticket.assignee_id = "support";
    detail.ticket.requester_resolution_summary = closed ? "Печать восстановлена без кода решения." : null;
    detail.actions.can_resolve_and_close = !closed;
    detail.actions.status_options = closed ? [] : [{ value: "resolved", label: "Решена" }];
    // A cached legacy projection must not revive retired manual code requirements.
    detail.actions.closure_requirements = [{ key: "resolution_code", label: "Устаревший код решения", met: false }, { key: "allowed_resolution_code", label: "Устаревший список кодов", met: false }];
    await route.fulfill({ response, json: payload });
  });
  await page.route("**/api/web/support/tickets/ticket-1/status", async route => {
    const command = route.request().postDataJSON(); commands.push(command);
    expect(command).toMatchObject({ to_status: "resolved", close_after_resolve: true, requester_resolution_summary: "Печать восстановлена без кода решения." });
    expect(command).not.toHaveProperty("resolution_code");
    closed = true;
    await route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", status: "closed", status_label: "Закрыта" } } });
  });
  await login(page);
  await page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "T-200001", exact: true }).click();
  await page.getByRole("button", { name: "Решить и закрыть", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Решить и закрыть", exact: true });
  await expect(dialog.getByRole("textbox", { name: /Код решения/ })).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: /Устаревший/ })).toHaveCount(0);
  await dialog.getByLabel("Итог для сотрудника").fill("Печать восстановлена без кода решения.");
  const complete = dialog.getByRole("button", { name: "Решить и закрыть", exact: true });
  await expect(complete).toBeEnabled();
  await complete.click();
  await expect(page.getByText("Обращение закрыто. Переписка и история доступны для просмотра.", { exact: true })).toBeVisible();
  await expect((await openContext(page)).getByText("Печать восстановлена без кода решения.", { exact: true })).toBeVisible();
  expect(commands).toHaveLength(1);
});

test("explicit evidence requirement opens the passport inside the ordinary ticket", async ({ page }) => {
  let commands = 0;
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/support/tickets/ticket-1/workspace", async route => {
    const response = await route.fetch(); const payload = await response.json(); const detail = payload.data.detail;
    detail.ticket.status = "in_progress"; detail.ticket.status_label = "В работе"; detail.ticket.assignee_id = "support";
    detail.actions.can_resolve_and_close = false;
    detail.actions.closure_requirements = [{ key: "priority_evidence", label: "Доказательство решения", met: false, detail: "Прикрепите доказательство проверки печати" }];
    await route.fulfill({ response, json: payload });
  });
  await page.route("**/api/web/support/tickets/ticket-1/status", route => { commands++; return route.abort(); });
  await login(page);
  await page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "T-200001", exact: true }).click();
  await page.getByRole("button", { name: "Решить обращение", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Решить обращение", exact: true });
  await expect(dialog.getByRole("textbox", { name: /Код решения/ })).toHaveCount(0);
  await dialog.getByLabel("Итог для сотрудника").fill("Печать восстановлена.");
  await expect(dialog.getByText("Для решения также требуются:", { exact: true })).toBeVisible();
  await dialog.getByRole("button", { name: "Доказательство решения", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByTestId("simple-support-workspace")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Разделы правой панели" }).getByRole("button", { name: "Паспорт", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("link", { name: "Открыть паспорт", exact: true })).toBeVisible();
  expect(commands).toBe(0);
});

for (const width of [1366, 1920, 390]) {
  test(`long public result expands without horizontal overflow at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 768 });
    const errors: string[] = []; const failures: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    page.on("requestfailed", request => failures.push(new URL(request.url()).pathname));
    const result = `${"Печать проверена: тестовый документ отправлен и получен без ошибок.\n".repeat(30)}Последняя проверка: сотрудник получил все страницы.`;
    await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
    await page.route("**/api/web/support/tickets/ticket-1/timeline?*", route => route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", filter: "all", items: [], total: 0, limit: 200 } } }));
    await page.route("**/api/web/support/tickets/ticket-1/workspace", async route => {
      const response = await route.fetch(); const payload = await response.json(); const detail = payload.data.detail;
      detail.ticket.status = "closed"; detail.ticket.status_label = "Закрыта"; detail.ticket.assignee_id = "support";
      detail.ticket.requester_resolution_summary = result;
      detail.ticket.resolution_summary = "Внутренний итог не должен подменять публичный.";
      detail.actions.can_resolve_and_close = false; detail.actions.status_options = []; detail.actions.take_in_work = { allowed: false };
      await route.fulfill({ response, json: payload });
    });
    await login(page);
    await page.getByRole("row", { name: /T-200001/ }).getByRole("button", { name: "T-200001", exact: true }).click();
    const summary = await openContext(page);
    const expand = summary.getByRole("button", { name: "Показать результат полностью", exact: true });
    await expect(expand).toHaveAttribute("aria-expanded", "false");
    const resultId = await expand.getAttribute("aria-controls");
    expect(resultId).toBeTruthy();
    const text = page.locator(`[id="${resultId}"]`);
    await expect(text).toHaveText(result);
    const collapsedHeight = (await text.boundingBox())!.height;
    await expand.click();
    await expect(summary.getByRole("button", { name: "Свернуть результат", exact: true })).toHaveAttribute("aria-expanded", "true");
    await expect(text).toHaveAttribute("data-expanded", "true");
    const expandedHeight = (await text.boundingBox())!.height;
    expect(expandedHeight).toBeGreaterThan(collapsedHeight);
    expect(expandedHeight).toBeLessThanOrEqual((width === 1920 ? 1080 : 768) * 0.28 + 1);
    await text.focus(); await text.press("Control+End");
    await expect.poll(() => text.evaluate(element => element.scrollTop + element.clientHeight >= element.scrollHeight - 1)).toBe(true);
    await expect(summary.getByText("Внутренний итог не должен подменять публичный.", { exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath(`public-result-expanded-${width}.png`), fullPage: true });
    await summary.getByRole("button", { name: "Свернуть результат", exact: true }).click();
    await expect(text).toHaveAttribute("data-expanded", "false");
    expect(errors).toEqual([]); expect(failures).toEqual([]);
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
  await expect(page.getByRole("columnheader",{name:"Действие",exact:true})).toHaveCount(0);
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
