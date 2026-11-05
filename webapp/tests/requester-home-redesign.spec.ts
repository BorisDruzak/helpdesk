import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1488, height: 1058 }, { width: 1920, height: 1080 }, { width: 390, height: 844 }]) {
  test(`requester home actions, readiness and OS guides ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [], unexpected: string[] = [];
    let writes = 0, complete = true, bound = true, failed = false, empty = false;
    const profile = { person_id: "synthetic-home", display_name: "Тестовый Сотрудник", full_name: "Тестовый Сотрудник", department_id: "it", phone: "0000" };
    const device = { device_id: "synthetic-device", hostname: "WORKSTATION-1", online: true, os: "Linux" };
    const tickets = [
      { ticket_id: "synthetic-1", ticket_code: "T-001042", title: "Не печатает принтер", status: "in_progress", requester_status_label: "В работе", created_at: "2026-11-05T04:15:00Z" },
      { ticket_id: "synthetic-2", ticket_code: "T-001038", title: "Не открывается программа", status: "waiting_on_user", requester_status_label: "Нужен ваш ответ", created_at: "2026-11-04T09:20:00Z" },
      { ticket_id: "synthetic-3", ticket_code: "T-001031", title: "Настроить рабочую почту", status: "resolved", requester_status_label: "Решено", created_at: "2026-11-03T06:00:00Z" },
    ];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error" && !message.text().includes("503")) errors.push(message.text()); });
    await page.route("**/api/**", async (route) => {
      const req = route.request(); const path = new URL(req.url()).pathname;
      if (req.method() !== "GET") writes++;
      let data: unknown = {};
      const completion = { complete, setup_path: "/app/requester/profile/setup", missing_fields: complete ? [] : [{ key: "phone", label: "Телефон" }], blocks: { ticket_create: !complete } };
      if (path === "/api/web/session/me") data = { user_login: "employee", actor_role: "user", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"], worktime_portal_url: "https://endpoint-staging.sosnadmin.local/employee" };
      else if (path === "/api/web/session/capabilities") data = {};
      else if (path === "/api/web/requester/bootstrap") {
        if (failed) return route.fulfill({ status: 503, json: { status: "error", error: { code: "DB_UNAVAILABLE" } } });
        data = { workspace: "requester", profile: complete ? profile : null, profile_completion: completion, devices: complete && bound ? [device] : [], primary_device: complete && bound ? device : null, primary_device_resolution: { status: complete && bound ? "available" : "missing" }, pending_registration_claims: [], feature_flags: { requester_ticket_create: complete, requester_no_device_create: true } };
      } else if (path === "/api/web/requester/profile") data = { profile: complete ? profile : null, profile_completion: completion, profile_schema: { fields: [] }, devices: [], active_bindings: [] };
      else if (path === "/api/web/requester/consents") data = { consents: [] };
      else if (path === "/api/service-catalog/current") return route.fulfill({ json: { status: "ok", services: [{ service_code: "ownership", title: "Устройства", offerings: [{ offering_code: "device_owner_change", full_code: "ownership.device_owner_change", title: "Проверка владельца устройства", request_template_key: "device_owner_change" }] }] } });
      else if (path === "/api/web/requester/tickets") data = { tickets: empty ? [] : tickets };
      else if (path === "/api/web/notifications/unread_count") return route.fulfill({ json: { status: "ok", unread_count: 0 } });
      else { unexpected.push(path); return route.fulfill({ status: 404, json: { status: "error" } }); }
      return route.fulfill({ json: { status: "success", data } });
    });
    await page.route("**/public_api/ticket_forms/current**", (route) => route.fulfill({ json: { status: "ok", pack: { key: "request_forms", version: "synthetic", forms: [{ key: "device_owner_change", title: "Проверка владельца устройства", availability_policy: { available_without_agent_binding: true, contact_required: true }, fields: [{ key: "owner_context", label: "Что нужно проверить", type: "textarea", required: true }] }] } } }));
    await page.goto("/app/requester");
    await expect(page.getByRole("heading", { name: "Чем можем помочь?" })).toBeVisible();
    const create = page.getByRole("link", { name: "Создать обращение", exact: true });
    await expect(create.first()).toBeInViewport();
    await expect(page.getByRole("link", { name: "Открыть список" })).toHaveAttribute("href", "/app/requester/tickets");
    await expect(page.getByText("Профиль заполнен")).toBeVisible();
    await expect(page.getByText("WORKSTATION-1")).toBeVisible();
    await expect(page.getByText("Онлайн", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: /Не печатает принтер/ })).toHaveAttribute("href", "/app/requester/tickets/T-001042");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("home-ready.png"), fullPage: true });

    complete = false; await page.reload();
    await expect(page.getByRole("link", { name: "Заполнить профиль" })).toBeVisible();
    await page.screenshot({ path: info.outputPath("home-reference-state.png"), fullPage: true });
    empty = true; await page.reload();
    await expect(page.getByRole("link", { name: "Заполнить профиль" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Привязать компьютер", exact: true })).toBeVisible();
    await expect(page.getByText("Обращений пока нет")).toBeVisible();
    await page.screenshot({ path: info.outputPath("home-setup.png"), fullPage: true });
    await page.getByRole("link", { name: "Привязать компьютер", exact: true }).click();
    await expect(page.getByText("Заполните профиль, чтобы привязать устройство.")).toBeVisible();
    await expect(page.getByRole("textbox")).toHaveCount(0);
    await page.getByRole("tab", { name: "Linux / ALT Linux" }).click();
    await expect(page.getByText(/В Linux получение кода через значок агента пока недоступно/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Попросить помочь с привязкой" })).toHaveAttribute("href", "/app/requester/new?intent=device_owner_change");
    await page.screenshot({ path: info.outputPath("linux-guide.png"), fullPage: true });
    await page.getByRole("tab", { name: "Linux / ALT Linux" }).press("ArrowLeft");
    await expect(page.getByRole("tab", { name: "Windows", exact: true })).toBeFocused();
    await expect(page.getByText(/правой кнопкой мыши/)).toBeVisible();
    await page.getByText("Показать на скриншотах", { exact: true }).click();
    await expect.poll(() => page.getByRole("img").evaluateAll((images) => images.every((img) => (img as HTMLImageElement).naturalWidth > 0))).toBe(true);

    complete = true; bound = false; await page.reload();
    await expect(page.getByRole("textbox")).toBeVisible();
    await expect(page.getByRole("button", { name: "Привязать устройство", exact: true })).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole("tab", { name: "Linux / ALT Linux" }).click();
    await page.getByRole("link", { name: "Попросить помочь с привязкой" }).click();
    await expect(page.getByRole("heading", { name: "Проверка владельца устройства", exact: true })).toBeVisible();
    await expect(page.getByLabel("Что нужно проверить")).toHaveValue("Нужно проверить владельца устройства");
    await expect(page.getByLabel("Устройство", { exact: true })).toHaveCount(0);
    failed = true; await page.goto("/app/requester");
    await expect(page.getByText("Не удалось открыть кабинет")).toBeVisible();
    await expect(page.getByText("Профиль заполнен")).toHaveCount(0);
    failed = false; await page.getByRole("button", { name: "Повторить" }).click();
    await expect(page.getByRole("heading", { name: "Чем можем помочь?" })).toBeVisible();
    expect(errors).toEqual([]); expect(unexpected).toEqual([]); expect(writes).toBe(0);
  });
}
