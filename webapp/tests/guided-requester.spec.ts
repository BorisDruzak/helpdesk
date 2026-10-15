import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  for (const mode of ["self-service", "ticket", "escape-ticket"]) {
  test(`guided requester ${mode} server steps and resume ${viewport.width}`, async ({ page }, info) => {
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
    let created = false;
    function step() {
      return { id: "guided-session", revision, state: created ? "ticket_created" : current === "finish" ? "completed_self_service" : "active", linked_ticket_id: created ? "test-ticket" : null, back_targets: [],
        block: current === "questions" ? { id: current, kind: "form_page", title: "Что происходит с принтером?", fields: [
          { key: "summary", type: "text", label: "Опишите проблему", required: true, value: answer },
          ...Array.from({ length: 8 }, (_, index) => ({ key: `detail_${index}`, type: "text", label: `Уточнение ${index + 1}`, required: false })),
        ] } : current === "instruction" ? { id: current, kind: "instruction", title: "Проверьте питание", acknowledgment_required: true, can_request_ticket: mode === "escape-ticket",
          content: { format: "plain", body: "Убедитесь, что кабель питания подключён." } }
          : current === "resolved" ? { id: current, kind: "resolution_check", title: "Удалось восстановить печать?" }
          : current === "review" ? { id: current, kind: "review", title: "Проверьте ответы", answers: [{ key: "summary", label: "Проблема", type: "text", value: answer, display_value: answer }] }
          : current === "submit" ? { id: current, kind: "submit_ticket", title: "Отправка в поддержку" }
          : { id: "finish", kind: "finish", title: "Печать восстановлена", message: "Проблема решена без обращения" } };
    }
    await page.route("**/api/web/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown = {};
      if (path === "/api/web/session/me") data = { user_login: "guided@example.test", actor_role: "user", auth_type: "web_session", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
      else if (path.endsWith("/requester/bootstrap")) data = { profile: { person_id: "p1", display_name: "Сотрудник" }, account_summary: { linked_profile: true }, profile_completion: { complete: true, required_fields: [], missing_fields: [], blocks: {} }, devices: [], feature_flags: { requester_ticket_create: true, requester_no_device_create: true }, policies: {} };
      else if (path.includes("/request-scenarios/sessions")) {
        if (path.endsWith("/sessions") && route.request().method() === "POST" && mode === "ticket") expect(route.request().postDataJSON()).toEqual({ offering_full_code: "workplace.printer", entry_point_key: "paper" });
        if (path.endsWith("/answer")) { const body = route.request().postDataJSON(); expect(body).toMatchObject({ revision: 1, expected_block_id: "questions" }); answer = body.answers.summary; current = "instruction"; revision++; }
        if (path.endsWith("/advance")) { const body = route.request().postDataJSON(); expect(body.revision).toBe(revision); if (mode === "escape-ticket" && current === "instruction") { expect(body.current_result).toBe("request_ticket"); current = "review"; } else current = current === "instruction" ? "resolved" : current === "review" ? "submit" : mode === "ticket" ? "review" : "finish"; revision++; }
        if (path.endsWith("/submit")) { expect(route.request().postDataJSON()).toEqual({ revision, confirm: true, device_scope: "none" }); created = true; revision++; }
        data = step();
        if (path.endsWith("/ticket-preview")) data = { ok: true, expected_resolution: "до 4 ч", approval: { text: "Согласование не требуется" }, blockers: [], warnings: [], would_create_ticket: false };
      } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.route("**/api/registry/options", route => route.fulfill({ json: { status: "success", data: { departments: [], locations: [] } } }));
    await page.route("**/public_api/ticket_forms/current**", route => route.fulfill({ json: { status: "ok", pack: { key: "request_forms", version: "test", forms: [{ key: "printer", title: "Не печатает", fields: [{ key: "legacy", label: "Старое поле", type: "text" }], availability_policy: { available_without_agent_binding: true } }] } } }));
    await page.route("**/api/service-catalog/current*", route => {
      if (new URL(route.request().url()).searchParams.has("q")) return route.fulfill({ json: { status: "ok", search: {
        results: [{ title: "Бумага застряла", description: "Помощь с бумагой", category: "Оборудование", help_mode: "guided",
          offering_full_code: "workplace.printer", entry_point_key: "paper", match_reason: "Совпало дополнительное поисковое выражение" }],
        suggestions: [], corrected_query: null,
      } } });
      return route.fulfill({ json: { status: "ok", catalog_version: "test", services: [{ service_code: "workplace", title: "Рабочее место", offerings: [{ offering_code: "printer", full_code: "workplace.printer", title: "Не печатает", request_template_key: "printer", guided_scenario_enabled: true, ...(mode === "ticket" ? { catalog_items: [{ key: "paper", title: "Бумага застряла", description: "Помощь с бумагой", synonyms: ["замятие"], entry_point_key: "paper", scenario_key: "printer", version_id: "v1", target_block_id: "questions" }] } : {}) }] }] } });
    });
    await page.goto(mode === "escape-ticket" ? "/app/requester/new/?offering=workplace.printer" : "/app/requester/new");
    if (mode === "self-service") await page.getByRole("combobox", { name: "Категория обращения" }).selectOption({ label: "Не печатает" });
    if (mode === "ticket") {
      await page.getByRole("searchbox", { name: "Найти проблему во всём каталоге" }).fill("замятие");
      const result = page.getByRole("button", { name: /Бумага застряла/ });
      await expect(result).toBeInViewport({ ratio: 1 });
      await expect(page.getByText("Оборудование · Пошаговая помощь")).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`${viewport.width}-catalog-search.png`) });
      await result.click();
    }
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
    if (mode === "escape-ticket") {
      await expect(page.getByRole("checkbox", { name: "Инструкция выполнена" })).not.toBeChecked();
      await page.getByRole("button", { name: "Нужна помощь поддержки" }).click();
      await expect(page.getByRole("heading", { name: "Проверьте ответы" })).toBeFocused();
    } else {
      await page.getByRole("checkbox", { name: "Инструкция выполнена" }).check();
      await next.click();
      await expect(page.getByRole("heading", { name: "Удалось восстановить печать?" })).toBeVisible();
      await page.getByRole("button", { name: mode === "ticket" ? "Нет, нужна помощь" : "Да, решено" }).click();
    }
    if (mode !== "self-service") {
      await expect(page.getByText(answer)).toBeVisible();
      await next.click();
      await page.getByRole("button", { name: "Проверить обработку" }).click();
      const submit = page.getByRole("button", { name: "Создать обращение" });
      await expect(submit).toBeInViewport({ ratio: 1 });
      await submit.click();
      await expect(page.getByRole("link", { name: "Открыть обращение" })).toHaveAttribute("href", "/app/requester/tickets/test-ticket");
      await page.reload();
      await expect(page.getByText("Обращение создано.")).toBeVisible();
    } else await expect(page.getByText("Проблема решена без обращения")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-requester-${mode}.png`) });
    expect(errors).toEqual([]); expect(failures).toEqual([]);
  });
  }
}
