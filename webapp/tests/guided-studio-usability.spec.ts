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
    else if (path.endsWith("/forms/current")) data={forms:[{key:"access",fields:[{key:"impact_scope",label:"Кого затронула проблема?",type:"select",required:true,options:[{value:"one_person",label:"Только меня"}],process_mapping:{roles:["priority_impact"]}},{key:"work_continuity",label:"Можно продолжать работу?",type:"select",required:true,options:[{value:"work_continues",label:"Да"}],process_mapping:{roles:["priority_urgency"]}}]}]};
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
    await page.getByRole("button",{name:"Создать услугу",exact:true}).click();await page.getByRole("combobox",{name:"Способ помощи",exact:true}).selectOption("map");await page.getByRole("button",{name:"Создать карту",exact:true}).click();
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
    await page.getByRole("button",{name:"Создать услугу",exact:true}).click();await page.getByRole("combobox",{name:"Способ помощи",exact:true}).selectOption("map");await page.getByRole("button",{name:"Создать карту",exact:true}).click();
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


test("manual route authoring isolates geometry, edits conditions and deletes connected blocks", async ({ page }, info) => {
  await page.setViewportSize({width:1366,height:900}); const state=await setup(page);
  await page.goto("/app/admin/request-template-studio");
  await page.getByRole("button",{name:"Создать услугу",exact:true}).click();await page.getByRole("combobox",{name:"Способ помощи",exact:true}).selectOption("map");await page.getByRole("button",{name:"Создать карту",exact:true}).click();
  await page.getByLabel("Название карты").fill("Проверка ручного маршрута");
  await page.getByLabel("Раздел каталога").selectOption("service:access");
  await page.getByRole("radio",{name:/Пустая карта/}).check();
  await page.getByRole("button",{name:"Создать карту →"}).click();
  await page.getByRole("button",{name:"+ Добавить первый шаг",exact:true}).click();
  await page.getByRole("dialog",{name:"Что добавить дальше?"}).getByRole("button",{name:/Спросить сотрудника/}).click();
  await page.getByLabel("Что спросить?",{exact:true}).fill("Нужен доступ к VPN?");
  await page.getByRole("combobox",{name:"Тип ответа",exact:true}).selectOption("checkbox");
  const question=await page.locator(".react-flow__node").filter({hasText:"Нужен доступ к VPN?"}).getAttribute("data-id");
  await page.getByRole("button",{name:"+ Условие",exact:true}).click();
  const decision=await page.locator(".react-flow__node").filter({hasText:"Условие"}).getAttribute("data-id");
  await page.getByRole("button",{name:"+ Результат",exact:true}).click();
  await page.getByLabel("Название блока",{exact:true}).fill("VPN в поддержку");
  await page.getByLabel("Тип создаваемого обращения").selectOption("access.grant");
  const ticket=await page.locator(".react-flow__node").filter({hasText:"VPN в поддержку"}).getAttribute("data-id");
  await page.getByRole("button",{name:"Свернуть библиотеку",exact:true}).click();
  await page.getByRole("button",{name:"Свернуть настройки",exact:true}).click();
  await page.getByRole("button",{name:"Вся карта",exact:true}).click();
  const from=page.locator(`.react-flow__node[data-id="${question}"] .react-flow__handle.source[data-handleid="new"]`), to=page.locator(`.react-flow__node[data-id="${decision}"] .react-flow__handle.target`);
  await from.dragTo(to);
  await expect(page.locator(`.react-flow__edge[data-id="${question}:0"]`)).toHaveCount(1);
  const positions=()=>page.locator('.react-flow__node').evaluateAll(es=>Object.fromEntries(es.map(e=>[e.getAttribute('data-id'),(e as HTMLElement).style.transform])));
  const before=await positions(); const box=await page.locator(`.react-flow__node[data-id="${question}"] strong`).boundingBox();
  await page.mouse.move(box!.x+40,box!.y+10); await page.mouse.down(); await page.mouse.move(box!.x+90,box!.y-30,{steps:12}); await page.mouse.up();
  const after=await positions(); expect(after[question!]).not.toBe(before[question!]);
  for(const id of Object.keys(before).filter(id=>id!==question)) expect(after[id]).toBe(before[id]);
  await page.locator(`.react-flow__node[data-id="${decision}"] strong`).click();
  await page.getByLabel("Добавить условную ветвь").selectOption(ticket!);
  await page.getByRole("combobox",{name:"Правило",exact:true}).selectOption("eq");
  await page.getByLabel("Значение условия").selectOption("true");
  await page.getByLabel("Если ни одно условие не выполнено").selectOption(ticket!);
  await page.getByRole("button",{name:"Сохранить черновик",exact:true}).click();
  await expect(page.getByText("Черновик сохранён. Ревизия 1.")).toBeVisible();
  const draft=state.draft(); const branch=draft.blocks.find((b:any)=>b.id===decision);
  expect(branch.transitions).toEqual([{to:ticket,when:{op:"eq",source:"answer",field:draft.blocks[0].fields[0].key,value:true}},{to:ticket,when:null}]);
  await page.screenshot({path:info.outputPath("manual-condition.png")});
  await page.getByRole("button",{name:"Свернуть настройки",exact:true}).click();
  await page.getByRole("button",{name:"Тестировать",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Проверка пользовательского сценария",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Закрыть панель",exact:true}).click();
  await page.getByRole("button",{name:"Предпросмотр страницы",exact:true}).click();
  await expect(page.getByRole("dialog").getByLabel("Нужен доступ к VPN?",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Вернуться к карте",exact:true}).click();
  await page.getByRole("button",{name:"Показать библиотеку",exact:true}).click();
  await page.getByRole("list",{name:"Блоки сценария"}).getByRole("button",{name:"VPN в поддержку",exact:true}).click();
  await page.getByRole("button",{name:"Удалить блок",exact:true}).click();
  const deletion=page.getByRole("dialog",{name:"Удалить блок «VPN в поддержку»?"}); await expect(deletion).toBeVisible();
  await expect(deletion.getByRole("button",{name:"Подтвердить удаление блока"})).toBeInViewport();
  await deletion.getByRole("button",{name:"Подтвердить удаление блока"}).click();
  await expect(page.locator(`.react-flow__node[data-id="${ticket}"]`)).toHaveCount(0);
  await page.getByRole("button",{name:"Отменить изменение",exact:true}).click();
  await expect(page.locator(`.react-flow__node[data-id="${ticket}"]`)).toHaveCount(1);
  await writeFile(info.outputPath('manual-draft.json'),JSON.stringify(draft));
  expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
});


test("canonical mandatory questions are inserted before the selected result",async({page})=>{
 await page.setViewportSize({width:1366,height:900});const state=await setup(page);await page.goto("/app/admin/request-template-studio");
 await page.getByRole("button",{name:"Создать услугу",exact:true}).click();await page.getByRole("combobox",{name:"Способ помощи",exact:true}).selectOption("map");await page.getByRole("button",{name:"Создать карту",exact:true}).click();await page.getByLabel("Название карты").fill("Проверка обязательных данных");await page.getByLabel("Раздел каталога").selectOption("service:access");await page.getByRole("button",{name:"Создать карту →"}).click();
 await page.getByRole("list",{name:"Блоки сценария"}).getByRole("button",{name:"Создать обращение",exact:true}).click();await page.getByLabel("Тип создаваемого обращения").selectOption("access.grant");
 await page.getByRole("button",{name:"Добавить обязательные вопросы типа обращения",exact:true}).click();
 await expect(page.getByRole("heading",{name:"Данные для обращения",exact:true})).toBeVisible();
 await page.getByRole("button",{name:"Сохранить черновик",exact:true}).click();await expect(page.getByText("Черновик сохранён. Ревизия 1.")).toBeVisible();
 const draft=state.draft(),added=draft.blocks.at(-1),ticket=draft.blocks.find((b:any)=>b.kind==="submit_ticket"),review=draft.blocks.find((b:any)=>b.kind==="review");
 expect(added.fields.map((f:any)=>f.process_mapping.fact_key)).toEqual(["impact_scope","work_continuity"]);expect(added.fields.every((f:any)=>f.required)).toBe(true);expect(review.transitions).toEqual([{to:added.id}]);expect(added.transitions).toEqual([{to:ticket.id}]);
 expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
});
