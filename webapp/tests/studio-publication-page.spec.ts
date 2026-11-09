import {expect,test,type Page} from "playwright/test";
import {installStudioV3Fixture} from "./fixtures/studio-v3";

async function setup(page:Page,width:number,blocked=false){
 await page.setViewportSize({width,height:width===1366?768:1080});const state=await installStudioV3Fixture(page);state.definition().schema_version=4;state.definition().execution_semantics=3;
 let visibility="public",publishCount=0;
 const offering=()=>({code:"print",full_code:"it.print",service_code:"it",public_title:"Проблемы с печатью",request_template_key:"print",lifecycle_status:"published",visibility});
 await page.route('**/request-studio/catalog?**',r=>r.fulfill({json:{status:'success',data:{categories:[],services:[{code:'it',public_title:'ИТ',visibility:'public',lifecycle_status:'published'}],offerings:[offering()],scenarios:[{id:'v3',title:'Проблемы с печатью',schema_version:4,status:'draft',offering_full_code:'it.print',issues:[]}],total:1,offset:0,limit:100,queue_mode:'unified',common_queue_code:'support'}}}));
 await page.route('**/notifications/push/config',r=>r.fulfill({json:{status:'ok',enabled:false,public_key:null}}));
 await page.route('**/request-studio/fragments',r=>r.fulfill({json:{status:'success',data:{items:[],total:0}}}));
 await page.route('**/settings',r=>r.fulfill({json:{status:'success',data:{queues:[{id:1,code:'support',name:'Единая поддержка',is_active:true},{id:2,code:'network',name:'Старая сеть',is_active:true}],calendars:[],ticket_settings:{operational_flags:{queue_mode:'unified',take_queue_common_code:'support'}}}}}));
 await page.route('**/scenarios/v3/catalog-visibility',r=>{const body=r.request().postDataJSON();expect(body.expected_visibility).toBe(visibility);visibility=body.visibility;return r.fulfill({json:{status:'success',data:{offering:offering()}}});});
 await page.route('**/scenarios/v3/publish-preview',r=>r.fulfill({json:{status:'success',data:{revision:r.request().postDataJSON().revision,source_hash:'safe',health:{health_status:blocked?'error':'ok'},catalog_visibility:visibility,readiness:{can_publish:!blocked,variants_checked:blocked?0:2,issues:blocked?[{code:'missing_fallback',path:'blocks.logic.transitions',message:'Добавьте запасной переход в условии.'}]:[]},outcomes:blocked?[]:[{kind:'ticket',terminal:'end',entry_point_key:'main',routing:{queue_title:'Единая поддержка',queue_code:'support'},sla:{first_response_min:30,resolution_min:120},approval_required:false},{kind:'ticket',terminal:'end',entry_point_key:'special',routing:{queue_title:'Единая поддержка',queue_code:'support'},sla:{first_response_min:120,resolution_min:300},approval_required:false}],diff:[],confirmation_token:blocked?null:'test-confirm',expires_at:new Date(Date.now()+300000).toISOString()}}}));
 await page.route('**/scenarios/v3/publish',r=>{publishCount++;return r.fulfill({json:{status:'success',data:{scenario:{id:'v3',archived:false},draft:{revision:1,definition:state.definition()},version:{version:2,id:'new',definition:state.definition()}}}});});
 await page.goto('/app/admin/request-template-studio');await page.getByRole('button',{name:'Настроить услугу Проблемы с печатью',exact:true}).dblclick();
 return{state,visibility:()=>visibility,publishes:()=>publishCount};
}
for(const width of [1366,1920]){
 test(`publication actions remain clickable after scroll with expanded navigation ${width}`,async({page})=>{
  const{state}=await setup(page,width);const expand=page.getByRole('button',{name:'Развернуть меню',exact:true});if(await expand.isVisible())await expand.click();await page.getByRole('button',{name:'Опубликовать',exact:true}).click();const prepare=page.getByRole('button',{name:'Подготовить публикацию',exact:true});await prepare.click();await page.getByRole('heading',{name:'Проверенные исходы',exact:true}).click();await page.mouse.move(width-100,500);await page.mouse.wheel(0,500);
  await expect.poll(()=>prepare.evaluate(e=>{const r=e.getBoundingClientRect(),top=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return top===e||!!top&&e.contains(top);})).toBe(true);expect(state.errors).toEqual([]);
 });
 test(`focused route and SLA settings on their own map blocks ${width}`,async({page},info)=>{
  const{state}=await setup(page,width);await page.getByRole('button',{name:'+ SLA',exact:true}).click();
  const sla=page.getByRole('group',{name:'Прикреплённая настройка SLA',exact:true});await sla.getByRole('combobox',{name:'Профиль SLA',exact:true}).selectOption('standard');
  const slaSettings=sla.getByRole('region',{name:'Настройки SLA',exact:true});await expect(slaSettings.getByRole('spinbutton',{name:'Срок решения',exact:true})).toBeVisible();expect(await sla.getByRole('combobox',{name:'Очередь Helpdesk',exact:true}).count()).toBe(0);
  await slaSettings.getByRole('spinbutton',{name:'Срок решения',exact:true}).fill('420');await expect.poll(()=>state.definition().processing?.sla_profiles.standard.resolution_minutes).toBe(420);
  await page.getByRole('button',{name:'+ Маршрут',exact:true}).click();const route=page.getByRole('group',{name:'Прикреплённая настройка маршрута',exact:true});await route.getByRole('combobox',{name:'Маршрут обработки',exact:true}).selectOption('support');
  const routeSettings=route.getByRole('region',{name:'Настройки направления',exact:true});const queue=routeSettings.getByRole('combobox',{name:'Очередь Helpdesk',exact:true});await expect(queue).toBeVisible();expect(await queue.locator('option').allTextContents()).toEqual(['Выберите действующую очередь','Единая поддержка']);expect(await route.getByRole('spinbutton',{name:'Срок решения',exact:true}).count()).toBe(0);
  await routeSettings.getByRole('button',{name:'Добавить направление',exact:true}).click();await expect.poll(()=>Object.keys(state.definition().processing!.routes).length).toBe(2);expect(Object.values(state.definition().processing!.routes).at(-1)?.queue_code).toBe('support');
  await page.screenshot({path:info.outputPath(`route-settings-${width}.png`),fullPage:true});expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
 });
 test(`full publication page and independent visibility ${width}`,async({page},info)=>{
  const{state,visibility,publishes}=await setup(page,width);await page.getByRole('button',{name:'Опубликовать',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Публикация сценария',exact:true})).toBeVisible();expect(await page.locator('.studio-map-popover:visible').count()).toBe(0);
  const check=page.getByRole('button',{name:'Подготовить публикацию',exact:true});await expect(check).toBeInViewport();await check.click();
  await expect(page.getByText('Единая поддержка',{exact:false}).first()).toBeVisible();await expect(page.getByRole('region',{name:'Проверенные исходы',exact:true}).getByText('Быстрый вход',{exact:true})).toBeVisible();
  const publication=page.getByRole('region',{name:'Публикация сценария',exact:true});await publication.getByRole('combobox',{name:'Видимость услуги',exact:true}).selectOption('internal');await publication.getByRole('button',{name:'Применить видимость',exact:true}).click();await expect.poll(visibility).toBe('internal');expect(publishes()).toBe(0);expect(state.writes).not.toContain('draft');
  await expect(page.getByRole('button',{name:'Опубликовать сценарий',exact:true})).toHaveCount(0);await check.click();
  await page.screenshot({path:info.outputPath(`publication-${width}.png`),fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Вернуться к карте',exact:true}).click();await expect(page.getByRole('complementary',{name:'Библиотека блоков',exact:true})).toBeVisible();expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
 });
 test(`publication blocker links back to exact map condition ${width}`,async({page})=>{
  const{state,publishes}=await setup(page,width,true);await page.getByRole('button',{name:'Опубликовать',exact:true}).click();await page.getByRole('button',{name:'Подготовить публикацию',exact:true}).click();await expect(page.getByText('Добавьте запасной переход в условии.',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Опубликовать сценарий',exact:true})).toHaveCount(0);await page.getByRole('button',{name:/Исправить:/}).first().click();await expect(page.locator('.studio-map-node.is-expanded')).toContainText('Выбрать обработку');expect(publishes()).toBe(0);expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
 });
}
