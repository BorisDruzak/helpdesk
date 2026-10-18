import { expect, type Page, test } from "playwright/test";

async function catalogFixture(page: Page) {
  const sessions: unknown[] = [], searchQueries: string[] = [], errors: string[] = [], failures: string[] = [];
  let releaseSearch!: () => void;
  const pending = new Promise<void>(resolve => { releaseSearch = resolve; });
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && !message.text().includes("503 (Service Unavailable)")) errors.push(message.text()); });
  page.on("requestfailed", request => failures.push(request.url()));
  page.on("response", response => { if (response.status() >= 400 && !(response.status() === 503 && new URL(response.url()).searchParams.get("q") === "сбой")) failures.push(`${response.status()} ${response.url()}`); });
  const entries = Array.from({ length: 86 }, (_, index) => ({ key: `entry_${index + 1}`, entry_point_key: `entry_${index + 1}`, title: `Проблема принтера ${index + 1}`, description: "Помощь с печатью", synonyms: [], scenario_key: "printer", version_id: "v1", target_block_id: "check" }));
  const fallback = { offering_code: "unknown", full_code: "other.unknown", title: "Общее обращение", request_template_key: "general_request" };
  await page.route("**/api/web/**", async route => {
    const path = new URL(route.request().url()).pathname; let data: unknown = {};
    if (path === "/api/web/session/me") data = { user_login: "selector@example.test", actor_role: "user", auth_type: "web_session", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
    else if (path.endsWith("/requester/bootstrap")) data = { profile: { person_id: "p1", display_name: "Сотрудник" }, profile_completion: { complete: true, blocks: {} }, devices: [], feature_flags: { requester_ticket_create: true, requester_no_device_create: true } };
    else if (path.includes("/request-scenarios/sessions")) {
      if (route.request().method() === "POST") sessions.push(route.request().postDataJSON());
      data = { id: "selector-session", revision: 1, state: "active", back_targets: [], block: { id: "check", kind: "instruction", title: "Проверьте бумагу", content: { body: "Инструкция выбранного входа" } } };
    } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
    await route.fulfill({ json: { status: "success", data } });
  });
  await page.route("**/public_api/ticket_forms/current**", route => route.fulfill({ json: { status: "ok", pack: { pack_key: "request_forms", version: "test", forms: [
    { key: "printer", title: "Принтер", fields: [], available_without_agent_binding: true },
    { key: "general_request", title: "Общее обращение", fields: [{ key: "free_description", type: "textarea", label: "Опишите, что случилось", required: true }], available_without_agent_binding: true },
    { key: "standalone", title: "Доступ к архиву", description: "Документы прошлых лет", fields: [{ key: "details", type: "text", label: "Какой архив нужен?" }], available_without_agent_binding: true },
  ] } } }));
  await page.route("**/api/service-catalog/current*", async route => {
    const query = new URL(route.request().url()).searchParams.get("q");
    if (query !== null) {
      searchQueries.push(query);
      if (query === "сбой") { await route.fulfill({ status: 503, json: { status: "error" } }); return; }
      if (query === "принтр") await pending;
      await route.fulfill({ json: { status: "ok", search: { results: query === "принтр" ? [{ title: "Принтер не печатает", description: "Проверьте очередь", category: "Рабочее место", offering_full_code: "workplace.printer", entry_point_key: "entry_1", help_mode: "guided", match_reason: "Совпало дополнительное поисковое выражение" }] : [], suggestions: [], corrected_query: query === "принтр" ? "принтер" : null } } }); return;
    }
    await route.fulfill({ json: { status: "ok", catalog_version: "test", fallback, services: [
      { service_code: "workplace", title: "Рабочее место", offerings: [{ offering_code: "printer", full_code: "workplace.printer", title: "Принтер", request_template_key: "printer", guided_scenario_enabled: true, catalog_items: entries }] },
      { service_code: "other", title: "Другое", offerings: [fallback] },
    ] } });
  });
  return { sessions, searchQueries, errors, failures, releaseSearch };
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`unified selector empty list keyboard and fallback ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport); const state = await catalogFixture(page); await page.goto("/app/requester/new");
    const input = page.getByRole("combobox", { name: "Найти проблему во всём каталоге", exact: true });
    const fallback = page.getByRole("button", { name: "Не нашёл свою проблему", exact: true });
    await expect(input).toBeVisible(); await expect(fallback).toBeEnabled();
    await expect(page.getByRole("combobox")).toHaveCount(2); // Search and the independent device context picker.
    await expect(page.getByLabel("Категория обращения", { exact: true })).toHaveCount(0);
    await input.focus(); await expect(page.getByRole("listbox", { name: "Доступные проблемы" })).toBeVisible();
    expect(state.sessions).toEqual([]); expect(state.searchQueries).toEqual([]);
    for (let index = 0; index < 86; index++) await input.press("ArrowDown");
    const last = page.getByRole("option").filter({ has: page.getByText("Проблема принтера 86", { exact: true }) });
    await expect(last).toBeInViewport({ ratio: 1 }); await expect(fallback).toBeInViewport({ ratio: 1 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-catalog-keyboard-list.png`) });
    await input.press("Enter"); await expect(page.getByRole("heading", { name: "Проверьте бумагу", exact: true })).toBeVisible();
    expect(state.sessions).toEqual([{ offering_full_code: "workplace.printer", entry_point_key: "entry_86" }]);
    await page.getByRole("button", { name: "Изменить проблему", exact: true }).click(); await expect(input).toBeFocused();
    expect(state.sessions).toHaveLength(1); await input.press("Escape");
    await fallback.click(); await expect(page.getByLabel("Опишите, что случилось")).toBeVisible();
    await expect(page.getByText("Выбрано: Общее обращение", { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Найти проблему", exact: true })).toHaveCount(0);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-catalog-fallback-form.png`) });
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
  test(`unified selector server search states and standalone form ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport); const state = await catalogFixture(page); await page.goto("/app/requester/new");
    const input = page.getByRole("combobox", { name: "Найти проблему во всём каталоге", exact: true });
    const fallback = page.getByRole("button", { name: "Не нашёл свою проблему", exact: true });
    await input.fill("принтр"); await expect(page.getByText("Ищем подходящие проблемы…", { exact: true })).toBeVisible();
    await expect(fallback).toBeEnabled(); expect(state.sessions).toEqual([]); state.releaseSearch();
    await expect(page.getByRole("option", { name: /Принтер не печатает/ })).toBeVisible();
    await expect(page.getByText("Возможно, вы имели в виду: принтер", { exact: true })).toBeVisible(); await expect(fallback).toBeEnabled();
    await input.fill("ничего"); await expect(page.getByRole("option", { name: /Принтер не печатает/ })).toHaveCount(0);
    await expect(page.getByText("Подходящих проблем не найдено. Попробуйте другое описание.", { exact: true })).toBeVisible(); await expect(fallback).toBeEnabled();
    await input.fill("сбой"); await expect(page.getByRole("alert")).toContainText("Не удалось выполнить поиск"); await expect(fallback).toBeEnabled();
    await page.screenshot({ path: info.outputPath(`${viewport.width}-catalog-search-error.png`) });
    await input.fill("прошлых лет"); await page.getByRole("option", { name: /Доступ к архиву/ }).click();
    await expect(page.getByLabel("Какой архив нужен?")).toBeVisible(); expect(state.sessions).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(state.errors).toEqual([]); expect(state.failures).toEqual([]);
  });
}
