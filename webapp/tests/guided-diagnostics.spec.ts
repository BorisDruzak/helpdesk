import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided diagnostic simulation boundary ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    const unexpected: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("requestfailed", request => errors.push(request.url()));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
    const definition = { schema_version: 1, scenario_key: "printer", title: "Не печатает", service_code: "it", offering_full_code: "it.printer", entry_block_id: "diagnostic", process_binding: { request_template_key: "printer" }, blocks: [
      { id: "diagnostic", kind: "diagnostic", title: "Проверка принтера", capability: "endpoint.context.diagnostic.collect", require_consent: true, timeout_seconds: 30, transitions: [{ to: "review" }] },
      { id: "review", kind: "review", title: "Проверьте данные", transitions: [{ to: "submit" }] },
      { id: "submit", kind: "submit_ticket", title: "Создать обращение" },
    ] };
    await page.route("**/api/web/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown;
      if (path === "/api/web/session/me") data = { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
      else if (path.endsWith("/request-studio/catalog")) data = { categories: [], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" }], scenarios: [{ id: "s1", title: definition.title, status: "draft", offering_full_code: "it.printer", issues: [] }], total: 1, offset: 0, limit: 100 };
      else if (path.endsWith("/scenarios/s1/simulate")) {
        expect(route.request().postDataJSON()).toEqual({ revision: 3, steps: [], diagnostic_outcomes: { diagnostic: "timeout" } });
        data = { state: { revision: 1, results: { diagnostic: { status: "timeout", reason: "simulated_timeout", simulated: true, operation_created: false, consent_required: true } } }, current_step: { id: "review", kind: "review", title: "Проверьте данные", answers: [] } };
      } else if (path.endsWith("/scenarios/s1")) data = { scenario: { id: "s1", archived: false }, draft: { revision: 3, definition } };
      else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      else if (path.endsWith("/helpdesk-model/policies")) data = { policies: {} };
      else { unexpected.push(`${route.request().method()} ${path}`); data = {}; }
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "Карта сценария", exact: true }).click();
    await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Проверка принтера", exact: true }).click();
    await expect(page.getByText("Согласие хранится как настройка. В симуляции реального разрешения нет.", { exact: true })).toBeVisible();
    await expect(page.getByText(/Запасной шаг: Проверьте данные/)).toBeVisible();
    await page.getByRole("button", { name: "Тестировать", exact: true }).click();
    const outcome = page.getByRole("combobox", { name: "Исход симуляции: Проверка принтера", exact: true });
    await outcome.selectOption("timeout");
    const start = page.getByRole("button", { name: "Начать проверку", exact: true });
    await start.focus(); await page.keyboard.press("Enter");
    await expect(page.getByText("Симуляция — реальная операция не выполнялась.", { exact: true })).toBeVisible();
    await expect(page.getByText("Проверка принтера: Истёк срок ожидания", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Проверьте данные", exact: true })).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-diagnostic-simulation.png`) });
    await outcome.selectOption("denied");
    await expect(page.getByText("Симуляция — реальная операция не выполнялась.", { exact: true })).toHaveCount(0);
    expect(errors).toEqual([]); expect(unexpected).toEqual([]);
  });
}
