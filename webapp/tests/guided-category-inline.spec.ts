import { expect, test, type Page } from "playwright/test";
import type { ScenarioCategory } from "../src/features/request-template-studio/scenario-api";
import type { ScenarioDraftDefinition } from "../src/features/request-template-studio/scenario-contract";

const categoryId = "10000000-0000-0000-0000-000000000001";

async function confirmDialog(page: Page, action: () => Promise<unknown>, message: string, accept = false) {
  const handled = page.waitForEvent("dialog").then(async dialog => {
    expect(dialog.message()).toBe(message);
    if (accept) await dialog.accept(); else await dialog.dismiss();
  });
  await action();
  await handled;
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`catalog category and service draft guards ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [], unexpected: string[] = [];
    const categories: ScenarioCategory[] = [];
    const writes: { path: string; body: unknown }[] = [];
    let savedDefinition: ScenarioDraftDefinition | undefined;
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("requestfailed", request => errors.push(request.url()));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
    await page.route("**/api/web/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname;
      let data: unknown = {};
      if (!["GET", "HEAD"].includes(request.method())) writes.push({ path, body: request.postDataJSON() });
      if (path === "/api/web/session/me") data = { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
      else if (path.endsWith("/request-studio/catalog")) data = { categories, services: [{ code: "access", public_title: "Доступы", lifecycle_status: "published", visibility: "public" }, { code: "workplace", public_title: "Рабочее место", lifecycle_status: "published", visibility: "public" }], offerings: [], scenarios: [], total: 0, offset: 0, limit: 100 };
      else if (path.endsWith("/categories") && request.method() === "POST") {
        const category = { ...request.postDataJSON(), id: categoryId, revision: 1 } as ScenarioCategory;
        expect(category).toMatchObject({ service_code: "workplace", parent_id: null, title: "Принтеры и МФУ" });
        categories.push(category); data = category;
      } else if (path.endsWith("/request-studio/services") && request.method() === "POST") {
        savedDefinition = request.postDataJSON().definition;
        data = { scenario: { id: "s-new", archived: false }, draft: { revision: 1, definition: { ...savedDefinition, offering_full_code: "workplace.printer", process_binding: { request_template_key: "printer" } } } };
      } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      else if (path.endsWith("/helpdesk-model/policies")) data = { policies: {} };
      else unexpected.push(`${request.method()} ${path}`);
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("button", { name: "Рабочее место · 0", exact: true }).click();
    await page.getByRole("button", { name: "Создать категорию", exact: true }).click();
    const section = page.getByRole("combobox", { name: "Раздел каталога", exact: true });
    await expect(section).toHaveValue("workplace"); await expect(section).toBeDisabled();
    const categoryTitle = page.getByRole("textbox", { name: "Название категории", exact: true });
    await categoryTitle.fill("Принтеры и МФУ");
    await confirmDialog(page, () => page.getByRole("button", { name: "Доступы · 0", exact: true }).click(), "Есть несохранённые настройки. Продолжить без сохранения?");
    await expect(categoryTitle).toHaveValue("Принтеры и МФУ");
    await confirmDialog(page, () => page.getByRole("button", { name: "Отмена", exact: true }).click(), "Закрыть категорию без сохранения изменений?");
    await expect(categoryTitle).toHaveValue("Принтеры и МФУ"); expect(writes).toEqual([]);
    await confirmDialog(page, () => page.getByRole("button", { name: "Отмена", exact: true }).click(), "Закрыть категорию без сохранения изменений?", true);
    await expect(categoryTitle).toHaveCount(0); expect(writes).toEqual([]);
    await page.getByRole("button", { name: "Создать категорию", exact: true }).click();
    await expect(categoryTitle).toBeEmpty(); await expect(section).toHaveValue("workplace");
    await categoryTitle.fill("Принтеры и МФУ");
    const saveCategory = page.getByRole("button", { name: "Сохранить категорию", exact: true });
    await saveCategory.focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Принтеры и МФУ", exact: true })).toBeVisible();
    expect(categories).toHaveLength(1); expect(writes).toHaveLength(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-catalog-category.png`) });

    await page.getByRole("button", { name: "Принтеры и МФУ", exact: true }).click();
    await page.getByRole("button", { name: "Создать услугу", exact: true }).click();
    const title = page.getByRole("textbox", { name: "Название услуги", exact: true });
    const category = page.getByRole("combobox", { name: "Категория (необязательно)", exact: true });
    await title.fill("Мой сценарий принтера");
    await expect(section).toHaveValue("workplace"); await expect(category).toHaveValue(categoryId);
    await page.getByText("Описание услуги", { exact: true }).click();
    await page.getByRole("textbox", { name: "Описание услуги", exact: true }).fill("Несохранённое описание");
    await page.getByRole("button", { name: "Каталог", exact: true }).click();
    const leave = page.getByRole("alert").filter({ hasText: "Уйти без сохранения локальных изменений?" });
    await expect(leave).toBeVisible();
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toBeDisabled();
    await leave.getByRole("button", { name: "Отмена", exact: true }).click();
    await expect(title).toHaveValue("Мой сценарий принтера"); await expect(category).toHaveValue(categoryId);
    await page.getByRole("button", { name: "Создать услугу", exact: true }).click();
    const switching = page.getByRole("alert").filter({ hasText: "Переключить карту без сохранения локальных изменений?" });
    await expect(switching).toBeVisible();
    await switching.getByRole("button", { name: "Отмена", exact: true }).click();
    await expect(title).toHaveValue("Мой сценарий принтера");
    await expect(page.getByRole("textbox", { name: "Описание услуги", exact: true })).toHaveValue("Несохранённое описание");
    expect(writes).toHaveLength(1);

    await page.getByRole("button", { name: "+ Инструкция", exact: true }).click();
    await page.getByRole("textbox", { name: "Название блока", exact: true }).fill("Проверьте бумагу");
    const blockId = await page.locator(".react-flow__node").filter({ has: page.locator("strong", { hasText: "Проверьте бумагу" }) }).getAttribute("data-id");
    expect(blockId).toBeTruthy();
    await page.getByRole("button", { name: "Настройки карты", exact: true }).first().click();
    await page.getByText("Подключить вход с клавиатуры", { exact: true }).click();
    await page.getByRole("combobox", { name: "Первый шаг", exact: true }).selectOption(blockId!);
    await category.selectOption(""); await category.selectOption(categoryId);
    expect(writes).toHaveLength(1);
    const save = page.getByRole("button", { name: "Сохранить черновик", exact: true });
    await expect(save).toBeInViewport(); await save.click();
    await expect(page.getByText("Черновик сохранён. Ревизия 1.", { exact: true })).toBeVisible();
    expect(savedDefinition).toMatchObject({ title: "Мой сценарий принтера", description: "Несохранённое описание", service_code: "workplace", category_id: categoryId, entry_points: [{ category_id: categoryId, target_block_id: blockId }] });
    expect(writes.map(item => item.path)).toEqual(["/api/web/admin/request-studio/categories", "/api/web/admin/request-studio/services"]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-category-service-draft.png`) });
    expect(errors).toEqual([]); expect(unexpected).toEqual([]);
  });
}
