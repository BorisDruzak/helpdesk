import { expect, test, type Page } from "playwright/test";

// Browser fixtures deliberately avoid real employees, passwords and grants.
const marinaId = "test-marina";
const person = (id: string, name: string) => ({
  id, person_id: id, full_name: name, display_name: name, status: "active",
  source: "manual", email: null, phone: null, login: null,
  department_id: "it", department_name: "Информационные технологии",
  location_id: "room", location_name: "Кабинет 101", position: "Специалист",
  workplace_label: "Кабинет 101", internal_extension: "1234",
  manager_person_id: null, manager_name: null, updated_at: null,
  primary_device_count: 0, shared_device_count: 0, active_ticket_count: 0,
  active_session_count: 0, last_seen_at: null,
});

type Account = { user_login: string; actor_role: string; is_active: boolean; queue_ids: number[]; group_ids: number[] };

async function installUsersFixture(page: Page) {
  let account: Account | null = null;
  const writes: Record<string, unknown>[] = [];
  const unexpected: string[] = [];
  const errors: string[] = [];
  let rejectSave = false;
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => {
    if (message.type() === "error" && !(rejectSave && message.text().includes("409"))) errors.push(message.text());
  });
  const queues = [{ queue_id: 7, queue_code: "service_desk", queue_name: "ServiceDesk L1", is_active: true, members_count: 0 }];
  const catalog = { version: "users-fixture", roles: [
    { code: "user", label: "Пользователь", permissions: ["workspace.requester.view"] },
    { code: "support", label: "Поддержка", permissions: ["workspace.support.view", "ticket.queue.view"] },
    { code: "admin", label: "Администратор", permissions: ["workspace.admin.view"] },
    { code: "auditor", label: "Аудитор", permissions: [] },
  ], groups: [] };
  const registry = () => ({
    summary: { assets: 0, people: 2, locations: 1, departments: 1, services: 0, vendors: 0,
      registrations_pending: 0, registrations_conflicts: 0, unregistered_devices: 0,
      active_bindings: 0, stale_bindings: 0, data_quality_issues: 0, suggestions: 0,
      ui_users: account ? 1 : 0, ui_users_linked: account ? 1 : 0, ui_users_unlinked: 0 },
    people: [person(marinaId, "Заваруха Марина"), person("test-ivan", "Петров Иван")],
    assets: [], active_bindings: [], bindings: [], registration_claims: [], data_quality: [], suggestions: [],
    locations: [{ id: "room", location_id: "room", display_name: "Кабинет 101", building: "Администрация", floor: "1", room: "101", source: "manual", status: "active", users_count: 2, devices_count: 0, updated_at: null }],
    departments: [{ id: "it", department_id: "it", name: "Информационные технологии", code: "it", source: "manual", status: "active", users_count: 2, devices_count: 0, updated_at: null }],
    services: [], vendors: [], ui_users: account ? [{ ...account, failed_attempts: 0, locked_until: null,
      last_login_at: null, created_at: null, updated_at: null, linked_person_id: marinaId,
      linked_person_name: "Заваруха Марина", linked_identity_id: "test-link", linked_identity_verified: true }] : [],
  });
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let data: unknown;
    if (path === "/api/web/session/me") data = { user_login: "fixture-admin", actor_role: "admin", auth_type: "ui_token", default_workspace: "admin", available_workspaces: ["admin", "support"], permissions: ["workspace.admin.view", "workspace.support.view", "admin.access.view", "admin.registry.view", "settings.view"] };
    else if (path === "/api/web/session/capabilities") data = { self_registration_enabled: false, sso_enabled: false };
    else if (path === "/api/web/notifications/push/config") return route.fulfill({ json: { status: "ok", enabled: false, public_key: null } });
    else if (path === "/api/web/notifications/unread_count") return route.fulfill({ json: { status: "ok", unread_count: 0 } });
    else if (path === "/api/web/notifications") data = { items: [], notifications: [], unread_count: 0 };
    else if (path === "/api/web/admin/registry") data = registry();
    else if (path === `/api/web/admin/registry/people/${marinaId}/inventory-devices`) {
      data = { sync_state: "current", assignments: [{
        assignment_id: "fixture-assignment", name: "Компьютер сотрудника", role: "primary",
        endpoint_binding_state: "confirmed", endpoint_status: "offline", diagnostic_target: false,
        inventory_url: "https://inventory.invalid/inventory/assets/fixture-pc",
      }] };
    }
    else if (path === "/api/web/admin/access/catalog") data = catalog;
    else if (path === "/api/web/admin/access/summary") data = { version: "users-fixture", queues, access_groups: [], notes: [], users: account ? [{ ...account, display_name: "Заваруха Марина", role_label: account.actor_role === "support" ? "Поддержка" : "Пользователь", groups: [], queue_count: account.queue_ids.length }] : [] };
    else if (path === "/api/web/admin/access/audit") data = { items: [] };
    else if (path === "/api/web/admin/access/effective") data = { actor_id: account?.user_login, actor_role: account?.actor_role, role_label: "Сотрудник техподдержки", permissions: ["workspace.support.view"], workspaces: ["support"], groups: [], sources: { role: "support" }, queues: account?.queue_ids.length ? [{ ...queues[0], role_in_queue: "member" }] : [] };
    else if (path === `/api/web/admin/users/${marinaId}/account`) {
      if (request.method() === "PUT") {
        const body = request.postDataJSON();
        if (rejectSave) return route.fulfill({ status: 409, json: { status: "error", error: "Доступ изменён другим администратором. Проверьте настройки.", error_code: "CONFLICT" } });
        writes.push(body);
        account = { user_login: body.user_login, actor_role: body.actor_role, is_active: body.is_active, queue_ids: body.queue_ids, group_ids: body.group_ids };
        data = { account };
      } else data = { accounts: account ? [account] : [] };
    } else if (path === "/api/web/admin/users/test-ivan/account") data = { accounts: [] };
    else if (path.includes("password-reset")) data = { items: [] };
    else if (path.includes("audience-groups")) data = { groups: [], members: [] };
    else { unexpected.push(`${request.method()} ${path}`); return route.fulfill({ status: 404, json: { status: "error", error: "Unmatched test endpoint" } }); }
    return route.fulfill({ json: { status: "success", data } });
  });
  return { writes, unexpected, errors, reject: () => { rejectSave = true; } };
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`unified person card assigns support and queue at ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const fixture = await installUsersFixture(page);
    await page.goto(`/app/admin/users?person=${marinaId}`);
    await expect(page.getByRole("heading", { name: "Пользователи", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Учётная запись", exact: true }).click();
    await page.getByLabel("Логин", { exact: true }).fill("fixture-marina");
    await page.getByLabel("Пароль для нового входа", { exact: true }).fill("Only-Test-Password_839!");
    await page.getByLabel("Роль", { exact: true }).selectOption("support");
    await page.getByRole("button", { name: "Права и очереди", exact: true }).click();
    await page.getByRole("checkbox", { name: "ServiceDesk L1", exact: true }).check();
    await page.getByLabel("Причина изменения", { exact: true }).fill("Синтетическая проверка назначения специалиста");
    const save = page.getByRole("button", { name: "Сохранить доступ", exact: true });
    await expect(save).toBeInViewport();
    await page.screenshot({ path: info.outputPath("users-permissions-before-save.png"), fullPage: true });
    await save.click();
    await expect(page.getByText("Доступ сохранён", { exact: true })).toBeVisible();
    expect(fixture.writes).toHaveLength(1);
    expect(fixture.writes[0]).toMatchObject({ user_login: "fixture-marina", actor_role: "support", is_active: true, queue_ids: [7], group_ids: [] });
    await page.reload();
    await page.getByRole("button", { name: "Учётная запись", exact: true }).click();
    await expect(page.getByLabel("Роль", { exact: true })).toHaveValue("support");
    await page.getByRole("button", { name: "Права и очереди", exact: true }).click();
    await expect(page.getByRole("checkbox", { name: "ServiceDesk L1", exact: true })).toBeChecked();
    await page.screenshot({ path: info.outputPath("users-permissions-saved.png"), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const sidebar = page.locator("aside");
    await expect(sidebar.getByRole("link", { name: /^Пользователи/ })).toHaveCount(1);
    await expect(sidebar.getByRole("link", { name: /^Доступ/ })).toHaveCount(0);
    expect(fixture.errors).toEqual([]);
    expect(fixture.unexpected).toEqual([]);
  });
}

test("registries and legacy access links lead to distinct workspaces", async ({ page }) => {
  const fixture = await installUsersFixture(page);
  await page.goto("/app/admin/registry");
  await expect(page.getByRole("heading", { name: "Реестры", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Пользователи", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Группы доступа", exact: true })).toHaveCount(0);
  await page.goto("/app/admin/access");
  await expect(page).toHaveURL(/\/app\/admin\/users/);
  await expect(page.getByRole("heading", { name: "Пользователи", exact: true })).toBeVisible();
  expect(fixture.errors).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});

test("failed access save preserves the chosen role, queue and reason", async ({ page }) => {
  const fixture = await installUsersFixture(page);
  fixture.reject();
  await page.goto(`/app/admin/users?person=${marinaId}`);
  await page.getByRole("button", { name: "Учётная запись", exact: true }).click();
  await page.getByLabel("Логин", { exact: true }).fill("fixture-marina");
  await page.getByLabel("Пароль для нового входа", { exact: true }).fill("Only-Test-Password_839!");
  await page.getByLabel("Роль", { exact: true }).selectOption("support");
  await page.getByRole("button", { name: "Права и очереди", exact: true }).click();
  await page.getByRole("checkbox", { name: "ServiceDesk L1", exact: true }).check();
  await page.getByLabel("Причина изменения", { exact: true }).fill("Не терять черновик при конфликте");
  await page.getByRole("button", { name: "Сохранить доступ", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Доступ изменён другим администратором. Проверьте настройки." })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "ServiceDesk L1", exact: true })).toBeChecked();
  await expect(page.getByLabel("Причина изменения", { exact: true })).toHaveValue("Не терять черновик при конфликте");
  await page.getByRole("button", { name: "Учётная запись", exact: true }).click();
  await expect(page.getByLabel("Роль", { exact: true })).toHaveValue("support");
  await expect(page.getByLabel("Логин", { exact: true })).toHaveValue("fixture-marina");
  expect(fixture.writes).toEqual([]);
  expect(fixture.errors).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});

test("person card remains usable on a narrow screen", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const fixture = await installUsersFixture(page);
  await page.goto(`/app/admin/users?person=${marinaId}`);
  await expect(page.getByRole("heading", { name: "Пользователи", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Учётная запись", exact: true }).click();
  await expect(page.getByLabel("Логин", { exact: true })).toBeVisible();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: info.outputPath("users-mobile.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(fixture.errors).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});


test("person profile shows assigned computers from inventory", async ({ page }, info) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  const fixture = await installUsersFixture(page);
  await page.goto(`/app/admin/users?person=${marinaId}`);
  const card = page.getByRole("article", { name: "Карточка пользователя" });
  await card.getByText("Назначенные компьютеры", { exact: true }).click();
  await expect(card.getByText("Компьютер сотрудника", { exact: true })).toBeVisible();
  await expect(card.getByText(/Агент не в сети/)).toBeVisible();
  await expect(card.getByRole("link", { name: "Открыть в инвентаризации" })).toHaveAttribute("href", /fixture-pc$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("person-inventory.png"), fullPage: true });
  expect(fixture.errors).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});
