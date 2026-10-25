import { expect, test, type Page, type Route } from "playwright/test";

async function prepareWorkspace(page: Page) {
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/support/tickets/*/timeline?*", route => route.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", filter: "all", items: [], total: 0, limit: 200 } } }));
  await page.route("**/api/web/support/tickets/*/workspace", async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.data.detail.ticket.status = "in_progress";
    payload.data.detail.ticket.assignee_id = "support";
    payload.data.detail.actions.can_send_public_message = true;
    await route.fulfill({ response, json: payload });
  });
  await page.goto("/app/login");
  await page.getByLabel("Логин").fill("support");
  await page.getByLabel("Пароль").fill("secret");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).not.toHaveURL(/\/app\/login/);
  await page.goto("/app/tickets/ticket-1?advanced=1");
  await expect(page.getByTestId("support-reply-composer")).toBeVisible();
}

function pendingRoute() {
  let capture!: (route: Route) => void;
  const request = new Promise<Route>(resolve => { capture = resolve; });
  return { request, capture: (route: Route) => capture(route) };
}

async function openSecondTicket(page: Page) {
  const workspaceReady = page.waitForResponse(response =>
    new URL(response.url()).pathname === "/api/web/support/tickets/ticket-2/workspace" && response.ok());
  await page.getByRole("button", { name: /T-200002.*Нужно уточнить статус печати/ }).click();
  await expect(page).toHaveURL(/\/app\/tickets\/ticket-2/);
  await workspaceReady;
  // Navigation updates the URL before the selected-ticket effect clears the old
  // composer. Wait for the new detail, rather than the previous textarea.
  await expect(page.getByRole("heading", { name: "T-200002 Нужно уточнить статус печати", exact: true })).toBeVisible();
  await expect(page.getByTestId("support-reply-composer")).toBeVisible();
}

for (const width of [1366, 1920]) {
  test(`late upload stays isolated from the next ticket at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1366 ? 768 : 1080 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    await prepareWorkspace(page);
    const upload = pendingRoute();
    await page.route("**/api/upload", upload.capture);
    await page.locator('input[type="file"]').setInputFiles({ name: "ticket-one.txt", mimeType: "text/plain", buffer: Buffer.from("ticket one") });
    const heldUpload = await upload.request;
    await openSecondTicket(page);
    await page.getByTestId("support-reply-composer").fill("Ответ для второго обращения");
    await heldUpload.fulfill({ json: { status: "success", artifact_id: "artifact-ticket-one", filename: "ticket-one.txt", name: "ticket-one.txt", url: "/api/artifacts/one/download", size: 10, sha256: "fixture", mime_type: "text/plain", kind: "file" } });
    const send = page.waitForRequest(request => request.url().endsWith("/tickets/ticket-2/messages"));
    await page.getByRole("button", { name: "Отправить", exact: true }).click();
    expect((await send).postDataJSON()).toMatchObject({ text: "Ответ для второго обращения", visibility: "public", attachment_refs: [] });
    await expect(page.getByTestId("support-reply-composer")).toHaveValue("");
    await expect(page.getByText("ticket-one.txt", { exact: true })).toHaveCount(0);
    await page.screenshot({ path: info.outputPath(`late-upload-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
  });

  test(`completed send preserves the next ticket's draft at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1366 ? 768 : 1080 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    await prepareWorkspace(page);
    const send = pendingRoute();
    await page.route("**/api/web/support/tickets/ticket-1/messages", send.capture);
    await page.getByTestId("support-reply-composer").fill("Ответ для первого обращения");
    await page.getByRole("button", { name: "Отправить", exact: true }).click();
    const heldSend = await send.request;
    await openSecondTicket(page);
    await page.getByTestId("support-reply-composer").fill("Черновик второго обращения");
    await heldSend.fulfill({ json: { status: "success", data: { ticket_id: "ticket-1", message: {} } } });
    await expect(page.getByRole("button", { name: "Отправить", exact: true })).toBeEnabled();
    await expect(page.getByTestId("support-reply-composer")).toHaveValue("Черновик второго обращения");
    await page.screenshot({ path: info.outputPath(`late-send-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
  });
}
