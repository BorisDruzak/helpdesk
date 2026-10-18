import { expect, type Page, test } from "playwright/test";
import { readFile } from "node:fs/promises";

const contact = { key: "preferred_contact_method", label: "Предпочтительный способ связи", type: "select", visible: true, editable: true, options: [
  { value: "phone", label: "Телефон" }, { value: "chat", label: "Чат в обращении" }, { value: "email", label: "Электронная почта" },
] };
const defaultFields = [
  { key: "full_name", label: "ФИО", type: "text", required: true, system: true, editable: true },
  { key: "login_identity", label: "Логин учетной записи", type: "identity", system: true, editable: false },
  { key: "department_id", label: "Подразделение", type: "department_picker", required: true, system: true, editable: true },
  { key: "location_id", label: "Локация", type: "location_picker", required: true, system: true, editable: true },
  { key: "phone", label: "Телефон или внутренний номер", type: "phone", required: true, system: true, editable: true },
  { key: "active_device_links", label: "Активные привязки устройств", type: "device_links", system: true, editable: false },
  contact,
];

async function actor(page: Page, role: "admin" | "user", extraPermissions: string[] = []) {
  await page.route("**/api/web/session/me", route => route.fulfill({ json: { status: "success", data: {
    user_login: "synthetic@example.test", actor_role: role, auth_type: "web_session", default_workspace: role === "admin" ? "admin" : "requester",
    available_workspaces: role === "admin" ? ["admin", "requester"] : ["requester"], permissions: [...(role === "admin" ? ["workspace.admin.view", "admin.registry.view"] : ["workspace.requester.view"]), ...extraPermissions],
  } } }));
  await page.route("**/api/web/notifications/unread_count", route => route.fulfill({ json: { status: "ok", unread_count: 0 } }));
}

for (const [width, height] of [[1366, 768], [1920, 1080]]) {
  test(`read-only readiness report shows feature impact and exports aggregates ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height });
    await actor(page, "admin");
    const errors: string[] = [], writes: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    page.on("request", request => { if (request.url().includes("/api/web/admin/registry") && request.method() !== "GET") writes.push(request.method()); });
    const registry = { summary: {}, assets: [], people: [], active_bindings: [], bindings: [], registration_claims: [], data_quality: [], locations: [], departments: [], ui_users: [], services: [], vendors: [], suggestions: [] };
    await page.route("**/api/web/admin/registry", route => route.fulfill({ json: { status: "success", data: registry } }));
    await page.route("**/api/web/admin/registry/password-reset-requests**", route => route.fulfill({ json: { status: "success", data: { items: [] } } }));
    await page.route("**/api/web/admin/registry/audience-groups", route => route.fulfill({ json: { status: "success", data: { groups: [] } } }));
    const counts = { blocks_function: 1, attention: 1, information: 1 };
    const labels = ["Идентичности", "Профили", "Подразделения", "Руководители", "Локации", "Устройства", "Схема профиля", "Очереди", "Карты v3"];
    const aggregate = { schema: "registry_scenario_readiness_aggregate_v1", counts, dimensions: labels.map((label, i) => ({ key: String(i), label, counts })) };
    let release: () => void = () => {};
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route("**/api/web/admin/registry/scenario-readiness", async route => {
      await pending;
      await route.fulfill({ json: { status: "success", data: { read_only: true, ...aggregate, export: aggregate, issues: [
        { kind: "scenario_manager_unavailable", issue_key: "scenario_manager_unavailable:request_template:access", severity: "danger", object_type: "request_template", object_id: "private-object", scenario_readiness: true, dimension: "managers", impact: "blocks_function", title: "Для услуги «Запрос доступа» невозможно определить согласующего", description: "Связь с руководителем не подтверждена.", affected_function: "Согласование руководителем", remediation: "Подтвердите руководителя или настройте резервного согласующего.", fix_href: "/app/admin/registry?tab=people" },
        { kind: "scenario_person_no_device", issue_key: "scenario_person_no_device:person:private-person", severity: "info", object_type: "person", object_id: "private-person", scenario_readiness: true, dimension: "devices", impact: "information", title: "Нет активной привязки компьютера", description: "Обычные обращения без устройства доступны.", affected_function: "Выбор устройства в сценарии" },
      ] } } });
    });
    await page.goto("/app/admin/registry?tab=quality");
    const check = page.getByRole("button", { name: "Проверить готовность к сценариям", exact: true });
    await expect(check).toBeInViewport();
    await check.click();
    await expect(page.getByText("Проверяем реестры, политики и опубликованные карты…")).toBeVisible();
    release();
    await expect(page.getByRole("heading", { name: "Готовность к сценариям", exact: true })).toBeVisible();
    await expect(page.getByText("Для услуги «Запрос доступа» невозможно определить согласующего", { exact: true })).toBeVisible();
    await expect(page.getByText("Обычные обращения без устройства доступны.", { exact: true })).toBeVisible();
    const downloadEvent = page.waitForEvent("download");
    await page.getByRole("button", { name: "Скачать агрегированный отчёт", exact: true }).click();
    const download = await downloadEvent;
    const path = info.outputPath("readiness.json"); await download.saveAs(path);
    const exported = await readFile(path, "utf8");
    expect(JSON.parse(exported).counts).toEqual(counts);
    expect(exported).not.toMatch(/private-object|private-person|issue_key|object_id/);
    await page.evaluate(() => scrollTo(0, 0));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`readiness-${width}.png`) });
    expect(writes).toEqual([]); expect(errors).toEqual([]);
  });

  test(`ordinary manager decides only the displayed assignment ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height });
    await actor(page, "user", ["approval.decide.assigned"]);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    await page.route("**/api/web/requester/bootstrap", route => route.fulfill({ json: { status: "success", data: { profile_completion: { complete: true, blocks: {} }, feature_flags: {}, policies: {}, recent_tickets: [], devices: [], pending_consents: [] } } }));
    let pending = true;
    let decision: unknown = null;
    await page.route("**/api/web/requester/approvals", route => route.fulfill({ json: { status: "success", data: { items: pending ? [{ approval_id: 7, ticket_id: "ticket-1", ticket_code: "T-1", title: "Синтетический запрос доступа", description: "Доступ к тестовой папке", status: "requested", can_decide: true, reject_requires_comment: true }] : [] } } }));
    await page.route("**/api/web/support/tickets/ticket-1/approvals/7/decision", async route => {
      decision = route.request().postDataJSON(); pending = false;
      await route.fulfill({ json: { status: "success", data: { approval: { status: "approved" } } } });
    });
    await page.goto("/app/requester/approvals");
    await expect(page.getByRole("heading", { name: "Ожидают моего решения", exact: true })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Боковая навигация заявителя" }).getByRole("link", { name: "Мои согласования", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Отклонить", exact: true })).toBeDisabled();
    const approve = page.getByRole("button", { name: "Согласовать", exact: true });
    await expect(approve).toBeInViewport();
    await page.getByLabel("Комментарий к решению").fill("Подтверждаю служебную необходимость");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`manager-${width}.png`) });
    await approve.click();
    await expect(page.getByText("Нет обращений, ожидающих вашего решения")).toBeVisible();
    expect(decision).toEqual({ decision: "approved", comment: "Подтверждаю служебную необходимость" });
    expect(errors).toEqual([]);
  });

  test(`administrator confirms pending organization in the existing person drawer ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height });
    await actor(page, "admin");
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    const person = { id: "p", person_id: "p", full_name: "Тестовый сотрудник", display_name: "Тестовый сотрудник", department_id: "old", department_name: "Прежний отдел", location_id: "loc", location_name: "Офис", status: "active", source: "test", organization_trust: { department_id: { state: "confirmed", value: "old", pending: { proposal_id: "proposal-1", value: "new", base_value: "old" } } } };
    const registry = { summary: {}, assets: [], people: [person], active_bindings: [], bindings: [], registration_claims: [], data_quality: [], locations: [{ location_id: "loc", display_name: "Офис" }], departments: [{ department_id: "old", name: "Прежний отдел" }, { department_id: "new", name: "Новый отдел" }], ui_users: [], services: [], vendors: [] };
    await page.route("**/api/web/admin/registry", route => route.fulfill({ json: { status: "success", data: registry } }));
    await page.route("**/api/web/admin/registry/password-reset-requests**", route => route.fulfill({ json: { status: "success", data: { items: [] } } }));
    await page.route("**/api/web/admin/registry/audience-groups", route => route.fulfill({ json: { status: "success", data: { groups: [] } } }));
    await page.route("**/api/web/admin/registry/timeline/person/p**", route => route.fulfill({ json: { status: "success", data: { items: [] } } }));
    let review: unknown = null;
    await page.route("**/api/web/admin/registry/people/p", async route => {
      review = route.request().postDataJSON();
      person.department_id = "new"; person.department_name = "Новый отдел";
      delete (person.organization_trust.department_id as { pending?: unknown }).pending;
      await route.fulfill({ json: { status: "success", data: { person } } });
    });
    await page.goto("/app/admin/registry");
    await page.getByRole("button", { name: "Пользователи", exact: true }).click();
    await page.getByRole("button", { name: "Тестовый сотрудник", exact: true }).click();
    await expect(page.getByText("Предложено: Новый отдел")).toBeVisible();
    await page.getByLabel("Причина решения").fill("Проверено на синтетических данных");
    await page.getByRole("button", { name: "Подтвердить изменение подразделения", exact: true }).click();
    await expect(page.getByText("Решение сохранено", { exact: true })).toBeVisible();
    expect(review).toEqual({ reason: "Проверено на синтетических данных", organization_review: { field: "department_id", proposal_id: "proposal-1", decision: "approve" } });
    await expect(page.getByText("Предложено: Новый отдел")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`review-${width}.png`) });
    expect(errors).toEqual([]);
  });

  test(`employee profile contact options typed values and legacy warning ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height });
    await actor(page, "user");
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    const profile = { person_id: "person-test", full_name: "Тестовый сотрудник", department_id: "dept", location_id: "loc", phone: "123", preferred_contact_method: "chat", custom_fields: { budget: 12.5, confirmed: false }, value_issues: [{ key: "retired", label: "Старое значение", message: "Проверьте сохранённое значение", code: "legacy_value_needs_correction" }] };
    const fields = [...defaultFields, { key: "budget", label: "Бюджет", type: "number", custom: true }, { key: "confirmed", label: "Подтверждение", type: "checkbox", custom: true, required: true }];
    const completion = { complete: true, required_fields: [], missing_fields: [], blocks: { ticket_create: false } };
    const data = { profile, profile_schema: { schema_key: "requester_profile", fields, required_fields: fields.filter(f => "required" in f && f.required).map(f => ({ key: f.key, label: f.label })) }, profile_completion: completion, profile_policy: { editable: true }, devices: [], active_bindings: [], pending_registration_claims: [] };
    await page.route("**/api/web/requester/bootstrap", route => route.fulfill({ json: { status: "success", data: { ...data, feature_flags: { requester_no_device_create: true }, policies: { device_selection_required: false }, recent_tickets: [], pending_consents: [] } } }));
    await page.route("**/api/registry/options", route => route.fulfill({ json: { status: "success", data: { departments: [{ value: "dept", label: "Подразделение" }], locations: [{ value: "loc", label: "Офис" }] } } }));
    let saved: Record<string, unknown> | null = null;
    await page.route("**/api/web/requester/profile", async route => {
      if (route.request().method() === "PUT") {
        saved = route.request().postDataJSON();
        Object.assign(profile, saved);
      }
      await route.fulfill({ json: { status: "success", data } });
    });
    await page.goto("/app/requester/profile");
    await expect(page.getByText("Старое значение: Проверьте сохранённое значение")).toBeVisible();
    await page.getByRole("button", { name: "Редактировать", exact: true }).click();
    await expect(page.getByLabel("Предпочтительный способ связи", { exact: true })).toHaveValue("chat");
    await expect(page.getByRole("option", { name: "Электронная почта", exact: true })).toBeAttached();
    await page.getByLabel("Предпочтительный способ связи", { exact: true }).selectOption("email");
    await page.getByRole("button", { name: /Сохранить профиль/ }).click();
    await expect.poll(() => saved).not.toBeNull();
    expect(saved!.custom_fields).toEqual({ budget: 12.5, confirmed: false });
    await page.reload();
    await expect(page.getByText("Электронная почта", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`employee-${width}.png`) });
    expect(errors).toEqual([]);
  });

  test(`profile schema default preview save reload and select editor ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });
    await actor(page, "admin");
    const schema = { schema_key: "requester_profile", fields: structuredClone(defaultFields), custom_fields: [], required_fields: [] };
    const registry = { summary: {}, assets: [], people: [], active_bindings: [], bindings: [], registration_claims: [], data_quality: [], locations: [], departments: [], ui_users: [], services: [], vendors: [] };
    await page.route("**/api/web/admin/registry", route => route.fulfill({ json: { status: "success", data: registry } }));
    await page.route("**/api/web/admin/registry/password-reset-requests**", route => route.fulfill({ json: { status: "success", data: { items: [] } } }));
    await page.route("**/api/web/admin/registry/audience-groups", route => route.fulfill({ json: { status: "success", data: { groups: [] } } }));
    await page.route("**/api/web/admin/access/summary", route => route.fulfill({ json: { status: "success", data: { groups: [], roles: [], permissions: [] } } }));
    let saves = 0;
    await page.route(/\/api\/web\/admin\/registry\/profile-schema(?:\/preview)?$/, async route => {
      if (route.request().method() === "PUT") {
        const payload = route.request().postDataJSON();
        schema.fields = [...defaultFields, ...payload.custom_fields];
        saves++;
      }
      await route.fulfill({ json: { status: "success", data: { schema, dry_run: route.request().url().endsWith("preview") } } });
    });
    await page.goto("/app/admin/registry");
    await page.getByRole("button", { name: /^Схема профиля/ }).click();
    const preview = page.getByRole("button", { name: "Предпросмотр", exact: true });
    await expect(preview).toBeEnabled();
    await preview.click();
    await page.getByLabel("Причина изменения").fill("Синтетическая проверка стандартной схемы");
    const save = page.getByRole("button", { name: "Сохранить схему", exact: true });
    await save.click();
    await expect.poll(() => saves).toBe(1);
    await page.getByLabel("Ключ поля", { exact: true }).fill("office_type");
    await page.getByLabel("Название", { exact: true }).fill("Тип офиса");
    await page.getByLabel("Тип", { exact: true }).selectOption("select");
    await page.getByRole("button", { name: "Добавить поле", exact: true }).click();
    await expect(preview).toBeDisabled();
    await page.getByRole("button", { name: "Добавить вариант", exact: true }).click();
    await page.getByLabel("Название варианта 1").fill("Основной офис");
    await page.getByLabel("Значение варианта 1").fill("main_office");
    await expect(preview).toBeEnabled();
    await page.getByLabel("Причина изменения").fill("Синтетическая настройка списка");
    await save.click();
    await expect.poll(() => saves).toBe(2);
    await page.reload();
    await page.getByRole("button", { name: /^Схема профиля/ }).click();
    await expect(page.getByLabel("Название варианта 1")).toHaveValue("Основной офис");
    await expect(page.getByLabel("Значение варианта 1")).toHaveValue("main_office");
    await page.evaluate(() => scrollTo(0, 0));
    await expect(save).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`schema-${width}.png`) });
    expect(errors).toEqual([]);
  });
}
