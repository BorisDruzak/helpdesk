import { expect, type Page, test } from "playwright/test";

for (const width of [1366,1920]) {
 test(`guided map first screen catalog resizing and hints ${width}`, async({page},info)=>{
  const height=width===1366?768:1080;await page.setViewportSize({width,height});
  const definition={scenario_key:"printer",title:"Не печатает",service_code:"it",offering_full_code:"it.printer",entry_block_id:"q",process_binding:{request_template_key:"printer"},blocks:[{id:"q",kind:"instruction",title:"Проверка бумаги",content:{body:"Проверьте лоток"},transitions:[]},{id:"end",kind:"submit_ticket",title:"Обращение"}]};
  const state=await fixture(page,false,definition);
  await page.route("**/api/web/admin/request-studio/scenarios/s1/publish-preview",route=>route.fulfill({json:{status:"success",data:{revision:3,health:{health_status:"ok"},readiness:{can_publish:false,variants_checked:0,issues:[]},diff:[],confirmation_token:null}}}));
  await page.goto("/app/admin/request-template-studio");
  await expect(page.getByLabel("Визуальная карта сценария",{exact:true})).toBeVisible();
  await expect(page.getByRole("link",{name:"Конструктор форм",exact:true})).toHaveCount(0);
  await expect(page.getByRole("link",{name:"Проверка политик",exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Принтер",exact:true}).click();
  await expect(page.getByLabel("Название сценария")).toHaveValue("Не печатает");
  await expect(page).toHaveURL(/\/app\/admin\/request-template-studio$/);
  await expect(page.getByRole("tab",{name:"Блоки",exact:true})).toHaveAttribute("aria-selected","true");
  const left=page.getByRole("separator",{name:"Ширина каталога и блоков"});
  const leftBefore=Number(await left.getAttribute("aria-valuenow"));const leftBox=(await left.boundingBox())!;
  await page.mouse.move(leftBox.x+4,leftBox.y+leftBox.height/2);await page.mouse.down();await page.mouse.move(leftBox.x+44,leftBox.y+leftBox.height/2,{steps:5});await page.mouse.up();
  await expect(left).toHaveAttribute("aria-valuenow",String(leftBefore+40));
  const right=page.getByRole("separator",{name:"Ширина инспектора"});const rightBefore=Number(await right.getAttribute("aria-valuenow"));const rightBox=(await right.boundingBox())!;
  await page.mouse.move(rightBox.x+4,rightBox.y+rightBox.height/2);await page.mouse.down();await page.mouse.move(rightBox.x-16,rightBox.y+rightBox.height/2,{steps:5});await page.mouse.up();
  await expect(right).toHaveAttribute("aria-valuenow",String(Math.min(rightBefore+20,Number(await right.getAttribute("aria-valuemax")))));
  const bottom=page.getByRole("separator",{name:"Высота редактора"});const before=Number(await bottom.getAttribute("aria-valuenow"));
  if(before>310){const box=(await bottom.boundingBox())!;await page.mouse.move(box.x+box.width/2,box.y+6);await page.mouse.down();await page.mouse.move(box.x+box.width/2,box.y-24,{steps:5});await page.mouse.up();await expect(bottom).toHaveAttribute("aria-valuenow",String(before-30));}
  expect(state.mutations).toHaveLength(0);
  await page.reload();await expect(left).toHaveAttribute("aria-valuenow",String(leftBefore+40));
  await page.getByRole("button",{name:"Принтер",exact:true}).click();await expect(page.getByLabel("Название сценария")).toHaveValue("Не печатает");
  await page.getByRole("button",{name:"Опубликовать",exact:true}).click();
  await expect(page.getByRole("button",{name:"Закрыть панель",exact:true})).toBeVisible();
  await page.getByRole("button",{name:/Что ещё настроить/}).click();
  await page.getByRole("button",{name:/«Проверка бумаги»: укажите следующий шаг/}).click();
  await expect(page.getByRole("complementary",{name:"Контекстный инспектор"}).getByRole("heading",{name:"Проверка бумаги",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Закрыть панель",exact:true})).toHaveCount(0);
  expect(state.mutations).toHaveLength(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  const canvas=(await page.getByLabel("Визуальная карта сценария",{exact:true}).boundingBox())!;expect(canvas.y+canvas.height).toBeLessThanOrEqual(height);
  await page.screenshot({path:info.outputPath(`${width}-map-first-resized-hints.png`)});
  expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
 });
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  for (const interaction of ["tab", "direct"] as const) {
  test(`guided studio dynamic simulation focus ${viewport.width} ${interaction}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page, true);
    let submitted = false;
    await page.route("**/api/web/admin/request-studio/scenarios/s1/simulate", async route => {
      const body = route.request().postDataJSON();
      if (body.preview) {
        expect(body.preview.answers.team_note).toBe("Synthetic department print work");
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      if (body.steps.length) {
        expect(body.steps[0].answers).toEqual({ team_note: "Synthetic department print work" });
        submitted = true;
      }
      await route.fulfill({ json: { status: "success", data: {
        state: { revision: body.steps.length + 1, results: {}, answers: {}, history: [] },
        current_step: body.steps.length ? { id: "review", kind: "review", title: "Проверьте ответы" }
          : { id: "details", kind: "form_page", title: "Подробности влияния", has_dynamic_fields: true,
              fields: [{ key: "team_note", type: "text", label: "Какая работа остановилась?", value: body.preview?.answers.team_note }] },
      } } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "Тестировать", exact: true }).click();
    await page.getByRole("button", { name: "Начать проверку", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Подробности влияния", exact: true })).toBeFocused();
    const input = page.getByRole("textbox", { name: "Какая работа остановилась?", exact: true });
    await input.fill("Synthetic department print work");
    if (interaction === "tab") {
      await page.keyboard.press("Tab");
      await expect(page.getByRole("button", { name: "Начать проверку", exact: true })).toBeEnabled();
      await expect(input).toHaveValue("Synthetic department print work");
    }
    await page.getByRole("button", { name: "Продолжить проверку", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Проверьте ответы", exact: true })).toBeFocused();
    expect(submitted).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-simulation-focus.png`) });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
  }

  test(`guided studio auditor route ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page, true);
    await page.route("**/api/web/session/me", route => route.fulfill({ json: { status: "success", data: {
      user_login: "auditor@example.test", actor_role: "auditor", auth_type: "web_session",
      default_workspace: null, available_workspaces: [], permissions: [],
    } } }));
    await page.goto("/app/admin/registry");
    await expect(page.getByRole("region", { name: "Каталог в редакторе", exact: true })).toBeVisible();
    await expect(page).toHaveURL(/\/app\/admin\/request-template-studio$/);
    await expect(page.getByRole("button", { name: "Создать сценарий", exact: true })).toHaveCount(0);
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    await expect(page.getByLabel("Название сценария", { exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Тестировать", exact: true }).click();
    await expect(page.getByRole("button", { name: "Начать проверку", exact: true })).toBeEnabled();
    expect(state.mutations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-auditor-studio.png`) });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided studio standalone offering ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    let offering: Record<string, unknown> | null = null;
    await page.route("**/api/web/admin/request-studio/catalog?**", route => route.fulfill({ json: { status: "success", data: { services: [{ code: "it", public_title: "Рабочее место", lifecycle_status: "published", visibility: "public" }], offerings: offering ? [offering] : [], entries: offering ? [{ offering, scenarios: [], active_mode: "form", requester_available: false, category_ids: [] }] : [], categories: [], scenarios: [], total: offering ? 1 : 0, offset: 0, limit: 100 } } }));
    await page.route("**/api/web/admin/helpdesk-model/policies", route => route.fulfill({ json: { status: "success", data: { request_templates: [{ template_code: "printer", version: "1", public_title: "Проблема печати", ticket_type: "incident", is_active: true, published_at: "2026-01-01" }] } } }));
    await page.route("**/api/web/admin/service-catalog/offerings/save-draft", async route => {
      const body = route.request().postDataJSON();
      expect(body).toMatchObject({ service_code: "it", public_title: "Не печатает", lifecycle_status: "draft", visibility: "public", request_template_key: "printer", ticket_type_code: "incident" });
      offering = { ...body, full_code: `it.${body.code}` };
      await route.fulfill({ json: { status: "ok", offering } });
    });
    await page.route("**/api/web/admin/request-studio/scenarios", async route => {
      const body = route.request().postDataJSON();
      expect(body.definition.publish_offering).toBe(true);
      expect(body.definition.offering_full_code).toBe(offering?.full_code);
      await route.fulfill({ json: { status: "success", data: { scenario: { id: "new", archived: false }, draft: { revision: 1, definition: body.definition } } } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("link", { name: "Создать услугу", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Создать услугу", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Карта сценария", exact: true })).toHaveCount(0);
    await page.getByLabel("Название услуги", { exact: true }).fill("Не печатает");
    await page.getByLabel("Краткое описание услуги", { exact: true }).fill("Помощь с печатью");
    await page.getByRole("combobox", { name: "Шаблон обработки", exact: true }).selectOption("printer");
    const create = page.getByRole("button", { name: "Создать черновик услуги", exact: true });
    await create.scrollIntoViewIfNeeded(); await create.focus();
    await expect(create).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-standalone-offering.png`) });
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Новая услуга", exact: true })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Страница услуги", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Создать сценарий для услуги", exact: true }).click();
    await expect(page.getByRole("combobox", { name: "Услуга", exact: true })).toHaveValue(String(offering?.full_code));
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect(page.getByRole("button", { name: "Карта сценария", exact: true })).toBeEnabled();
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

async function fixture(page: Page, publication = false, customDefinition?: Record<string, unknown>) {
  const errors: string[] = [];
  const failures: string[] = [];
  const mutations: unknown[] = [];
  let revision = 3;
  let definition: Record<string, unknown> = customDefinition ?? { schema_version: 1, scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Не печатает", description: "Сценарий помощи с печатью", category_id: "c1", blocks: publication ? [{ id: "instruction", kind: "instruction", title: "Проверьте бумагу", content: { body: "Добавьте бумагу в лоток" } }] : [], process_binding: { request_template_key: "printer" } };
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("requestfailed", request => failures.push(request.url()));
  page.on("response", response => { if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`); });
  await page.route("**/api/web/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = {};
    if (path === "/api/web/session/me") data = { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
    else if (path.includes("/request-studio/catalog")) data = { categories: [{ id: "c1", parent_id: null, service_code: "it", title: "Оборудование", slug: "hardware", revision: 1, visibility: "internal", lifecycle_status: "draft" }, { id: "c2", parent_id: "c1", service_code: "it", title: "Принтеры", slug: "printers", lifecycle_status: "draft" }], services: [{ code: "it", public_title: "ИТ" }], offerings: [{ full_code: "it.printer", service_code: "it", public_title: "Принтер", request_template_key: "printer" }], scenarios: [{ id: "s1", title: definition.title, description: definition.description, service_code: "it", status: "draft", published_version: 7, updated_at: "2026-10-11T10:00:00Z", offering_full_code: "it.printer", category_id: "c2", issues: [] }], total: 1, offset: 0, limit: 100 };
    else if (path.includes("/request-studio/scenarios/s1")) {
      if (route.request().method() === "PUT") { const body = route.request().postDataJSON(); mutations.push(body); definition = body.definition; revision += 1; }
      data = { scenario: { id: "s1", archived: false }, draft: { revision, definition } };
    } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
    await route.fulfill({ json: { status: "success", data } });
  });
  return { errors, failures, mutations };
}

for (const width of [1366, 1440, 1920, 820]) {
  test(`guided studio publication issue focus ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1080 });
    const state = await fixture(page, true);
    await page.route("**/api/web/admin/request-studio/scenarios/s1", route => route.fulfill({ json: { status: "success", data: { scenario: { id: "s1", archived: false }, draft: { revision: 3, definition: {
      schema_version: 1, scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Не печатает", process_binding: { request_template_key: "printer" }, entry_block_id: "first",
      blocks: [{ id: "first", kind: "finish", title: "Начало", message: "Готово" }, { id: "instruction", kind: "instruction", title: "Проверьте бумагу", content: { body: "Добавьте бумагу" }, transitions: [{ to: "first", when: null }, { to: "missing", when: null }] }],
    } } } } }));
    let issue = { code: "unknown_target", path: "blocks.instruction.transitions", message: "Целевой блок не найден" };
    await page.route("**/api/web/admin/request-studio/scenarios/s1/publish-preview", route => route.fulfill({ json: { status: "success", data: { health: { health_status: "ok" }, readiness: { can_publish: false, issues: [issue], variants_checked: 0 }, diff: [], confirmation_token: null } } }));
    await page.route("**/api/web/admin/request-studio/scenarios/s1/versions", route => route.fulfill({ json: { status: "success", data: [] } }));
    await page.route("**/api/web/admin/helpdesk-model/policies", route => route.fulfill({ json: { status: "success", data: { policies: {} } } }));
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    for (const [code, label] of [["unknown_target", "Проверьте бумагу"], ["routing_unavailable", "Маршрут и очередь"], ["sla_unavailable", "Сроки обслуживания"], ["closure_missing", "Закрытие обращения"]]) {
      issue = { code, path: code === "unknown_target" ? "blocks.instruction.transitions" : "process_binding", message: "Исправьте настройку" };
      await page.getByRole("button", { name: "Опубликовать", exact: true }).click();
      await page.getByRole("button", { name: "Подготовить публикацию", exact: true }).click();
      await expect(page.getByRole("button", { name: "Опубликовать сценарий", exact: true })).toHaveCount(0);
      const fix = page.getByRole("button", { name: `Исправить: ${label}`, exact: true });
      await fix.focus(); await page.keyboard.press("Enter");
      if (code === "unknown_target") {
        await expect(page.getByRole("combobox", { name: "Целевой блок", exact: true })).toBeFocused();
      } else await expect(page.getByRole("combobox", { name: label, exact: true })).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
    await page.screenshot({ path: info.outputPath(`${width}-issue-focus.png`) });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]); expect(state.mutations).toEqual([]);
  });
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided studio publication confirmation ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page, true);
    await page.route("**/api/web/admin/request-studio/scenarios/s1/versions", route => route.fulfill({ json: { status: "success", data: [{ id: "v1", version: 1, state: "retired" }] } }));
    await page.route("**/api/web/admin/request-studio/scenarios/s1/rollback-draft", async route => {
      expect(route.request().postDataJSON()).toEqual({ revision: 3, version_id: "v1" });
      await route.fulfill({ json: { status: "success", data: { scenario: { id: "s1", archived: false }, draft: { revision: 4,
        definition: { schema_version: 1, scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Прежний сценарий печати", category_id: "c1", blocks: [], process_binding: { request_template_key: "printer" } } } } } });
    });
    await page.route("**/api/web/admin/request-studio/scenarios/s1/publish*", async route => {
      const body = route.request().postDataJSON();
      let data: unknown;
      if (new URL(route.request().url()).pathname.endsWith("/publish-preview")) {
        expect(body).toEqual({ revision: 3 });
        data = { revision: 3, health: { health_status: "ok" }, readiness: { can_publish: true, issues: [], variants_checked: 4 },
          diff: [{ path: "title", before: "Раньше", after: "Не печатает" }, ...Array.from({ length: 35 }, (_, index) => ({ path: `Вопрос ${index + 1}`, before: "Не задано", after: `Уточнение ${index + 1}` }))],
          confirmation_token: "browser-fixture-token", expires_at: "2099-01-01T00:00:00Z", source_hash: "fixture" };
      } else {
        expect(body).toEqual({ revision: 3, confirm: true, confirmation_token: "browser-fixture-token" });
        data = { version: { version: 1 }, scenario: { id: "s1" }, draft: { revision: 3 } };
      }
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "Опубликовать", exact: true }).click();
    await page.getByRole("button", { name: "Подготовить публикацию", exact: true }).click();
    await expect(page.getByText("Раньше", { exact: true })).toBeVisible();
    const checkbox = page.getByRole("checkbox", { name: "Изменения проверены, подтверждаю публикацию" });
    await checkbox.scrollIntoViewIfNeeded();
    const publish = page.getByRole("button", { name: "Опубликовать сценарий", exact: true });
    await expect(publish).toBeDisabled();
    await checkbox.focus(); await page.keyboard.press("Space");
    await expect(publish).toBeEnabled(); await expect(publish).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-publication-confirmation.png`) });
    await publish.click();
    await expect(page.getByText("Опубликована версия 1.", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Что увидит сотрудник", exact: true })).toBeVisible();
    await expect(page.getByText("Услуга: Принтер", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Открыть сценарий сотрудника", exact: true })).toHaveAttribute("href", "/app/requester/new?offering=it.printer");
    await page.getByText("1. Проверьте бумагу", { exact: true }).click();
    await expect(page.getByText("Добавьте бумагу в лоток", { exact: true })).toBeVisible();
    await page.screenshot({ path: info.outputPath(`${viewport.width}-publication-result.png`) });
    await expect(publish).toHaveCount(0);
    await page.getByRole("button", { name: /Версии/ }).click();
    await page.getByRole("button", { name: "История версий", exact: true }).click();
    await page.getByRole("combobox", { name: "Версия для черновика", exact: true }).selectOption("v1");
    const restore = page.getByRole("button", { name: "Вернуть выбранную версию в черновик", exact: true });
    await restore.focus(); await page.keyboard.press("Enter");
    await expect(page.getByText("Версия скопирована в черновик. Перед публикацией проверьте её заново.", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Закрыть панель", exact: true }).click();
    await page.getByRole("button", { name: "Начало", exact: true }).click();
    await expect(page.getByLabel("Название сценария", { exact: true })).toHaveValue("Прежний сценарий печати");
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}
for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided studio catalog and wizard ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    await page.goto("/app/admin/request-template-studio");
    const create = page.getByRole("button", { name: "Новая карта", exact: true });
    await expect(create).toBeInViewport(); await expect(create).toBeEnabled();
    await expect(page.getByLabel("Визуальная карта сценария", { exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Каталог", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByLabel("Раздел и категория")).toBeVisible();
    await expect(page.getByText("ИТ → Оборудование → Принтеры", { exact: true })).toBeVisible();
    await expect(page.getByText("Сценарий помощи с печатью", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Версия 7", { exact: true })).toBeVisible();
    await expect(page.locator("time")).toHaveAttribute("datetime", "2026-10-11T10:00:00Z");
    await page.getByLabel("Раздел и категория").selectOption("c2");
    await expect(page.getByLabel("Визуальная карта сценария", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("catalog.png") });
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    await expect(page.getByLabel("Название сценария")).toHaveValue("Не печатает");
    await page.getByLabel("Название сценария").fill("Помощь с печатью");
    const save = page.getByRole("button", { name: "Сохранить черновик", exact: true });
    await expect(save).toBeInViewport(); await save.click();
    await expect(page.getByText("Черновик сохранён. Ревизия 4.")).toBeVisible();
    await page.getByText("Расширенные настройки", { exact: true }).click();
    await expect(page.getByLabel("Ключ сценария")).toBeVisible();
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("wizard-inline-settings.png") });
    await page.getByRole("button", { name: "Карта сценария", exact: true }).click();
    await expect(page.getByRole("complementary", { name: "Библиотека блоков" })).toBeVisible();
    await expect(page.getByText("Экспертный", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Начало", exact: true }).click();
    await page.getByLabel("Название сценария").fill("Несохранённая правка");
    page.once("dialog", dialog => dialog.dismiss());
    if (viewport.width < 1024) { await page.getByRole("button", { name: "Новая карта", exact: true }).click(); await page.getByRole("button", { name: "Отмена", exact: true }).click(); }
    else await page.getByRole("link", { name: /Центр администрирования/ }).click();
    await expect(page).toHaveURL(/admin\/request-template-studio$/);
    await expect(page.getByLabel("Название сценария")).toHaveValue("Несохранённая правка");
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ revision: 3 });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`guided map keyboard editing and saved geometry ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "+ Вопрос", exact: true }).click();
    await page.getByLabel("Название блока", { exact: true }).fill("Опишите проблему");
    await page.getByLabel("Название вопроса", { exact: true }).fill("Что не работает?");
    await page.getByRole("button", { name: "+ Инструкция", exact: true }).click();
    await page.getByRole("textbox", { name: "Текст инструкции", exact: true }).fill("Проверьте питание устройства.");
    await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Опишите проблему", exact: true }).click();
    await page.getByRole("combobox", { name: "Соединить с блоком", exact: true }).selectOption({ label: "Инструкция" });
    await page.getByRole("button", { name: "Расположение и стабильные параметры", exact: true }).count().then(async count => { if (!count) await page.getByText("Расположение и стабильные параметры", { exact: true }).click(); });
    await page.getByLabel("X", { exact: true }).fill("420");
    await page.getByLabel("Y", { exact: true }).fill("160");
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect(page.getByText(/Черновик сохранён. Ревизия/)).toBeVisible();
    const saved = state.mutations.at(-1) as { definition: { blocks: { id: string; title: string; transitions: unknown[] }[]; editor_layout: { positions: Record<string, { x: number; y: number }> } } };
    const question = saved.definition.blocks.find(block => block.title === "Опишите проблему")!;
    expect(saved.definition.editor_layout.positions[question.id]).toEqual({ x: 420, y: 160 });
    expect(question.transitions).toHaveLength(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-map-editor.png`) });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

test("guided studio loading empty error and retry states", async ({ page }) => {
  const state = await fixture(page);
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  const pattern = "**/api/web/admin/request-studio/catalog**";
  await page.route(pattern, async route => { await pending; await route.fulfill({ json: { status: "success", data: { categories: [], services: [], offerings: [], scenarios: [], legacy_offerings: [], total: 0, offset: 0, limit: 100 } } }); });
  await page.goto("/app/admin/request-template-studio");
  await expect(page.getByText("Загрузка Студии", { exact: true })).toBeVisible();
  release();
  await expect(page.getByText("Услуги не найдены. Измените поиск или раздел.", { exact: true })).toBeVisible();
  await page.unroute(pattern);
  await page.route(pattern, route => route.fulfill({ status: 500, json: { status: "error", error_code: "FIXTURE_EXPECTED_FAILURE" } }));
  await page.reload();
  await expect(page.getByText("Каталог недоступен", { exact: true })).toBeVisible({ timeout: 15000 });
  await page.unroute(pattern);
  await page.getByRole("button", { name: /Повторить/ }).click();
  await expect(page.getByRole("button", { name: "Принтер", exact: true })).toBeVisible();
  expect(state.errors.filter(error => !error.includes("Failed to load resource"))).toEqual([]);
  expect(state.failures.every(failure => failure.startsWith("500 ") && failure.includes("/request-studio/catalog"))).toBe(true);
});

for (const width of [1366, 1920]) {
  test(`guided map pointer editing and compound undo ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1366 ? 768 : 1080 });
    const condition = { op: "eq", source: "current_result", value: "acknowledged" };
    const definition = { scenario_key: "printer", title: "Не печатает", service_code: "it", offering_full_code: "it.printer", entry_block_id: "q", process_binding: { request_template_key: "printer" },
      editor_layout: { positions: { q: { x: 0, y: 0 }, b: { x: 380, y: 0 }, c: { x: 380, y: 230 } } },
      entry_points: [{ key: "paper", title: "Застряла бумага", target_block_id: "q" }], blocks: [
        { id: "q", kind: "instruction", title: "Проверка бумаги", content: { body: "Проверьте лоток" }, transitions: [{ to: "b", when: condition }, { to: "c" }] },
        { id: "b", kind: "review", title: "Сводка", transitions: [{ to: "c" }] }, { id: "c", kind: "submit_ticket", title: "Обращение" },
      ] };
    const state = await fixture(page, false, definition);
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "Вся карта", exact: true }).click();
    const sourceNode = page.locator('.react-flow__node[data-id="q"]');
    const sourceBox = await sourceNode.boundingBox(); expect(sourceBox).not.toBeNull();
    await page.mouse.move(sourceBox!.x + 60, sourceBox!.y + 35); await page.mouse.down(); await page.mouse.move(sourceBox!.x + 110, sourceBox!.y + 65, { steps: 10 }); await page.mouse.up();
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect(page.getByText(/Черновик сохранён. Ревизия/)).toBeVisible();
    type Saved = { definition: { blocks: { id: string; transitions?: { to: string; when?: unknown }[] }[]; editor_layout: { positions: Record<string, { x: number; y: number }> }; entry_points: { target_block_id: string }[] } };
    const moved = (state.mutations.at(-1) as Saved).definition;
    expect(moved.blocks).toEqual(definition.blocks);
    expect(moved.editor_layout.positions.q).not.toEqual({ x: 0, y: 0 });
    async function drag(from: ReturnType<Page["locator"]>, to: ReturnType<Page["locator"]>) {
      const a = await from.boundingBox(), b = await to.boundingBox(); expect(a).not.toBeNull(); expect(b).not.toBeNull();
      await page.mouse.move(a!.x + a!.width / 2, a!.y + a!.height / 2); await page.mouse.down(); await page.mouse.move(b!.x + b!.width / 2, b!.y + b!.height / 2, { steps: 15 }); await page.mouse.up();
    }
    await drag(sourceNode.locator('.react-flow__handle[data-handleid="new"]'), page.locator('.react-flow__node[data-id="c"] .react-flow__handle.target'));
    const newEdge = page.locator('.react-flow__edge[data-id="q:2"] .react-flow__edge-path');
    await expect(newEdge).toBeVisible();
    expect(await newEdge.evaluate(element => (element as SVGPathElement).getTotalLength())).toBeGreaterThan(0);
    const firstEdge = page.locator('.react-flow__edge[data-id="q:0"]');
    await firstEdge.hover();
    await drag(firstEdge.locator('.react-flow__edgeupdater-target'), page.locator('.react-flow__node[data-id="c"] .react-flow__handle.target'));
    await expect(firstEdge).toHaveAttribute("aria-label", "Edge from q to c");
    await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Проверка бумаги", exact: true }).click();
    await page.getByRole("button", { name: "Условие → Обращение", exact: true }).click();
    await expect(page.getByRole("combobox", { name: "Целевой блок", exact: true })).toHaveValue("c");
    const transfer = await page.evaluateHandle(() => new DataTransfer());
    await transfer.evaluate(data => data.setData("application/x-scenario-kind", "instruction"));
    const edgeBox = await firstEdge.boundingBox();
    await firstEdge.dispatchEvent("drop", { dataTransfer: transfer, clientX: edgeBox!.x + edgeBox!.width / 2, clientY: edgeBox!.y + edgeBox!.height / 2 });
    await page.getByRole("button", { name: "Вставить между шагами", exact: true }).first().click();
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect(page.getByText(/Черновик сохранён. Ревизия/)).toBeVisible();
    const inserted = (state.mutations.at(-1) as Saved).definition;
    const added = inserted.blocks.find(block => !definition.blocks.some(old => old.id === block.id))!;
    expect(inserted.blocks.find(block => block.id === "q")?.transitions?.[0]).toEqual({ to: added.id, when: condition });
    expect(added.transitions).toEqual([{ to: "c" }]);
    await page.getByRole("button", { name: "Вся карта", exact: true }).click();
    const canvasBox = await page.getByLabel("Визуальная карта сценария", { exact: true }).boundingBox();
    expect(canvasBox!.y + canvasBox!.height).toBeLessThanOrEqual((width === 1366 ? 768 : 1080) + 1);
    await page.screenshot({ path: info.outputPath(`${width}-pointer-routes.png`) });
    await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Проверка бумаги", exact: true }).click();
    await page.getByRole("button", { name: "Удалить блок", exact: true }).click();
    await page.getByRole("combobox", { name: "Перенаправить на", exact: true }).selectOption("b");
    await page.getByRole("combobox", { name: "Привязанные точки входа", exact: true }).selectOption("reassign");
    await page.getByRole("button", { name: "Подтвердить удаление блока", exact: true }).click();
    await expect(page.locator('.react-flow__node[data-id="q"]')).toHaveCount(0);
    await page.getByRole("button", { name: "Отменить изменение", exact: true }).click();
    await expect(page.locator('.react-flow__node[data-id="q"]')).toBeVisible();
    await page.getByRole("button", { name: "Повторить изменение", exact: true }).click();
    await expect(page.locator('.react-flow__node[data-id="q"]')).toHaveCount(0);
    await page.screenshot({ path: info.outputPath(`${width}-pointer-edits.png`) });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}
for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided studio independent template ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport); const state = await fixture(page);
    await page.route("**/api/web/session/me", route => route.fulfill({ json: { status: "success", data: { user_login: "studio-test@example.test", actor_role: "admin", auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view", "admin.forms.publish"] } } }));
    await page.route("**/api/web/admin/helpdesk-model/policies", route => route.fulfill({ json: { status: "success", data: { policies: {} } } }));
    const published: unknown[] = [];
    await page.route("**/api/web/admin/helpdesk-model/request-templates/publish-from-form", async route => {
      const body = route.request().postDataJSON(); published.push(body);
      expect(body).toMatchObject({ publish_policies: false, form: { title: "Восстановление почты", fields: [{ label: "Опишите проблему" }, { label: "Адрес почты" }] } });
      await route.fulfill({ json: { status: "success", data: { request_template: { template_code: body.form.key } } } });
    });
    await page.goto("/app/admin/forms/new");
    const primary=page.getByRole("button", { name: "Опубликовать шаблон", exact: true });
    await expect(primary).toBeInViewport({ ratio: 1 });await expect(primary).toBeDisabled();
    await page.getByRole("textbox", { name: "Название шаблона", exact: true }).fill("Восстановление почты");
    await page.getByRole("button", { name: "Добавить вопрос", exact: true }).click();
    await page.getByRole("textbox", { name: "Название вопроса 2", exact: true }).fill("Адрес почты");
    await primary.click(); expect(published).toHaveLength(0);
    await page.getByRole("button", { name: "Продолжить редактирование", exact: true }).click();
    await primary.click(); await page.getByRole("button", { name: "Подтвердить публикацию шаблона", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Шаблон опубликован: Восстановление почты", exact: true })).toBeVisible();
    expect(published).toHaveLength(1);expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-template-published.png`) });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`guided approval confirmation uses canonical registry ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    let published = 0;
    let policy: Record<string, unknown> | null = null;
    await page.route("**/api/web/admin/helpdesk-model/policies", route => route.fulfill({ json: { status: "success", data: { policies: { approval: policy ? [policy] : [] } } } }));
    await page.route("**/api/web/admin/registry", route => route.fulfill({ json: { status: "success", data: { ui_users: [{ user_login: "support-approval", actor_role: "support", is_active: true, linked_person_name: "Анна Согласующая" }] } } }));
    await page.route("**/api/web/admin/helpdesk-model/policies/publish", async route => {
      const body = route.request().postDataJSON();
      expect(body).toMatchObject({ kind: "approval", title: "Руководитель отдела", config: { approval_mode: "sequential", approver_source: { type: "explicit_users", user_ids: ["support-approval"] } } });
      published++; policy = { ...body, version: "1", published_at: "2026-10-13", is_active: true };
      await route.fulfill({ json: { status: "success", data: { policy, message: "Опубликовано" } } });
    });
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Карты сценариев" }).getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "Согласования", exact: true }).click();
    await page.getByRole("button", { name: "Создать схему согласования", exact: true }).click();
    await page.getByLabel("Название", { exact: true }).fill("Руководитель отдела");
    await page.getByRole("combobox", { name: "Источник согласующего", exact: true }).selectOption("explicit_users");
    await page.getByRole("checkbox", { name: "Анна Согласующая", exact: true }).check();
    await page.getByRole("combobox", { name: "Режим согласования", exact: true }).selectOption("sequential");
    await page.getByRole("button", { name: "Опубликовать схему", exact: true }).click();
    expect(published).toBe(0);
    await page.getByRole("button", { name: "Подтвердить публикацию схемы", exact: true }).click();
    await expect(page.getByRole("combobox", { name: "Схема для карты", exact: true })).not.toHaveValue("");
    expect(published).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-approval-registry.png`) });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}
