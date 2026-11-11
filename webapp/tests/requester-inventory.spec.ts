import { expect, test } from "playwright/test";

for (const width of [390, 1366]) {
  test(`requester sees only the assigned computers at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const errors: string[] = [];
    const failed: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", (response) => { if (response.status() >= 400) failed.push(new URL(response.url()).pathname); });
    const profile = { person_id: "fixture-person", full_name: "Тестовый Сотрудник", department_id: "it", phone: "0000" };
    const completion = { complete: true, required_fields: [], missing_fields: [], blocks: {} };
    let outage = false;
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown = {};
      if (path === "/api/web/session/me") {
        data = { user_login: "fixture-user", actor_role: "user", auth_type: "ui_token", default_workspace: "requester",
          available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
      } else if (path === "/api/web/requester/bootstrap") {
        data = { workspace: "requester", profile, profile_completion: completion, devices: [], feature_flags: {}, policies: {} };
      } else if (path === "/api/web/requester/profile") {
        data = { profile, profile_completion: completion, profile_schema: { fields: [] }, devices: [],
          active_bindings: [], inventory_devices_enabled: true };
      } else if (path === "/api/registry/options") {
        data = { departments: [{ value: "it", label: "ИТ" }], locations: [] };
      } else if (path === "/api/web/requester/inventory-devices") {
        data = { sync_state: outage ? "stale" : "current", assignments: [
          { assignment_id: "fixture-offline", name: "Тестовый ПК 1", os_name: "ALT Linux",
            endpoint_device_id: "fixture-endpoint", endpoint_binding_state: "confirmed",
            endpoint_status: outage ? "unknown" : "offline", last_seen_at: "2026-11-11T10:00:00Z" },
          { assignment_id: "fixture-missing", name: "Тестовый ПК 2", os_name: "Windows",
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
    await expect(section.getByRole("link", { name: "Создать обращение для компьютера" })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("inventory-profile.png"), fullPage: true });

    outage = true;
    await page.reload();
    await expect(section.getByText(/Инвентаризация сейчас недоступна/)).toBeVisible();
    await expect(section.getByText("Тестовый ПК 1")).toBeVisible();
    await expect(section.getByText(/Агент не в сети/)).toHaveCount(0);
    expect(errors).toEqual([]);
    expect(failed).toEqual([]);
  });
}
