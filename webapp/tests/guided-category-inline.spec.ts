import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`category creation preserves wizard draft ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    const unexpected: string[] = [];
    const categories: Record<string, unknown>[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("requestfailed", request => errors.push(request.url()));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
    const definition = { scenario_key: "printer", title: "Не печатает", description: "Несохранённое описание", service_code: "workplace", offering_full_code: "workplace.printer_issue", process_binding: { request_template_key: "printer" }, blocks: [] };
    await page.route("**/api/web/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown = {};
      if (path === "/api/web/session/me") data = { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
      else if (path.endsWith("/request-studio/catalog")) data = { categories, services: [{ code: "workplace", public_title: "Рабочее место" }], offerings: [{ full_code: "workplace.printer_issue", service_code: "workplace", public_title: "Не печатает", request_template_key: "printer" }], scenarios: [{ id: "s1", title: definition.title, status: "draft", offering_full_code: "workplace.printer_issue", issues: [] }], total: 1, offset: 0, limit: 100 };
      else if (path.endsWith("/scenarios/s1")) data = { scenario: { id: "s1", archived: false }, draft: { revision: 3, definition } };
      else if (path.endsWith("/categories") && route.request().method() === "POST") {
        const category = { ...route.request().postDataJSON(), id: "printers", revision: 1 };
        expect(category.service_code).toBe("workplace");
        categories.push(category); data = category;
      } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      else unexpected.push(`${route.request().method()} ${path}`);
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByLabel("Название сценария", { exact: true }).fill("Мой сценарий принтера");
    await page.getByRole("button", { name: "Создать категорию здесь", exact: true }).click();
    await expect(page.getByRole("button", { name: "Следующий этап", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Вернуться в каталог", exact: true })).toBeDisabled();
    await expect(page.getByRole("combobox", { name: "Сервис", exact: true })).toBeDisabled();
    await page.getByLabel("Название категории", { exact: true }).fill("Принтеры и МФУ");
    const save = page.getByRole("button", { name: "Сохранить категорию", exact: true });
    await save.focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("combobox", { name: "Категория", exact: true })).toHaveValue("printers");
    await expect(page.getByLabel("Название сценария", { exact: true })).toHaveValue("Мой сценарий принтера");
    await expect(page.getByRole("textbox", { name: "Описание", exact: true })).toHaveValue("Несохранённое описание");
    await expect(page.getByRole("button", { name: "Следующий этап", exact: true })).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-category-inline.png`) });
    expect(categories).toHaveLength(1); expect(errors).toEqual([]); expect(unexpected).toEqual([]);
  });
}
