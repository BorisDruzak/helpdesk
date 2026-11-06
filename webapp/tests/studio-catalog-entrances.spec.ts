import { expect, test } from "playwright/test";
import { installStudioV3Fixture } from "./fixtures/studio-v3";

for (const width of [1366,1920]) test(`Start-only catalog entrances preserve legacy map ${width}`,async({page},info)=>{
 test.setTimeout(60000);await page.setViewportSize({width,height:width===1366?768:1080});
 const state=await installStudioV3Fixture(page),before=structuredClone(state.definition());
 await page.route("**/api/web/notifications/push/config",r=>r.fulfill({json:{status:"ok",enabled:false,public_key:null}}));
 await page.route("**/request-studio/fragments",r=>r.fulfill({json:{status:"success",data:{items:[],total:0}}}));
 await page.route("**/scenarios/v3/simulate",r=>{
  const body=r.request().postDataJSON();expect(body.author_preview).toBe(true);
  const d=state.definition(),id=d.entry_points?.find(e=>e.key===body.entry_point_key)?.target_block_id??d.entry_block_id;
  return r.fulfill({json:{status:"success",data:{state:{revision:1,current_block_id:id,history:[],answers:{},results:{}},current_step:d.blocks?.find(b=>b.id===id)}}});
 });
 await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Настроить услугу Проблемы с печатью",exact:true}).dblclick();
 for(const [target,title] of [["q2","Сразу к масштабу"],["q3","Сразу к возможности работать"]]){
  await page.getByRole("button",{name:"+ Вход из каталога",exact:true}).click();
  const form=page.getByRole("dialog",{name:"Новый вход из каталога",exact:true});
  await expect(form).toContainText("Всегда подключён к блоку «Начало»");await expect(form.getByRole("button",{name:"Создать вход от «Начала»"})).toBeDisabled();
  await form.getByRole("combobox",{name:"Первый блок для сотрудника",exact:true}).selectOption(target);await form.getByLabel("Название входа",{exact:true}).fill(title);await form.getByRole("button",{name:"Создать вход от «Начала»"}).click();
  await expect(page.getByRole("status").filter({hasText:"Черновик сохранён"})).toBeVisible();
  const entry=state.definition().entry_points!.find(e=>e.title===title)!;expect(entry.target_block_id).toBe(target);
  const rootEdge=page.locator(`.react-flow__edge[data-id="studio:entry-point:${entry.key}:input"]`);await expect(rootEdge).toHaveCount(1);
  const card=page.locator(`[data-scenario-edge="studio:entry-point:${entry.key}"]`);await expect(card).toContainText("Вход из каталога");await expect(card.getByRole("combobox",{name:"Первый блок для сотрудника",exact:true})).toHaveValue(target);
  await expect(page.locator('.studio-map-popover')).toHaveCount(0);
 }
 const saved=state.definition();expect(saved.blocks).toEqual(before.blocks);expect(saved.schema_version).toBe(3);expect(saved.entry_block_id).toBe(before.entry_block_id);expect(saved.entry_points!.slice(0,2)).toEqual(before.entry_points);
 expect(saved.entry_points).toHaveLength(4);await page.screenshot({path:info.outputPath(`catalog-entrance-${width}.png`),fullPage:true});
 await page.reload();await page.getByRole("button",{name:"Настроить услугу Проблемы с печатью",exact:true}).dblclick();await page.getByRole("button",{name:"Как у сотрудника",exact:true}).click();
 const preview=page.getByRole("dialog",{name:"Предпросмотр полной страницы",exact:true});await preview.getByRole("combobox",{name:"Вход из каталога",exact:true}).selectOption(saved.entry_points![2].key);await expect(preview.getByRole("radio",{name:"Весь отдел",exact:true})).toBeVisible();
 await preview.getByRole("combobox",{name:"Вход из каталога",exact:true}).selectOption(saved.entry_points![3].key);await expect(preview.getByRole("radio",{name:"Нет",exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
});
