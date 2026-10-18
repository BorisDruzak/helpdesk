import { expect, test } from "playwright/test";
import { installStudioV3Fixture } from "./fixtures/studio-v3";

for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
  test(`connect an answer handle and reconnect a saved branch ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const state = await installStudioV3Fixture(page);
    state.definition().blocks = [
      { id: "q1", kind: "form_page", title: "123", fields: [{ key: "working", label: "Работает принтер?", type: "checkbox" }], transitions: [{ to: "logic" }] },
      { id: "logic", kind: "decision", title: "Условие", transitions: [{ to: "yes", when: { source: "answer", field: "working", op: "eq", value: true }, priority: 7, processing: { route: "support", sla_profile: "urgent" } }] },
      { id: "yes", kind: "instruction", title: "Проверить печать", content: { body: "Проверка" }, transitions: [] },
      { id: "no", kind: "instruction", title: "Проверить подключение", content: { body: "Проверка кабеля" }, transitions: [] },
    ];
    state.definition().entry_points = [{ key: "main", title: "Проверка принтера", target_block_id: "q1" }];
    state.definition().editor_layout = { positions: { system_start: { x: -300, y: 0 }, q1: { x: 0, y: 0 }, logic: { x: 320, y: 0 }, yes: { x: 640, y: -120 }, no: { x: 640, y: 200 } } };
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Каталог услуг", exact: true }).getByRole("button", { name: "Настроить услугу Проблемы с печатью", exact: true }).click();
    await page.getByRole("button", { name: "Открыть карту сценария", exact: true }).click();
    const node = page.locator('.react-flow__node[data-id="logic"]');
    const destination = page.locator('.react-flow__node[data-id="no"] .react-flow__handle.target');
    async function drag(handle: ReturnType<typeof page.locator>) {
      const source = await handle.boundingBox(), target = await destination.boundingBox();
      expect(source).not.toBeNull(); expect(target).not.toBeNull();
      await page.mouse.move(source!.x + source!.width / 2, source!.y + source!.height / 2);
      await page.mouse.down();
      await page.mouse.move(target!.x + target!.width / 2, target!.y + target!.height / 2, { steps: 15 });
      await page.mouse.up();
    }
    await drag(node.locator('.react-flow__handle[data-handleid="answer-1"]'));
    await expect(node.locator('.react-flow__handle[data-handleid="route-1"]')).toHaveCount(1);
    await drag(node.locator('.react-flow__handle[data-handleid="route-0"]'));
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect.poll(() => state.definition().blocks![1].transitions![0].to).toBe("no");
    expect(state.definition().blocks![1].transitions).toEqual([
      { to: "no", when: { source: "answer", field: "working", op: "eq", value: true }, priority: 7, processing: { route: "support", sla_profile: "urgent" } },
      { to: "no", when: { source: "answer", field: "working", op: "eq", value: false } },
    ]);
    expect(state.errors).toEqual([]); expect(state.unexpected).toEqual([]);
    expect(state.writes.every(write => write === "draft")).toBe(true);
  });
  test(`build yes and no branches from an empty condition ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = await installStudioV3Fixture(page);
    state.definition().blocks = [
      { id: "q1", kind: "form_page", title: "123", fields: [{ key: "working", label: "Работает принтер?", type: "checkbox", required: true }], transitions: [{ to: "logic" }] },
      { id: "logic", kind: "decision", title: "Условие", transitions: [] },
    ];
    state.definition().entry_points = [{ key: "main", title: "Проверка принтера", target_block_id: "q1" }];
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Каталог услуг", exact: true }).getByRole("button", { name: "Настроить услугу Проблемы с печатью", exact: true }).click();
    await page.getByRole("button", { name: "Открыть карту сценария", exact: true }).click();
    const library = page.getByRole("list", { name: "Блоки сценария", exact: true });
    await library.getByRole("button", { name: "Условие", exact: true }).click();
    const branches = page.getByRole("region", { name: "Ветвление по ответам", exact: true });
    await expect(branches.getByRole("combobox", { name: "Вопрос для ветвления", exact: true })).toHaveValue("working");
    await expect(branches.getByRole("group", { name: "Ответ «Да»", exact: true })).toBeVisible();
    await expect(branches.getByRole("group", { name: "Ответ «Нет»", exact: true })).toBeVisible();
    await expect(branches.getByRole("option", { name: "123", exact: true })).toHaveCount(0);
    // The first target is created from the answer on the node, not pre-seeded.
    await page.getByRole("button", { name: "Добавить шаг для «Да» после «Условие»", exact: true }).click();
    await page.getByRole("dialog", { name: "Что добавить дальше?", exact: true }).getByRole("button", { name: /^Показать инструкцию/ }).click();
    await expect(page.getByRole("textbox", { name: "Текст инструкции", exact: true })).toBeVisible();
    await library.getByRole("button", { name: "Условие", exact: true }).click();
    // A second independent target is created from the inspector.
    await branches.getByRole("button", { name: "Добавить шаг для «Нет»", exact: true }).click();
    await page.getByRole("dialog", { name: "Что добавить дальше?", exact: true }).getByRole("button", { name: /^Спросить сотрудника/ }).click();
    await expect(page.getByRole("textbox", { name: "Что спросить?", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Отменить изменение", exact: true }).click();
    await expect(library.getByRole("button")).toHaveCount(3);
    await page.getByRole("button", { name: "Повторить изменение", exact: true }).click();
    await expect(library.getByRole("button")).toHaveCount(4);
    await page.getByRole("button", { name: "Сохранить черновик", exact: true }).click();
    await expect.poll(() => state.definition().blocks?.length).toBe(4);
    const saved = structuredClone(state.definition());
    const decision = saved.blocks!.find(block => block.id === "logic")!;
    expect(decision.transitions).toHaveLength(2);
    const [yes, no] = decision.transitions!;
    expect(yes.when).toEqual({ source: "answer", field: "working", op: "eq", value: true });
    expect(no.when).toEqual({ source: "answer", field: "working", op: "eq", value: false });
    expect(yes.to).not.toBe(no.to);
    expect(saved.blocks!.find(block => block.id === yes.to)!.kind).toBe("instruction");
    expect(saved.blocks!.find(block => block.id === no.to)!.kind).toBe("form_page");
    expect(saved.blocks!.find(block => block.id === yes.to)!.transitions ?? []).toEqual([]);
    expect(saved.blocks![0].transitions).toEqual([{ to: "logic" }]);
    // Save also refreshes the catalog. Let that request finish before the
    // deliberate full reload so navigation does not abort our own refresh.
    await page.waitForLoadState("networkidle");
    await page.reload();
    await page.getByRole("region", { name: "Каталог услуг", exact: true }).getByRole("button", { name: "Настроить услугу Проблемы с печатью", exact: true }).click();
    await page.getByRole("button", { name: "Открыть карту сценария", exact: true }).click();
    await library.getByRole("button", { name: "Условие", exact: true }).click();
    await expect(branches.getByRole("group", { name: "Ответ «Да»", exact: true }).getByRole("combobox", { name: "Следующий шаг", exact: true })).toHaveValue(yes.to);
    await expect(branches.getByRole("group", { name: "Ответ «Нет»", exact: true }).getByRole("combobox", { name: "Следующий шаг", exact: true })).toHaveValue(no.to);
    const canvas = page.getByLabel("Визуальная карта сценария", { exact: true });
    await expect(canvas.getByText("Работает принтер? равно «Да»", { exact: true })).toBeVisible();
    await expect(canvas.getByText("Работает принтер? равно «Нет»", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${viewport.width}-answer-branches.png`) });
    expect(state.writes.length).toBeGreaterThan(0);
    expect(state.writes.every(write => write === "draft")).toBe(true);
    expect(state.errors).toEqual([]);
    expect(state.unexpected).toEqual([]);
  });
}
