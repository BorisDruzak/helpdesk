import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test } from "playwright/test";

const bundle = resolve(import.meta.dirname, "../.e2e-compat");

for (const viewport of [{width: 1366, height: 768}, {width: 1920, height: 1080}]) {
  test(`compatibility ticket detail preserves draft on refetch ${viewport.width}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    const failures: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", error=>errors.push(error.message));
    page.on("console", message=> { if (message.type() === "error") consoleErrors.push(message.text()); });
    page.on("response", response=> { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    await page.route("**/api/web/notifications/unread_count", route=>route.fulfill({
      status:200,contentType:"application/json",body:JSON.stringify({status:"ok",unread_count:0}),
    }));
    await page.goto("/app/login");
    await page.getByLabel("Логин", {exact:true}).fill("support");
    await page.getByLabel("Пароль", {exact:true}).fill("secret");
    await page.getByRole("button", {name:"Войти", exact:true}).click();
    await expect(page).toHaveURL(/\/app\/support$/);
    // The shared fixture omits this compatibility-only read; supply an empty candidate collection.
    await page.route("**/api/web/support/tickets/ticket-1/passport/evidence-candidates", route=>route.fulfill({
      status:200,contentType:"application/json",body:JSON.stringify({status:"success",data:{ticket_id:"ticket-1",candidates:[]}}),
    }));
    await page.route("**/__compat_assets/**", async route=> {
      const asset = new URL(route.request().url()).pathname.replace("/__compat_assets/", "");
      expect(asset).not.toContain("..");
      await route.fulfill({body: await readFile(resolve(bundle, asset)), contentType: asset.endsWith("css") ? "text/css" : "text/javascript"});
    });
    await page.route("**/app/tickets/ticket-1", async route=>route.fulfill({body:await readFile(resolve(bundle,"compat-detail.html")),contentType:"text/html"}));
    errors.length = 0;
    failures.length = 0;
    consoleErrors.length = 0;
    await page.goto("/app/tickets/ticket-1");
    await expect(page.getByText("Операционная карточка", {exact:true})).toBeVisible();
    // Check the initial viewport before fill/click can automatically scroll.
    await expect(page.getByRole("button", {name:"Применить статус", exact:true})).toBeInViewport();
    const draft = page.getByLabel("Ответ оператору");
    await draft.fill("Сохранить черновик при обновлении");
    const refreshed = page.waitForResponse(response=>response.url().endsWith("/api/web/support/tickets/ticket-1"));
    await page.getByRole("button", {name:"Обновить", exact:true}).click();
    await refreshed;
    await expect(draft).toHaveValue("Сохранить черновик при обновлении");
    expect(await page.evaluate(()=>document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(2);
    await expect(page.getByRole("button", {name:"Обновить",exact:true})).toBeInViewport();
    await page.screenshot({path:testInfo.outputPath(`ticket-detail-${viewport.width}.png`),fullPage:true});
    expect(errors).toEqual([]);
    expect(failures).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
}
