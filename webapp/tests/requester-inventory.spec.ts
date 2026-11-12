import { expect, test } from "playwright/test";

for (const width of [390, 1366, 1920]) {
  test(`requester sees only the assigned computers at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const errors: string[] = [];
    const failed: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", (response) => { if (response.status() >= 400) failed.push(new URL(response.url()).pathname); });
    const profile = { person_id: "fixture-person", full_name: "Тестовый Сотрудник", department_id: "it", phone: "0000" };
    const completion = { complete: true, required_fields: [], missing_fields: [], blocks: {} };
    const device = { device_id: "fixture-helpdesk-device", name: "Тестовый ПК 1" };
    let outage = false;
    await page.route("**/public_api/ticket_forms/current**", (route) => route.fulfill({
      json: { status: "ok", pack: { key: "request_forms", version: "inventory", forms: [{
        key: "manual_help", title: "Ручная помощь", request_kind: "service_request",
        availability_policy: { available_without_agent_binding: true, contact_required: true },
        fields: [{ key: "description", label: "Описание", type: "textarea", required: true }],
      }] } },
    }));
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown = {};
      if (path === "/api/web/session/me") {
        data = { user_login: "fixture-user", actor_role: "user", auth_type: "ui_token", default_workspace: "requester",
          available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
      } else if (path === "/api/web/requester/bootstrap") {
        data = { workspace: "requester", profile, profile_completion: completion, devices: [device],
          primary_device: device, primary_device_resolution: { status: "available" }, feature_flags: {}, policies: {} };
      } else if (path === "/api/service-catalog/current") {
        return route.fulfill({ json: { status: "ok", services: [{ service_code: "manual", title: "Помощь", offerings: [{
          offering_code: "manual_help", full_code: "manual.manual_help", title: "Ручная помощь без устройства",
          request_template_key: "manual_help",
        }] }] } });
      } else if (path === "/api/web/requester/profile") {
        data = { profile, profile_completion: completion, profile_schema: { fields: [] }, devices: [],
          active_bindings: [], inventory_devices_enabled: true };
      } else if (path === "/api/registry/options") {
        data = { departments: [{ value: "it", label: "ИТ" }], locations: [] };
      } else if (path === "/api/web/requester/inventory-devices") {
        data = { sync_state: outage ? "stale" : "current", assignments: [
          { assignment_id: "fixture-offline", name: "Тестовый ПК 1", os_name: "ALT Linux",
            endpoint_device_id: "fixture-endpoint", endpoint_binding_state: "confirmed", request_device_id: "fixture-helpdesk-device",
            endpoint_status: outage ? "unknown" : "offline", last_seen_at: "2026-11-11T10:00:00Z" },
          { assignment_id: "fixture-missing", name: "Тестовый ПК 2", os_name: "Windows", inventory_number: "INV-2",
            endpoint_binding_state: "unbound", endpoint_status: outage ? "unknown" : "not_detected" },
        ] };
      }
      return route.fulfill({ json: { status: "success", data } });
    });

    await page.goto("/app/requester/profile");
    const section = page.getByRole("region", { name: "Мои компьютеры" });
    await expect(section.getByText("Тестовый ПК 1")).toBeVisible();
    await expect(section.getByText(/Агент не в сети/)).toBeVisible();
    await expect(section.getByText(/Агент не обнаружен/)).toBeVisible();
    const createRequest = section.getByRole("link", { name: "Создать обращение для компьютера" });
    await expect(createRequest).toHaveAttribute("href", "/app/requester/new");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("inventory-profile.png"), fullPage: true });

    await createRequest.click();
    await expect(page).toHaveURL(/\/app\/requester\/new$/);
    expect(await page.evaluate(() => history.state?.usr?.requestDeviceId)).toBe("fixture-helpdesk-device");

    await page.goBack();
    const installRequest = section.getByRole("link", { name: "Запросить установку" });
    await installRequest.click();
    await expect(page).toHaveURL(/\/app\/requester\/new\?intent=endpoint_install$/);
    await page.getByRole("searchbox", { name: "Найти проблему во всём каталоге" }).click();
    await page.getByRole("button", { name: "Ручная помощь без устройства" }).click();
    await expect(page.getByLabel("Описание")).toHaveValue("Прошу установить Endpoint Agent на компьютер Тестовый ПК 2 (INV-2).");
    await expect(page.getByLabel("Компьютер для обращения")).toHaveValue("");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("inventory-installation-draft.png"), fullPage: true });

    outage = true;
    await page.goto("/app/requester/profile");
    await expect(section.getByText(/Инвентаризация сейчас недоступна/)).toBeVisible();
    await expect(section.getByText("Тестовый ПК 1")).toBeVisible();
    await expect(section.getByText(/Агент не в сети/)).toHaveCount(0);
    await expect(createRequest).toHaveCount(0);
    await expect(installRequest).toHaveCount(0);
    expect(errors).toEqual([]);
    expect(failed).toEqual([]);
  });
}
