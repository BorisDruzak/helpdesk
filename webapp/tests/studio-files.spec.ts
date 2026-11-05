import { expect, test, type Page } from "playwright/test";
import { installStudioV3Fixture } from "./fixtures/studio-v3";
import type { ScenarioAttachment } from "../src/features/request-template-studio/scenario-contract";

const png = "iVBORw0KGgoAAAANSUhEUgAAAEAAAAAgCAIAAAAt/+nTAAAAT0lEQVR4nNXOMREAIBDAsNIJd9hBPiJ+4BoFWfseyiRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4iRO4vwdmHqdZQEPa89hlQAAAABJRU5ErkJggg==";
const files = [{name: "example.png", mimeType: "image/png", buffer: Buffer.from(png, "base64")}, {name: "steps.txt", mimeType: "text/plain", buffer: Buffer.from("Synthetic instruction document")}];
function asset(name: string, index: number): ScenarioAttachment {
  const id = `11111111-1111-4111-8111-${String(index).padStart(12, "0")}`;
  return {asset_id: id, name, mime_type: name.endsWith(".png") ? "image/png" : "text/plain", size_bytes: 100, url: `/api/web/request-scenario-assets/${id}/download`};
}
async function openMap(page: Page) {
  await page.goto("/app/admin/request-template-studio");
  await page.getByRole("region", {name: "Каталог услуг", exact: true}).getByRole("button", {name: "Настроить услугу Проблемы с печатью", exact: true}).click();
  await page.getByRole("button", {name: "Открыть карту сценария", exact: true}).click();
}
for (const width of [1366, 390]) {
  test(`Studio saves files with field help and instructions at ${width}`, async ({page}, info) => {
    await page.setViewportSize({width, height: width === 390 ? 844 : 768});
    const state = await installStudioV3Fixture(page); let uploaded = 0;
    const definition = state.definition();
    definition.blocks!.push({id: "instruction", kind: "instruction", title: "Памятка", content: {body: "Инструкция с материалами", format: "plain"}, transitions: [{to: "end"}]});
    const question = definition.blocks!.find(block => block.id === "q1");
    if (question?.kind !== "form_page") throw new Error("Missing fixture question");
    question.fields = [{key: "summary", type: "textarea", label: "Описание проблемы", help_text: "Приложите материалы", required: true}];
    await page.route("**/api/web/admin/request-studio/scenarios/v3/attachments", async route => {
      const body = route.request().postDataBuffer()!.toString();
      const name = /filename="([^"]+)"/.exec(body)?.[1] || "file";
      await route.fulfill({json: {status: "success", data: asset(name, ++uploaded)}});
    });
    await page.route("**/api/web/request-scenario-assets/*/download", route => route.fulfill({contentType: "image/png", body: Buffer.from(png, "base64")}));
    await openMap(page);
    await page.getByRole("list", {name: "Блоки сценария"}).getByRole("button", {name: "Тип проблемы", exact: true}).click();
    await page.getByLabel('Прикрепить скриншоты или файлы', {exact: true}).setInputFiles(files);
    await expect(page.getByRole("button", {name: "Открыть изображение example.png", exact: true})).toBeVisible();
    await page.getByRole("button", {name: "Сохранить черновик", exact: true}).click();
    await expect.poll(() => state.writes.length).toBe(1);
    await page.getByRole("list", {name: "Блоки сценария"}).getByRole("button", {name: "Памятка", exact: true}).click();
    await page.getByLabel('Прикрепить скриншоты или файлы', {exact: true}).setInputFiles(files);
    await expect(page.getByRole("link", {name: "steps.txt", exact: true})).toBeVisible();
    await page.getByRole("textbox", {name: "Текст инструкции", exact: true}).fill("Инструкция и два приложенных файла");
    await page.getByRole("button", {name: "Сохранить черновик", exact: true}).click();
    await expect.poll(() => state.writes.length).toBe(2);
    await page.reload();
    await page.getByRole("region", {name: "Каталог услуг", exact: true}).getByRole("button", {name: "Настроить услугу Проблемы с печатью", exact: true}).click();
    await page.getByRole("button", {name: "Открыть карту сценария", exact: true}).click();
    await page.getByRole("list", {name: "Блоки сценария"}).getByRole("button", {name: "Памятка", exact: true}).click();
    await expect(page.getByRole("textbox", {name: "Текст инструкции", exact: true})).toHaveValue("Инструкция и два приложенных файла");
    await page.getByRole("button", {name: "Открыть изображение example.png", exact: true}).click();
    await expect(page.getByRole("dialog", {name: "Просмотр изображения: example.png", exact: true})).toBeVisible();
    await page.getByRole("button", {name: "Закрыть просмотр изображения", exact: true}).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({path: info.outputPath(`studio-instruction-files-${width}.png`)});
    const saved = state.definition().blocks!;
    expect(saved.find(block => block.kind === "form_page" && block.id === "q1")?.kind).toBe("form_page");
    expect((saved.find(block => block.id === "q1") as typeof question).fields[0].help_attachments).toHaveLength(2);
    const instruction = saved.find(block => block.id === "instruction");
    expect(instruction?.kind === "instruction" && instruction.content.attachments?.length).toBe(2);
    expect(uploaded).toBe(4); expect(state.errors).toEqual([]); expect(state.unexpected).toEqual([]);
  });
}

async function requesterFixture(page: Page) {
  let current = "questions", revision = 1, answer = "", created = false, uploads = 0;
  let attachments: ScenarioAttachment[] = [];
  const submitted: object[] = [], errors: string[] = [], unexpected: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => {if (message.type() === "error") errors.push(message.text());});
  page.on("response", response => {if (response.status() >= 400) errors.push(`${response.status()} ${new URL(response.url()).pathname}`);});
  const material = asset("example.png", 100);
  const step = () => ({id: "files-session", revision, state: created ? "ticket_created" : "active", linked_ticket_id: created ? "file-ticket" : null, version_id: "version-files", back_targets: current === "questions" ? [] : [{id: "questions", title: "Описание проблемы"}],
    block: current === "questions" ? {id: current, kind: "form_page", title: "Описание проблемы", fields: [{key: "summary", type: "textarea", label: "Расскажите о проблеме", required: true, value: answer, help_text: "Приложите снимок и журнал", help_attachments: [material], answer_attachments: attachments}]} : current === "instruction" ? {id: current, kind: "instruction", title: "Памятка", acknowledgment_required: true, content: {body: "Откройте инструкцию и приложенный документ.", format: "plain", attachments: [material, asset("manual.txt", 101)]}} : current === "review" ? {id: current, kind: "review", title: "Проверьте ответы", answers: [{key: "summary", label: "Проблема", type: "textarea", value: answer, display_value: answer, answer_attachments: attachments}]} : {id: current, kind: "submit_ticket", title: "Отправка в поддержку"}});
  await page.route("**/api/web/**", async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    let data: unknown = {};
    if (path.endsWith("/session/me")) data = {user_login: "requester-files", actor_role: "user", default_workspace: "requester", available_workspaces: ["requester"], permissions: ["workspace.requester.view"]};
    else if (path.endsWith("/bootstrap")) data = {profile_completion: {complete: true}, devices: [], account_summary: {linked_profile: true}, feature_flags: {requester_ticket_create: true, requester_no_device_create: true}, policies: {}};
    else if (path.endsWith("unread_count")) return route.fulfill({json: {status: "ok", unread_count: 0}});
    else if (path.endsWith("/consents")) data = {consents: []};
    else if (path.includes("/request-scenario-assets/")) return route.fulfill({contentType: "image/png", body: Buffer.from(png, "base64")});
    else if (path.endsWith("/attachments") && request.method() === "POST") {
      const body = request.postDataBuffer()!.toString(); expect(body).toContain("summary"); expect(body).toContain("questions");
      const item = asset(/filename="([^"]+)"/.exec(body)?.[1] || "file", ++uploads); attachments.push(item); data = item;
    } else if (path.includes("/attachments/") && request.method() === "DELETE") {attachments = attachments.filter(item => !path.endsWith(item.asset_id)); data = {};}
    else if (path.includes("/request-scenarios/sessions")) {
      if (path.endsWith("/step-preview")) return route.fulfill({json: {status: "success", data: step()}});
      if (path.endsWith("/answer")) {const body = request.postDataJSON(); expect(body.answers.summary).toBe("Печать не работает"); answer = body.answers.summary; revision++; current = "instruction";}
      if (path.endsWith("/advance")) {current = current === "instruction" ? "review" : "submit"; revision++;}
      if (path.endsWith("/back")) {current = "questions"; revision++;}
      if (path.endsWith("/ticket-preview")) return route.fulfill({json: {status: "success", data: {ok: true, blockers: [], warnings: [], approval: {text: "Согласование не требуется"}}}});
      if (path.endsWith("/submit")) {submitted.push(request.postDataJSON()); created = true;}
      data = step();
    } else if (path.includes("/tickets/file-ticket")) data = {ticket: {ticket_id: "file-ticket", ticket_code: "T-009998", title: "Проверка файлов", status: "new", actions: {}}, messages: [{message_id: "files", from_role: "user", text: answer, attachments}], events: []};
    else unexpected.push(`${request.method()} ${path}`);
    return route.fulfill({json: {status: "success", data}});
  });
  await page.route("**/api/service-catalog/current*", route => route.fulfill({json: {status: "ok", catalog_version: "files", services: [{service_code: "it", title: "ИТ", offerings: [{offering_code: "print", full_code: "it.print", title: "Печать", request_template_key: "print", guided_scenario_enabled: true}]}]}}));
  await page.route("**/api/registry/options", route => route.fulfill({json: {status: "success", data: {departments: [], locations: []}}}));
  await page.route("**/public_api/ticket_forms/current**", route => route.fulfill({json: {status: "ok", pack: {key: "request_forms", version: "files", forms: [{key: "print", title: "Печать", fields: [], availability_policy: {available_without_agent_binding: true}}]}}}));
  await page.goto("/app/requester/new/?offering=it.print");
  return {submitted, errors, unexpected};
}
for (const width of [1366, 390]) {
  test(`requester persists answer files, removes one, sees instructions and submits at ${width}`, async ({page}, info) => {
    await page.setViewportSize({width, height: width === 390 ? 844 : 768});
    const state = await requesterFixture(page);
    const answer = page.getByRole("textbox", {name: /Расскажите о проблеме/});
    await answer.fill("Печать не работает");
    await page.getByLabel('Прикрепить скриншоты или файлы', {exact: true}).setInputFiles(files);
    await expect(page.getByRole("button", {name: "Убрать вложение steps.txt", exact: true})).toBeVisible();
    await expect(answer).toHaveValue("Печать не работает");
    await page.getByRole("button", {name: "Продолжить", exact: true}).click();
    await expect(page.getByRole("heading", {name: "Памятка", exact: true})).toBeVisible();
    await expect(page.getByRole("link", {name: "manual.txt", exact: true})).toBeVisible();
    await page.getByRole("button", {name: "Открыть изображение example.png", exact: true}).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("button", {name: "Закрыть просмотр изображения", exact: true}).click();
    await page.getByRole("button", {name: "Вернуться: Описание проблемы", exact: true}).click();
    await page.reload();
    await expect(answer).toHaveValue("Печать не работает");
    await expect(page.getByRole("button", {name: "Убрать вложение steps.txt", exact: true})).toBeVisible();
    await page.getByRole("button", {name: "Убрать вложение steps.txt", exact: true}).click();
    await expect(page.getByRole("button", {name: "Убрать вложение steps.txt", exact: true})).toHaveCount(0);
    await page.getByRole("button", {name: "Продолжить", exact: true}).click();
    await page.getByRole("checkbox", {name: "Инструкция выполнена", exact: true}).check();
    await page.getByRole("button", {name: "Продолжить", exact: true}).click();
    await expect(page.getByRole("definition").filter({hasText: "Печать не работает"})).toBeVisible();
    await expect(page.getByRole("button", {name: "Открыть изображение example.png", exact: true})).toBeVisible();
    await expect(page.getByRole("link", {name: "steps.txt", exact: true})).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({path: info.outputPath(`requester-file-review-${width}.png`)});
    await page.getByRole("button", {name: "Продолжить", exact: true}).click();
    await page.getByRole("button", {name: "Создать обращение", exact: true}).click();
    await expect(page.getByRole("heading", {name: "Проверка файлов", exact: true})).toBeVisible();
    expect(state.submitted).toHaveLength(1); expect(state.errors).toEqual([]); expect(state.unexpected).toEqual([]);
  });
}

test("requester native image and text paste retains both parts in the answer", async ({page}) => {
  const state = await requesterFixture(page);
  const answer = page.getByRole("textbox", {name: /Расскажите о проблеме/});
  await answer.fill("Описание:");
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.evaluate(async png => {
    const bytes = Uint8Array.from(atob(png), char => char.charCodeAt(0));
    await navigator.clipboard.write([new ClipboardItem({
      "image/png": new Blob([bytes], {type: "image/png"}),
      "text/plain": new Blob([" вставленный текст"], {type: "text/plain"}),
    })]);
  }, png);
  await answer.press("Control+v");
  await expect(answer).toHaveValue("Описание: вставленный текст");
  await expect(page.getByRole("button", {name: /^Убрать вложение/})).toHaveCount(1);
  expect(state.submitted).toHaveLength(0); expect(state.errors).toEqual([]);
});

test("Studio copy saves materials under the new scenario scope", async ({page}) => {
  const state = await installStudioV3Fixture(page);
  const source = asset("example.png", 77), copied = asset("example.png", 220);
  const question = state.definition().blocks!.find(block => block.id === "q1");
  if (question?.kind !== "form_page") throw new Error("Missing question");
  question.fields = [{key: "summary", type: "textarea", label: "Описание проблемы", help_attachments: [source]}];
  let creates = 0;
  await page.route("**/api/web/request-scenario-assets/*/download", route => route.fulfill({contentType: "image/png", body: Buffer.from(png, "base64")}));
  await page.route("**/api/web/admin/request-studio/services", async route => {
    const body = route.request().postDataJSON(); creates++;
    expect(body.copy_source_id).toBe("v3");
    expect(body.definition.blocks[0].fields[0].help_attachments).toEqual([source]);
    const definition = structuredClone(body.definition);
    definition.offering_full_code = "it.copy";
    definition.process_binding.request_template_key = "print";
    definition.blocks[0].fields[0].help_attachments = [copied];
    await route.fulfill({json: {status: "success", data: {scenario: {id: "copy-v3", archived: false}, draft: {revision: 1, definition}, asset_rebindings: {[source.asset_id]: copied}}}});
  });
  await openMap(page);
  await page.getByRole("button", {name: "Создать копию", exact: true}).click();
  await page.getByRole("button", {name: "Сохранить черновик", exact: true}).click();
  await expect(page.getByText(/Черновик сохранён/).first()).toBeVisible();
  await page.getByRole("list", {name: "Блоки сценария"}).getByRole("button", {name: "Тип проблемы", exact: true}).click();
  await expect(page.getByRole("img", {name: "Миниатюра: example.png", exact: true})).toHaveAttribute("src", copied.url);
  expect(creates).toBe(1); expect(state.errors).toEqual([]); expect(state.unexpected).toEqual([]);
});
