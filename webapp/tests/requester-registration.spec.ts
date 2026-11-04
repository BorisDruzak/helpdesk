import { expect, test } from "playwright/test";

for (const viewport of [{width:1366,height:768},{width:1920,height:1080},{width:390,height:844}]) {
  test(`registration completes profile before enabling an explicit request at ${viewport.width}`, async ({page}, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    const unexpected: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    let authenticated = false;
    let registrations = 0;
    let ticketWrites = 0;
    const user = {user_login:"ipetrov2",actor_role:"user",auth_type:"ui_token",default_workspace:"requester",available_workspaces:["requester"],permissions:["workspace.requester.view"]};
    const departments = [{value:"legal",label:"Юридический отдел"},{value:"it",label:"Отдел информационных технологий"}];
    await page.route("**/api/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let data: unknown = {};
      if(path === "/api/web/session/capabilities") data={self_registration_enabled:true,sso_enabled:true};
      else if(path === "/api/web/session/me") {
        if(!authenticated) return route.fulfill({status:401,json:{status:"error"}});
        data=user;
      } else if(path === "/api/web/session/registration-options") data={departments,profile_schema:{fields:[]}};
      else if(path === "/api/web/session/register-requester") {
        registrations++;
        const payload=route.request().postDataJSON();
        expect(payload).toMatchObject({first_name:"Иван",last_name:"Петров",department_id:"legal",phone:"1234"});
        expect(payload).not.toHaveProperty("location_id");
        return route.fulfill({status:201,json:{status:"success",data:{user_login:"ipetrov2",actor_role:"user",profile_complete:true}}});
      } else if(path === "/api/web/session/login") {
        expect(route.request().postDataJSON().login).toBe("ipetrov2"); authenticated=true;data=user;
      } else if(path === "/api/web/requester/bootstrap") data={workspace:"requester",account_summary:{login:"ipetrov2",linked_profile:true},
        profile:{person_id:"fixture",full_name:"Петров Иван Сергеевич",display_name:"Петров Иван Сергеевич",department_id:"legal",phone:"1234"},
        profile_completion:{complete:true,required_fields:[],missing_fields:[],blocks:{}},devices:[],feature_flags:{requester_ticket_create:true,requester_no_device_create:true},policies:{}};
      else if(path === "/api/web/requester/tickets") {if(route.request().method()!=="GET") ticketWrites++;data=[];}
      else if(path === "/api/web/requester/consents") data=[];
      else if(path === "/api/web/notifications/unread_count") return route.fulfill({json:{status:"ok",unread_count:0}});
      else if(path === "/api/registry/options") data={departments,locations:[]};
      else if(path === "/api/service-catalog/current") return route.fulfill({json:{status:"ok",catalog_version:"fixture",services:[]}});
      else {unexpected.push(path);return route.fulfill({status:404,json:{status:"error"}});}
      return route.fulfill({json:{status:"success",data}});
    });
    await page.route("**/public_api/ticket_forms/current**", route=>route.fulfill({json:{status:"ok",pack:{key:"request_forms",version:"fixture",forms:[{key:"other",title:"Другая проблема",fields:[{key:"summary",label:"Опишите проблему",type:"textarea",required:true}],availability_policy:{available_without_agent_binding:true}}]}}}));
    await page.goto("/app/register?next=%2Fapp%2Frequester%2Fnew");
    await expect(page.getByRole("heading",{name:"Регистрация сотрудника"})).toBeVisible();
    await page.getByRole("button",{name:"Продолжить",exact:true}).click();
    await expect(page.getByLabel("Фамилия",{exact:true})).toBeFocused();
    await page.getByLabel("Фамилия",{exact:true}).fill("Петров");
    await page.getByLabel("Имя",{exact:true}).fill("Иван");
    await page.getByLabel("Отчество",{exact:true}).fill("Сергеевич");
    await expect(page.getByText("ipetrov",{exact:true})).toBeVisible();
    await page.screenshot({path:info.outputPath("names.png"),fullPage:true});
    await page.getByRole("button",{name:"Продолжить",exact:true}).click();
    await page.getByLabel("Найти отдел",{exact:true}).fill("юрид");
    await page.getByLabel("Отдел",{exact:true}).selectOption("legal");
    await page.getByLabel("Телефон или внутренний номер",{exact:true}).fill("1234");
    await expect(page.getByLabel("Локация",{exact:true})).toHaveCount(0);
    await page.getByRole("button",{name:"Назад",exact:true}).click();
    await expect(page.getByLabel("Фамилия",{exact:true})).toHaveValue("Петров");
    await page.getByRole("button",{name:"Продолжить",exact:true}).click();
    await expect(page.getByLabel("Отдел",{exact:true})).toHaveValue("legal");
    await page.getByRole("button",{name:"Продолжить",exact:true}).click();
    await page.getByLabel("Пароль",{exact:true}).fill("Synthetic-registration-password-43!");
    await page.getByLabel("Повторите пароль",{exact:true}).fill("Synthetic-registration-password-43!");
    const submit=page.getByRole("button",{name:"Зарегистрироваться",exact:true});
    if(viewport.width>=1366) await expect(submit).toBeInViewport();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:info.outputPath("password.png"),fullPage:true});
    await submit.click();
    await expect(page).toHaveURL(/\/app\/requester$/);
    await expect(page.getByRole("heading",{name:"Главная",exact:true})).toBeVisible();
    await expect(page.getByRole("status").filter({hasText:"Ваш логин"})).toContainText("ipetrov2");
    expect(registrations).toBe(1);expect(ticketWrites).toBe(0);
    await page.screenshot({path:info.outputPath("home.png"),fullPage:true});
    await page.getByRole("main").getByRole("link",{name:"Создать обращение",exact:true}).first().click();
    await expect(page).toHaveURL(/\/app\/requester\/new$/);
    await expect(page.getByRole("heading",{name:"Категория и форма",exact:true})).toBeVisible();
    expect(ticketWrites).toBe(0);expect(errors).toEqual([]);expect(unexpected).toEqual([]);
  });
}

test("an existing incomplete account completes its profile and returns home without registration", async ({page}) => {
  let saved=false;
  let accountWrites=0;
  await page.route("**/api/**",async route => {
    const path=new URL(route.request().url()).pathname;
    let data:unknown={};
    if(path==="/api/web/session/me") data={user_login:"existing.employee",actor_role:"user",auth_type:"ui_token",default_workspace:"requester",available_workspaces:["requester"],permissions:["workspace.requester.view"]};
    else if(path==="/api/registry/options") data={departments:[{value:"legal",label:"Юридический отдел"}],locations:[]};
    else if(path==="/api/web/requester/profile") {
      if(route.request().method()==="PUT") {const body=route.request().postDataJSON();expect(body).toMatchObject({full_name:"Существующий Сотрудник",department_id:"legal",phone:"1234"});expect(body).not.toHaveProperty("location_id");saved=true;}
      data={profile:{person_id:"existing",full_name:"Существующий Сотрудник",department_id:saved?"legal":"",phone:saved?"1234":""},
        profile_completion:{complete:saved,required_fields:[{key:"full_name",label:"ФИО"},{key:"department_id",label:"Отдел"},{key:"phone",label:"Телефон или внутренний номер"}],missing_fields:saved?[]:[{key:"department_id",label:"Отдел"},{key:"phone",label:"Телефон или внутренний номер"}]},
        profile_policy:{editable:true},profile_schema:{fields:[]},devices:[],active_bindings:[]};
    } else if(path==="/api/web/requester/bootstrap") data={workspace:"requester",profile:{person_id:"existing",display_name:"Существующий Сотрудник"},profile_completion:{complete:saved,required_fields:[],missing_fields:[],blocks:{}},devices:[],feature_flags:{requester_ticket_create:true,requester_no_device_create:true},policies:{}};
    else if(path==="/api/web/requester/tickets") data={tickets:[]};
    else if(path==="/api/web/requester/consents") data=[];
    else if(path==="/api/web/notifications/unread_count") return route.fulfill({json:{status:"ok",unread_count:0}});
    else if(path.includes("register")) {accountWrites++;return route.fulfill({status:500,json:{status:"error"}});}
    return route.fulfill({json:{status:"success",data}});
  });
  await page.goto("/app/requester/profile/setup?next=/app/requester/new");
  await page.getByLabel("Отдел",{exact:true}).selectOption("legal");
  await page.getByLabel("Телефон или внутренний номер",{exact:true}).fill("1234");
  await expect(page.getByLabel("Локация",{exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Назад",exact:true}).click();
  await expect(page.getByLabel("ФИО",{exact:true})).toHaveValue("Существующий Сотрудник");
  await page.getByRole("button",{name:"Продолжить",exact:true}).click();
  await page.getByRole("button",{name:"Сохранить профиль",exact:true}).click();
  await expect(page).toHaveURL(/\/app\/requester$/);
  await expect(page.getByRole("heading",{name:"Главная",exact:true})).toBeVisible();
  expect(accountWrites).toBe(0);
});
