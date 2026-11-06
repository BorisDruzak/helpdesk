import { expect,test } from "playwright/test";
import { installStudioV3Fixture } from "./fixtures/studio-v3";
for(const width of [1366,1920])test(`existing catalog entrances reconnect visually without changing legacy graph ${width}`,async({page})=>{
 await page.setViewportSize({width,height:width===1366?768:1080});const state=await installStudioV3Fixture(page),before=structuredClone(state.definition());
 await page.route("**/api/web/notifications/push/config",r=>r.fulfill({json:{status:"ok",enabled:false,public_key:null}}));await page.route("**/request-studio/fragments",r=>r.fulfill({json:{status:"success",data:{items:[],total:0}}}));
 await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Настроить услугу Проблемы с печатью",exact:true}).dblclick();await page.getByRole("button",{name:"Редактировать выбранный блок",exact:true}).click();await page.getByRole("button",{name:"Вся карта",exact:true}).click();
 const card=page.locator('[data-scenario-edge="studio:entry-point:special"]');const input=card.getByRole("textbox",{name:"Название входа «Быстрый вход»",exact:true});await input.fill("Быстрый визуальный вход");await input.press("Enter");
 const from=await page.locator('.react-flow__handle[data-nodeid="studio:link:entry:named:special"][data-handleid="out"]').boundingBox(),to=await page.locator('.react-flow__handle[data-nodeid="q2"].target').boundingBox();expect(from).not.toBeNull();expect(to).not.toBeNull();
 await page.mouse.move(from!.x+from!.width/2,from!.y+from!.height/2);await page.mouse.down();await page.mouse.move(to!.x+to!.width/2,to!.y+to!.height/2,{steps:15});await page.mouse.up();
 await expect.poll(()=>state.definition().entry_points?.find(e=>e.key==="special")?.target_block_id).toBe("q2");expect(state.definition().entry_points?.find(e=>e.key==="special")?.title).toBe("Быстрый визуальный вход");expect(state.definition().blocks).toEqual(before.blocks);expect(state.definition().entry_block_id).toBe("q1");expect(state.definition().schema_version).toBe(3);expect(state.definition().entry_points).toHaveLength(2);expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
});
