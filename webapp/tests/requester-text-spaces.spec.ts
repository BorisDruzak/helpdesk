import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }, { width: 390, height: 844 }]) {
  test(`requester preserves typed spaces and line breaks ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [], unexpected: string[] = [], answers: unknown[] = [];
    let ticketWrites = 0;
    const fields = [
      { key: "details", type: "textarea", label: "Что произошло или какая помощь нужна?", required: true },
      { key: "room", type: "text", label: "Кабинет / местоположение" },
      { key: "phone", type: "phone", label: "Номер для связи" },
    ];
    const step = { id: "spaces-session", revision: 1, state: "active", back_targets: [], block: {
      id: "details", kind: "form_page", title: "Опишите проблему своими словами", layout: "group", has_dynamic_fields: true, fields,
    } };
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    await page.route("**/api/**", async route => {
      const req = route.request(), path = new URL(req.url()).pathname; let data: unknown;
      if (path === "/api/web/session/me") data = { user_login: "spaces-employee", actor_role: "user", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
      else if (path === "/api/web/session/capabilities") data = {};
      else if (path === "/api/web/notifications/unread_count") return route.fulfill({ json: { status: "ok", unread_count: 0 } });
      else if (path === "/api/web/notifications/push/config") return route.fulfill({ json: { status: "ok", enabled: false, public_key: null } });
      else if (path === "/api/web/requester/catalog-events" && req.method() === "POST") return route.fulfill({ status: 204 });
      else if (path === "/api/web/requester/bootstrap") data = { workspace: "requester", profile: { person_id: "spaces-employee", display_name: "Тестовый сотрудник", full_name: "Тестовый сотрудник", department_id: "it", phone: "0000" }, profile_completion: { complete: true, blocks: {} }, devices: [], primary_device: null, feature_flags: { requester_ticket_create: true, requester_no_device_create: true } };
      else if (path === "/api/web/requester/tickets") { if (req.method() === "POST") ticketWrites++; data = { tickets: [] }; }
      else if (path === "/api/service-catalog/current") return route.fulfill({ json: { status: "ok", services: [{ service_code: "other", title: "Другое", offerings: [{ full_code: "other.unknown", offering_code: "unknown", title: "Другая проблема или вопрос", request_template_key: "general_request", guided_scenario_enabled: true, catalog_items: [{ key: "not_found", entry_point_key: "not_found", title: "Не нашёл свою проблему" }] }] }] } });
      else if (path === "/api/web/requester/request-scenarios/sessions" || path === "/api/web/requester/request-scenarios/sessions/spaces-session") data = step;
      else if (path.endsWith("/step-preview")) {
        const submitted = req.postDataJSON().answers;
        // Even a normalized server projection must not rewrite the live editor.
        data = { ...step, block: { ...step.block, fields: fields.map(field => ({ ...field, value: String(submitted[field.key] ?? "").trim() })) } };
      } else if (path.endsWith("/answer")) {
        answers.push(req.postDataJSON().answers);
        data = { ...step, revision: 2, block: { id: "review", kind: "review", title: "Проверьте ответы", answers: [] } };
      } else { unexpected.push(path); return route.fulfill({ status: 404, json: { status: "error" } }); }
      return route.fulfill({ json: { status: "success", data } });
    });
    await page.route("**/public_api/ticket_forms/current**", route => route.fulfill({ json: { status: "ok", pack: { key: "request_forms", version: "spaces", forms: [{ key: "general_request", title: "Помощь", availability_policy: { available_without_agent_binding: true }, fields: [] }] } } }));
    await page.goto("/app/requester/new");
    await page.getByRole("searchbox", { name: "Найти проблему во всём каталоге" }).click();
    await page.getByRole("button", { name: "Другая проблема или вопрос", exact: true }).click();
    await page.getByRole("button", { name: "Не нашёл свою проблему", exact: true }).click();
    const description = page.getByRole("textbox", { name: "Что произошло или какая помощь нужна?", exact: true });
    await description.pressSequentially("Не открывается");
    const preview = page.waitForResponse(response => response.url().endsWith("/step-preview") && response.request().postDataJSON().answers.details === "Не открывается ");
    await description.press("Space");
    await expect(description).toHaveValue("Не открывается ");
    await preview;
    await description.pressSequentially(" окно");
    await description.press("Enter");
    await description.pressSequentially("Нужна помощь ");
    await expect(description).toHaveValue("Не открывается  окно\nНужна помощь ");
    const room = page.getByRole("textbox", { name: "Кабинет / местоположение", exact: true });
    await room.pressSequentially("Кабинет  12 ");
    await expect(room).toHaveValue("Кабинет  12 ");
    const phone = page.getByRole("textbox", { name: "Номер для связи", exact: true });
    await phone.pressSequentially("8 999 123 45 67 ");
    await expect(phone).toHaveValue("8 999 123 45 67 ");
    await page.screenshot({ path: info.outputPath("typed-spaces.png"), fullPage: true });
    await page.getByRole("button", { name: "Продолжить", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Проверьте ответы", exact: true })).toBeVisible();
    expect(answers).toEqual([{ details: "Не открывается  окно\nНужна помощь ", room: "Кабинет  12 ", phone: "8 999 123 45 67 " }]);
    expect(ticketWrites).toBe(0);expect(errors).toEqual([]);expect(unexpected).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
