import {expect,test,type Page} from 'playwright/test';
import {installStudioV3Fixture} from './fixtures/studio-v3';

async function setup(page:Page,width:number,navigation=false){
 await page.setViewportSize({width,height:width===1366?768:1080});
 const state=await installStudioV3Fixture(page);
 if(navigation){const d=state.definition();d.schema_version=4;d.execution_semantics=3;d.blocks!.find(b=>b.id==='q1')!.transitions=[{to:'nav'}];d.blocks!.push({id:'nav',title:'Выбор продолжения',kind:'navigation',transition_mode:'buttons',transitions:[{to:'end',button:{key:'continue',label:'Создать обращение'}}]});}
 await page.route('**/api/web/notifications/push/config',r=>r.fulfill({json:{status:'ok',enabled:false,public_key:null}}));
 await page.route('**/request-studio/fragments',r=>r.fulfill({json:{status:'success',data:{items:[],total:0}}}));
 await page.goto('/app/admin/request-template-studio');await page.getByRole('button',{name:'Настроить услугу Проблемы с печатью',exact:true}).dblclick();
 return state;
}
for(const width of [1366,1920]){
 test(`catalogue entrances are roots and service settings belong to publication ${width}`,async({page},info)=>{
  const state=await setup(page,width),before=structuredClone(state.definition());
  await expect(page.locator('.react-flow__node[data-id="studio:metadata"]')).toHaveCount(0);
  await expect(page.locator('[data-id="studio:link:entry:named:main"] .react-flow__handle.target')).toHaveCount(0);
  expect(state.definition()).toEqual(before);expect(state.writes).not.toContain('draft');
  await page.getByRole('button',{name:'Опубликовать',exact:true}).click();const service=page.getByRole('button',{name:'Настройки услуги',exact:true});
  if(await service.getAttribute('aria-expanded')!=='true')await service.click();
  await expect(page.getByRole('textbox',{name:'Название услуги',exact:true})).toHaveValue(before.title);expect(state.definition()).toEqual(before);expect(state.writes).not.toContain('draft');
  await page.getByRole('button',{name:'Вернуться к карте',exact:true}).click();await page.getByRole('button',{name:'+ Вход из каталога',exact:true}).click();
  await expect.poll(()=>state.definition().editor_layout?.pending_entrances?.length).toBe(1);const entry=state.definition().editor_layout!.pending_entrances![0];
  const collapse=page.getByRole('button',{name:'Свернуть редактор',exact:true});if(await collapse.count())await collapse.click();await page.getByRole('button',{name:'Вся карта',exact:true}).click();
  const from=page.locator(`.react-flow__handle[data-nodeid="studio:link:entry:named:${entry.key}"][data-handleid="out"]`),to=page.locator('.react-flow__handle[data-nodeid="q2"].target');
  const a=(await from.boundingBox())!,b=(await to.boundingBox())!;expect(a).not.toBeNull();expect(b).not.toBeNull();await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:16});await page.mouse.up();
  await expect.poll(()=>state.definition().entry_points?.find(e=>e.key===entry.key)?.target_block_id).toBe('q2');
  await page.getByRole('button',{name:'+ Вход из каталога',exact:true}).press('Enter');
  await expect.poll(()=>state.definition().editor_layout?.pending_entrances?.length).toBe(1);const keyboardEntry=state.definition().editor_layout!.pending_entrances![0];
  const pending=page.locator('section[aria-label="Незавершённый вход из каталога"]');
  await expect(pending.getByRole('combobox',{name:'Первый блок для сотрудника',exact:true})).toHaveCount(0);
  await pending.getByText('Подключение с клавиатуры',{exact:true}).press('Enter');
  await pending.getByRole('combobox',{name:'Первый блок для сотрудника',exact:true}).press('ArrowDown');
  await expect.poll(()=>state.definition().entry_points?.find(e=>e.key===keyboardEntry.key)?.target_block_id).toBe('q1');
  expect(state.definition().editor_layout?.pending_entrances??[]).toHaveLength(0);
  expect(state.definition().blocks).toEqual(before.blocks);expect(state.definition().schema_version).toBe(3);expect(state.definition().entry_block_id).toBe(before.entry_block_id);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:info.outputPath(`entry-first-${width}.png`),fullPage:true});expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
 });
 test(`navigation block has no duplicate incoming transition card ${width}`,async({page},info)=>{
  const state=await setup(page,width,true),before=structuredClone(state.definition());
  await expect(page.locator('.react-flow__node[data-id="nav"]')).toHaveCount(1);
  await expect(page.locator('[data-scenario-edge="q1:0"]')).toHaveCount(0);
  await expect(page.locator('[data-scenario-edge="q2:0"]')).toHaveCount(1);
  await expect(page.locator('.react-flow__edge[data-id="q1:0"]')).toHaveCount(1);
  expect(state.definition()).toEqual(before);expect(state.writes).not.toContain('draft');
  await page.screenshot({path:info.outputPath(`navigation-no-duplicate-${width}.png`),fullPage:true});expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
 });
}
