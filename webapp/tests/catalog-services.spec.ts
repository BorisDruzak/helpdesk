import {expect,test,type Page} from "playwright/test";
async function fixture(page:Page){
 const errors:string[]=[],failures:string[]=[],writes:any[]=[];
 page.on("pageerror",error=>errors.push(error.message));page.on("response",response=>{if(response.status()>=400)failures.push(`${response.status()} ${new URL(response.url()).pathname}`);});
 const section={code:"work",public_title:"Рабочее место",lifecycle_status:"published",visibility:"public"};
 const offering:any={code:"print",full_code:"work.print",service_code:"work",public_title:"Проблемы с печатью",short_description:"Помощь с принтером",lifecycle_status:"published",visibility:"public",request_template_key:"printer",request_type:"incident",metadata:{private_note:"preserve",studio_catalog:{synonyms:["принтер"]}}};
 let definition:any={schema_version:1,scenario_key:"print",service_code:"work",offering_full_code:"work.print",title:"Общая диагностика печати",process_binding:{request_template_key:"printer"},entry_block_id:"q",blocks:[{id:"q",kind:"instruction",title:"Проверка принтера",content:{body:"Проверьте питание"},transitions:[{to:"done"}]},{id:"done",kind:"finish",title:"Готово",message:"Готово"}],entry_points:[{key:"paper",title:"Застряла бумага",description:"Замятие в принтере",target_block_id:"q",synonyms:["замятие"],visibility:"public",enabled:true}]};
 let revision=2;
 const category={id:"10000000-0000-0000-0000-000000000001",service_code:"work",parent_id:null,title:"Принтеры и МФУ",slug:"printers",description:"",revision:1,visibility:"public",lifecycle_status:"published",sort_order:0};
 await page.route("**/api/web/**",async route=>{
  const path=new URL(route.request().url()).pathname,method=route.request().method();let data:any={};
  const map={id:"s1",...definition,archived:false,enabled:false,revision,status:"draft",issues:[],category_id:null,entry_points:definition.entry_points,published_entry_points:[],published_public_entry_keys:[]};
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
 return{errors,failures,writes};
}
for(const viewport of [{width:1366,height:768},{width:1920,height:1080},{width:820,height:1180}]){
 test(`unified catalog service settings and map return ${viewport.width}`,async({page},info)=>{
  await page.setViewportSize(viewport);const state=await fixture(page);await page.goto("/app/admin/request-template-studio");
  const create=page.getByRole("button",{name:"Создать услугу",exact:true});await expect(create).toBeVisible();expect((await create.boundingBox())!.y).toBeLessThan(viewport.height);
  await expect(page.getByRole("region",{name:"Карты сценариев"})).toHaveCount(0);
  await page.getByRole("button",{name:"Настроить услугу Проблемы с печатью"}).click();
  const inspector=page.getByRole("complementary",{name:"Настройки услуги"});await expect(inspector.getByLabel("Название услуги")).toHaveValue("Проблемы с печатью");
  await inspector.getByLabel("Категория (необязательно)").selectOption("10000000-0000-0000-0000-000000000001");
  await inspector.getByLabel("Слова для поиска").fill("принтер\nпечать");await inspector.getByRole("button",{name:"Сохранить",exact:true}).click();await expect(inspector.getByText("Настройки услуги сохранены.")).toBeVisible();
  expect(state.writes[0].body.metadata).toEqual({private_note:"preserve",studio_catalog:{category_id:"10000000-0000-0000-0000-000000000001",synonyms:["принтер","печать"]}});
  await inspector.getByRole("tab",{name:"Помощь сотруднику"}).click();await inspector.getByRole("button",{name:"Открыть карту",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Библиотека блоков"})).toBeVisible();await expect(page.getByRole("tab",{name:"Каталог",exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Каталог",exact:true}).click();await expect(page.getByRole("button",{name:"Создать услугу",exact:true})).toBeVisible();await expect(page.getByLabel("Визуальная карта сценария",{exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Настроить услугу Застряла бумага"}).click();await inspector.getByLabel("Название услуги").fill("Бумага застряла в принтере");await inspector.getByRole("button",{name:"Сохранить",exact:true}).click();await expect(inspector.getByText(/Черновик пункта сохранён/)).toBeVisible();
  expect(state.writes[1].body.definition.offering_full_code).toBe("work.print");expect(state.writes[1].body.definition.entry_points[0].title).toBe("Бумага застряла в принтере");
  await page.reload();await expect(page.getByRole("button",{name:"Настроить услугу Бумага застряла в принтере"})).toBeVisible();
  await page.getByRole("button",{name:"Настроить услугу Проблемы с печатью"}).click();
  if(viewport.width>1100){const resize=page.getByRole("separator",{name:"Ширина структуры каталога"});await resize.focus();await page.keyboard.press("ArrowRight");}
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole("heading",{name:"Каталог услуг",exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath(`catalog-${viewport.width}.png`),fullPage:viewport.width<1100});
  expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);expect(state.writes).toHaveLength(2);
 });
}
test("create another service as an entrance without creating another Offering",async({page})=>{
 const state=await fixture(page);await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Создать услугу",exact:true}).click();await page.getByRole("combobox",{name:"Способ помощи",exact:true}).selectOption("entry");await page.getByRole("combobox",{name:"Карта сценария",exact:true}).selectOption("s1");await page.getByLabel("Название новой услуги").fill("Бледная печать");await page.getByRole("combobox",{name:"Точка входа",exact:true}).selectOption("q");await page.getByRole("button",{name:"Создать черновик пункта"}).click();await expect(page.getByRole("button",{name:"Настроить услугу Бледная печать"})).toBeVisible();expect(state.writes).toHaveLength(1);expect(state.writes[0].path).toContain("/scenarios/s1/draft");expect(state.writes[0].body.definition.entry_points).toHaveLength(2);expect(state.errors).toEqual([]);expect(state.failures).toEqual([]);
});
test("cancel keeps edits and confirmed discard resets the inspector on a matching search",async({page})=>{
 const state=await fixture(page);await page.goto("/app/admin/request-template-studio");
 await page.getByRole("button",{name:"Настроить услугу Проблемы с печатью"}).click();
 await page.getByLabel("Название услуги",{exact:true}).fill("Несохранённое название");
 page.once("dialog",dialog=>dialog.dismiss());await page.getByRole("tab",{name:"Карты сценариев",exact:true}).click();
 await expect(page.getByLabel("Название услуги",{exact:true})).toHaveValue("Несохранённое название");
 page.once("dialog",dialog=>dialog.accept());await page.getByLabel("Поиск услуг",{exact:true}).fill("Проблемы");
 await expect(page.getByLabel("Название услуги",{exact:true})).toHaveValue("Проблемы с печатью");
 expect(state.writes).toHaveLength(0);expect(state.errors).toEqual([]);
});
