import { expect, test } from "playwright/test";
import { installStudioV3Fixture } from "./fixtures/studio-v3";

for (const width of [1366, 1920]) {
  test(`visual page, question order, resize and distinct buttons ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1366 ? 768 : 1080 });
    const state = await installStudioV3Fixture(page);
    const definition = state.definition();
    definition.schema_version = 4;
    definition.execution_semantics = 3;
    const first = definition.blocks!.find(block => block.id === "q1")!;
    if (first.kind !== "form_page") throw new Error("Expected form page");
    first.layout = "group";
    first.fields.push({ key: "contact", label: "Контакт для связи", type: "text" }, { key: "details", label: "Описание проблемы", type: "textarea" });
    first.transition_mode = "buttons";
    first.transitions = [
      { to: "q2", button: { key: "route-a", label: "Продолжить" } },
      { to: "q3", button: { key: "route-b", label: "Продолжить" } },
    ];
    await page.route("**/api/web/notifications/push/config", route => route.fulfill({ json: { status: "ok", enabled: false, public_key: null } }));
    await page.route("**/request-studio/fragments", route => route.fulfill({ json: { status: "success", data: { items: [], total: 0 } } }));
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("button", { name: "Настроить услугу Проблемы с печатью", exact: true }).dblclick();
    await page.getByRole("list", { name: "Блоки сценария", exact: true }).getByRole("button", { name: "Тип проблемы", exact: true }).click();
    await page.locator('[data-id="q1"] .studio-map-node').dblclick();
    await expect(page.getByLabel("Вопрос 1", { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Что спросить?", exact: true })).toHaveCount(3);
    await expect(page.getByRole("button", { name: "Оформить подсказку визуально", exact: true })).toHaveCount(0);
    await page.getByLabel("Вопрос 2", { exact: true }).getByRole("textbox", { name: "Что спросить?", exact: true }).fill("Телефон для связи");
    await page.getByRole("button", { name: "Переместить вопрос 2", exact: true }).press("ArrowUp");
    await expect(page.getByLabel("Вопрос 1", { exact: true }).getByRole("textbox", { name: "Что спросить?", exact: true })).toHaveValue("Телефон для связи");
    await page.getByRole("button", { name: "Переместить вопрос 3", exact: true }).press("ArrowUp");
    await page.getByRole("button", { name: "Развернуть редактор", exact: true }).click();
    const full = page.getByRole("dialog", { name: "Полный редактор блока", exact: true });
    await expect(full).toBeVisible();
    // Keep both handles visible before the gesture; dragTo's independent
    // autoscrolls can move the source before Chromium starts native dragging.
    await full.locator('.studio-resizable-editor__body').evaluate(body => {
      const firstHandle = body.querySelector('[aria-label="Переместить вопрос 1"]')!;
      body.scrollTop += firstHandle.getBoundingClientRect().top - body.getBoundingClientRect().top - 12;
    });
    const sourceHandle = page.getByRole("button", { name: "Переместить вопрос 2", exact: true });
    await expect(sourceHandle).toBeInViewport();
    const sourcePoint = (await sourceHandle.boundingBox())!;
    const targetPoint = (await page.getByLabel("Вопрос 1", { exact: true }).boundingBox())!;
    await page.mouse.move(sourcePoint.x + 20, sourcePoint.y + sourcePoint.height / 2);
    await page.mouse.down();
    await page.mouse.move(sourcePoint.x + 28, sourcePoint.y + 4, { steps: 3 });
    await page.mouse.move(targetPoint.x + targetPoint.width / 2, targetPoint.y + targetPoint.height / 2, { steps: 12 });
    await page.mouse.move(targetPoint.x + targetPoint.width / 2 + 2, targetPoint.y + targetPoint.height / 2 + 2);
    await page.mouse.up();
    await expect(page.getByLabel("Вопрос 1", { exact: true }).getByRole("textbox", { name: "Что спросить?", exact: true })).toHaveValue("Описание проблемы");
    await page.getByRole("spinbutton", { name: "Количество вопросов", exact: true }).fill("2");
    await expect(page.getByRole("textbox", { name: "Что спросить?", exact: true })).toHaveCount(3);
    await page.getByRole("spinbutton", { name: "Количество вопросов", exact: true }).fill("4");
    await expect(page.getByRole("textbox", { name: "Что спросить?", exact: true })).toHaveCount(4);
    await page.getByRole("button", { name: "Изменить размер полного редактора", exact: true }).press("ArrowLeft");
    expect(await full.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`question-page-${width}.png`), fullPage: true });
    await page.getByRole("button", { name: "Вернуться к карте", exact: true }).click();
    const node = page.locator('[data-id="q1"] .studio-map-node');
    const before = (await node.boundingBox())!;
    await page.getByRole("button", { name: "Изменить размер редактора блока", exact: true }).press("ArrowRight");
    await expect.poll(async () => (await node.boundingBox())!.width).toBeGreaterThan(before.width);
    const inlineEditor = node.locator('.studio-resizable-editor');
    const editorBeforePointer = (await inlineEditor.boundingBox())!;
    const resizeHandle = (await page.getByRole("button", { name: "Изменить размер редактора блока", exact: true }).boundingBox())!;
    await page.mouse.move(resizeHandle.x + resizeHandle.width / 2, resizeHandle.y + resizeHandle.height / 2);
    await page.mouse.down();
    await page.mouse.move(resizeHandle.x + resizeHandle.width / 2 + 45, resizeHandle.y + resizeHandle.height / 2 + 30, { steps: 8 });
    await page.mouse.up();
    await expect.poll(async () => (await inlineEditor.boundingBox())!.width).toBeGreaterThan(editorBeforePointer.width);
    const sizePreferenceKey = 'studio-editor-size:v1:print:q1:inline';
    const preferredSize = await page.evaluate(key => JSON.parse(localStorage.getItem(key) ?? 'null'), sizePreferenceKey);
    expect(preferredSize).toMatchObject({ width: expect.any(Number), height: expect.any(Number) });
    await page.getByRole("separator", { name: "Высота редактора", exact: true }).press("Home");
    for (let zoom = 0; zoom < 4; zoom++) await page.getByRole("button", { name: "Zoom In", exact: true }).click();
    await expect.poll(() => inlineEditor.evaluate(element => element.clientHeight)).toBeGreaterThanOrEqual(160);
    await page.getByRole("separator", { name: "Высота редактора", exact: true }).press("End");
    await expect.poll(() => inlineEditor.evaluate(element => element.clientHeight)).toBeGreaterThan(160);
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key) ?? 'null'), sizePreferenceKey)).toEqual(preferredSize);
    await page.locator('.studio-map-toolbar > details > summary').click();await page.getByRole("button",{name:"Редактировать выбранный блок",exact:true}).click();await page.locator('.studio-map-toolbar > details > summary').click();
    await page.getByRole("button", { name: "Вся карта", exact: true }).click();
    await page.locator('[data-scenario-edge="q1:0"] input').fill("Проверить принтер");
    await page.locator('[data-scenario-edge="q1:0"] input').press("Enter");
    await page.locator('[data-scenario-edge="q1:1"] input').fill("Проверить подключение");
    await page.locator('[data-scenario-edge="q1:1"] input').press("Enter");
    await expect.poll(() => {
      const block = state.definition().blocks!.find(item => item.id === "q1")!;
      return block.transitions!.map(edge => [edge.button?.key, edge.button?.label]);
    }).toEqual([["route-a", "Проверить принтер"], ["route-b", "Проверить подключение"]]);
    await page.locator('[data-scenario-edge="q2:0"] .studio-route-button').click();
    const popup = page.locator('[data-scenario-edge="q2:0"] .studio-resizable-editor');
    await expect(popup).toBeVisible();
    await page.getByRole("button", { name: "Размер редактора перехода", exact: true }).press("ArrowLeft");
    expect(await popup.locator('.studio-resizable-editor__body').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    await expect(popup.getByRole("button", { name: "Закрыть", exact: true })).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByRole("button", { name: "Сохранить черновик", exact: true })).toBeInViewport();
    await page.screenshot({ path: info.outputPath(`connections-and-popover-${width}.png`), fullPage: true });
    expect(state.errors).toEqual([]);
    expect(state.unexpected).toEqual([]);
  });
}
