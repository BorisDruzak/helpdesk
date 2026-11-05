import { expect, test } from "playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }, { width: 390, height: 844 }]) {
  test(`service search and unknown-service intake ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [], unexpected: string[] = [], starts: Array<Record<string, unknown>> = [];
    let ticketWrites = 0;
    const entry = (key: string, title: string) => ({ key, title, entry_point_key: key, synonyms: [], scenario_key: "test", version_id: "published", target_block_id: "request" });
    const offerings = [
      { offering_code: "budget", full_code: "systems.budget", title: "Электронный бюджет", request_template_key: "general_request", guided_scenario_enabled: true, catalog_items: [entry("login", "Электронный бюджет: не удаётся войти")] },
      { offering_code: "eis", full_code: "systems.eis", title: "ЕИС — Единая информационная система в сфере закупок", request_template_key: "general_request", guided_scenario_enabled: true, catalog_items: [entry("login", "ЕИС: не удаётся войти")] },
      { offering_code: "actual_other", full_code: "other.actual_other", title: "Другая проблема или вопрос", request_template_key: "general_request", guided_scenario_enabled: true, catalog_items: [entry("not_found", "Не нашёл свою проблему")] },
      { offering_code: "computer", full_code: "systems.computer", title: "Компьютеры и системные блоки", request_template_key: "general_request", guided_scenario_enabled: true, catalog_items: [entry("power", "Компьютер не включается")] },
      { offering_code: "software", full_code: "systems.software", title: "Установка и изменение программ", request_template_key: "general_request", guided_scenario_enabled: true, catalog_items: [entry("launch", "Программа не запускается")] },
      { offering_code: "printer", full_code: "systems.printer", title: "Принтеры и МФУ", request_template_key: "general_request", guided_scenario_enabled: true, catalog_items: [entry("print", "Принтер не печатает")] },
    ];
    const services = [{ service_code: "systems", title: "Информационные системы", offerings }];
    // Feed the real pure backend search into the UI fixture, rather than duplicating its algorithm.
    const queries = ["не работает", "не включается", "не работает принтер", "электронный бюджет", "ЕИС", "совсем неизвестная услуга"];
    const searches = JSON.parse(execFileSync(process.env.PYTHON ?? "python", ["-X", "utf8", "-c",
      "import sys,json;sys.path.insert(0,sys.argv[1]);from tickets.service_catalog_search import search_public_catalog;p=json.load(sys.stdin);print(json.dumps({q:search_public_catalog(p['catalog'],q) for q in p['queries']}))",
      fileURLToPath(new URL("../../server", import.meta.url))], { input: JSON.stringify({ catalog: { services }, queries }), encoding: "utf8" }));
    const profile = { person_id: "synthetic-search", display_name: "Тестовый Сотрудник", full_name: "Тестовый Сотрудник", department_id: "it", phone: "0000" };
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
    await page.addInitScript(() => sessionStorage.setItem("pc_client.scenario.selection:employee:systems.budget", "remembered_wrong"));
    await page.route("**/api/**", async (route) => {
      const req = route.request(), url = new URL(req.url()), path = url.pathname; let data: unknown = {};
      if (path === "/api/web/session/me") data = { user_login: "employee", actor_role: "user", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"] };
      else if (path === "/api/web/session/capabilities") data = {};
      else if (path === "/api/web/requester/bootstrap") data = { workspace: "requester", profile, profile_completion: { complete: true, blocks: {} }, devices: [], primary_device: null, feature_flags: { requester_ticket_create: true, requester_no_device_create: true } };
      else if (path === "/api/web/notifications/unread_count") return route.fulfill({ json: { status: "ok", unread_count: 0 } });
      else if (path === "/api/web/requester/tickets") { if (req.method() === "POST") ticketWrites++; data = { tickets: [] }; }
      else if (path === "/api/service-catalog/current") {
        const q = url.searchParams.get("q") ?? "";
        if (q && !searches[q]) { unexpected.push(`uncovered search: ${q}`); return route.fulfill({ status: 400, json: { status: "error" } }); }
        return route.fulfill({ json: q ? { status: "ok", search: searches[q] }
          : { status: "ok", services, fallback: { ...offerings[2], entry_point_key: "not_found" } } });
      } else if (path === "/api/web/requester/request-scenarios/sessions") {
        const body = req.postDataJSON(); starts.push(body);
        data = { id: "search-session", revision: 1, state: "active", back_targets: [], block: { id: "request", kind: "form_page", title: body.entry_point_key === "not_found" ? "Опишите любую проблему" : "Опишите проблему в системе", layout: "group", fields: [{ key: "request_details", type: "textarea", label: "Что произошло?", required: true }] } };
      } else { unexpected.push(path); return route.fulfill({ status: 404, json: { status: "error" } }); }
      return route.fulfill({ json: { status: "success", data } });
    });
    await page.route("**/public_api/ticket_forms/current**", (route) => route.fulfill({ json: { status: "ok", pack: { key: "request_forms", version: "synthetic", forms: [{ key: "general_request", title: "Помощь", availability_policy: { available_without_agent_binding: true }, fields: [] }] } } }));
    await page.goto("/app/requester/new");
    const search = page.getByRole("searchbox", { name: "Найти проблему во всём каталоге" });
    await search.fill("не работает");
    await expect(page.getByRole("button", { name: /Компьютер не включается.*Компьютеры и системные блоки/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Принтер не печатает.*Принтеры и МФУ/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /ЕИС: не удаётся войти/ })).toBeVisible();
    await page.screenshot({ path: info.outputPath("generic-symptom.png"), fullPage: true });
    await search.fill("не включается");
    await expect(page.getByRole("button", { name: /Компьютер не включается/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Программа не запускается/ })).toBeVisible();
    await page.screenshot({ path: info.outputPath("startup-symptom.png"), fullPage: true });
    await search.fill("не работает принтер");
    await expect(page.getByRole("button", { name: /Принтер не печатает/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Компьютер не включается/ })).toHaveCount(0);
    await search.fill("электронный бюджет");
    await page.getByRole("button", { name: /^Электронный бюджет.*Услуга/ }).click();
    expect(starts).toEqual([]);
    await expect(page.getByRole("button", { name: "Электронный бюджет: не удаётся войти", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Электронный бюджет: не удаётся войти", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Опишите проблему в системе" })).toBeVisible();
    expect(starts[0]).toMatchObject({ offering_full_code: "systems.budget", entry_point_key: "login" });
    await search.fill("ЕИС");
    await expect(page.getByRole("button", { name: /^ЕИС.*Услуга/ })).toBeVisible();
    await page.screenshot({ path: info.outputPath("eis-service.png"), fullPage: true });
    await search.fill("совсем неизвестная услуга");
    await expect(page.getByText(/Услуга или проблема не найдена/)).toBeVisible();
    await page.screenshot({ path: info.outputPath("unknown-service.png"), fullPage: true });
    await page.getByRole("button", { name: "Не знаю / моей услуги нет в списке" }).click();
    await expect(page.getByRole("heading", { name: "Опишите любую проблему" })).toBeVisible();
    expect(starts[1]).toMatchObject({ offering_full_code: "other.actual_other", entry_point_key: "not_found" });
    expect(ticketWrites).toBe(0); expect(errors).toEqual([]); expect(unexpected).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
