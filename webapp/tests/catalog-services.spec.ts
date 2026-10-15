import {expect,test,type Page} from "playwright/test";
async function fixture(page:Page,archived=false){
 const errors:string[]=[],failures:string[]=[],writes:any[]=[];
 page.on("pageerror",error=>errors.push(error.message));page.on("console",message=>{if(message.type()==="error")errors.push(message.text());});page.on("requestfailed",request=>failures.push(`${request.method()} ${new URL(request.url()).pathname}`));page.on("response",response=>{if(response.status()>=400)failures.push(`${response.status()} ${new URL(response.url()).pathname}`);});
 const section={code:"work",public_title:"Рабочее место",lifecycle_status:"published",visibility:"public"};
 const offering:any={code:"print",full_code:"work.print",service_code:"work",public_title:"Проблемы с печатью",short_description:"Помощь с принтером",lifecycle_status:"published",visibility:"public",request_template_key:"printer",request_type:"incident",metadata:{private_note:"preserve",studio_catalog:{synonyms:["принтер"]}}};
 let definition:any={schema_version:2,scenario_key:"print",service_code:"work",offering_full_code:"work.print",title:"Общая диагностика печати",process_binding:{request_template_key:"printer"},entry_block_id:"q",blocks:[{id:"q",kind:"instruction",title:"Проверка принтера",content:{body:"Проверьте питание"},transitions:[{to:"done"}]},{id:"done",kind:"finish",title:"Готово",message:"Готово"}],entry_points:[{key:"paper",title:"Застряла бумага",description:"Замятие в принтере",target_block_id:"q",synonyms:["замятие"],visibility:"public",enabled:true}]};
 let revision=2;
 const category={id:"10000000-0000-0000-0000-000000000001",service_code:"work",parent_id:null,title:"Принтеры и МФУ",slug:"printers",description:"",revision:1,visibility:"public",lifecycle_status:"published",sort_order:0};
 await page.route("**/api/web/**",async route=>{
  const path=new URL(route.request().url()).pathname,method=route.request().method();let data:any={};
  const map={id:"s1",...definition,archived,enabled:false,revision,status:archived?"archived":"draft",issues:[],category_id:definition.category_id??null,entry_points:definition.entry_points,published_entry_points:[],published_public_entry_keys:[]};
  if(path.endsWith("/session/me"))data={user_login:"studio-fixture@example.test",actor_role:"admin",auth_type:"web_session",default_workspace:"admin",available_workspaces:["admin"],permissions:["workspace.admin.view"]};
  else if(path.endsWith("/request-studio/catalog"))data={services:[section],categories:[category],offerings:[offering],scenarios:[map],entries:[{offering,scenarios:[map],active_mode:"form",requester_available:offering.visibility==="public",category_ids:offering.metadata.studio_catalog.category_id?[category.id]:[]}],total:1,limit:100,offset:0};
  else if(path.endsWith("/offerings/save-draft")){const body=route.request().postDataJSON();writes.push({path,body});Object.assign(offering,body);await route.fulfill({json:{status:"ok",offering}});return;}
  else if(path.endsWith("/helpdesk-model/policies"))data={request_templates:[{template_code:"printer",public_title:"Проблема с принтером",is_active:true,published_at:"2026-10-13T00:00:00Z"}],policies:{}};
  else if(path.endsWith("/draft")){const body=route.request().postDataJSON();expect(body.revision).toBe(revision);writes.push({path,body});definition=body.definition;revision++;data={scenario:map,draft:{revision,definition}};}
  else if(path.endsWith("/scenarios/s1"))data={scenario:map,draft:{revision,definition}};
  else if(path.endsWith("/categories")){const body=route.request().postDataJSON();writes.push({path,body});data={...category,...body,id:"10000000-0000-0000-0000-000000000002",revision:1};}
  else if(path.endsWith("unread_count")){await route.fulfill({json:{status:"ok",unread_count:0}});return;}
  await route.fulfill({json:{status:"success",data}});
 });
 return{errors,failures,writes,offering};
}
async function openMap(page:Page){await page.getByRole("button",{name:"Настроить услугу Общая диагностика печати",exact:true}).click();await page.getByRole("button",{name:"Открыть карту сценария",exact:true}).click();}
async function settings(page:Page){await page.getByRole("button",{name:"Настройки карты",exact:true}).first().click();}
async function saveMap(page:Page,revision:number){const save=page.getByRole("button",{name:"Сохранить черновик",exact:true});if(await save.isEnabled())await save.click();await expect(page.getByText(`Черновик сохранён. Ревизия ${revision}.`,{exact:true})).toBeVisible();}
async function editEntrance(page:Page,title:string){await page.getByRole("button",{name:"Вся карта",exact:true}).click();await page.getByRole("textbox",{name:"Название входа «Застряла бумага»",exact:true}).click();await page.getByLabel("Название пункта",{exact:true}).fill(title);}
for(const viewport of [{width:1366,height:768},{width:1920,height:1080},{width:820,height:1180}]){
 test(`unified catalog service settings and map return ${viewport.width}`,async({page},info)=>{
  await page.setViewportSize(viewport);const state=await fixture(page);await page.goto("/app/admin/request-template-studio");
  const create=page.getByRole("button",{name:"Создать услугу",exact:true});await expect(create).toBeVisible();expect((await create.boundingBox())!.y).toBeLessThan(viewport.height);
  await expect(page.getByRole("tab",{name:"Карты сценариев"})).toHaveCount(0);
  const tree=page.getByRole("navigation",{name:"Категории услуг"});
  await expect(tree.getByRole("button",{name:"Услуга Общая диагностика печати · Сценарий",exact:true})).toBeVisible();
  await expect(tree.getByRole("button",{name:"↳ Застряла бумага",exact:true})).toBeVisible();
  await expect(page.getByRole("region",{name:"Каталог услуг",exact:true}).getByRole("button",{name:/^Настроить услугу /})).toHaveCount(1);
  await expect(page.getByRole("button",{name:"Настроить услугу Застряла бумага",exact:true})).toHaveCount(0);
  await openMap(page);await settings(page);
  await expect(page.getByLabel("Название услуги",{exact:true})).toHaveValue("Общая диагностика печати");
  await page.getByRole("combobox",{name:"Категория (необязательно)",exact:true}).selectOption("10000000-0000-0000-0000-000000000001");
  await saveMap(page,3);
  expect(state.writes[0].body.definition).toMatchObject({offering_full_code:"work.print",category_id:"10000000-0000-0000-0000-000000000001",process_binding:{request_template_key:"printer"},entry_points:[{key:"paper",category_id:"10000000-0000-0000-0000-000000000001",synonyms:["замятие"]}]});
  expect(state.offering.metadata).toEqual({private_note:"preserve",studio_catalog:{synonyms:["принтер"]}});
  await expect(page.getByRole("heading",{name:"Библиотека блоков"})).toBeVisible();await expect(page.getByRole("tab",{name:"Каталог",exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Каталог",exact:true}).click();await expect(page.getByRole("button",{name:"Создать услугу",exact:true})).toBeVisible();await expect(page.getByLabel("Визуальная карта сценария",{exact:true})).toHaveCount(0);
  await expect(tree.getByRole("button",{name:"Принтеры и МФУ",exact:true})).toBeVisible();
  await openMap(page);await editEntrance(page,"Бумага застряла в принтере");
  await page.getByText("Поиск в каталоге",{exact:true}).click();await page.getByRole("textbox",{name:"Дополнительные поисковые выражения",exact:true}).fill("замятие\nпечать");await saveMap(page,4);
  expect(state.writes[1].body.definition.offering_full_code).toBe("work.print");expect(state.writes[1].body.definition.entry_points[0]).toMatchObject({title:"Бумага застряла в принтере",description:"Замятие в принтере",target_block_id:"q",synonyms:["замятие","печать"]});
  await page.getByRole("button",{name:"Каталог",exact:true}).click();await page.reload();await expect(tree.getByRole("button",{name:"↳ Бумага застряла в принтере",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Настроить услугу Общая диагностика печати",exact:true}).click();
  if(viewport.width>1100){const resize=page.getByRole("separator",{name:"Ширина структуры каталога"});await resize.focus();await page.keyboard.press("ArrowRight");}
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole("heading",{name:"Каталог услуг",exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath(`catalog-${viewport.width}.png`),fullPage:viewport.width<1100});
  expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);expect(state.writes).toHaveLength(2);
 });
}
test("create another entrance on the service map without creating another Offering",async({page})=>{
 const state=await fixture(page);await page.goto("/app/admin/request-template-studio");await openMap(page);await settings(page);
 await page.getByText("Подключить вход с клавиатуры",{exact:true}).click();await page.getByRole("combobox",{name:"Первый шаг",exact:true}).selectOption("done");await saveMap(page,3);
 expect(state.writes).toHaveLength(1);expect(state.writes[0].path).toContain("/scenarios/s1/draft");expect(state.writes[0].body.definition.entry_points).toHaveLength(2);expect(state.writes[0].body.definition.entry_points[1]).toMatchObject({title:"Готово",target_block_id:"done"});
 await page.getByRole("button",{name:"Каталог",exact:true}).click();const tree=page.getByRole("navigation",{name:"Категории услуг"});await expect(tree.getByRole("button",{name:"↳ Готово",exact:true})).toBeVisible();await expect(page.getByRole("button",{name:/^Настроить услугу /})).toHaveCount(1);expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
});
test("cancel keeps section edits and confirmed discard resets the inspector on a matching search",async({page})=>{
 const state=await fixture(page);await page.goto("/app/admin/request-template-studio");
 await page.getByRole("button",{name:"Изменить раздел Рабочее место",exact:true}).click();
 await page.getByLabel("Название раздела",{exact:true}).fill("Несохранённое название");
 page.once("dialog",dialog=>dialog.dismiss());await page.getByRole("button",{name:"Создать услугу",exact:true}).click();
 await expect(page.getByLabel("Название раздела",{exact:true})).toHaveValue("Несохранённое название");
 page.once("dialog",dialog=>dialog.accept());await page.getByLabel("Поиск услуг",{exact:true}).fill("печати");
 await expect(page.getByLabel("Название раздела",{exact:true})).toHaveValue("Рабочее место");
 await expect(page.getByRole("button",{name:"Настроить услугу Общая диагностика печати",exact:true})).toBeVisible();
 expect(state.writes).toHaveLength(0);expect(state.errors).toEqual([]);
});

test("a tree entrance opens its own map at its target and asks before discarding changes",async({page})=>{
 const state=await fixture(page);await page.goto("/app/admin/request-template-studio");
 const tree=page.getByRole("navigation",{name:"Категории услуг"});
 await tree.getByRole("button",{name:"↳ Застряла бумага",exact:true}).click();
 await expect(page.locator('.react-flow__node[data-id="q"] .studio-map-node')).toHaveClass(/is-selected/);
 await editEntrance(page,"Несохранённая бумага");await page.getByRole("button",{name:"Каталог",exact:true}).click();
 await expect(page.getByText("Уйти без сохранения локальных изменений?",{exact:true})).toBeVisible();await page.getByRole("button",{name:"Отмена",exact:true}).click();await expect(page.getByLabel("Название пункта",{exact:true})).toHaveValue("Несохранённая бумага");
 await page.getByRole("button",{name:"Каталог",exact:true}).click();await page.getByRole("button",{name:"Уйти без сохранения",exact:true}).click();
 await expect(tree.getByRole("button",{name:"↳ Застряла бумага",exact:true})).toBeVisible();await tree.getByRole("button",{name:"↳ Застряла бумага",exact:true}).click();await editEntrance(page,"Застряла бумага");
 expect(state.writes).toHaveLength(0);expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
});

test("legacy forms convert to a draft map and new services use only map creation",async({page})=>{
 const state=await fixture(page);
 const offering={full_code:"work.form",code:"form",service_code:"work",public_title:"Обычная заявка",request_template_key:"printer",visibility:"public",lifecycle_status:"published"};
 await page.route("**/api/web/admin/request-studio/catalog?**",route=>route.fulfill({json:{status:"success",data:{services:[{code:"work",public_title:"Рабочее место"}],categories:[],offerings:[offering],entries:[{offering,scenarios:[],active_mode:"form",category_ids:[]}],scenarios:[],total:1,offset:0,limit:100}}}));
 const convertedDefinition={schema_version:2,scenario_key:"form",title:"Обычная заявка",service_code:"work",offering_full_code:"work.form",process_binding:{request_template_key:"printer"},entry_block_id:"question",entry_points:[{key:"main",title:"Обычная заявка",target_block_id:"question"}],blocks:[{id:"question",kind:"form_page",title:"Вопросы формы",fields:[{key:"details",type:"text",label:"Опишите проблему"}],transitions:[{to:"submit"}]},{id:"submit",kind:"submit_ticket",title:"Создание обращения"}]};
 await page.route("**/api/web/admin/request-studio/convert-forms",async route=>{
  const body=route.request().postDataJSON();state.writes.push({path:new URL(route.request().url()).pathname,body});
  await route.fulfill({json:{status:"success",data:{items:[{offering_full_code:"work.form",status:"converted",detail:{scenario:{id:"converted",archived:false},draft:{revision:1,definition:convertedDefinition}}}]}}});
 });
 await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Услуга Обычная заявка · Ожидает переноса",exact:true}).click();
 await expect(page.getByRole("button",{name:/Открыть карту сценария/})).toHaveCount(0);
 await page.getByRole("button",{name:"Перенести в сценарий",exact:true}).click();await expect(page.getByLabel("Название услуги",{exact:true})).toHaveValue("Обычная заявка");await page.getByRole("list",{name:"Блоки сценария",exact:true}).getByRole("button",{name:"Вопросы формы",exact:true}).click();await page.getByRole("tab",{name:"Как у сотрудника",exact:true}).click();await expect(page.getByLabel("Опишите проблему",{exact:true})).toBeVisible();
 expect(state.writes).toHaveLength(1);expect(state.writes[0].body).toEqual({apply:true,offering_full_code:"work.form"});
 await page.getByRole("button",{name:"Каталог",exact:true}).click();await page.getByRole("button",{name:"Создать услугу",exact:true}).click();await expect(page.getByLabel("Название услуги",{exact:true})).toHaveValue("Новая услуга");await expect(page.locator(".react-flow__node")).toHaveCount(1);
 await expect(page.getByRole("combobox",{name:"Способ помощи",exact:true})).toHaveCount(0);await expect(page.getByRole("link",{name:"Создать шаблон",exact:true})).toHaveCount(0);
 expect(state.writes).toHaveLength(1);expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
});

test("each service entrance opens its own map instead of another service map",async({page})=>{
 const state=await fixture(page),opened:string[]=[];
 const secondOffering={...state.offering,full_code:"work.scan",code:"scan",public_title:"Сканирование"};
 const secondDefinition={schema_version:2,scenario_key:"scan",service_code:"work",offering_full_code:"work.scan",title:"Карта сканирования",process_binding:{request_template_key:"printer"},entry_block_id:"scan",entry_points:[{key:"scan",title:"Не сканирует",target_block_id:"scan"}],blocks:[{id:"scan",kind:"instruction",title:"Проверка сканера",content:{body:"Проверьте соединение"},transitions:[]}]};
 const firstMap={id:"s1",title:"Общая диагностика печати",service_code:"work",offering_full_code:"work.print",archived:false,status:"draft",entry_points:[{key:"paper",title:"Застряла бумага",target_block_id:"q"}]},secondMap={...secondDefinition,id:"s2",archived:false,status:"draft"};
 await page.route("**/api/web/admin/request-studio/catalog?**",route=>route.fulfill({json:{status:"success",data:{services:[{code:"work",public_title:"Рабочее место"}],categories:[],offerings:[state.offering,secondOffering],scenarios:[firstMap,secondMap],entries:[{offering:state.offering,scenarios:[firstMap],active_mode:"scenario",category_ids:[]},{offering:secondOffering,scenarios:[secondMap],active_mode:"scenario",category_ids:[]}],total:2,offset:0,limit:100}}}));
 await page.route("**/api/web/admin/request-studio/scenarios/s2",route=>route.fulfill({json:{status:"success",data:{scenario:secondMap,draft:{revision:1,definition:secondDefinition}}}}));
 page.on("request",request=>{if(/\/scenarios\/s[12]$/.test(new URL(request.url()).pathname))opened.push(new URL(request.url()).pathname.split("/").at(-1)!);});
 await page.goto("/app/admin/request-template-studio");const tree=page.getByRole("navigation",{name:"Категории услуг"});await tree.getByRole("button",{name:"↳ Не сканирует",exact:true}).click();
 await expect(page.locator('.react-flow__node[data-id="scan"] .studio-map-node')).toHaveClass(/is-selected/);await settings(page);await expect(page.getByLabel("Название услуги",{exact:true})).toHaveValue("Карта сканирования");
 await page.getByRole("button",{name:"Каталог",exact:true}).click();await tree.getByRole("button",{name:"↳ Застряла бумага",exact:true}).click();await expect(page.locator('.react-flow__node[data-id="q"] .studio-map-node')).toHaveClass(/is-selected/);
 expect(opened).toEqual(["s2","s1"]);expect(state.writes).toHaveLength(0);expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
});

test("blocked legacy conversion retains the original service and offers no publication",async({page})=>{
 const state=await fixture(page),offering=state.offering;
 await page.route("**/api/web/admin/request-studio/catalog?**",route=>route.fulfill({json:{status:"success",data:{services:[{code:"work",public_title:"Рабочее место"}],categories:[],offerings:[offering],scenarios:[],entries:[{offering,scenarios:[],active_mode:"form",category_ids:[]}],total:1,offset:0,limit:100}}}));
 await page.route("**/api/web/admin/request-studio/convert-forms",async route=>{state.writes.push({path:new URL(route.request().url()).pathname,body:route.request().postDataJSON()});await route.fulfill({json:{status:"success",data:{items:[{offering_full_code:offering.full_code,status:"blocked",issues:[{code:"unsupported_field",message:"Требуется ручная проверка вопросов формы."}]}]}}});});
 await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Настроить услугу Проблемы с печатью",exact:true}).click();await page.getByRole("button",{name:"Перенести в сценарий",exact:true}).click();
 await expect(page.getByText("Требуется ручная проверка вопросов формы.",{exact:true})).toBeVisible();await expect(page.getByRole("button",{name:"Настроить услугу Проблемы с печатью",exact:true})).toBeVisible();await expect(page.getByLabel("Визуальная карта сценария",{exact:true})).toHaveCount(0);await expect(page.getByRole("button",{name:"Опубликовать",exact:true})).toHaveCount(0);
 expect(state.writes).toHaveLength(1);expect(state.writes[0].body).toEqual({apply:true,offering_full_code:"work.print"});expect(state.offering.lifecycle_status).toBe("published");expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
});

test("auditor can open an archived map from service help without edit controls",async({page})=>{
 const state=await fixture(page,true);
 await page.route("**/api/web/session/me",route=>route.fulfill({json:{status:"success",data:{user_login:"audit@example.test",actor_role:"auditor",auth_type:"web_session",default_workspace:"admin",available_workspaces:["admin"],permissions:["workspace.admin.view"]}}}));
 const offering={full_code:"work.print",code:"print",service_code:"work",public_title:"Печать",request_template_key:"printer"},map={id:"s1",title:"Архив печати",offering_full_code:"work.print",archived:true,status:"archived"};
 await page.route("**/api/web/admin/request-studio/catalog?**",route=>route.fulfill({json:{status:"success",data:{services:[{code:"work",public_title:"Рабочее место"}],categories:[],offerings:[offering],entries:[{offering,scenarios:[map],active_mode:"form",category_ids:[]}],scenarios:[map],total:1,offset:0,limit:100}}}));
 await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Настроить услугу Печать",exact:true}).click();
 await expect(page.getByRole("button",{name:"Создать услугу",exact:true})).toHaveCount(0);await page.getByText("Архив карт услуги",{exact:true}).click();await page.getByRole("button",{name:"Открыть архивную карту",exact:true}).click();
 await settings(page);await expect(page.getByLabel("Название услуги",{exact:true})).toBeDisabled();
 await expect(page.getByRole("heading",{name:"Библиотека блоков",exact:true})).toBeVisible();await expect(page.getByRole("button",{name:"Сохранить черновик",exact:true})).toHaveCount(0);
 expect(state.writes).toHaveLength(0);expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
});
