import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "playwright/test";
import type { ScenarioDraftDefinition } from "../src/features/request-template-studio/scenario-contract";

const categoryId = "10000000-0000-0000-0000-000000000001";
const fixturePath = new URL("./fixtures/printer-pilot-v3.yaml", import.meta.url);
const documentJson = new URL("./fixtures/printer-pilot-v3.json", import.meta.url);
async function fixture(page: Page, role = "admin") {
 const source = await readFile(fixturePath, "utf8"), original = JSON.parse(await readFile(documentJson, "utf8")) as ScenarioDraftDefinition;
 const errors: string[] = [], unexpected: string[] = [], calls: { path: string; body: Record<string, unknown> }[] = [];
 let resourceError = false, failCreate = false, expected503 = false, created = false;
 let normalized: ScenarioDraftDefinition = { ...original, service_code: "it", offering_full_code: "it.imported", scenario_key: "imported", process_binding: { request_template_key: "generated" } };
 page.on("pageerror", error => errors.push(error.message)); page.on("console", message => { if (message.type() === "error" && !(expected503 && message.text().includes("503"))) errors.push(message.text()); });
 page.on("requestfailed", request => errors.push(request.url()));
 page.on("response", response => { if (response.status() >= 400 && !(expected503 && response.status() === 503 && response.url().endsWith("/services/from-document"))) errors.push(`${response.status()} ${response.url()}`); });
 await page.route("**/api/web/**", async route => {
  const request = route.request(), path = new URL(request.url()).pathname;
  let data: unknown = {};
  if (path.endsWith("/session/me")) data = { user_login: "fixture@example.test", actor_role: role, auth_type: "web_session", default_workspace: "admin", available_workspaces: ["admin"], permissions: ["workspace.admin.view"] };
  else if (path.endsWith("/request-studio/catalog")) data = { services: [{ code: "it", public_title: "ИТ", lifecycle_status: "published", visibility: "public" }, { code: "access", public_title: "Доступ", lifecycle_status: "published", visibility: "public" }], categories: [{ id: categoryId, service_code: "it", title: "Принтеры", lifecycle_status: "published", parent_id: null }], offerings: created ? [{ full_code: normalized.offering_full_code, service_code: normalized.service_code, public_title: normalized.title, request_template_key: "generated" }] : [], scenarios: [], total: 0, offset: 0, limit: 100 };
  else if (path.endsWith("/services/document-preview")) {
   const body = request.postDataJSON(); calls.push({ path, body });
   normalized = { ...normalized, service_code: body.service_code, category_id: body.category_id, entry_points: original.entry_points?.map(entry => ({ ...entry, category_id: body.category_id })) };
   data = { creation_key: body.creation_key, source_hash: "checked-document", definition: normalized, issues: resourceError ? [{ code: "processing_queue_unavailable", path: "processing.routes.printer_team.queue_code", message: "Очередь workplace_support недоступна. Выберите действующую очередь в документе." }] : [] };
  } else if (path.endsWith("/services/from-document")) {
   const body = request.postDataJSON(); calls.push({ path, body });
   if (failCreate) { failCreate = false; await route.fulfill({ status: 503, json: { status: "error", error_code: "TEMPORARY_UNAVAILABLE" } }); return; }
   expect(body.source_hash).toBe("checked-document"); created = true; data = { scenario: { id: "imported", archived: false }, draft: { revision: 1, definition: normalized } };
  } else if (path.endsWith("unread_count")) { await route.fulfill({ json: { status: "ok", unread_count: 0 } }); return; }
  else unexpected.push(`${request.method()} ${path}`);
  await route.fulfill({ json: { status: "success", data } });
 });
 return { source, errors, unexpected, calls, resourceError: (enabled = true) => { resourceError = enabled; }, failCreation: () => { failCreate = true; expected503 = true; } };
}
for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
 test(`create a new service from the original printer YAML file ${viewport.width}`, async ({ page }, info) => {
  await page.setViewportSize(viewport); const state = await fixture(page);
  await page.goto(`/app/admin/request-template-studio?service=it`);
  const open = page.getByRole("button", { name: "Создать услугу из JSON/YAML", exact: true }); await expect(open).toBeInViewport();
  await open.click(); const dialog = page.getByRole("dialog", { name: "Создать услугу из JSON/YAML", exact: true });
  await dialog.getByRole("combobox", { name: /^Категория новой услуги/ }).selectOption(categoryId);
  await dialog.getByLabel("Загрузить JSON/YAML", { exact: true }).setInputFiles(fileURLToPath(fixturePath));
  await expect(dialog.getByRole("textbox", { name: "Документ новой услуги", exact: true })).toHaveValue(state.source.replaceAll("\r\n", "\n"));
  expect(state.calls).toEqual([]);
  await dialog.getByRole("button", { name: "Проверить документ", exact: true }).click();
  await expect(dialog.getByText("Шагов: 16. Входов в каталог: 3.", { exact: true })).toBeVisible();
  expect(state.calls.map(call => call.path)).toEqual(["/api/web/admin/request-studio/services/document-preview"]);
  expect(state.calls[0].body).toMatchObject({ content: state.source, service_code: "it", category_id: categoryId, format: "yaml" });
  expect(state.source).toContain("service_code: workplace");
  await dialog.getByRole("button", { name: "Создать услугу-черновик", exact: true }).scrollIntoViewIfNeeded();
  await dialog.getByRole("region", { name: "Результат проверки документа", exact: true }).evaluate(element=>element.scrollIntoView({block:"center"}));
  const resultBounds=await dialog.getByRole("region",{name:"Результат проверки документа",exact:true}).boundingBox();
  const footerBounds=await dialog.locator(".studio-create-dialog__footer").boundingBox();
  expect(resultBounds && footerBounds && resultBounds.y+resultBounds.height<=footerBounds.y).toBe(true);
  await expect(dialog.getByText("Шагов: 16. Входов в каталог: 3.", { exact: true })).toBeInViewport();
  await expect(dialog.getByRole("button", { name: "Создать услугу-черновик", exact: true })).toBeInViewport();
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath(`${viewport.width}-import-preview.png`) });
  await dialog.getByRole("button", { name: "Создать услугу-черновик", exact: true }).click();
  await expect(dialog).toHaveCount(0); await expect(page.getByLabel("Визуальная карта сценария", { exact: true })).toBeVisible();
  expect(state.calls.filter(call => call.path.endsWith("/from-document"))).toHaveLength(1);
  expect(state.calls.some(call => call.path.includes("publish"))).toBe(false); expect(state.errors).toEqual([]); expect(state.unexpected).toEqual([]);
  await page.screenshot({ path: info.outputPath(`${viewport.width}-imported-draft.png`) });
 });
 test(`import validation edits and uncertain creation retry ${viewport.width}`, async ({ page }) => {
  await page.setViewportSize(viewport); const state = await fixture(page); state.resourceError();
  await page.goto("/app/admin/request-template-studio"); await page.getByRole("button", { name: "Создать услугу из JSON/YAML", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Создать услугу из JSON/YAML", exact: true });
  await dialog.getByRole("textbox", { name: "Документ новой услуги", exact: true }).fill(state.source);
  await dialog.getByRole("button", { name: "Проверить документ", exact: true }).click();
  await expect(dialog.getByText("processing.routes.printer_team.queue_code", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Создать услугу-черновик", exact: true })).toHaveCount(0);
  expect(state.calls.every(call => call.path.endsWith("/document-preview"))).toBe(true);
  const enteredSource=await dialog.getByRole("textbox",{name:"Документ новой услуги",exact:true}).inputValue();
  page.once("dialog",warning=>warning.dismiss());await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();await expect(dialog.getByRole("textbox",{name:"Документ новой услуги",exact:true})).toHaveValue(enteredSource);
  // The next fixture response represents a separately corrected document; the UI never remaps a queue.
  state.resourceError(false); state.failCreation();
  await dialog.getByRole("textbox", { name: "Документ новой услуги", exact: true }).fill(state.source + "\n# Исправленная копия\n");
  await dialog.getByRole("button", { name: "Проверить документ", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Создать услугу-черновик", exact: true })).toBeVisible();
  await dialog.getByRole("combobox", { name: /^Формат документа/ }).selectOption("json");
  await expect(dialog.getByRole("button", { name: "Создать услугу-черновик", exact: true })).toHaveCount(0);
  await dialog.getByRole("combobox", { name: /^Формат документа/ }).selectOption("yaml");
  await dialog.getByRole("button", { name: "Проверить документ", exact: true }).click();
  await dialog.getByRole("button", { name: "Создать услугу-черновик", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Создание не подтверждено");
  await dialog.getByRole("button", { name: "Создать услугу-черновик", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const attempts = state.calls.filter(call => call.path.endsWith("/from-document")); expect(attempts).toHaveLength(2); expect(attempts[0].body).toEqual(attempts[1].body);
  expect(state.errors).toEqual([]); expect(state.unexpected).toEqual([]);
 });
}
test("auditor has no create-from-document action", async ({ page }) => {
 await fixture(page, "auditor"); await page.goto("/app/admin/request-template-studio");
 await expect(page.getByText("Режим чтения: изменения доступны администратору.")).toBeVisible();
 await expect(page.getByRole("button", { name: "Создать услугу из JSON/YAML", exact: true })).toHaveCount(0);
});
test("creates a new draft from a JSON file with automatically selected format", async ({ page }) => {
 const state=await fixture(page);await page.goto("/app/admin/request-template-studio");await page.getByRole("button",{name:"Создать услугу из JSON/YAML",exact:true}).click();
 const dialog=page.getByRole("dialog",{name:"Создать услугу из JSON/YAML",exact:true});
 await dialog.getByLabel("Загрузить JSON/YAML",{exact:true}).setInputFiles(fileURLToPath(documentJson));
 await expect(dialog.getByRole("combobox",{name:/^Формат документа/})).toHaveValue("json");
 await dialog.getByRole("button",{name:"Проверить документ",exact:true}).click();await expect(dialog.getByText("Шагов: 16. Входов в каталог: 3.",{exact:true})).toBeVisible();
 expect(state.calls[0].body.format).toBe("json");expect(JSON.parse(String(state.calls[0].body.content))).toMatchObject({schema_version:3,service_code:"workplace"});
 await dialog.getByRole("button",{name:"Создать услугу-черновик",exact:true}).click();await expect(dialog).toHaveCount(0);
 expect(state.calls.filter(call=>call.path.endsWith("/from-document"))).toHaveLength(1);expect(state.errors).toEqual([]);expect(state.unexpected).toEqual([]);
});
