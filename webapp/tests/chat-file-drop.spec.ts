import { expect, test, type Page } from "playwright/test";

type Actor = "requester" | "support";
async function fixture(page: Page, actor: Actor, rejectFile = false) {
  const login = actor === "requester" ? "fixture.requester" : "support";
  await page.addInitScript((user) => localStorage.setItem(`helpdesk-notification-intro-v1:${user}`, "1"), login);
  const uploads: string[] = []; const sent: Record<string, unknown>[] = []; const messages: Record<string, unknown>[] = [];
  const attachments = new Map<string, Record<string, unknown>>();
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({json: {status: "ok", unread_count: 0}}));
  await page.route("**/api/upload", async route => {
    const body = route.request().postDataBuffer()!.toString("utf8");
    const name = /filename="([^"]+)"/.exec(body)?.[1] || "file";
    uploads.push(name);
    expect(body).toContain(actor === "support" ? "ticket-1" : "requester-ticket");
    if (rejectFile && name === "bad.txt") return route.fulfill({status: 500, json: {status: "error", error: "Не удалось прикрепить файл", error_code: "UPLOAD_FAILED"}});
    const id = `drop-${uploads.length}`;
    const item = {artifact_id: id, filename: name, name, url: `/api/artifacts/${id}/download`, mime_type: name.endsWith(".png") ? "image/png" : "text/plain", kind: name.endsWith(".png") ? "screenshot" : "file", size: 4, sha256: "fixture"};
    attachments.set(id, item);
    await route.fulfill({json: {status: "success", ...item}});
  });
  await page.route("**/api/artifacts/drop-*/download", route => route.fulfill({contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAEAAAAAgCAIAAAAt/+nTAAAAT0lEQVR4nNXOMREAIBDAsNIJd9hBPiJ+4BoFWfseyiRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4vwdmHqdZQEPa89hlQAAAABJRU5ErkJggg==", "base64")}));
  const record = async (route: import("playwright/test").Route) => {
    const body = route.request().postDataJSON(); sent.push(body);
    const message = {event_id: `sent-${sent.length}`, message_id: `sent-${sent.length}`, event_type: "chat_message", visibility: body.visibility || "public", from_role: actor === "support" ? "support" : "user", text: body.text, ts: "2026-11-05T10:00:00Z", attachments: body.attachment_refs.map((id: string) => attachments.get(id))};
    messages.push(message);
    await route.fulfill({json: {status: "success", data: {ticket_id: actor === "support" ? "ticket-1" : "requester-ticket", message}}});
  };
  if (actor === "requester") {
    await page.route("**/api/web/session/me", route => route.fulfill({json: {status: "success", data: {user_login: "fixture.requester", actor_role: "user", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"]}}}));
    await page.route("**/api/web/requester/bootstrap", route => route.fulfill({json: {status: "success", data: {profile_completion: {complete: true}, devices: [], recent_tickets: [], feature_flags: {}}}}));
    await page.route("**/api/web/requester/consents**", route => route.fulfill({json: {status: "success", data: {consents: []}}}));
    await page.route("**/api/web/requester/tickets/T-009999", route => route.fulfill({json: {status: "success", data: {ticket: {ticket_id: "requester-ticket", ticket_code: "T-009999", title: "Тест вложений", status: "in_progress", requester_status_label: "В работе", actions: {can_send_message: true, can_attach_files: true}}, messages, events: []}}}));
    await page.route("**/api/web/requester/tickets/T-009999/message", record);
    await page.goto("/app/requester/tickets/T-009999");
  } else {
    await page.route("**/api/web/support/tickets/ticket-1/workspace", async route => {
      const response = await route.fetch(); const payload = await response.json(); const detail = payload.data.detail;
      detail.ticket.status = "in_progress"; detail.ticket.status_label = "В работе"; detail.ticket.assignee_id = "support";
      detail.actions.can_send_public_message = true; detail.actions.can_send_internal_note = true;
      await route.fulfill({response, json: payload});
    });
    await page.route("**/api/web/support/tickets/ticket-1/timeline?*", route => route.fulfill({json: {status: "success", data: {ticket_id: "ticket-1", items: messages, total: messages.length, limit: 200}}}));
    await page.route("**/api/web/support/tickets/ticket-1/messages", record);
    await page.goto("/app/login?next=/app/tickets");
    await page.getByLabel("Логин").fill("support"); await page.getByLabel("Пароль").fill("secret"); await page.getByRole("button", {name: "Войти", exact: true}).click();
    await expect(page.getByRole("heading", {name: "Очередь обращений", exact: true})).toBeVisible();
    await page.goto("/app/tickets/ticket-1");
  }
  return {uploads, sent, messages};
}
async function drag(page: Page, actor: Actor, names: string[]) {
  const target = page.getByRole("region", {name: actor === "requester" ? "Чат обращения" : "Переписка обращения", exact: true});
  const dataTransfer = await page.evaluateHandle(names => {
    const data = new DataTransfer();
    names.forEach(name => data.items.add(new File(["test bytes"], name, {type: name.endsWith(".png") ? "image/png" : "text/plain"})));
    return data;
  }, names);
  await target.dispatchEvent("dragenter", {dataTransfer});
  await expect(page.getByText("Отпустите файлы, чтобы прикрепить к сообщению")).toBeVisible();
  await target.dispatchEvent("drop", {dataTransfer});
  await dataTransfer.dispose();
}

for (const actor of ["requester", "support"] as const) {
  for (const width of [1366, 1920, 390]) {
    test(`${actor} groups dropped image and file with text at ${width}`, async ({page}, info) => {
      await page.setViewportSize({width, height: width === 1920 ? 1080 : width === 390 ? 844 : 768});
      const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => {if (message.type() === "error") errors.push(message.text());});
      page.on("response", response => {if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`);});
      const state = await fixture(page, actor);
      const reply = page.getByRole("textbox", {name: actor === "requester" ? "Ответ заявителя" : "Сообщение сотруднику"});
      await expect(reply).toBeEnabled(); await reply.fill("Скриншот и журнал одной проблемы");
      await drag(page, actor, ["shot.png", "log.txt"]);
      const group = page.getByRole("region", {name: "Вложения к сообщению"});
      await expect(group.getByText("Будут отправлены вместе с текстом")).toBeVisible();
      await expect(group.getByRole("button", {name: "Открыть изображение shot.png"})).toBeVisible();
      await page.locator('input[type="file"]').setInputFiles({name: "remove.txt", mimeType: "text/plain", buffer: Buffer.from("remove")});
      await expect(group.getByRole("button", {name: "Убрать вложение remove.txt"})).toBeVisible();
      await group.getByRole("button", {name: "Убрать вложение remove.txt"}).click();
      await expect(group.getByRole("button", {name: "Убрать вложение remove.txt"})).toHaveCount(0);
      const send = page.getByRole("button", {name: "Отправить", exact: true});
      await expect(send).toBeInViewport();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({path: info.outputPath(`grouped-draft-${actor}-${width}.png`)});
      await send.click(); await expect(group).toHaveCount(0); await expect(reply).toHaveValue("");
      expect(state.sent).toHaveLength(1);
      expect(state.sent[0]).toMatchObject({text: "Скриншот и журнал одной проблемы", attachment_refs: ["drop-1", "drop-2"]});
      expect(state.messages).toHaveLength(1);
      const bubble = page.getByText("Скриншот и журнал одной проблемы", {exact: true}).locator("..");
      await expect(bubble.getByRole("button", {name: "Открыть изображение shot.png"})).toBeVisible();
      await expect(bubble.getByRole("link", {name: "log.txt"})).toBeVisible();
      await page.screenshot({path: info.outputPath(`grouped-message-${actor}-${width}.png`)});
      expect(errors).toEqual([]);
    });
  }
  test(`${actor} keeps successful files and text after a partial upload failure`, async ({page}) => {
    const state = await fixture(page, actor, true);
    const reply = page.getByRole("textbox", {name: actor === "requester" ? "Ответ заявителя" : "Сообщение сотруднику"});
    await expect(reply).toBeEnabled(); await reply.fill("Черновик остаётся");
    await drag(page, actor, ["one.txt", "bad.txt", "two.txt"]);
    await expect(page.getByText(/bad.txt:/).first()).toBeVisible();
    const group = page.getByRole("region", {name: "Вложения к сообщению"});
    await expect(group.getByText("Будут отправлены вместе с текстом")).toBeVisible();
    await expect(group.getByRole("link", {name: "one.txt"})).toBeVisible();
    await expect(group.getByRole("link", {name: "two.txt"})).toBeVisible();
    await expect(reply).toHaveValue("Черновик остаётся"); expect(state.sent).toHaveLength(0);
    expect(state.uploads).toEqual(["one.txt", "bad.txt", "two.txt"]);
  });
  test(`${actor} queues another drop while uploading and blocks premature send`, async ({page}) => {
    const state = await fixture(page, actor);
    let release!: () => void; const wait = new Promise<void>(resolve => {release = resolve;}); let first = true;
    await page.route("**/api/upload", async route => {if (first) {first = false; await wait;} await route.fallback();});
    const reply = page.getByRole("textbox", {name: actor === "requester" ? "Ответ заявителя" : "Сообщение сотруднику"});
    await reply.fill("Очередь вложений"); await drag(page, actor, ["slow.png"]);
    await expect(page.getByRole("button", {name: "Отправить", exact: true})).toBeDisabled();
    await drag(page, actor, ["later.txt"]); expect(state.sent).toHaveLength(0);
    release();
    const group = page.getByRole("region", {name: "Вложения к сообщению"});
    await expect(group.getByText("Будут отправлены вместе с текстом")).toBeVisible();
    await reply.press("Control+Enter"); await expect(reply).toHaveValue("");
    expect(state.sent).toHaveLength(1); expect(state.sent[0].attachment_refs).toEqual(["drop-1", "drop-2"]);
  });
}

test("support keeps private file drafts separate from the public reply", async ({page}) => {
  const state = await fixture(page, "support");
  const reply = page.getByRole("textbox", {name: "Сообщение сотруднику"});
  await reply.fill("Публичный черновик");
  await page.getByRole("tab", {name: "Внутренние заметки", exact: true}).click();
  await page.getByRole("textbox", {name: "Внутренняя заметка", exact: true}).fill("Внутренний черновик");
  await drag(page, "support", ["private.png"]);
  await expect(page.getByText("Будут отправлены вместе с текстом")).toBeVisible();
  await page.getByRole("tab", {name: "Диалог", exact: true}).click();
  await expect(reply).toHaveValue("Публичный черновик");
  await expect(page.getByRole("region", {name: "Вложения к сообщению"})).toHaveCount(0);
  await page.getByRole("tab", {name: "Внутренние заметки", exact: true}).click();
  await expect(page.getByRole("button", {name: "Открыть изображение private.png"})).toBeVisible();
  await page.getByRole("button", {name: "Отправить", exact: true}).click();
  await expect(page.getByRole("textbox", {name: "Внутренняя заметка", exact: true})).toHaveValue("");
  expect(state.sent).toHaveLength(1); expect(state.sent[0]).toMatchObject({visibility: "internal", text: "Внутренний черновик", attachment_refs: ["drop-1"]});
});

async function copyScreenshot(page: Page) {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.evaluate(async () => {
    const bytes = Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAEAAAAAgCAIAAAAt/+nTAAAAT0lEQVR4nNXOMREAIBDAsNIJd9hBPiJ+4BoFWfseyiRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4vwdmHqdZQEPa89hlQAAAABJRU5ErkJggg=="), char => char.charCodeAt(0));
    await navigator.clipboard.write([new ClipboardItem({"image/png": new Blob([bytes], {type: "image/png"})})]);
  });
}
for (const actor of ["requester", "support"] as const) {
  for (const width of [1366, 390]) {
    test(`${actor} pastes a screenshot with Ctrl+V and sends it with text at ${width}`, async ({page}, info) => {
      await page.setViewportSize({width, height: width === 390 ? 844 : 768});
      const errors: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => {if (message.type() === "error") errors.push(message.text());});
      page.on("response", response => {if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`);});
      const state = await fixture(page, actor);
      const reply = page.getByRole("textbox", {name: actor === "requester" ? "Ответ заявителя" : "Сообщение сотруднику"});
      await reply.fill("Описание ошибки: ");
      await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
      await page.evaluate(() => navigator.clipboard.writeText("обычный текст"));
      await reply.press("Control+v");
      await expect(reply).toHaveValue("Описание ошибки: обычный текст");
      expect(state.uploads).toHaveLength(0);
      await copyScreenshot(page); await reply.press("Control+v");
      const group = page.getByRole("region", {name: "Вложения к сообщению"});
      await expect(group.getByText("Будут отправлены вместе с текстом")).toBeVisible();
      await expect(group.getByRole("button", {name: /^Открыть изображение/})).toHaveCount(1);
      await expect(reply).toHaveValue("Описание ошибки: обычный текст");
      expect(state.uploads).toHaveLength(1); expect(state.sent).toHaveLength(0);
      await reply.press("Control+v");
      await expect(group.getByRole("button", {name: /^Открыть изображение/})).toHaveCount(2);
      await expect(group.getByText("Будут отправлены вместе с текстом")).toBeVisible();
      expect(state.uploads).toHaveLength(2);
      const send = page.getByRole("button", {name: "Отправить", exact: true});
      await expect(send).toBeInViewport();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({path: info.outputPath(`clipboard-draft-${actor}-${width}.png`)});
      await send.click(); await expect(reply).toHaveValue("");
      expect(state.sent).toHaveLength(1);
      expect(state.sent[0]).toMatchObject({text: "Описание ошибки: обычный текст", attachment_refs: ["drop-1", "drop-2"]});
      await expect(group).toHaveCount(0);
      expect(errors).toEqual([]);
    });
  }
}
test("support clipboard screenshot stays in the internal note draft", async ({page}) => {
  const state = await fixture(page, "support");
  await page.getByRole("tab", {name: "Внутренние заметки", exact: true}).click();
  const note = page.getByRole("textbox", {name: "Внутренняя заметка", exact: true});
  await note.fill("Приватное описание");
  await copyScreenshot(page); await note.press("Control+v");
  await expect(page.getByText("Будут отправлены вместе с текстом")).toBeVisible();
  await page.getByRole("tab", {name: "Диалог", exact: true}).click();
  await expect(page.getByRole("region", {name: "Вложения к сообщению"})).toHaveCount(0);
  await page.getByRole("tab", {name: "Внутренние заметки", exact: true}).click();
  await expect(note).toHaveValue("Приватное описание");
  await page.getByRole("button", {name: "Отправить", exact: true}).click();
  await expect(note).toHaveValue("");
  expect(state.sent).toHaveLength(1);
  expect(state.sent[0]).toMatchObject({visibility: "internal", text: "Приватное описание", attachment_refs: ["drop-1"]});
});
