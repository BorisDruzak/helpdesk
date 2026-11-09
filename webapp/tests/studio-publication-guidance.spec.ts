import {expect,test} from 'playwright/test';
import {installStudioV3Fixture} from './fixtures/studio-v3';
for(const width of [1366,1920]){
 test(`moved inspector leaves no empty blocking frame ${width}`,async({page})=>{
  await page.setViewportSize({width,height:width===1366?768:1080});const state=await installStudioV3Fixture(page);state.definition().schema_version=4;state.definition().execution_semantics=3;
  await page.route('**/notifications/push/config',r=>r.fulfill({json:{status:'ok',enabled:false,public_key:null}}));await page.route('**/request-studio/fragments',r=>r.fulfill({json:{status:'success',data:{items:[],total:0}}}));
  await page.goto('/app/admin/request-template-studio');await page.getByRole('button',{name:'Настроить услугу Проблемы с печатью',exact:true}).dblclick();await page.getByRole('button',{name:'Тестировать',exact:true}).click();
  const host=page.locator('.studio-map-popover'),editor=host.locator('.studio-resizable-editor'),body=editor.locator('.studio-resizable-editor__body');await expect(editor).toBeVisible();const before=(await editor.boundingBox())!;
  const blank=await body.evaluate(e=>{const r=e.getBoundingClientRect();for(const dx of[1,2,3])for(const dy of[15,30,45,60]){const x=r.x+dx,y=r.y+dy,t=document.elementFromPoint(x,y);if(t?.closest('.studio-resizable-editor__body')===e&&!t.closest('button,input,textarea,select,label,a,summary,[contenteditable],.studio-editor-resize'))return{x,y};}throw Error('No visible editor padding');});
  await page.mouse.move(blank.x,blank.y);await page.mouse.down();await page.mouse.move(blank.x-180,blank.y+40,{steps:16});await page.mouse.up();await expect.poll(async()=>Math.round((await editor.boundingBox())!.x-before.x)).toBeLessThan(-100);
  const point={x:before.x+before.width-20,y:before.y+before.height/2};await expect.poll(()=>page.evaluate(p=>!document.elementFromPoint(p.x,p.y)?.closest('.studio-map-popover'),point)).toBe(true);expect(state.errors).toEqual([]);
 });
}
