import { readFileSync } from "node:fs";
import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`publication explains delayed server work ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const definition = JSON.parse(readFileSync(new URL("./fixtures/printer-pilot-v3.json", import.meta.url), "utf8"));
    const errors: string[] = [], failures: string[] = [], unexpected: string[] = [];
    const checks: unknown[] = [], publications: unknown[] = [];
    let releaseCheck!: () => void, releasePublish!: () => void;
    const checking = new Promise<void>(resolve => { releaseCheck = resolve; });
    const publishing = new Promise<void>(resolve => { releasePublish = resolve; });
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("requestfailed", request => failures.push(request.url()));
    page.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`); });
    const detail = { scenario: { id: "s1", archived: false }, draft: { revision: 3, definition } };
    await page.route("**/api/web/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown;
      if (path === "/api/web/session/me") data = { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
      else if (path.endsWith("/request-studio/catalog")) data = { categories: [], services: [{ code: definition.service_code, public_title: "Рабочее место", lifecycle_status: "published", visibility: "public" }], offerings: [{ full_code: definition.offering_full_code, service_code: definition.service_code, public_title: definition.title, request_template_key: definition.process_binding.request_template_key }], scenarios: [{ id: "s1", title: definition.title, description: definition.description, service_code: definition.service_code, status: "draft", offering_full_code: definition.offering_full_code, issues: [] }], total: 1, offset: 0, limit: 100 };
      else if (path.endsWith("/scenarios/s1/publish-preview")) {
        checks.push(route.request().postDataJSON()); await checking;
        data = { revision: 3, health: { health_status: "ok" }, readiness: { can_publish: true, issues: [], variants_checked: 220 }, diff: [], confirmation_token: "fixture-reviewed-token" };
      } else if (path.endsWith("/scenarios/s1/publish")) {
        publications.push(route.request().postDataJSON()); await publishing;
        data = { ...detail, version: { version: 1, definition } };
      } else if (path.endsWith("/scenarios/s1")) data = detail;
      else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      else { unexpected.push(path); data = {}; }
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("button", { name: /^Настроить услугу / }).click();
    await page.getByRole("button", { name: "Открыть карту сценария", exact: true }).click();
    await page.getByRole("button", { name: "Опубликовать", exact: true }).click();
    const inspector = page.getByRole("complementary", { name: "Контекстный инспектор", exact: true });
    await inspector.getByRole("button", { name: "Подготовить публикацию", exact: true }).click();
    const checkingStatus = inspector.getByRole("status").filter({ hasText: "Проверяем публикацию" });
    await expect(checkingStatus).toBeVisible(); await expect(checkingStatus).toBeInViewport({ ratio: 1 });
    const checkingButton = inspector.getByRole("button", { name: "Проверяем публикацию…", exact: true });
    await expect(checkingButton).toBeDisabled();
    await checkingButton.evaluate(element => (element as HTMLButtonElement).click());
    await expect.poll(() => checks.length).toBe(1); expect(publications).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-publication-checking.png`) });
    releaseCheck();
    const confirmation = inspector.getByRole("checkbox", { name: "Изменения проверены, подтверждаю публикацию", exact: true });
    await expect(confirmation).toBeVisible(); await expect(checkingStatus).toHaveCount(0);
    const publish = inspector.getByRole("button", { name: "Опубликовать сценарий", exact: true });
    await expect(publish).toBeDisabled(); await confirmation.check(); await publish.click();
    const publishingStatus = inspector.getByRole("status").filter({ hasText: "Публикуем сценарий" });
    await expect(publishingStatus).toBeVisible(); await expect(publishingStatus).toBeInViewport({ ratio: 1 });
    const publishingButton = inspector.getByRole("button", { name: "Публикуем сценарий…", exact: true });
    await expect(publishingButton).toBeDisabled(); await expect(publishingButton).toBeInViewport({ ratio: 1 });
    await publishingButton.evaluate(element => (element as HTMLButtonElement).click());
    await expect.poll(() => publications.length).toBe(1);
    expect(checks).toEqual([{ revision: 3 }]);
    expect(publications).toEqual([{ revision: 3, confirm: true, confirmation_token: "fixture-reviewed-token" }]);
    expect(await inspector.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-publication-publishing.png`) });
    releasePublish();
    await expect(inspector.getByText("Опубликована версия 1.", { exact: true })).toBeVisible();
    await expect(publishingStatus).toHaveCount(0);
    await expect(inspector.getByRole("button", { name: "Подготовить публикацию", exact: true })).toBeEnabled();
    await expect(inspector.getByRole("link", { name: "Открыть сценарий сотрудника", exact: true })).toBeVisible();
    expect(errors).toEqual([]); expect(failures).toEqual([]); expect(unexpected).toEqual([]);
  });
}
