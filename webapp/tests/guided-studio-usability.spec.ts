import { writeFile } from "node:fs/promises";
import { expect, test, type Page } from "playwright/test";

async function setup(page: Page) {
  const errors: string[] = [], failures: string[] = [], writes: { path: string; body: Record<string, any> }[] = [];
  let definition: any = null, revision = 0;
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("requestfailed", request => failures.push(request.url()));
  page.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`); });
  const offering = { full_code: "access.grant", code: "grant", service_code: "access", public_title: "Выдача доступа", request_template_key: "access", lifecycle_status: "published", visibility: "public" };
  await page.route("**/api/web/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let data: any = {};
    if (path.endsWith("/session/me")) data = { user_login: "studio-fixture@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
    else if (path.endsWith("/request-studio/catalog")) data = { categories: [{ id: "10000000-0000-0000-0000-000000000001", service_code: "access", title: "Запросы доступа", lifecycle_status: "published", parent_id: null }], services: [{ code: "access", public_title: "Доступы", lifecycle_status: "published", visibility: "public" }], offerings: [offering], scenarios: [], entries: [{ offering, scenarios: [], active_mode: "form", category_ids: [] }], total: 1, offset: 0, limit: 100 };
    else if (path.endsWith("/helpdesk-model/policies")) data = { policies: {}, request_templates: [{ template_code: "access", public_title: "Заявка на доступ", is_active: true, published_at: "2026-10-13T00:00:00Z" }] };
    else if (path.endsWith("/simulate")) {
      const body = route.request().postDataJSON(); writes.push({ path, body });
      let current = definition.entry_block_id;
      const answers: Record<string, unknown> = {};
      for (const [i, answer] of body.steps.entries()) {
        expect(answer.expected_block_id).toBe(current); expect(answer.revision).toBe(i + 1);
        Object.assign(answers, answer.answers ?? {});
        current = definition.blocks.find((block: any) => block.id === current).transitions[0].to;
      }
      const step = definition.blocks.find((block: any) => block.id === current);
      data = { state: { revision: body.steps.length + 1, answers, history: body.steps.map((answer: any) => answer.expected_block_id), current_block_id: step.id }, current_step: { ...step, ...(step.kind === "review" ? { answers: Object.entries(answers).map(([key,value])=>({key,label:definition.blocks.flatMap((block:any)=>block.fields??[]).find((field:any)=>field.key===key)?.label,display_value:String(value)})) } : {}) }, ...(step.kind === "submit_ticket" ? { processing: { priority: {priority_class:"standard"},routing:{queue_title:"Поддержка доступа"},sla:{first_response_min:30,resolution_min:480},approval:{required:false},validated_facts:answers,would_create_ticket:false} } : {}) };

    } else if (path.endsWith("/publish-preview")) {
      writes.push({ path, body: route.request().postDataJSON() }); data = { health: { health_status: "ok" }, readiness: { can_publish: false, issues: [{ code: "routing_unavailable", path: "process_binding", message: "Проверьте действующую политику маршрутизации" }], variants_checked: 0 }, diff: [], confirmation_token: null };
    } else if (path.endsWith("/scenarios") || /\/scenarios\/s-new$/.test(path)) {
      if (["POST", "PUT"].includes(route.request().method())) { const body = route.request().postDataJSON(); writes.push({ path, body }); if (route.request().method() === "PUT") expect(body.revision).toBe(revision); definition = body.definition; revision++; }
      data = { scenario: { id: "s-new", archived: false }, draft: { revision, definition } };
    } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
    await route.fulfill({ json: { status: "success", data } });
  });
  return { errors, failures, writes, draft: () => definition };
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`studio understandable access authoring ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport); const state = await setup(page);
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("button", { name: "Новая карта", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "С чего начнём?" });
    await dialog.getByLabel("Название карты").fill("Выдать доступ"); await dialog.getByLabel("Раздел каталога").selectOption("10000000-0000-0000-0000-000000000001");
    await expect(dialog.getByRole("radio", { name: /Простая заявка/ })).toBeChecked();
    await expect(dialog.getByRole("button", { name: "Создать карту →" })).toBeInViewport();
    await page.screenshot({ path: info.outputPath(`${viewport.width}-01-create.png`) });
    await dialog.getByRole("button", { name: "Создать карту →" }).click();
    await page.getByLabel("Что спросить?", { exact: true }).fill("К какой системе нужен доступ?");
    await expect(page.locator('.react-flow__node[data-id="studio:metadata"]')).toHaveCount(0);
    await expect(page.locator('.react-flow__node').filter({ hasText: "Пункт каталога · точка входа" })).toHaveCount(1);
    const plus = page.getByRole("button", { name: /Добавить шаг между «Что нужно сотруднику\?» и «Проверка ответов»/ });
    await plus.click(); const menu = page.getByRole("dialog", { name: "Что добавить дальше?" });
    await page.screenshot({ path: info.outputPath(`${viewport.width}-02-add-step.png`) });
    await menu.getByRole("button", { name: "Спросить сотрудника", exact: false }).click();
    await page.getByLabel("Что спросить?", { exact: true }).fill("Для чего необходим доступ?");
    await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Создать обращение", exact: true }).click();
    const inspector = page.getByRole("complementary", { name: "Контекстный инспектор" });
    await inspector.getByLabel("Тип создаваемого обращения").selectOption("access.grant");
    await expect(inspector.getByText("Заявка на доступ", { exact: true })).toBeVisible();
    const viewportBefore = await page.locator(".react-flow__viewport").getAttribute("style");
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect(page.getByText("Черновик сохранён. Ревизия 1.")).toBeVisible();
    expect(await page.locator(".react-flow__viewport").getAttribute("style")).toBe(viewportBefore);
    const draft = state.draft(); const questions = draft.blocks.filter((block: any) => block.kind === "form_page");
    expect(questions).toHaveLength(2); expect(questions.map((block: any) => block.fields[0].label)).toEqual(["К какой системе нужен доступ?", "Для чего необходим доступ?"]);
    expect(questions[0].transitions[0].to).toBe(questions[1].id);
    expect(draft.entry_points[0].target_block_id).toBe(questions[0].id);
    expect(draft.offering_full_code).toBe("access.grant");
    await writeFile(info.outputPath(`${viewport.width}-simple-draft.json`),JSON.stringify(draft));
    await page.screenshot({ path: info.outputPath(`${viewport.width}-03-result.png`) });
    await inspector.getByRole("button", { name: "Проверить пример обработки" }).click(); await page.getByRole("button", { name: "Начать проверку", exact: true }).click();
    await expect(page.getByRole("complementary", { name: "Контекстный инспектор" }).getByLabel("К какой системе нужен доступ?", { exact: true })).toBeVisible();
    await page.getByRole("complementary", { name: "Контекстный инспектор" }).getByLabel("К какой системе нужен доступ?",{exact:true}).fill("Система учёта");
    await page.getByRole("button",{name:"Продолжить проверку",exact:true}).click();
    await page.getByRole("complementary", { name: "Контекстный инспектор" }).getByLabel("Для чего необходим доступ?",{exact:true}).fill("Работа отдела");
    await page.getByRole("button",{name:"Продолжить проверку",exact:true}).click();
    await expect(page.getByRole("complementary", { name: "Контекстный инспектор" }).getByText("Работа отдела",{exact:true})).toBeVisible();
    await page.getByRole("button",{name:"Продолжить проверку",exact:true}).click();
    await expect(page.getByRole("region",{name:"Результат серверной проверки обработки"})).toBeVisible();
    await expect(page.getByText("Очередь: Поддержка доступа",{exact:true})).toBeVisible();
    await page.screenshot({path:info.outputPath(`${viewport.width}-04-safe-preview.png`)});
    await page.getByRole("button", { name: "Опубликовать", exact: true }).click(); await page.getByRole("button", { name: "Подготовить публикацию", exact: true }).click();
    await expect(page.getByRole("button", { name: "Опубликовать сценарий", exact: true })).toHaveCount(0);
    expect(state.writes.some(write => write.path.endsWith("/publish"))).toBe(false);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });

  test(`studio diagnostic branches and shared entrances ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport); const state = await setup(page); await page.goto("/app/admin/request-template-studio");
    await page.getByRole("button", { name: "Новая карта", exact: true }).click();
    await page.getByLabel("Название карты").fill("Проблемы с печатью"); await page.getByLabel("Раздел каталога").selectOption("service:access");
    await page.getByRole("radio", { name: /Диагностика проблемы/ }).check(); await page.getByRole("button", { name: "Создать карту →" }).click();
    await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Создать обращение", exact: true }).click();
    await page.getByLabel("Тип создаваемого обращения").selectOption("access.grant");
    await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Первый шаг решения", exact: true }).click();
    await page.getByText("Пункты каталога для этого шага", { exact: true }).click();
    await page.getByRole("button", { name: "Добавить точку входа из каталога", exact: true }).click();
    await page.getByLabel("Название пункта", { exact: true }).last().fill("Принтер не печатает");
    await page.getByRole("button", { name: /Добавить шаг между «Проблема решена\?» и «Передать в поддержку»/ }).first().click();
    await page.getByRole("dialog", { name: "Что добавить дальше?" }).getByRole("button", { name: /Показать инструкцию/ }).click();
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click(); await expect(page.getByText("Черновик сохранён. Ревизия 1.")).toBeVisible();
    const draft = state.draft(), check = draft.blocks.find((block: any) => block.kind === "resolution_check"), finish = draft.blocks.find((block: any) => block.kind === "finish");
    expect(check.transitions[0]).toEqual({ to: finish.id, when: { source: "current_result", op: "eq", value: "yes" } });
    expect(check.transitions[1].when).toEqual({ source: "current_result", op: "eq", value: "no" });
    expect(check.transitions[2].to).not.toBe(finish.id); expect(draft.entry_points).toHaveLength(2);
    expect(draft.entry_points[0].target_block_id).toBe(draft.entry_points[1].target_block_id);
    await writeFile(info.outputPath(`${viewport.width}-diagnostic-draft.json`),JSON.stringify(draft));
    await page.getByRole("button", { name: "Отменить изменение", exact: true }).click();
    expect(await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button").count()).toBe(5);
    await page.getByRole("button", { name: "Повторить изменение", exact: true }).click();
    expect(await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button").count()).toBe(6);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-diagnostic-shared.png`) });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}
