import { expect, type Page, test } from "playwright/test";
import { writeFile } from "node:fs/promises";

const humanText = "Профиль не синхронизируется: сообщение пользователя.";
const internalText = "Внутренняя заметка fixture: проверяю настройки.";
const systemText = "Системная запись fixture: обращение создано автоматически.";
const diagnosticText = "Диагностика fixture: проверка завершена.";
const timeline = [
  { message_id: "fixture-human", event_id: 801, event_type: "chat_message", from_role: "user", sender_display_name: "Алексей", text: humanText },
  { message_id: "fixture-system", event_id: 802, event_type: "chat_message", from_role: "system", sender_display_name: "Система", text: systemText },
  { message_id: "fixture-diagnostic", event_id: 803, event_type: "tool_call_result", from_role: "system", sender_display_name: "Диагностика", text: diagnosticText, tool_name: "fixture check", tool_status: "succeeded" },
  { message_id: "fixture-internal", event_id: 804, event_type: "chat_message", from_role: "support", sender_display_name: "Поддержка", text: internalText, visibility: "internal" },
].map(item => ({ visibility: "public", ...item, ts: "2026-04-20T08:11:00+05:00", direction: "to_agent", attachments: [] }));

async function prepareSupport(page: Page) {
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/support/tickets/*/timeline?*", route => {
    const filter = new URL(route.request().url()).searchParams.get("filter") ?? "all";
    const items = filter === "messages" ? timeline.filter(item => item.event_type === "chat_message" && item.visibility !== "internal")
      : filter === "internal" ? timeline.filter(item => item.visibility === "internal") : timeline;
    return route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", filter, items } } });
  });
  await page.route("**/api/web/support/tickets/*/read", route => route.fulfill({ json: { status: "success", data: { last_read_event_id: 803 } } }));
  await page.route("**/api/web/support/tickets/ticket-1/workspace*", async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.data.detail.timeline = timeline;
    await route.fulfill({ response, json: payload });
  });
  await page.addInitScript(() => localStorage.setItem("support-workspace-last-mode", "queue"));
  await page.goto("/app/login");
  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).not.toHaveURL(/\/app\/login/);
  await expect(page.getByRole("heading", { name: "Центр действий", exact: true })).toBeVisible();
}

async function noBodyOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(2);
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }, { width: 2569, height: 1292 }]) {
  test(`ticket queue navigation, primary actions and context at ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [], failures: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    page.on("requestfailed", request => failures.push(request.url()));
    await prepareSupport(page);

    // A direct card URL takes precedence over the last persisted queue mode.
    await page.goto("/app/tickets/ticket-1");
    const workspace = page.getByTestId("support-workspace-root");
    await expect(workspace).toHaveAttribute("data-mode", "ticket");
    await expect(workspace.getByRole("heading", { name: /T-200001 Ошибка синхронизации/ })).toBeVisible();
    await workspace.getByRole("link", { name: "Все тикеты", exact: true }).click();
    await expect(page).toHaveURL(/\/app\/tickets$/);
    await expect(workspace).toHaveAttribute("data-mode", "queue");

    const queue = page.getByRole("heading", { name: "Очередь тикетов", exact: true }).locator("xpath=ancestor::section[1]");
    const table = queue.getByRole("table");
    await expect(table.getByRole("row").filter({ hasText: "T-200001" })).toBeVisible();
    const workspaceBox = await workspace.boundingBox(), queueBox = await queue.boundingBox();
    expect(queueBox!.width).toBeGreaterThan(workspaceBox!.width * 0.92);
    expect((await workspace.getByTestId("support-command-strip").boundingBox())!.height).toBeLessThan(120);
    expect((await table.boundingBox())!.height).toBeGreaterThan(100);
    expect((await table.locator("..").boundingBox())!.height).toBeGreaterThan(120);
    const queueMetrics = await page.evaluate(() => {
      const root = document.querySelector('[data-testid="support-workspace-root"]')!;
      const table = root.querySelector("table")!;
      return { scrollY, scrollHeight: document.documentElement.scrollHeight, clientHeight: document.documentElement.clientHeight,
        root: root.getBoundingClientRect().toJSON(), table: table.getBoundingClientRect().toJSON(),
        tableContainer: table.parentElement!.getBoundingClientRect().toJSON(),
        commandStrip: root.querySelector('[data-testid="support-command-strip"]')!.getBoundingClientRect().toJSON() };
    });
    const metricsPath = info.outputPath(`queue-metrics-${viewport.width}.json`);
    await writeFile(metricsPath, JSON.stringify(queueMetrics, null, 2));
    await info.attach(`queue-metrics-${viewport.width}`, { path: metricsPath, contentType: "application/json" });
    await noBodyOverflow(page);
    await page.screenshot({ path: info.outputPath(`queue-${viewport.width}.png`) });

    await table.getByRole("row").filter({ hasText: "T-200001" }).click();
    await expect(page).toHaveURL(/\/app\/tickets\/ticket-1$/);
    await expect(workspace).toHaveAttribute("data-mode", "ticket");
    await page.goBack();
    await expect(page).toHaveURL(/\/app\/tickets$/);
    await expect(workspace).toHaveAttribute("data-mode", "queue");
    await page.goForward();
    await expect(workspace).toHaveAttribute("data-mode", "ticket");

    const composer = page.getByLabel("Сообщение в тикет", { exact: true });
    await expect(composer).toBeInViewport({ ratio: 1 });
    await composer.fill("Только черновик fixture, без отправки.");
    for (const label of ["Взять себе", "Сменить статус", "Отправить"]) {
      const action = workspace.getByRole("button", { name: label, exact: true });
      await expect(action).toBeInViewport({ ratio: 1 });
      await expect(action).toBeEnabled();
    }
    await expect(workspace.getByTestId("closure-plan-panel")).toHaveCount(0);
    const conversation = workspace.getByRole("region", { name: "Переписка", exact: true });
    await expect(conversation.getByText(humanText, { exact: true })).toBeVisible();
    await expect(conversation.getByText(internalText, { exact: true })).toBeVisible();
    await expect(conversation.getByText(systemText, { exact: true })).toHaveCount(0);
    await expect(conversation.getByText(diagnosticText, { exact: true })).toHaveCount(0);
    await noBodyOverflow(page);
    await page.screenshot({ path: info.outputPath(`card-${viewport.width}.png`) });

    await workspace.getByRole("button", { name: "Ещё", exact: true }).click();
    await workspace.getByRole("button", { name: "Требования к закрытию", exact: true }).click();
    const requirements = workspace.getByTestId("closure-plan-panel");
    await requirements.scrollIntoViewIfNeeded();
    await expect(requirements).toBeVisible();
    await workspace.getByRole("button", { name: "Ещё", exact: true }).click();
    await workspace.getByRole("button", { name: "Требования к закрытию", exact: true }).click();
    await expect(requirements).toHaveCount(0);
    await conversation.getByRole("button", { name: "Открыть контекст", exact: true }).click();
    const context = workspace.getByRole("region", { name: "Системные события", exact: true });
    await context.getByText(systemText, { exact: true }).scrollIntoViewIfNeeded();
    await expect(context.getByText(systemText, { exact: true })).toBeVisible();
    await expect(context.getByText(diagnosticText, { exact: true })).toBeVisible();
    await noBodyOverflow(page);
    await page.screenshot({ path: info.outputPath(`context-${viewport.width}.png`) });
    expect(errors).toEqual([]);
    expect(failures).toEqual([]);
  });
}

test("requester reply keeps its draft after refusal and sends the explicit retry", async ({ page }, info) => {
  const errors: string[] = [], failures: string[] = [], sent: unknown[] = [];
  const requesterSystemText = "Системная запись fixture: безопасное уведомление заявителю.";
  const requesterHumanText = "Сообщение заявителя fixture в переписке.";
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && !message.text().includes("403 (Forbidden)")) errors.push(message.text()); });
  page.on("response", response => { if (response.status() >= 400 && !(response.status() === 403 && response.url().endsWith("/message"))) failures.push(response.url()); });
  page.on("requestfailed", request => failures.push(request.url()));
  await page.route("**/api/web/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = {};
    if (path.endsWith("/session/me")) data = { user_login: "owner-admin", actor_role: "admin", auth_type: "web_session", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
    else if (path.endsWith("/requester/bootstrap")) data = { profile: { person_id: "own-person", display_name: "Заявитель" }, devices: [], profile_completion: { complete: true, blocks: {} } };
    else if (path.endsWith("/requester/consents")) data = { consents: [] };
    else if (path.endsWith("/unread_count")) return route.fulfill({ json: { status: "ok", unread_count: 0 } });
    else if (path.endsWith("/requester/tickets/owned-fixture/message")) {
      sent.push(route.request().postDataJSON());
      if (sent.length === 1) return route.fulfill({ status: 403, json: { status: "error", error_code: "FORBIDDEN" } });
      data = { message_id: "reply-fixture", event_id: 2 };
    } else if (path.endsWith("/requester/tickets/owned-fixture")) data = {
      ticket: { ticket_id: "owned-fixture", ticket_code: "T-FIXTURE", title: "Проверка ответа", status: "waiting_on_user", actions: { can_send_message: true, can_attach_files: false } },
      messages: [
        { from_role: "user", event_id: 8, message_id: "human-8", text: requesterHumanText },
        { from_role: "system", event_id: "9", message_id: "system-9", text: requesterSystemText },
      ],
      events: [{ event_id: 9, requester_timeline_kind: "system_event", requester_timeline_text: requesterSystemText }],
    };
    await route.fulfill({ json: { status: "success", data } });
  });
  await page.goto("/app/requester/tickets/owned-fixture");
  const conversation = page.getByRole("heading", { name: "Переписка", exact: true }).locator("..");
  await expect(conversation.getByText(requesterHumanText, { exact: true })).toBeVisible();
  await expect(conversation.getByText(requesterSystemText, { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Описание и история", exact: true }).click();
  const history = page.getByRole("list", { name: "История обращения", exact: true });
  await expect(history.getByText(requesterSystemText, { exact: true })).toHaveCount(1);
  await expect(history.getByText(requesterSystemText, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Вернуться к чату", exact: true }).click();
  await expect(conversation.getByText(requesterHumanText, { exact: true })).toBeVisible();
  const reply = page.getByLabel("Ответ заявителя", { exact: true });
  await reply.fill("Привет");
  await page.getByRole("button", { name: "Отправить", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Это действие недоступно для вашего аккаунта.");
  await expect(reply).toHaveValue("Привет");
  await expect(page.getByRole("button", { name: "Отправить", exact: true })).toBeEnabled();
  await page.screenshot({ path: info.outputPath("requester-reply-retained.png") });
  await page.getByRole("button", { name: "Отправить", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Ответ отправлен");
  await expect(reply).toHaveValue("");
  expect(sent).toEqual([{ text: "Привет" }, { text: "Привет" }]);
  expect(errors).toEqual([]);
  expect(failures).toEqual([]);
});
