import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided processing choices and complete simulation ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    const unsafe: string[] = [];
    let selected = false;
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("requestfailed", request => errors.push(request.url()));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
    const definition = { schema_version: 1, scenario_key: "printer", title: "Не печатает", service_code: "it", offering_full_code: "it.printer", entry_block_id: "questions", process_binding: { request_template_key: "printer" }, blocks: [
      { id: "questions", title: "Кого затронуло?", kind: "form_page", fields: [{ key: "scope", label: "Влияние", type: "radio", options: [{ value: "team", label: "Весь отдел" }], process_mapping: { fact_key: "affected_scope", roles: ["priority_impact"] } }], transitions: [{ to: "submit" }] },
      { id: "submit", kind: "submit_ticket", title: "Отправка" },
    ] };
    await page.route("**/api/web/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown = {};
      if (path === "/api/web/session/me") data = { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
      else if (path.endsWith("/request-studio/catalog")) data = { categories: [], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" }], scenarios: [{ id: "s1", title: definition.title, status: "draft", offering_full_code: "it.printer", issues: [] }], total: 1, offset: 0, limit: 100 };
      else if (path.endsWith("/helpdesk-model/policies")) {
        if (route.request().method() !== "GET") unsafe.push("registry mutation");
        data = { policies: { routing: [{ code: "printer_route", title: "Поддержка печати", version: "1", is_active: true, published_at: "2026-10-11" }] } };
      } else if (path.endsWith("/scenarios/s1/simulate")) {
        data = { state: { revision: 2, history: ["questions"], results: {} }, current_step: { id: "submit", kind: "submit_ticket", title: "Отправка" }, processing: {
          priority: { priority_class: "P2", reason: "impact=team" }, routing: { queue_code: "print" }, sla: { first_response_min: 30, resolution_min: 120 }, ola: { ack_min: 15, processing_min: 60 },
          approval: { required: false }, closure: { requires_public_summary: true, requires_resolution_code: true }, notification: { would_send: false, recipient_groups: ["queue"], channels: [] }, validated_facts: { affected_scope: "team" }, would_create_ticket: false,
        } };
      } else if (path.endsWith("/scenarios/s1") || path.endsWith("/scenarios/s1/draft")) {
        if (route.request().method() === "PUT") { expect(route.request().postDataJSON().definition.process_binding.policy_refs).toEqual({ routing: "printer_route" }); selected = true; }
        data = { scenario: { id: "s1", archived: false }, draft: { revision: selected ? 4 : 3, definition: { ...definition, ...(selected ? { process_binding: { ...definition.process_binding, policy_refs: { routing: "printer_route" } } } : {}) } } };
      } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      else unsafe.push(`${route.request().method()} ${path}`);
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "3. Обработка обращения", exact: true }).click();
    await page.getByRole("combobox", { name: "Маршрут и очередь", exact: true }).selectOption("printer_route");
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect(page.getByText("Черновик сохранён. Ревизия 4.", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "4. Тестирование", exact: true }).click();
    const start = page.getByRole("button", { name: "Начать проверку", exact: true });
    await start.focus(); await page.keyboard.press("Enter");
    await expect(page.getByText("Весь отдел", { exact: true })).toBeVisible();
    await expect(page.getByText("Кого затронуло? → Отправка", { exact: true })).toBeVisible();
    await expect(page.getByText("При закрытии обязательны итог для сотрудника и код решения.", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-processing-simulation.png`) });
    expect(selected).toBe(true); expect(errors).toEqual([]); expect(unsafe).toEqual([]);
  });
}
