import { expect, test } from "playwright/test";
import type { ScenarioDraftDefinition, ScenarioAnswerRequest } from "../src/features/request-template-studio/scenario-contract";
import { installStudioV3Fixture } from "./fixtures/studio-v3";

for (const width of [1366,1920]) test(`new draft autosave, early screenshot and two employee routes ${width}`,async({page},info)=>{
 test.setTimeout(90000);await page.setViewportSize({width,height:width===1366?768:1080});
 const state=await installStudioV3Fixture(page);
 const original=state.definition();let draft:ScenarioDraftDefinition|null=null,revision=0,creates=0,uploads=0;const simulations:unknown[]=[];
 const response=(data:unknown)=>({json:{status:"success",data}});
 const detail=()=>({scenario:{id:"fresh",scenario_key:draft!.scenario_key,service_code:"it",offering_full_code:"it.fresh",archived:false,enabled:false,published_version_id:null,title:draft!.title},draft:{revision,definition:draft}});
 await page.route("**/api/web/notifications/push/config",r=>r.fulfill(response({enabled:false,public_key:null})));
 await page.route("**/request-studio/fragments",r=>r.fulfill(response({items:[],total:0})));
 await page.route("**/request-studio/catalog**",r=>{
  const onlyDrafts=new URL(r.request().url()).searchParams.get("status")==="draft";
  const oldOffering={full_code:"it.print",service_code:"it",public_title:original.title,request_template_key:"print",visibility:"public",lifecycle_status:"published"};
  const oldMap={id:"v3",title:original.title,offering_full_code:"it.print",archived:false,enabled:true,published_version:1,published_version_id:"published",status:"published",has_draft_changes:false,issues:[]};
  const newOffering=draft?{...oldOffering,full_code:"it.fresh",public_title:draft.title,lifecycle_status:"draft"}:null;
  const newMap=draft?{...oldMap,id:"fresh",title:draft.title,offering_full_code:"it.fresh",enabled:false,published_version:null,published_version_id:null,status:"draft",has_draft_changes:true}:null;
  const entries=[...(!onlyDrafts?[{offering:oldOffering,scenarios:[oldMap],active_mode:"scenario",category_ids:[],requester_available:true}]:[]),...(newOffering?[{offering:newOffering,scenarios:[newMap],active_mode:"form",category_ids:[],requester_available:false}]:[])];
  return r.fulfill(response({categories:[],services:[{code:"it",public_title:"ИТ",visibility:"public",lifecycle_status:"published"}],offerings:[oldOffering,...(newOffering?[newOffering]:[])],scenarios:[...(!onlyDrafts?[oldMap]:[]),...(newMap?[newMap]:[])],entries,total:entries.length,offset:0,limit:100}));
 });
 await page.route("**/request-studio/services",async r=>{
  creates++;draft=r.request().postDataJSON().definition;draft!.offering_full_code="it.fresh";draft!.process_binding.request_template_key="print";draft!.publish_offering=true;draft!.processing=structuredClone(original.processing);revision=1;
  await r.fulfill(response(detail()));
 });
 await page.route("**/scenarios/fresh/draft",async r=>{
  const body=r.request().postDataJSON();expect(body.revision).toBe(revision);draft=body.definition;revision++;await r.fulfill(response(detail()));
 });
 await page.route("**/scenarios/fresh/publish-preview", r => r.fulfill(response({
  revision, health: { health_status: "ok" }, readiness: { can_publish: false, variants_checked: 0, issues: [] },
  diff: [], outcomes: [], confirmation_token: null,
 })));
 await page.route("**/scenarios/fresh/attachments",async r=>{
  const body=r.request().postDataBuffer()!.toString();const blockId=body.match(/name="block_id"\r\n\r\n([^\r]+)/)![1],fieldKey=body.match(/name="field_key"\r\n\r\n([^\r]+)/)![1];
  expect(draft!.blocks!.some(block=>block.id===blockId&&block.kind==="form_page"&&block.fields.some(field=>field.key===fieldKey))).toBe(true);
  uploads++;await r.fulfill(response({asset_id:"11111111-1111-4111-8111-111111111111",name:"early.png",mime_type:"image/png",size_bytes:68,url:"/fixture/early.png"}));
 });
 const png=Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII=","base64");
 await page.route("**/fixture/early.png",r=>r.fulfill({contentType:"image/png",body:png}));
 await page.route("**/scenarios/fresh/simulate",async r=>{
  const body=r.request().postDataJSON();simulations.push(body);expect(body.revision).toBe(revision);expect(body.author_preview).toBe(true);
  const steps=body.steps as ScenarioAnswerRequest[];let id=draft!.entry_block_id!,answers:Record<string,unknown>={};
  for(const step of steps){expect(step.expected_block_id).toBe(id);answers={...answers,...step.answers};const block=draft!.blocks!.find(b=>b.id===id)!;id=(block.transitions?.find(edge=>edge.button?.key===step.action_key)??block.transitions?.[0])?.to??id;}
  const block=draft!.blocks!.find(b=>b.id===id)!;const current={...block,...(block.kind==="form_page"?{fields:block.fields}:{}),...(block.transition_mode==="buttons"?{actions:block.transitions?.map(edge=>edge.button)}:{})};
  await r.fulfill(response({revision,current_block:block,current_step:current,state:{current_block_id:id,revision:steps.length,answers,history:steps.map(s=>s.expected_block_id),results:{},state:"active"},processing:null,processing_error:null}));
 });
 await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Создать услугу",exact:true}).click();
 await page.getByRole("textbox",{name:"Название услуги",exact:true}).fill("Проверка автосохранения");
 await page.getByRole("button",{name:"Вернуться к карте",exact:true}).click();
 await page.getByRole("button",{name:"+ Вопрос",exact:true}).click();
 await page.getByRole("textbox",{name:"Что спросить?",exact:true}).fill("Какой путь выбрать?");
 await page.getByLabel("Прикрепить скриншоты или файлы",{exact:true}).setInputFiles({name:"early.png",mimeType:"image/png",buffer:png});
 await expect.poll(()=>uploads).toBe(1);await expect.poll(()=>draft?.blocks?.filter(b=>b.kind==="form_page")[0]?.fields[0].help_attachments?.length).toBe(1);
 expect(creates).toBe(1);expect(draft!.schema_version).toBe(4);
 const sourceId=draft!.blocks![0].id;
 await page.getByRole("button",{name:"+ Вопрос",exact:true}).click();await page.getByRole("textbox",{name:"Что спросить?",exact:true}).fill("Первый вариант");
 await expect.poll(()=>draft!.blocks!.length).toBe(2);const firstId=draft!.blocks![1].id;
 await page.getByRole("button",{name:"+ Вопрос",exact:true}).click();await page.getByRole("textbox",{name:"Что спросить?",exact:true}).fill("Второй вариант");
 await expect.poll(()=>draft!.blocks!.length).toBe(3);const secondId=draft!.blocks![2].id;
 await page.locator('.studio-map-toolbar > details > summary').click();await page.getByRole("button",{name:"Редактировать выбранный блок",exact:true}).click();await page.locator('.studio-map-toolbar > details > summary').click();await page.getByRole("button",{name:"Вся карта",exact:true}).click();
 for(const targetId of [firstId,secondId]){
  const from=page.locator(`[data-id="${sourceId}"] .react-flow__handle[data-handleid="new"]`),to=page.locator(`[data-id="${targetId}"] .react-flow__handle.target`);
  await expect(from).toBeInViewport();await expect(to).toBeInViewport();const a=(await from.boundingBox())!,b=(await to.boundingBox())!;
  await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:20});await page.mouse.up();
 }
 await expect.poll(()=>draft!.blocks!.find(b=>b.id===sourceId)?.transition_mode).toBe("buttons");
 await page.getByRole("button",{name:"Вся карта",exact:true}).click();
 for(const [index,title] of ["Первый путь","Второй путь"].entries()){
  const input=page.locator(`[data-scenario-edge="${sourceId}:${index}"] input`);await input.fill(title);await input.press("Enter");
 }
 const link=page.locator(`[data-scenario-edge="${sourceId}:0"]`);
 async function expandNearBoundary(card:ReturnType<typeof page.locator>){
  await page.getByRole("button",{name:"Вся карта",exact:true}).click();
  const canvas=page.locator('.studio-map-canvas'),c=(await canvas.boundingBox())!,node=(await card.boundingBox())!,kind=(await card.locator('.studio-map-node__kind').boundingBox())!;
  const dx=c.x+c.width-node.width-18-node.x,dy=c.y+c.height-node.height-18-node.y;
  await page.mouse.move(kind.x+5,kind.y+kind.height/2);await page.mouse.down();await page.mouse.move(kind.x+5+dx,kind.y+kind.height/2+dy,{steps:20});await page.mouse.up();
  await card.getByRole("button",{name:/^Редактировать (переход|вход)$/,exact:true}).click();
  await expect.poll(async()=>{const a=(await canvas.boundingBox())!,b=(await card.locator('.studio-resizable-editor').boundingBox())!;return b.x>=a.x+2&&b.y>=a.y+2&&b.x+b.width<=a.x+a.width-2&&b.y+b.height<=a.y+a.height-2;}).toBe(true);
  await expect(card.getByRole("button",{name:"Закрыть",exact:true})).toBeInViewport();
 }
 await expandNearBoundary(link);
 await expect(page.locator('.studio-map-popover')).toHaveCount(0);
 const corner=link.locator('[data-resize-direction="se"]');expect((await corner.boundingBox())!.width).toBeGreaterThanOrEqual(24);
 await page.screenshot({path:info.outputPath(`transition-cards-${width}.png`),fullPage:true});
 await link.getByRole("button",{name:"Закрыть",exact:true}).click();
 const entrance=page.locator('.studio-map-link-card').filter({hasText:"Вход из каталога"}).first();await expandNearBoundary(entrance);
 await expect(page.locator('.studio-map-popover')).toHaveCount(0);await entrance.getByRole("button",{name:"Закрыть",exact:true}).click();
 await page.getByRole("button",{name:"Как у сотрудника",exact:true}).click();const preview=page.getByRole("dialog",{name:"Предпросмотр полной страницы",exact:true});
 await expect(preview.getByRole("button",{name:"Первый путь",exact:true})).toBeEnabled();await expect(preview.getByRole("button",{name:"Второй путь",exact:true})).toBeEnabled();
 await preview.getByRole("textbox",{name:"Какой путь выбрать?",exact:false}).fill("Проверка");await preview.getByRole("button",{name:"Первый путь",exact:true}).click();await expect(preview.getByRole("textbox",{name:"Первый вариант",exact:false})).toBeVisible();
 await preview.getByRole("button",{name:"Назад",exact:true}).click();await preview.getByRole("button",{name:"Второй путь",exact:true}).click();await expect(preview.getByRole("textbox",{name:"Второй вариант",exact:false})).toBeVisible();
 await page.screenshot({path:info.outputPath(`interactive-employee-${width}.png`),fullPage:true});await page.getByRole("button",{name:"Вернуться к карте",exact:true}).click();
 await page.getByRole("button",{name:"Каталог",exact:true}).click();await page.getByRole("button",{name:"Черновики",exact:true}).click();
 await expect(page.getByRole("button",{name:"Настроить услугу Проверка автосохранения",exact:true})).toBeVisible();await expect(page.getByRole("button",{name:"Настроить услугу Проблемы с печатью",exact:true})).toHaveCount(0);
 expect(creates).toBe(1);expect(simulations.length).toBeGreaterThanOrEqual(4);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
});
