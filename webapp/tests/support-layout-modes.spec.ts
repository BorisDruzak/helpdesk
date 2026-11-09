import { expect, test, type Page } from "playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("helpdesk-notification-intro-v1:support", "1"));
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
  await page.route("**/api/web/problems?ticket_id=*", route => route.fulfill({ json: { status: "ok", items: [] } }));
  await page.route("**/api/web/support/tickets/*/read", route => route.fulfill({ json: { status: "success", data: { last_read_event_id: 0 } } }));
  await page.route("**/api/web/support/tickets/*/timeline?*", async route => {
    const url = new URL(route.request().url());
    const response = await route.fetch({ url: url.origin + url.pathname.replace(/\/timeline$/, "/workspace") });
    const payload = await response.json();
    await route.fulfill({ json: { status: "success", data: { items: payload.data.detail.timeline ?? [], total: payload.data.detail.timeline?.length ?? 0, limit: 200, filter: "messages" } } });
  });
});

async function login(page: Page) {
  await page.goto("/app/login?next=/app/tickets");
  await page.getByLabel("Логин", { exact: true }).fill("support");
  await page.getByLabel("Пароль", { exact: true }).fill("secret");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Очередь обращений", exact: true })).toBeVisible();
}

test("browser Back restores the queue search intent",async({page})=>{
  await login(page);
  await page.goto("/app/tickets?search=T-200001");
  const search=page.getByRole("searchbox",{name:"Поиск обращений",exact:true});
  await expect(search).toHaveValue("T-200001");
  await search.fill("T-200");
  await page.getByRole("button",{name:"T-200001",exact:true}).click();
  await expect(page).toHaveURL(/\/app\/tickets\/ticket-1$/);
  await expect(page.locator(".simple-ticket")).toBeVisible();
  await page.goBack();
  await expect(search).toHaveValue("T-200001");
});

test.describe("touch navigation",()=>{
  test.use({hasTouch:true,viewport:{width:1280,height:800}});
  test("manual expansion stays open for touch without a hover",async({page})=>{
    await login(page);
    const navigation=page.getByTestId("support-navigation");
    await expect(navigation).toHaveAttribute("data-expanded","false");
    await page.getByRole("button",{name:"Развернуть или свернуть меню",exact:true}).tap();
    await expect(navigation).toHaveAttribute("data-expanded","true");
    await page.getByRole("button",{name:"Развернуть или свернуть меню",exact:true}).tap();
    await expect(navigation).toHaveAttribute("data-expanded","false");
  });
});

for (const width of [390, 1366, 1440, 1920]) {
  test(`three queue modes retain the ticket and reply at ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : width === 1920 ? 1080 : 900 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.route("**/api/web/support/tickets/ticket-1/workspace",async route=>{
      const response=await route.fetch();const payload=await response.json();
      payload.data.detail.ticket.status="in_progress";
      payload.data.detail.ticket.status_label="В работе";
      payload.data.detail.ticket.assignee_id="support";
      payload.data.detail.actions.can_send_public_message=true;
      payload.data.detail.actions.status_options=[{value:"resolved",label:"Решить"}];
      await route.fulfill({response,json:payload});
    });
    await login(page);
    await expect(page.getByRole("button", { name: "Очередь рядом", exact: true })).toBeDisabled();
    await page.getByRole("button", { name: "T-200001", exact: true }).click();
    await expect(page.locator(".simple-ticket")).toBeVisible();
    await expect(page.getByRole("button", { name: "Свернуть очередь", exact: true })).toHaveAttribute("aria-pressed","true");
    const reply = page.getByRole("textbox", { name: "Сообщение сотруднику", exact: true });
    await expect(reply).toBeEnabled();
    await reply.fill("Черновик ответа — не отправлять");
    if (width === 1366) {
      await page.route("**/api/upload",route=>route.fulfill({json:{status:"success",artifact_id:"draft-layout",filename:"reply-draft.txt",url:"/api/artifacts/draft-layout/download",size:32,mime_type:"text/plain",kind:"file"}}));
      await page.locator(".simple-conversation input[type=file]").setInputFiles({ name:"reply-draft.txt",mimeType:"text/plain",buffer:Buffer.from("Черновик вложения") });
      await expect(page.getByText("reply-draft.txt",{exact:true})).toBeVisible();
      await page.getByRole("button",{name:"Закрепить панель",exact:true}).click();
      await page.mouse.move(900,100);
      await expect(reply).toHaveValue("Черновик ответа — не отправлять");
      await page.getByRole("button",{name:"Открепить панель",exact:true}).click();
      await page.mouse.move(900,100);
    }
    await page.getByRole("button", { name: "Полная очередь", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Очередь обращений", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Полная очередь", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page).toHaveURL(/\/app\/tickets\/ticket-1$/);
    await page.getByRole("button", { name: /Вернуться к обращению/ }).click();
    await expect(reply).toHaveValue("Черновик ответа — не отправлять");
    if (width === 1366) await expect(page.getByText("reply-draft.txt",{exact:true})).toBeVisible();
    await page.getByRole("button", { name: "Свернуть очередь", exact: true }).click();
    await expect(page.getByRole("button", { name: "Свернуть очередь", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(reply).toHaveValue("Черновик ответа — не отправлять");
    await page.getByRole("button", { name: "Очередь рядом", exact: true }).click();
    await expect(page.getByRole("button", { name: "Очередь рядом", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".simple-workspace > .simple-queue--compact")).toBeVisible();
    await expect(reply).toHaveValue("Черновик ответа — не отправлять");
    if (width >= 1024) {
      await page.getByRole("link", { name: "Очередь обращений", exact: true }).click();
      await expect(page).toHaveURL(/\/app\/tickets$/);
      await page.getByRole("button", { name: /Вернуться к обращению/ }).click();
      await expect(reply).toHaveValue("Черновик ответа — не отправлять");
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: info.outputPath(`queue-modes-${width}.png`), fullPage: true });
    expect(errors).toEqual([]);
  });
}

test("miniatures show complete numbers, status and SLA with five colored filters",async({page},info)=>{
  await page.setViewportSize({width:1440,height:900});
  await login(page);await page.getByRole("button",{name:"T-200001",exact:true}).click();
  const rail=page.getByRole("region",{name:"Список заявок",exact:true});
  await expect(rail).toBeVisible();
  const first=rail.getByRole("button",{name:/T-200001.*SLA/});
  await expect(first).toBeVisible();
  expect((await rail.boundingBox())!.width).toBe(96);
  const number=await first.locator("strong").boundingBox();const card=await first.boundingBox();
  expect(number!.x+number!.width).toBeLessThanOrEqual(card!.x+card!.width);
  await page.screenshot({path:info.outputPath("queue-miniatures.png"),fullPage:true});
  await rail.getByRole("button",{name:"Показать список заявок",exact:true}).click();
  const compact=page.getByRole("region",{name:"Моя рабочая очередь",exact:true});
  await expect(compact.locator(".simple-queue__compact-controls button")).toHaveCount(2);
  await expect(compact.getByRole("tab",{name:"SLA риск",exact:true})).toHaveCount(0);
  await expect(compact.getByRole("tab")).toHaveCount(5);
  const colors=await compact.getByRole("tab").evaluateAll(tabs=>tabs.map(e=>getComputedStyle(e).getPropertyValue("--filter-color")));
  expect(new Set(colors).size).toBe(5);
  await compact.getByRole("tab",{name:"Новые",exact:true}).click();
  await expect(compact.getByRole("tab",{name:"Новые",exact:true})).toHaveAttribute("aria-selected","true");
  await page.getByRole("button",{name:"Тёмная тема",exact:true}).click();
  await page.screenshot({path:info.outputPath("queue-filters-dark.png"),fullPage:true});
});

test("navigation hover overlays without moving the ticket, pin persists, keyboard can escape", async ({ page }, info) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  const navigation = page.getByTestId("support-navigation");
  await page.mouse.move(900, 100);
  await expect(navigation).toHaveAttribute("data-expanded", "false");
  const content = page.getByTestId("support-workspace-root");
  const before = await content.boundingBox();
  await navigation.hover({ position: { x: 12, y: 200 } });
  await expect(navigation).toHaveAttribute("data-expanded", "true");
  expect((await content.boundingBox())!.x).toBe(before!.x);
  await page.mouse.move(900, 100);
  await expect(navigation).toHaveAttribute("data-expanded", "false");
  await page.getByRole("button", { name: "Закрепить панель", exact: true }).click();
  await page.mouse.move(900, 100);
  await expect(navigation).toHaveAttribute("data-pinned", "true");
  await expect(navigation).toHaveAttribute("data-expanded", "true");
  await page.reload();
  await expect(navigation).toHaveAttribute("data-expanded", "true");
  await page.getByRole("button", { name: "Открепить панель", exact: true }).click();
  await page.mouse.move(900, 100);
  await expect(navigation).toHaveAttribute("data-expanded", "false");
  await page.keyboard.press("Tab");
  await navigation.getByRole("link", { name: "Очередь обращений", exact: true }).focus();
  await expect(navigation).toHaveAttribute("data-expanded", "true");
  await page.keyboard.press("Escape");
  await expect(navigation).toHaveAttribute("data-expanded", "false");
  await page.screenshot({ path: info.outputPath("navigation-auto-hide.png"), fullPage: true });
});

test("SLA cards respond to a narrow inspector without breaking words", async ({ page }, info) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await login(page);
  await page.getByRole("button", { name: "T-200001", exact: true }).click();
  await page.getByRole("navigation", { name: "Разделы правой панели", exact: true }).getByRole("button", { name: "SLA", exact: true }).click();
  const resizer = page.getByRole("separator", { name: "Ширина панели сведений", exact: true });
  await resizer.focus();
  for (let step = 0; step < 8; step++) await page.keyboard.press("ArrowRight");
  await expect(resizer).toHaveAttribute("aria-valuenow", "300");
  const timers = page.locator(".support-sla-timers");
  await expect(timers).toBeVisible();
  expect(await timers.evaluate(element => getComputedStyle(element).gridTemplateColumns.split(" ").length)).toBe(1);
  const first = page.locator(".support-sla-card__title").first();
  const geometry = await first.evaluate(element => {
    const node = element.firstChild!;
    const word = element.textContent!.split(" ")[0];
    const range = document.createRange();range.setStart(node,0);range.setEnd(node,word.length);
    return { fragments:range.getClientRects().length,fontSize:parseFloat(getComputedStyle(element).fontSize),width:element.getBoundingClientRect().width };
  });
  expect(geometry.fragments).toBe(1);
  expect(geometry.fontSize).toBeGreaterThanOrEqual(12);
  expect(geometry.fontSize).toBeLessThanOrEqual(14);
  expect(geometry.width).toBeGreaterThan(70);
  await page.screenshot({ path: info.outputPath("sla-inspector-300.png"), fullPage: true });
  await page.getByRole("tab", { name: "OLA", exact: true }).click();
  expect(await page.locator(".support-sla-timers").evaluate(element => getComputedStyle(element).gridTemplateColumns.split(" ").length)).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
});
