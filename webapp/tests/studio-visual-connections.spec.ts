import type { ScenarioDraftDefinition } from "../src/features/request-template-studio/scenario-contract";
import { expect,test,type Page,type Locator } from "playwright/test";
import { installStudioV3Fixture } from "./fixtures/studio-v3";
async function emptyPoint(page:Page){return page.locator('.studio-map-canvas').evaluate(e=>{const r=e.getBoundingClientRect();for(const [fx,fy]of[[.8,.15],[.75,.8],[.25,.18],[.2,.8],[.5,.5]]){const x=r.x+r.width*fx,y=r.y+r.height*fy,t=document.elementFromPoint(x,y);if(t?.closest('.studio-map-canvas')===e&&!t.closest('.react-flow__node,.react-flow__edge,.studio-map-context,.studio-map-empty'))return{x,y};}throw new Error('No empty canvas drop');});}
async function drag(page:Page,from:Locator,to:{x:number;y:number}|Locator){const hit=await from.evaluate(e=>{const r=e.getBoundingClientRect(),top=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {ok:top===e||!!top&&e.contains(top),coveredBy:top?.className};});expect(hit,JSON.stringify(hit)).toMatchObject({ok:true});const a=await from.boundingBox();expect(a).not.toBeNull();const b='boundingBox'in to?await to.boundingBox():null;const end=b?{x:b.x+b.width/2,y:b.y+b.height/2}:to as{x:number;y:number};await page.mouse.move(a!.x+a!.width/2,a!.y+a!.height/2);await page.mouse.down();await page.mouse.move(end.x,end.y,{steps:16});await page.mouse.up();}
async function dragEmpty(page:Page,from:Locator){
 let previous="";await expect.poll(async()=>{const r=await from.boundingBox();const current=r?JSON.stringify([r.x,r.y,r.width,r.height].map(n=>Math.round(n))):"";const stable=!!current&&current===previous;previous=current;return stable;}).toBe(true);
 await drag(page,from,await emptyPoint(page));
}
async function setup(page:Page,width:number,mutate?:(d:ScenarioDraftDefinition)=>void){await page.setViewportSize({width,height:width===1366?768:1080});const state=await installStudioV3Fixture(page);mutate?.(state.definition());await page.route('**/api/web/notifications/push/config',r=>r.fulfill({json:{status:'ok',enabled:false,public_key:null}}));await page.route('**/request-studio/fragments',r=>r.fulfill({json:{status:'success',data:{items:[],total:0}}}));await page.goto('/app/admin/request-template-studio');await page.getByRole('button',{name:'Настроить услугу Проблемы с печатью',exact:true}).dblclick();await page.getByRole('button',{name:'Вся карта',exact:true}).click();return state;}
const port=(page:Page,node:string,handle='new')=>page.locator(`.react-flow__handle[data-nodeid="${node}"][data-handleid="${handle}"]`);
test('empty map starts visually and pending deletion/undo persists before connection',async({page})=>{
 test.setTimeout(60000);const state=await setup(page,1366,d=>{d.schema_version=4;d.execution_semantics=3;d.blocks=[];d.entry_points=[];d.entry_block_id=null;d.editor_layout={positions:{}};});
 await page.getByRole('complementary',{name:'Библиотека блоков'}).getByRole('button',{name:'+ Вход из каталога',exact:true}).click();
 await expect.poll(()=>state.definition().editor_layout?.pending_entrances?.length).toBe(1);const entry=state.definition().editor_layout!.pending_entrances![0];
 await page.getByRole('button',{name:'Удалить незавершённый вход',exact:true}).click();await expect.poll(()=>state.definition().editor_layout?.pending_entrances?.length).toBe(0);await page.getByRole('button',{name:'Отменить изменение',exact:true}).click();await expect.poll(()=>state.definition().editor_layout?.pending_entrances?.[0]?.key).toBe(entry.key);
 await page.getByRole('button',{name:'Вся карта',exact:true}).click();await dragEmpty(page,port(page,`studio:link:entry:named:${entry.key}`,'out'));await page.getByRole('menu',{name:'Добавить на конец связи'}).getByRole('menuitem',{name:'Вопрос',exact:true}).click();
 await expect.poll(()=>state.definition().blocks?.length).toBe(1);expect(state.definition().entry_points?.[0].key).toBe(entry.key);expect(state.definition().entry_block_id).toBe(state.definition().blocks![0].id);expect(state.definition().editor_layout?.pending_entrances??[]).toHaveLength(0);expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
});
test('answer handle creates typed condition and route-card insertion preserves continuation',async({page})=>{
 test.setTimeout(60000);const state=await setup(page,1920,d=>{d.schema_version=4;d.execution_semantics=3;});
 await page.getByRole('list',{name:'Блоки сценария',exact:true}).getByRole('button',{name:'Выбрать обработку',exact:true}).click();
 await dragEmpty(page,port(page,'logic','answer-0'));await page.getByRole('menu',{name:'Добавить на конец связи'}).getByRole('menuitem',{name:'Инструкция',exact:true}).click();await expect.poll(()=>state.definition().blocks?.length).toBe(6);
 const branch=state.definition().blocks!.find(b=>b.id==='logic')!.transitions!.find(e=>e.to===state.definition().blocks!.at(-1)!.id)!;expect(branch.when).toEqual({source:'answer',field:'work',op:'eq',value:'blocked'});
 await page.getByRole('button',{name:'Свернуть редактор',exact:true}).click();await page.getByRole('button',{name:'Вся карта',exact:true}).click();
 await dragEmpty(page,port(page,'studio:link:route:q1:0','out'));const menu=page.getByRole('menu',{name:'Добавить на конец связи'});await expect(menu.getByRole('menuitem',{name:'Результат',exact:true})).toHaveCount(0);await menu.getByRole('menuitem',{name:'Инструкция',exact:true}).click();await expect.poll(()=>state.definition().blocks?.length).toBe(7);
 expect(state.definition().blocks!.find(b=>b.id==='q1')!.transitions![0].to).toBe(state.definition().blocks!.at(-1)!.id);expect(state.definition().blocks!.at(-1)!.transitions).toEqual([{to:'q2'}]);
 await page.getByRole('button',{name:'Отменить изменение',exact:true}).click();await expect.poll(()=>state.definition().blocks?.length).toBe(6);expect(state.definition().blocks!.find(b=>b.id==='q1')!.transitions![0].to).toBe('q2');expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
});
for(const width of [1366,1920]){
 test(`independent catalogue entrance, pending autosave/reload and completion ${width}`,async({page},info)=>{
  test.setTimeout(90000);const state=await setup(page,width),before=structuredClone(state.definition());
  await page.getByRole('complementary',{name:'Библиотека блоков'}).getByRole('button',{name:'+ Вход из каталога',exact:true}).click();
  const menu=page.getByRole('menu',{name:'Добавить на конец связи',exact:true});
  await expect(page.getByRole('combobox',{name:'Первый блок для сотрудника',exact:true})).toHaveCount(0);
  await expect.poll(()=>state.definition().editor_layout?.pending_entrances?.length).toBe(1);const pending=state.definition().editor_layout!.pending_entrances![0];
  const card=page.locator(`[data-scenario-edge="studio:entry-point:${pending.key}"]`);await expect(card).toContainText('Тяните связь справа');
  const title=card.getByRole('textbox',{name:'Название входа «Новый вход»',exact:true});await title.fill('Визуальный вход');await title.press('Enter');
  await expect.poll(()=>state.definition().editor_layout?.pending_entrances?.[0].title).toBe('Визуальный вход');await page.reload();await page.getByRole('button',{name:'Настроить услугу Проблемы с печатью',exact:true}).dblclick();
  await page.getByRole('button',{name:'Вся карта',exact:true}).click();
  await drag(page,port(page,`studio:link:entry:named:${pending.key}`,'out'),page.locator('.react-flow__handle[data-nodeid="q2"][data-handletype="target"],.react-flow__handle[data-nodeid="q2"].target'));
  await expect.poll(()=>state.definition().entry_points?.find(e=>e.key===pending.key)?.target_block_id).toBe('q2');expect(state.definition().editor_layout?.pending_entrances??[]).toHaveLength(0);expect(state.definition().blocks).toEqual(before.blocks);expect(state.definition().entry_block_id).toBe(before.entry_block_id);expect(state.definition().schema_version).toBe(3);
  await page.getByRole('button',{name:'+ Вход из каталога',exact:true}).click();await expect(page.getByRole('dialog',{name:'Новый вход из каталога'})).toHaveCount(0);await expect.poll(()=>state.definition().editor_layout?.pending_entrances?.length).toBe(1);
  await page.getByRole('button',{name:'Свернуть редактор',exact:true}).click();await page.getByRole('button',{name:'Вся карта',exact:true}).click();const second=state.definition().editor_layout!.pending_entrances![0];await dragEmpty(page,port(page,`studio:link:entry:named:${second.key}`,'out'));await menu.getByRole('menuitem',{name:'Инструкция',exact:true}).click();
  await expect.poll(()=>state.definition().blocks?.length).toBe(before.blocks!.length+1);expect(state.definition().entry_points?.at(-1)?.key).toBe(second.key);expect(state.definition().blocks?.at(-1)?.kind).toBe('instruction');
  await page.screenshot({path:info.outputPath(`visual-entrance-${width}.png`),fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
 });
 test(`all palette blocks connect visually and policies stay attachments ${width}`,async({page},info)=>{
  test.setTimeout(90000);const state=await setup(page,width);state.definition().schema_version=4;state.definition().execution_semantics=3;await page.reload();await page.getByRole('button',{name:'Настроить услугу Проблемы с печатью',exact:true}).dblclick();
  const menu=page.getByRole('menu',{name:'Добавить на конец связи',exact:true});
  for(const [label,kind]of[['Вопрос','form_page'],['Инструкция','instruction'],['Условие','decision'],['Проверка результата','resolution_check'],['Результат','submit_ticket'],['Переходы · кнопки','navigation'],['Завершить без обращения','finish']]){
   await page.getByRole('list',{name:'Блоки сценария',exact:true}).getByRole('button',{name:'Тип проблемы',exact:true}).click();const old=state.definition().blocks!.length;
   await dragEmpty(page,port(page,'q1'));await menu.getByRole('menuitem',{name:label,exact:true}).click();await expect.poll(()=>state.definition().blocks?.length).toBe(old+1);expect(state.definition().blocks?.at(-1)?.kind).toBe(kind);
  }
  for(const [label,kind]of[['Сроки обработки','sla_attachment'],['Маршрут','routing_attachment']]){
   await page.getByRole('button',{name:`+ ${label}`,exact:true}).click();await expect.poll(()=>state.definition().blocks?.at(-1)?.kind).toBe(kind);const attachment=state.definition().blocks!.at(-1)!,oldTransitions=structuredClone(state.definition().blocks!.find(b=>b.id==='q1')!.transitions);
   if(kind==='sla_attachment'){await dragEmpty(page,port(page,attachment.id,'policy'));await menu.getByRole('menuitem',{name:'Инструкция',exact:true}).click();await expect.poll(()=>state.definition().blocks?.find(b=>b.id===attachment.id)?.kind==='sla_attachment'&&(state.definition().blocks!.find(b=>b.id===attachment.id) as {attached_to?:string}).attached_to).toBeTruthy();}
   else {await page.getByRole('button',{name:'Свернуть редактор',exact:true}).click();await page.getByRole('button',{name:'Вся карта',exact:true}).click();await drag(page,port(page,attachment.id,'policy'),page.locator('.react-flow__handle[data-nodeid="q1"].target'));await expect.poll(()=>(state.definition().blocks!.find(b=>b.id===attachment.id) as {attached_to?:string}).attached_to).toBe('q1');}
   expect(state.definition().blocks!.find(b=>b.id==='q1')!.transitions).toEqual(oldTransitions);
  }
  await page.getByRole('button',{name:'Вся карта',exact:true}).click();await page.screenshot({path:info.outputPath(`visual-palette-${width}.png`),fullPage:true});expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
 });
}
