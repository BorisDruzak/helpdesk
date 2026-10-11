import { expect, type Page, test } from "playwright/test";

async function fixture(page: Page) {
  const errors: string[] = [];
  const failures: string[] = [];
  const mutations: unknown[] = [];
  let revision = 3;
  let definition = { schema_version: 1, scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Не печатает", description: "Сценарий помощи с печатью", category_id: "c1", blocks: [], process_binding: { request_template_key: "printer" } };
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("requestfailed", request => failures.push(request.url()));
  page.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`); });
  await page.route("**/api/web/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = {};
    if (path === "/api/web/session/me") data = { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
    else if (path.includes("/request-studio/catalog")) data = { categories: [{ id: "c1", parent_id: null, service_code: "it", title: "Оборудование", slug: "hardware", revision: 1, visibility: "internal", lifecycle_status: "draft" }], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" }], scenarios: [{ id: "s1", title: definition.title, status: "draft", offering_full_code: "it.printer", category_id: "c1", issues: [] }], total: 1, offset: 0, limit: 100 };
    else if (path.includes("/request-studio/scenarios/s1")) {
      if (route.request().method() === "PUT") { const body = route.request().postDataJSON(); mutations.push(body); definition = body.definition; revision += 1; }
      data = { scenario: { id: "s1", archived: false }, draft: { revision, definition } };
    } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
    await route.fulfill({ json: { status: "success", data } });
  });
  return { errors, failures, mutations };
}
for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`guided studio catalog and wizard ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    await page.goto("/app/admin/request-template-studio");
    const create = page.getByRole("button", { name: "Создать сценарий", exact: true });
    await expect(create).toBeInViewport(); await expect(create).toBeEnabled();
    await expect(page.getByRole("button", { name: "Оборудование", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("catalog.png") });
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await expect(page.getByLabel("Название сценария")).toHaveValue("Не печатает");
    await page.getByLabel("Название сценария").fill("Помощь с печатью");
    const save = page.getByRole("button", { name: "Сохранить черновик", exact: true });
    await expect(save).toBeInViewport(); await save.click();
    await expect(page.getByText("Черновик сохранён. Ревизия 4.")).toBeVisible();
    await page.getByText("Расширенные настройки", { exact: true }).click();
    await expect(page.getByLabel("Ключ сценария")).toBeVisible();
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("wizard-inline-settings.png") });
    await page.getByRole("button", { name: "Следующий этап", exact: true }).click();
    await expect(page.getByText("Сценарий пока пуст")).toBeVisible();
    await expect(page.getByLabel("Название сценария")).toHaveCount(0);
    await expect(page.getByText("Экспертный", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Предыдущий этап", exact: true }).click();
    await page.getByLabel("Название сценария").fill("Несохранённая правка");
    page.once("dialog", dialog => dialog.dismiss());
    await page.getByRole("link", { name: /Центр администрирования/ }).click();
    await expect(page).toHaveURL(/admin\/request-template-studio$/);
    await expect(page.getByLabel("Название сценария")).toHaveValue("Несохранённая правка");
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ revision: 3 });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

test("guided studio loading empty error and retry states", async ({ page }) => {
  const state = await fixture(page);
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  const pattern = "**/api/web/admin/request-studio/catalog**";
  await page.route(pattern, async route => { await pending; await route.fulfill({ json: { status: "success", data: { categories: [], services: [], offerings: [], scenarios: [], legacy_offerings: [], total: 0, offset: 0, limit: 100 } } }); });
  await page.goto("/app/admin/request-template-studio");
  await expect(page.getByText("Загрузка Студии", { exact: true })).toBeVisible();
  release();
  await expect(page.getByText("Сценарии не найдены", { exact: true })).toBeVisible();
  await page.unroute(pattern);
  await page.route(pattern, route => route.fulfill({ status: 500, json: { status: "error", error_code: "FIXTURE_EXPECTED_FAILURE" } }));
  await page.reload();
  await expect(page.getByText("Каталог недоступен", { exact: true })).toBeVisible({ timeout: 15000 });
  await page.unroute(pattern);
  await page.getByRole("button", { name: /Повторить/ }).click();
  await expect(page.getByRole("button", { name: "Не печатает", exact: true })).toBeVisible();
  expect(state.errors.filter(error => !error.includes("Failed to load resource"))).toEqual([]);
  expect(state.failures.every(failure => failure.startsWith("500 ") && failure.includes("/request-studio/catalog"))).toBe(true);
});
