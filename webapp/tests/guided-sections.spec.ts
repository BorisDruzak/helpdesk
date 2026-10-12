import { expect, test } from "playwright/test";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`32 questions retain one editor and requester section preview ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = []; const unexpected: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    page.on("requestfailed", request => errors.push(request.url()));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
    const fields = Array.from({ length: 32 }, (_, index) => ({ key: `question_${index}`, type: "text", label: `Вопрос ${index + 1}`, allow_unknown: index === 0, group: index < 16 ? "device" : "impact", group_title: index < 16 ? "Устройство" : "Влияние" }));
    const definition = { scenario_key: "printer", title: "Не печатает", service_code: "workplace", offering_full_code: "workplace.printer_issue", entry_block_id: "questions", process_binding: { request_template_key: "printer" }, blocks: [
      { id: "questions", title: "Вопросы о печати", kind: "form_page", layout: "section", fields, transitions: [{ to: "submit" }] }, { id: "submit", title: "Отправка", kind: "submit_ticket" },
    ] };
    await page.route("**/api/web/**", async route => {
      const path = new URL(route.request().url()).pathname; let data: unknown = {};
      if (path === "/api/web/session/me") data = { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
      else if (path.endsWith("/request-studio/catalog")) data = { categories: [], services: [{ code: "workplace", public_title: "Рабочее место" }], offerings: [{ full_code: "workplace.printer_issue", service_code: "workplace", public_title: "Не печатает", request_template_key: "printer" }], scenarios: [{ id: "s1", title: definition.title, status: "draft", offering_full_code: "workplace.printer_issue", issues: [] }], total: 1, offset: 0, limit: 100 };
      else if (path.endsWith("/scenarios/s1")) data = { scenario: { id: "s1", archived: false }, draft: { revision: 3, definition } };
      else if (path.endsWith("/scenarios/s1/simulate")) {
        const steps = route.request().postDataJSON().steps;
        if (steps.length) expect(steps[0].answers).toEqual({ question_0: null });
        data = { state: { revision: steps.length ? 2 : 1, history: steps.length ? ["questions"] : [], results: {} }, current_step: steps.length ? { id: "review", kind: "review", title: "Ответы проверены" } : { id: "questions", kind: "form_page", title: "Вопросы о печати", layout: "section", fields } };
      }
      else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
      else if (path.endsWith("/helpdesk-model/policies")) data = { policies: {} };
      else unexpected.push(`${route.request().method()} ${path}`);
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("link", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "Карта сценария", exact: true }).click();
    await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Вопросы о печати", exact: true }).click();
    const questions = page.getByRole("list", { name: "Вопросы страницы", exact: true });
    const questionListSize = await questions.evaluate(element => ({ height: element.clientHeight, content: element.scrollHeight }));
    expect(questionListSize.height).toBeLessThanOrEqual(200);
    expect(questionListSize.content).toBeGreaterThan(questionListSize.height);
    const last = page.getByRole("button", { name: "Вопрос 32", exact: true });
    await last.focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("group", { name: "Редактор вопроса", exact: true })).toHaveCount(1);
    await expect(page.getByRole("textbox", { name: "Название вопроса", exact: true })).toHaveValue("Вопрос 32");
    await page.getByRole("button", { name: "Тестировать", exact: true }).click();
    await expect(page.getByRole("button", { name: "Начать проверку", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Начать проверку", exact: true }).click();
    await expect(page.getByRole("group", { name: "Устройство", exact: true })).toBeVisible();
    await page.getByRole("checkbox", { name: "Не знаю", exact: true }).check();
    await page.getByRole("button", { name: "Продолжить проверку", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Ответы проверены", exact: true })).toBeVisible();
    expect(errors).toEqual([]); expect(unexpected).toEqual([]);
  });
}
