import { expect, type Page, test } from "playwright/test";

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
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "4. Тестирование", exact: true }).click();
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
    await expect(page.getByRole("region", { name: "Каталог сценариев", exact: true })).toBeVisible();
    await expect(page).toHaveURL(/\/app\/admin\/request-template-studio$/);
    await expect(page.getByRole("button", { name: "Создать сценарий", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await expect(page.getByLabel("Название сценария", { exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "4. Тестирование", exact: true }).click();
    await expect(page.getByRole("button", { name: "Начать проверку", exact: true })).toBeEnabled();
    expect(state.mutations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-auditor-studio.png`) });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided studio inline offering ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    let offering: Record<string, unknown> | null = null;
    await page.route("**/api/web/admin/request-studio/catalog?**", route => route.fulfill({ json: { status: "success", data: { services: [{ code: "it", public_title: "Рабочее место", lifecycle_status: "published", visibility: "public" }], offerings: offering ? [offering] : [], categories: [], scenarios: [], total: 0, offset: 0, limit: 100 } } }));
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
    await page.getByRole("button", { name: "Создать сценарий", exact: true }).click();
    await page.getByRole("button", { name: "Создать услугу здесь", exact: true }).click();
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Вернуться в каталог", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "2. Пользовательский сценарий", exact: true })).toBeDisabled();
    await page.getByLabel("Название услуги", { exact: true }).fill("Не печатает");
    await page.getByLabel("Краткое описание услуги", { exact: true }).fill("Помощь с печатью");
    await page.getByRole("combobox", { name: "Шаблон обработки", exact: true }).selectOption("printer");
    const create = page.getByRole("button", { name: "Создать черновик услуги", exact: true });
    await create.scrollIntoViewIfNeeded(); await create.focus();
    await expect(create).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-inline-offering.png`) });
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Новая услуга", exact: true })).toHaveCount(0);
    await expect(page.getByRole("combobox", { name: "Услуга", exact: true })).toHaveValue(String(offering?.full_code));
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect(page.getByRole("button", { name: "2. Пользовательский сценарий", exact: true })).toBeEnabled();
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

async function fixture(page: Page, publication = false) {
  const errors: string[] = [];
  const failures: string[] = [];
  const mutations: unknown[] = [];
  let revision = 3;
  let definition = { schema_version: 1, scenario_key: "printer", service_code: "it", offering_full_code: "it.printer", title: "Не печатает", description: "Сценарий помощи с печатью", category_id: "c1", blocks: publication ? [{ id: "instruction", kind: "instruction", title: "Проверьте бумагу", content: { body: "Добавьте бумагу в лоток" } }] : [], process_binding: { request_template_key: "printer" } };
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
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    for (const [code, label] of [["unknown_target", "Проверьте бумагу"], ["routing_unavailable", "Маршрут и очередь"], ["sla_unavailable", "Сроки обслуживания"], ["closure_missing", "Закрытие обращения"]]) {
      issue = { code, path: code === "unknown_target" ? "blocks.instruction.transitions" : "process_binding", message: "Исправьте настройку" };
      await page.getByRole("button", { name: "5. Публикация", exact: true }).click();
      await page.getByRole("button", { name: "Подготовить публикацию", exact: true }).click();
      await expect(page.getByRole("button", { name: "Опубликовать сценарий", exact: true })).toHaveCount(0);
      const fix = page.getByRole("button", { name: `Исправить: ${label}`, exact: true });
      await fix.focus(); await page.keyboard.press("Enter");
      if (code === "unknown_target") {
        await expect(page.getByLabel("Название блока", { exact: true })).toHaveValue("Проверьте бумагу");
        await expect(page.getByRole("combobox", { name: "Следующий блок", exact: true }).nth(1)).toBeFocused();
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
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "5. Публикация", exact: true }).click();
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
    await page.getByRole("button", { name: "История версий", exact: true }).click();
    await page.getByRole("combobox", { name: "Версия для черновика", exact: true }).selectOption("v1");
    const restore = page.getByRole("button", { name: "Вернуть выбранную версию в черновик", exact: true });
    await restore.focus(); await page.keyboard.press("Enter");
    await expect(page.getByText("Версия скопирована в черновик. Перед публикацией проверьте её заново.", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "1. Категория и назначение", exact: true }).click();
    await expect(page.getByLabel("Название сценария", { exact: true })).toHaveValue("Прежний сценарий печати");
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}
for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided studio catalog and wizard ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    await page.goto("/app/admin/request-template-studio");
    const create = page.getByRole("button", { name: "Создать сценарий", exact: true });
    await expect(create).toBeInViewport(); await expect(create).toBeEnabled();
    await expect(page.getByRole("button", { name: "Оборудование", exact: true })).toBeVisible();
    await expect(page.getByText("ИТ → Оборудование → Принтеры", { exact: true })).toBeVisible();
    await expect(page.getByText("Сценарий помощи с печатью", { exact: true })).toBeVisible();
    await expect(page.getByText("Версия 7", { exact: true })).toBeVisible();
    await expect(page.locator("time")).toHaveAttribute("datetime", "2026-10-11T10:00:00Z");
    const collapse = page.getByRole("button", { name: "Свернуть категорию Оборудование", exact: true });
    await collapse.focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Принтеры", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Развернуть категорию Оборудование", exact: true }).click();
    await expect(page.getByRole("button", { name: "Принтеры", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("catalog.png") });
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
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
    await page.getByRole("button", { name: "Следующий этап", exact: true }).click();
    await expect(page.getByText("Сценарий пока пуст")).toBeVisible();
    await expect(page.getByLabel("Название сценария")).toHaveCount(0);
    await expect(page.getByText("Экспертный", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Предыдущий этап", exact: true }).click();
    await page.getByLabel("Название сценария").fill("Несохранённая правка");
    page.once("dialog", dialog => dialog.dismiss());
    if (viewport.width < 1024) await page.getByRole("button", { name: "Вернуться в каталог", exact: true }).click();
    else await page.getByRole("link", { name: /Центр администрирования/ }).click();
    await expect(page).toHaveURL(/admin\/request-template-studio$/);
    await expect(page.getByLabel("Название сценария")).toHaveValue("Несохранённая правка");
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ revision: 3 });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }, { width: 820, height: 1180 }]) {
  test(`guided block builder keyboard and preview ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await fixture(page);
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "2. Пользовательский сценарий", exact: true }).click();
    await page.getByRole("button", { name: "Добавить блок", exact: true }).click();
    await expect(page.getByLabel("Название блока", { exact: true })).toBeFocused();
    await page.getByLabel("Название блока", { exact: true }).fill("Опишите проблему");
    await page.getByLabel("Название вопроса", { exact: true }).fill("Что не работает?");
    await page.getByRole("combobox", { name: "Тип ответа", exact: true }).selectOption("select");
    const field = page.getByRole("group", { name: "Редактор вопроса", exact: true });
    await field.getByText("Расширенные настройки", { exact: true }).last().click();
    await field.getByLabel("Влияние на приоритет", { exact: true }).check();
    await field.getByLabel("Отчётность", { exact: true }).check();
    await expect(field.getByLabel("Влияние на приоритет", { exact: true })).toBeChecked();
    await expect(field.getByLabel("Отчётность", { exact: true })).toBeChecked();
    const aliases = field.getByRole("textbox", { name: "Прежние ключи (через запятую)", exact: true });
    await aliases.pressSequentially("old_key,new_key");
    await expect(aliases).toHaveValue("old_key,new_key");
    await page.getByRole("combobox", { name: "Тип нового блока", exact: true }).selectOption("instruction");
    await page.getByRole("button", { name: "Добавить блок", exact: true }).click();
    await expect(page.getByLabel("Название вопроса", { exact: true })).toHaveCount(0);
    await page.getByRole("textbox", { name: "Текст инструкции", exact: true }).fill("Проверьте питание устройства.\nПовторите попытку.");
    await page.getByRole("button", { name: "Опишите проблему", exact: true }).click();
    const blockEditor = page.getByRole("region", { name: "Редактор выбранного блока", exact: true });
    await blockEditor.getByText("Расширенные настройки", { exact: true }).last().click();
    await blockEditor.getByRole("button", { name: "Добавить переход", exact: true }).click();
    const condition = blockEditor.getByRole("group", { name: "Условие перехода", exact: true });
    await condition.getByRole("button", { name: "Добавить условие", exact: true }).click();
    await condition.getByRole("combobox", { name: "Правило", exact: true }).selectOption("in");
    await condition.getByRole("checkbox", { name: "Нет", exact: true }).check();
    await expect(condition.getByRole("checkbox", { name: "Да", exact: true })).toBeChecked();
    await expect(condition.getByRole("checkbox", { name: "Нет", exact: true })).toBeChecked();
    await page.getByRole("button", { name: "Инструкция", exact: true }).click();
    await page.getByRole("button", { name: "Переместить блок вверх", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("list", { name: "Блоки сценария", exact: true }).getByRole("button").first()).toHaveText("Инструкция");
    await page.getByRole("button", { name: "Предпросмотр шага", exact: true }).click();
    if (viewport.width < 1440) {
      const dialog = page.getByRole("dialog", { name: "Предпросмотр выбранного шага", exact: true });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole("button", { name: "Закрыть предпросмотр", exact: true })).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(dialog.getByRole("button", { name: "Закрыть предпросмотр", exact: true })).toBeFocused();
      await page.screenshot({ path: info.outputPath("builder-preview.png") });
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await expect(page.getByRole("button", { name: "Предпросмотр шага", exact: true })).toBeFocused();
    } else {
      const panel = page.getByRole("complementary", { name: "Предпросмотр выбранного шага", exact: true });
      await expect(panel).toBeVisible();
      const editorBox = await blockEditor.boundingBox(); const previewBox = await panel.boundingBox();
      expect(editorBox).not.toBeNull(); expect(previewBox).not.toBeNull();
      expect(previewBox!.x).toBeGreaterThanOrEqual(editorBox!.x + editorBox!.width);
      expect(Math.abs(previewBox!.y - editorBox!.y)).toBeLessThan(2);
      await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toBeInViewport({ ratio: 1 });
      expect((await page.getByRole("button", { name: "Сохранить черновик", exact: true }).boundingBox())!.y).toBeGreaterThanOrEqual(80);
      await page.screenshot({ path: info.outputPath("builder-preview.png") });
      await page.getByRole("button", { name: "Скрыть предпросмотр", exact: true }).click();
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const save = page.getByRole("button", { name: "Сохранить черновик", exact: true });
    await expect(save).toBeInViewport({ ratio: 1 }); await save.click();
    await expect(page.getByText("Черновик сохранён. Ревизия 4.")).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Не печатает", exact: true }).click();
    await page.getByRole("button", { name: "2. Пользовательский сценарий", exact: true }).click();
    await page.getByRole("button", { name: "Опишите проблему", exact: true }).click();
    await expect(page.getByLabel("Название вопроса", { exact: true })).toHaveValue("Что не работает?");
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toBeDisabled();
    await page.screenshot({ path: info.outputPath("builder-restored.png") });
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ revision: 3, definition: { blocks: [{ kind: "instruction" }, { kind: "form_page", fields: [{ aliases: ["old_key", "new_key"], process_mapping: { roles: ["priority_impact", "reporting_dimension"] } }], transitions: [{ when: { op: "in", value: ["yes", "no"] } }] }] } });
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
  await expect(page.getByText("Сценарии не найдены", { exact: true })).toBeVisible();
  await page.unroute(pattern);
  await page.route(pattern, route => route.fulfill({ status: 500, json: { status: "error", error_code: "FIXTURE_EXPECTED_FAILURE" } }));
  await page.reload();
  await expect(page.getByText("Каталог недоступен", { exact: true })).toBeVisible({ timeout: 15000 });
  await page.unroute(pattern);
  await page.getByRole("button", { name: /Повторить/ }).click();
  await expect(page.getByRole("button", { name: "Не печатает", exact: true })).toBeVisible();
  expect(state.errors.filter(error => !error.includes("Failed to load resource"))).toEqual([]);
  expect(state.failures.every(failure => failure.startsWith("500 ") && failure.includes("/request-studio/catalog"))).toBe(true);
});
