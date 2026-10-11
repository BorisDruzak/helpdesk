import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided requester server steps and resume ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    const failures: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("response", response => { if (response.status() >= 400) failures.push(response.url()); });
    page.on("requestfailed", request => failures.push(request.url()));
    let revision = 1;
    let current = "questions";
    let answer = "";
    function step() {
      return { id: "guided-session", revision, state: current === "finish" ? "completed_self_service" : "active", back_targets: [],
        block: current === "questions" ? { id: current, kind: "form_page", title: "Что происходит с принтером?", fields: [
          { key: "summary", type: "text", label: "Опишите проблему", required: true, value: answer },
        ] } : current === "instruction" ? { id: current, kind: "instruction", title: "Проверьте питание", acknowledgment_required: true,
          content: { format: "plain", body: "Убедитесь, что кабель питания подключён." } }
          : current === "resolved" ? { id: current, kind: "resolution_check", title: "Удалось восстановить печать?" }
          : { id: "finish", kind: "finish", title: "Печать восстановлена", message: "Проблема решена без обращения" } };
    }
    await page.route("**/api/web/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown = {};
      if (path === "/api/web/session/me") data = { user_login: "guided@example.test", actor_role: "user", auth_type: "web_session", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
      else if (path.endsWith("/requester/bootstrap")) data = { profile: { person_id: "p1", display_name: "Сотрудник" }, account_summary: { linked_profile: true }, profile_completion: { complete: true, required_fields: [], missing_fields: [], blocks: {} }, devices: [], feature_flags: { requester_ticket_create: true, requester_no_device_create: true }, policies: {} };
      else if (path.includes("/request-scenarios/sessions")) {
        if (path.endsWith("/answer")) { const body = route.request().postDataJSON(); expect(body).toMatchObject({ revision: 1, expected_block_id: "questions" }); answer = body.answers.summary; current = "instruction"; revision++; }
        if (path.endsWith("/advance")) { const body = route.request().postDataJSON(); expect(body.revision).toBe(revision); current = current === "instruction" ? "resolved" : "finish"; revision++; }
        data = step();
      } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.route("**/api/registry/options", route => route.fulfill({ json: { status: "success", data: { departments: [], locations: [] } } }));
    await page.route("**/public_api/ticket_forms/current**", route => route.fulfill({ json: { status: "ok", pack: { key: "request_forms", version: "test", forms: [{ key: "printer", title: "Не печатает", fields: [{ key: "legacy", label: "Старое поле", type: "text" }], availability_policy: { available_without_agent_binding: true } }] } } }));
    await page.route("**/api/service-catalog/current", route => route.fulfill({ json: { status: "ok", catalog_version: "test", services: [{ service_code: "workplace", title: "Рабочее место", offerings: [{ offering_code: "printer", full_code: "workplace.printer", title: "Не печатает", request_template_key: "printer", guided_scenario_enabled: true }] }] } }));
    await page.goto("/app/requester/new");
    await page.getByRole("combobox", { name: "Категория обращения" }).selectOption({ label: "Не печатает" });
    await expect(page.getByRole("heading", { name: "Что происходит с принтером?" })).toBeVisible();
    await expect(page.getByText("Старое поле")).toHaveCount(0);
    await page.getByRole("textbox", { name: /Опишите проблему/ }).fill("Задание остаётся в очереди");
    const next = page.getByRole("button", { name: "Продолжить", exact: true });
    await expect(next).toBeInViewport({ ratio: 1 });
    await next.click();
    await expect(page.getByRole("heading", { name: "Проверьте питание" })).toBeFocused();
    await expect(next).toBeDisabled();
    await page.reload();
    await expect(page.getByRole("heading", { name: "Проверьте питание" })).toBeVisible();
    await page.getByRole("checkbox", { name: "Инструкция выполнена" }).check();
    await next.click();
    await expect(page.getByRole("heading", { name: "Удалось восстановить печать?" })).toBeVisible();
    await page.getByRole("button", { name: "Да, решено" }).click();
    await expect(page.getByText("Проблема решена без обращения")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-requester-finish.png`) });
    expect(errors).toEqual([]); expect(failures).toEqual([]);
  });
}
