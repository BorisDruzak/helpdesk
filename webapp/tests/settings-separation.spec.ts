import {expect,test} from 'playwright/test';
import {createSettingsPayload} from '../src/pages/settings/settings-test-fixtures';

test.beforeEach(async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('helpdesk-notification-intro-v1:admin','1'));
 await page.route('**/api/web/notifications/unread_count',route=>route.fulfill({json:{status:'ok',unread_count:0}}));
 await page.route('**/api/web/notifications/preferences',route=>route.fulfill({json:{status:'ok',preferences:{mute_internal:false,muted_event_types:[],suppress_self:true}}}));
 await page.route('**/api/web/settings',route=>{
  const data=createSettingsPayload();data.ticket_settings.operational_flags.queue_mode='unified';
  return route.fulfill({json:{status:'success',data}});
 });
 await page.route('**/api/web/admin/tech/alerts',route=>route.fulfill({json:{status:'ok',alerts:[{id:'1',kind:'observer_degradation',severity:'warning',summary:'Проверьте обработку событий',details:{},link:'/app/admin/observer'}]}}));
});
async function login(page:import('playwright/test').Page,next:string){
 await page.goto('/app/login?next='+encodeURIComponent(next));
 await page.getByLabel('Логин',{exact:true}).fill('admin');await page.getByLabel('Пароль',{exact:true}).fill('secret');
 await page.getByRole('button',{name:'Войти',exact:true}).click();
 await expect(page).not.toHaveURL(/\/login/);
}
for(const width of [1366,1920])test(`personal and service settings remain separate at ${width}`,async({page},info)=>{
 await page.setViewportSize({width,height:width===1366?768:1080});
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 let serviceReads=0;page.on('request',request=>{if(new URL(request.url()).pathname==='/api/web/settings')serviceReads++;});
 await login(page,'/app/settings');await expect(page.getByRole('heading',{name:'Мои настройки',exact:true})).toBeVisible();
 expect(serviceReads).toBe(0);await expect(page.getByRole('checkbox',{name:/Новые сообщения/})).toBeEnabled();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath(`personal-${width}.png`),fullPage:true});
 await page.goto('/app/admin/settings');await expect(page.getByRole('heading',{name:'Настройки службы',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Очереди',exact:true}).click();await expect(page).toHaveURL(/section=queues/);
 await page.getByRole('button',{name:'Новая очередь',exact:true}).click();
 await page.getByLabel('Код',{exact:true}).fill('new_queue');await page.getByLabel('Название',{exact:true}).fill('Черновик очереди');
 await expect(page.getByRole('button',{name:/^Сохранить:/})).toBeInViewport();
 await page.getByRole('button',{name:'Сроки',exact:true}).click();await expect(page.getByRole('alertdialog')).toBeVisible();
 await page.getByRole('button',{name:'Продолжить редактирование'}).click();await expect(page.getByLabel('Название',{exact:true})).toHaveValue('Черновик очереди');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.evaluate(()=>window.scrollTo(0,0));
 await page.screenshot({path:info.outputPath(`service-${width}.png`),fullPage:true});
 await page.getByRole('link',{name:'Мои настройки',exact:true}).last().click();await expect(page.getByRole('alertdialog')).toBeVisible();
 await page.getByRole('button',{name:'Остаться',exact:true}).click();await expect(page.getByLabel('Название',{exact:true})).toHaveValue('Черновик очереди');
 await page.getByRole('button',{name:'Отменить изменения',exact:true}).click();
 await page.getByRole('button',{name:'Состояние системы',exact:true}).click();await expect(page.getByText('Проверьте обработку событий')).toBeVisible();
 expect(errors).toEqual([]);
});
test('service read failure does not look like empty configuration',async({page})=>{
 await page.route('**/api/web/settings',route=>route.fulfill({status:503,json:{status:'error'}}));
 await login(page,'/app/admin/settings');await expect(page.getByRole('alert')).toContainText('Не удалось загрузить настройки службы');
 await expect(page.getByRole('heading',{name:'Рабочие очереди'})).toHaveCount(0);
});
