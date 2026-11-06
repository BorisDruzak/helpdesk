import { expect, test } from "playwright/test";
// The headless shell denies OS notifications; full Chromium supports this API.
test.use({ channel: "chromium" });

const events = [
  { id: 901, ticket_id: "ticket-1", event_type: "chat_message", title: "Новое сообщение по обращению T-000077", body: "Откройте обращение, чтобы посмотреть подробности.", url: "/app/tickets/ticket-1", is_read: false, created_at: "2026-11-06T07:00:00Z" },
  { id: 902, ticket_id: "ticket-1", event_type: "status_changed", title: "Изменён статус обращения T-000077", body: "В работе", url: "/app/tickets/ticket-1", is_read: false, created_at: "2026-11-06T07:01:00Z" },
];

for (const width of [1366, 1920, 390]) {
  test(`bell shows events and reads an individual item at ${width}`, async ({ page, context }, info) => {
    const errors: string[] = [], failures: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/web/support/tickets/ticket-1/timeline**", route => route.fulfill({ json: { status: "success", data: { events: [], timeline: [], next_cursor: null } } }));
    await page.route("**/api/web/support/tickets/ticket-1/read", route => route.fulfill({ json: { status: "success", data: {} } }));
    await context.request.post("/__fixtures/notifications", { data: { notifications: events } });
    await context.request.post("/api/web/session/login", { data: { login: "support", password: "secret" } });
    await page.goto("/app/tickets");
    await page.getByRole("button", { name: "Уведомления", exact: true }).click();
    await expect(page.getByText(events[0].title)).toBeVisible();
    await expect(page.getByText(events[1].title)).toBeVisible();
    const bounds = await page.getByRole("dialog", { name: "События обращений" }).boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    await page.screenshot({ path: info.outputPath(`bell-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole("link", { name: /Новое сообщение по обращению/ }).click();
    await expect.poll(async () => (await (await context.request.get("/__fixtures/notifications")).json()).notifications[0].is_read).toBe(true);
    await expect(page).toHaveURL(/\/app\/tickets\/ticket-1$/);
    expect(errors).toEqual([]); expect(failures).toEqual([]);
  });
}

test("registered worker shows both event types after the tab closes, deduplicates and blocks another account", async ({ page, context, baseURL }, info) => {
  await context.grantPermissions(["notifications"], { origin: baseURL });
  await context.request.post("/__fixtures/notifications", { data: { notifications: events } });
  await context.request.post("/api/web/session/login", { data: { login: "support", password: "secret" } });
  await page.goto("/app/tickets");
  expect(await page.evaluate(() => Notification.permission)).toBe("granted");
  const anchor = await context.newPage();
  const cdp = await context.newCDPSession(anchor);
  let registrationId = "";
  cdp.on("ServiceWorker.workerRegistrationUpdated", (event: { registrations: { scopeURL: string; registrationId: string }[] }) => {
    registrationId = event.registrations.find(item => item.scopeURL === `${baseURL}/`)?.registrationId ?? registrationId;
  });
  await cdp.send("ServiceWorker.enable");
  const workerPromise = context.waitForEvent("serviceworker");
  await page.evaluate(async () => { await navigator.serviceWorker.register("/helpdesk-notifications-sw.js", { scope: "/" }); await navigator.serviceWorker.ready; });
  const worker = await workerPromise;
  await worker.evaluate(() => {
    const fake = { endpoint: "https://fcm.googleapis.com/fcm/send/synthetic-browser", unsubscribe: async () => true };
    Object.defineProperty(ServiceWorkerRegistration.prototype, "pushManager", { configurable: true, get: () => ({ getSubscription: async () => fake }) });
  });
  await context.request.post("/api/web/notifications/push/subscribe", { data: { endpoint: "https://fcm.googleapis.com/fcm/send/synthetic-browser" } });
  await expect.poll(() => registrationId).not.toBe("");
  await page.close();
  expect(context.pages().every(item => !item.url().includes("/app"))).toBe(true);
  await cdp.send("ServiceWorker.deliverPushMessage", { origin: baseURL!, registrationId, data: "" });
  await expect.poll(async () => worker.evaluate(async () => (await self.registration.getNotifications()).length)).toBe(2);
  const displayed = await worker.evaluate(async () => (await self.registration.getNotifications()).map(item => ({ title: item.title, body: item.body, tag: item.tag })));
  expect(displayed.map(item => item.title).sort()).toEqual(events.map(item => item.title).sort());
  await cdp.send("ServiceWorker.deliverPushMessage", { origin: baseURL!, registrationId, data: "" });
  await expect.poll(async () => (await (await context.request.get("/__fixtures/notifications")).json()).shown.length).toBe(4);
  expect(await worker.evaluate(async () => (await self.registration.getNotifications()).length)).toBe(2);
  await context.request.post("/api/web/session/login", { data: { login: "admin", password: "secret" } });
  await worker.evaluate(async () => { (await self.registration.getNotifications()).forEach(item => item.close()); });
  await context.request.post("/__fixtures/notifications", { data: { notifications: [{ ...events[0], id: 903 }] } });
  await context.request.post("/api/web/notifications/push/subscribe", { data: { endpoint: "https://fcm.googleapis.com/fcm/send/synthetic-browser" } });
  await cdp.send("ServiceWorker.deliverPushMessage", { origin: baseURL!, registrationId, data: "" });
  // A real suspend message drains the worker before the negative assertion.
  // Keep this page outside the Helpdesk app, so the original tab remains closed.
  await anchor.goto(`${baseURL}/__fixtures/notifications`);
  await anchor.evaluate(async () => {
    const registration = await navigator.serviceWorker.getRegistration("/");
    await new Promise<void>(resolve => {
      const channel = new MessageChannel();
      channel.port1.onmessage = () => { channel.port1.close(); resolve(); };
      registration!.active!.postMessage({ type: "helpdesk-notifications-suspend" }, [channel.port2]);
    });
  });
  await expect.poll(async () => worker.evaluate(async () => (await self.registration.getNotifications()).length)).toBe(0);
  await info.attach("closed-tab-notifications.json", { body: JSON.stringify({ displayed, transport: "CDP synthetic push; no external provider contacted", account_switch_blocked: true }), contentType: "application/json" });
  await anchor.close();
});

test("browser opt-in and opt-out are explicit and update the menu", async ({ page, context, baseURL }) => {
  await context.grantPermissions(["notifications"], { origin: baseURL });
  await context.request.post("/__fixtures/notifications", { data: { notifications: [] } });
  await context.request.post("/api/web/session/login", { data: { login: "support", password: "secret" } });
  await page.addInitScript(() => {
    let subscribed = false;
    const subscription = { endpoint: "https://fcm.googleapis.com/fcm/send/synthetic-browser", options: {}, unsubscribe: async () => { subscribed = false; return true; } };
    Object.defineProperty(ServiceWorkerRegistration.prototype, "pushManager", { configurable: true, get: () => ({ getSubscription: async () => subscribed ? subscription : null, subscribe: async () => { subscribed = true; return subscription; } }) });
  });
  await page.goto("/app/tickets");
  await page.getByRole("button", { name: "Уведомления", exact: true }).click();
  await expect(page.getByText("Уведомлений пока нет")).toBeVisible();
  expect((await (await context.request.get("/__fixtures/notifications")).json()).subscribed).toBe(false);
  await page.getByRole("button", { name: "Включить уведомления в браузере", exact: true }).click();
  await expect(page.getByRole("button", { name: "Отключить уведомления в этом браузере" })).toBeVisible();
  expect((await (await context.request.get("/__fixtures/notifications")).json()).subscribed).toBe(true);
  await page.getByRole("button", { name: "Отключить уведомления в этом браузере" }).click();
  await expect(page.getByRole("button", { name: "Включить уведомления в браузере", exact: true })).toBeVisible();
  expect((await (await context.request.get("/__fixtures/notifications")).json()).subscribed).toBe(false);
});

for (const width of [1366, 390]) {
  test(`requester bell keeps its events within the viewport at ${width}`, async ({ page, context }, info) => {
    const errors: string[] = [], failures: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) failures.push(new URL(response.url()).pathname); });
    await page.setViewportSize({ width, height: 900 });
    await context.request.post("/__fixtures/notifications", { data: { notifications: events.map(item => ({ ...item, url: "/app/requester/tickets/ticket-1" })) } });
    await context.request.post("/api/web/session/login", { data: { login: "support", password: "secret" } });
    await page.route("**/api/web/session/me", route => route.fulfill({ json: { status: "success", data: { user_login: "support", actor_role: "user", auth_type: "ui_token", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] } } }));
    await page.route("**/api/web/requester/bootstrap", route => route.fulfill({ json: { status: "success", data: { workspace: "requester", profile: { display_name: "Тестовый сотрудник", full_name: "Тестовый сотрудник", department_id: "it", phone: "0000" }, profile_completion: { complete: true, blocks: {} }, devices: [], primary_device: null, feature_flags: {} } } }));
    await page.route("**/api/web/requester/tickets", route => route.fulfill({ json: { status: "success", data: { tickets: [] } } }));
    await page.goto("/app/requester/tickets");
    await expect(page.getByRole("heading", { name: "Мои обращения", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Уведомления", exact: true }).click();
    const menu = page.getByRole("dialog", { name: "События обращений" });
    await expect(menu.getByText(events[0].title)).toBeVisible();
    await expect(menu.getByText(events[1].title)).toBeVisible();
    const bounds = await menu.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    await expect(menu.getByRole("link", { name: /Новое сообщение/ })).toHaveAttribute("href", "/app/requester/tickets/ticket-1");
    await page.screenshot({ path: info.outputPath(`requester-bell-${width}.png`), fullPage: true });
    expect(errors).toEqual([]); expect(failures).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Уведомления", exact: true })).toBeFocused();
  });
}
