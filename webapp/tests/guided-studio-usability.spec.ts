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
    } else if (path.endsWith("/request-studio/services") || path.endsWith("/scenarios") || /\/scenarios\/s-new(?:\/draft)?$/.test(path)) {
      if (["POST", "PUT"].includes(route.request().method())) { const body = route.request().postDataJSON(); writes.push({ path, body }); if (route.request().method() === "PUT") expect(body.revision).toBe(revision); definition = {...body.definition,offering_full_code:"access.grant",process_binding:{...body.definition.process_binding,request_template_key:"access"}}; revision++; }
      data = { scenario: { id: "s-new", archived: false }, draft: { revision, definition } };
    } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
    await route.fulfill({ json: { status: "success", data } });
  });
  return { errors, failures, writes, draft: () => definition };
}

const blocks=(page:Page)=>page.getByRole("list",{name:"Блоки сценария"});
async function connect(page:Page, title:string, target:string){
 await blocks(page).getByRole("button",{name:title,exact:true}).click();
 await page.getByText("Подключение с клавиатуры",{exact:true}).click();
 await page.getByRole("combobox",{name:"Следующий шаг",exact:true}).selectOption(target);
}
async function entrance(page:Page,target:string){
 await page.getByRole("button",{name:"Настройки карты",exact:true}).first().click();
 await page.getByText("Подключить вход с клавиатуры",{exact:true}).click();
 await page.getByRole("combobox",{name:"Первый шаг",exact:true}).selectOption(target);
}
async function add(page:Page,kind:string,title:string){
 await page.getByRole("button",{name:`+ ${kind}`,exact:true}).click();
 if(kind==="Вопрос") await page.getByLabel("Что спросить?",{exact:true}).fill(title);
 else await page.getByLabel("Название блока",{exact:true}).fill(title);
 return (await page.locator(".react-flow__node").filter({has:page.locator("strong",{hasText:title})}).getAttribute("data-id"))!;
}
for(const viewport of [{width:1366,height:768},{width:1920,height:1080},{width:820,height:1180}]){
 test(`studio unified service authoring and local preview ${viewport.width}`,async({page},info)=>{
  await page.setViewportSize(viewport);const state=await setup(page);await page.goto("/app/admin/request-template-studio");
  await page.getByRole("button",{name:"Создать услугу",exact:true}).click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button",{name:"+ Диагностика",exact:true})).toHaveCount(0);
  await expect(page.getByRole("button",{name:"+ Сводка",exact:true})).toHaveCount(0);
  await page.getByLabel("Название услуги",{exact:true}).fill("Выдать доступ");
  await page.getByRole("combobox",{name:"Категория (необязательно)",exact:true}).selectOption("10000000-0000-0000-0000-000000000001");
  const question=await add(page,"Вопрос","К какой системе нужен доступ?");
  await page.getByLabel("Обязательный ответ",{exact:true}).check();
  const result=await add(page,"Результат","Создать обращение");
  await connect(page,"К какой системе нужен доступ?",result);await entrance(page,question);
  const name=page.getByRole("textbox",{name:/^Название входа/});await name.fill("Запросить доступ");await name.press("Enter");
  const viewportBefore=await page.locator(".react-flow__viewport").getAttribute("style");
  await page.getByRole("button",{name:"Сохранить черновик",exact:true}).click();
  await expect(page.getByText("Черновик сохранён. Ревизия 1.")).toBeVisible();
  expect(await page.locator(".react-flow__viewport").getAttribute("style")).toBe(viewportBefore);
  const draft=state.draft();expect(draft.schema_version).toBe(3);expect(draft.blocks).toHaveLength(2);
  expect(draft.entry_points).toMatchObject([{title:"Запросить доступ",target_block_id:question,category_id:draft.category_id}]);
  expect(draft.blocks[0].transitions).toEqual([{to:result}]);expect(draft.blocks[0].fields[0]).toMatchObject({label:"К какой системе нужен доступ?",required:true,type:"text"});
  const writes=state.writes.length;
  await blocks(page).getByRole("button",{name:"К какой системе нужен доступ?",exact:true}).click();
  await page.getByRole("tab",{name:"Как у сотрудника",exact:true}).click();
  await page.getByLabel("К какой системе нужен доступ?",{exact:true}).fill("Система учёта");
  await expect(page.getByRole("button",{name:"Продолжить",exact:true})).toBeDisabled();
  await page.getByRole("button",{name:"Открыть полную страницу",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"Предпросмотр полной страницы"});
  await expect(dialog.getByLabel("К какой системе нужен доступ?",{exact:true})).toBeVisible();
  await dialog.getByLabel("К какой системе нужен доступ?",{exact:true}).fill("Локальный ответ");await page.keyboard.press("Escape");
  await expect(page.getByLabel("К какой системе нужен доступ?",{exact:true})).toHaveValue("Система учёта");
  expect(state.writes).toHaveLength(writes);
  await page.getByRole("button",{name:"Тестировать",exact:true}).click();await page.getByRole("button",{name:"Начать проверку",exact:true}).click();
  await page.getByLabel("К какой системе нужен доступ?",{exact:true}).fill("Система учёта");await page.getByRole("button",{name:"Продолжить проверку",exact:true}).click();
  await expect(page.getByRole("region",{name:"Результат серверной проверки обработки"})).toBeVisible();
  await expect(page.getByText("Очередь: Поддержка доступа",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Закрыть панель",exact:true}).click();
  await page.getByRole("button",{name:"Опубликовать",exact:true}).click();await page.getByRole("button",{name:"Подготовить публикацию",exact:true}).click();
  await expect(page.getByRole("button",{name:"Опубликовать сценарий",exact:true})).toHaveCount(0);
  expect(state.writes.some(item=>item.path.endsWith("/publish"))).toBe(false);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath(`${viewport.width}-unified-service.png`)});
  await writeFile(info.outputPath("draft.json"),JSON.stringify(draft));expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
 });
 test(`studio decision chains and independent collapsible branches ${viewport.width}`,async({page},info)=>{
  await page.setViewportSize(viewport);const state=await setup(page);await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Создать услугу",exact:true}).click();
  const question=await add(page,"Вопрос","Нужен VPN?");await page.getByRole("combobox",{name:"Тип ответа",exact:true}).selectOption("checkbox");
  const first=await add(page,"Условие","Проверка доступа"), second=await add(page,"Условие","Проверка сети"), result=await add(page,"Результат","Передать в поддержку");
  await connect(page,"Нужен VPN?",first);await entrance(page,question);
  for(const [title,target] of [["Проверка доступа",second],["Проверка сети",result]]){
   await blocks(page).getByRole("button",{name:title,exact:true}).click();
   await expect(page.getByLabel("Название блока",{exact:true})).toHaveCount(1);
   await page.getByRole("combobox",{name:"Добавить условную ветвь",exact:true}).selectOption(target);
   await page.getByRole("combobox",{name:"Значение условия",exact:true}).selectOption("true");
   await page.getByRole("button",{name:/^Иначе/}).click();await page.getByRole("combobox",{name:"Если ни одно условие не выполнено",exact:true}).selectOption(result);
  }
  await page.getByRole("button",{name:"Сохранить черновик",exact:true}).click();await expect(page.getByText("Черновик сохранён. Ревизия 1.")).toBeVisible();
  const draft=state.draft(),field=draft.blocks[0].fields[0].key;
  expect(draft.blocks.find((b:any)=>b.id===first).transitions).toEqual([{to:second,when:{op:"eq",source:"answer",field,value:true}},{to:result,when:null}]);
  const writes=state.writes.length;
  const branch=page.getByRole("button",{name:/^Ветвь 1/});await expect(branch).toHaveAttribute("aria-expanded","true");
  await page.getByRole("button",{name:"Свернуть все ветви",exact:true}).click();await expect(branch).toHaveAttribute("aria-expanded","false");
  await expect(page.getByRole("combobox",{name:"Значение условия",exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Развернуть все ветви",exact:true}).click();await expect(branch).toHaveAttribute("aria-expanded","true");
  await branch.click();await expect(page.getByRole("button",{name:/^Иначе/})).toHaveAttribute("aria-expanded","true");expect(state.writes).toHaveLength(writes);
  await page.screenshot({path:info.outputPath(`${viewport.width}-decision-chain.png`)});
  expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
 });
}
