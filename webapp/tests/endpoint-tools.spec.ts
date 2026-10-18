import {expect,test,type Page} from "playwright/test";
import {installEndpointToolsFixture} from "./fixtures/endpoint-tools";
async function login(page:Page) {
 await page.goto("/app/login");await page.getByLabel("Логин").fill("support");await page.getByLabel("Пароль").fill("secret");await page.getByRole("button",{name:"Войти"}).click();await expect(page).not.toHaveURL(/\/app\/login/);
 await page.goto("/app/tickets/ticket-1");await expect(page.getByTestId("support-workspace-root")).toBeVisible();
}
async function openTools(page:Page) {
 const inspector=page.getByTestId("support-inspector-panel");if(!await inspector.isVisible())await page.getByTestId("support-command-strip").getByRole("button",{name:"Контекст",exact:true}).click();await expect(inspector).toBeVisible();
 await page.getByRole("button",{name:"Инструменты",exact:true}).click();await page.getByRole("tab",{name:"Диагностика",exact:true}).click();await expect(page.getByRole("heading",{name:"Инструменты Endpoint"})).toBeVisible();
}
for(const width of [390,1366,1920,2582]) {
 test(`published tool input/result, passport and panels at ${width}`,async({page},info)=>{
  await page.setViewportSize({width,height:width===390?844:width===1366?768:1080});
  const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});page.on("response",r=>{if(r.status()>=400)errors.push(`${r.status()} ${new URL(r.url()).pathname}`);});
  const fixture=await installEndpointToolsFixture(page);await login(page);
  if(width>767){await page.getByRole("button",{name:"Свернуть меню"}).click();await expect(page.getByRole("button",{name:"Развернуть меню"})).toHaveAttribute("aria-expanded","false");await page.getByRole("button",{name:"Скрыть список заявок"}).click();await expect(page.getByPlaceholder("Поиск по моим тикетам...")).toHaveCount(0);await expect(page.getByLabel("Сообщение в тикет")).toBeVisible();await page.screenshot({path:info.outputPath(`collapsed-${width}.png`)});await page.getByRole("button",{name:"Показать список заявок"}).click();}
  await openTools(page);
  await page.getByRole("combobox",{name:"Инструмент Endpoint"}).selectOption("helpdesk.ping:1.0.0");await expect(page.getByRole("button",{name:"Запустить проверку"})).toBeDisabled();
  await page.getByRole("combobox",{name:"Инструмент Endpoint"}).selectOption("helpdesk.dns:1.0.0");await page.getByLabel(/Адрес или имя/).fill("router.example.test");
  const run=page.getByRole("button",{name:"Запустить проверку"});await expect(run).toBeInViewport();await run.click();
  await expect(page.getByText("203.0.113.7 · IPv4",{exact:true})).toBeVisible();expect(fixture.receipts).toHaveLength(1);expect(fixture.receipts[0].inputs).toEqual({target:"router.example.test"});expect(fixture.receipts[0].expected_device_ref).toBe(fixture.catalog.device_ref);
  await page.getByRole("button",{name:"Приложить к паспорту",exact:true}).click();await expect(page.getByRole("button",{name:"В паспорте"})).toBeDisabled();expect(fixture.attached.size).toBe(1);
  await page.screenshot({path:info.outputPath(`tool-result-${width}.png`)});
  await page.getByRole("button",{name:"Собрать общий контекст"}).click();await expect(page.getByText("Частичный результат",{exact:true})).toBeVisible();await expect(page.getByRole("button",{name:/Выбрать результат/})).toHaveCount(6);
  await page.getByRole("button",{name:"Выбрать результат: Сеть",exact:true}).click();await expect(page.getByText(/Сохранённый результат отсутствует/)).toBeVisible();await page.screenshot({path:info.outputPath(`partial-${width}.png`)});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(2);expect(errors).toEqual([]);
 });
}
test("a provider failure keeps the ticket chat available",async({page},info)=>{
 await page.setViewportSize({width:1366,height:768});await installEndpointToolsFixture(page);await login(page);
 await page.route("**/api/web/support/tickets/ticket-1/endpoint-tools",route=>route.fulfill({status:502,json:{status:"error",error_code:"endpoint_forbidden",error:"Инструменты временно недоступны"}}));
 await openTools(page);await expect(page.getByRole("alert").filter({hasText:"Не удалось получить инструменты Endpoint"})).toBeVisible();
 await page.getByRole("button",{name:"Вернуться к чату",exact:true}).click();await expect(page.getByLabel("Сообщение в тикет")).toBeVisible();await expect(page).not.toHaveURL(/\/app\/login/);await page.screenshot({path:info.outputPath("endpoint-degraded-chat.png")});
});

test("a late response for run B cannot replace selected historical run A",async({page})=>{
 await page.setViewportSize({width:1920,height:1080});const fixture=await installEndpointToolsFixture(page);await login(page);await openTools(page);
 await page.getByRole("combobox",{name:"Инструмент Endpoint"}).selectOption("helpdesk.dns:1.0.0");
 await page.getByLabel(/Адрес или имя/).fill("first.example.test");await page.getByRole("button",{name:"Запустить проверку"}).click();
 await expect(page.getByText("203.0.113.7 · IPv4",{exact:true})).toBeVisible();
 const first=[...fixture.runs.keys()][0];let release!:()=>void;const delayed=new Promise<void>(resolve=>{release=resolve;});let secondRead=false;
 await page.route(/\/endpoint-tools\/runs\/[^/?]+$/,async route=>{
  const id=new URL(route.request().url()).pathname.split("/").at(-1)!;
  if(id===first){await route.fallback();return;}
  secondRead=true;await delayed;
  await route.fulfill({json:{status:"success",data:fixture.runs.get(id)}});
 });
 await page.getByLabel(/Адрес или имя/).fill("second.example.test");await page.getByRole("button",{name:"Запустить проверку"}).click();
 await expect.poll(()=>secondRead).toBe(true);
 await page.getByText("История запусков",{exact:true}).click();
 const history=page.getByRole("button",{name:/helpdesk\.dns ·/});await expect(history).toHaveCount(2);await history.first().click();
 const result=page.getByRole("region",{name:"Выбранный результат"});await expect(result).toContainText("first.example.test");
 release();await expect(result).not.toContainText("second.example.test");await expect(result).toContainText("203.0.113.7");
});
