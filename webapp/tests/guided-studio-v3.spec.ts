import { expect, test, type Page, type TestInfo } from "playwright/test";
import { installStudioV3Fixture } from "./fixtures/studio-v3";

async function evidence(page: Page, info: TestInfo, name: string) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect.poll(async () => {
    const action = await page.getByRole("button", { name: "Сохранить черновик", exact: true }).boundingBox();
    return !!action && action.y >= 0 && action.y + action.height <= page.viewportSize()!.height;
  }).toBe(true);
  await page.screenshot({ path: info.outputPath(`${page.viewportSize()!.width}-${name}.png`) });
}
async function simulationAnswers(page: Page, scope: string) {
  await page.getByRole("radio", { name: "Принтер", exact: true }).check(); await page.getByRole("button", { name: "Продолжить проверку", exact: true }).click();
  await page.getByRole("radio", { name: scope, exact: true }).check(); await page.getByRole("button", { name: "Продолжить проверку", exact: true }).click();
  await page.getByRole("radio", { name: "Нет", exact: true }).check(); await page.getByRole("button", { name: "Продолжить проверку", exact: true }).click();
}
for (const viewport of [{ width: 1366, height: 768 }, { width: 1920, height: 1080 }]) {
 test(`schema v3 connected question choices initialize and follow source ${viewport.width}`, async ({ page }, info) => {
  await page.setViewportSize(viewport);
  const state = await installStudioV3Fixture(page);
  const decision = state.definition().blocks!.find(block => block.id === "logic")!;
  decision.transitions = [{ to: "end" }];
  await page.goto("/app/admin/request-template-studio");
  await page.getByRole("region", { name: "Каталог услуг", exact: true }).getByRole("button", { name: "Настроить услугу Проблемы с печатью", exact: true }).click();
  await page.getByRole("button", { name: "Открыть карту сценария", exact: true }).click();
  await page.getByText("Иначе", { exact: true }).click();
  const rule = page.getByRole("group", { name: "Условие перехода", exact: true });
  await rule.getByRole("button", { name: "Добавить условие", exact: true }).click();
  await expect(rule.getByRole("combobox", { name: "Правило", exact: true })).toHaveValue("eq");
  const source = rule.getByRole("combobox", { name: "Источник", exact: true });
  const value = rule.getByRole("combobox", { name: "Значение условия", exact: true });
  await expect(source).toHaveValue("issue");
  await expect(value.getByRole("option", { name: "Принтер", exact: true })).toHaveCount(1);
  await expect(value.getByRole("option", { name: "Сеть", exact: true })).toHaveCount(1);
  await value.selectOption("network");
  await source.selectOption("scope");
  await expect(rule.getByRole("combobox", { name: "Правило", exact: true })).toHaveValue("eq");
  await expect(value.getByRole("option", { name: "Весь отдел", exact: true })).toHaveCount(1);
  await expect(value.getByRole("option", { name: "Один сотрудник", exact: true })).toHaveCount(1);
  await expect(value.getByRole("option", { name: "Сеть", exact: true })).toHaveCount(0);
  await value.selectOption("single");
  await source.selectOption("work");
  await expect(value.getByRole("option", { name: "Да", exact: true })).toHaveCount(1);
  await expect(value.getByRole("option", { name: "Нет", exact: true })).toHaveCount(1);
  await evidence(page, info, "connected-question-choices");
  expect(state.writes).toEqual([]);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
 });
 test(`schema v3 map processing rules and server comparison ${viewport.width}`, async ({ page }, info) => {
  test.setTimeout(90000); await page.setViewportSize(viewport); const state = await installStudioV3Fixture(page);
  await page.goto("/app/admin/request-template-studio");
  await page.getByRole("region", { name: "Каталог услуг", exact: true }).getByRole("button", { name: "Настроить услугу Проблемы с печатью", exact: true }).click();
  await page.getByRole("button", { name: "Открыть карту сценария", exact: true }).click();
  await page.getByRole("button", { name: "Обработка услуги", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Куда направлять обращения", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: /^Очередь Helpdesk/ }).selectOption("network");
  await expect(page.getByRole("option", { name: "Отключённая очередь", exact: true })).toHaveCount(0);
  const urgent = page.getByRole("group", { name: "Срочный", exact: true });
  await urgent.getByRole("combobox", { name: /^Единица срока решения/ }).selectOption("60");
  await urgent.getByLabel("Срок решения", { exact: true }).fill("2");
  await urgent.getByRole("combobox", { name: /^Учёт времени/ }).selectOption("business");
  await urgent.getByRole("combobox", { name: /^Рабочий календарь/ }).selectOption("8");
  await page.getByRole("combobox", { name: /^Направление по умолчанию/ }).selectOption("support");
  await page.getByRole("combobox", { name: /^Профиль SLA по умолчанию/ }).selectOption("standard");
  await evidence(page, info, "map-local-sla");
  await urgent.getByRole("combobox", { name: /^Рабочий календарь/ }).scrollIntoViewIfNeeded();
  await evidence(page, info, "working-calendar");
  await page.getByRole("list", { name: "Блоки сценария" }).getByRole("button", { name: "Выбрать обработку", exact: true }).click();
  await expect(page.getByText(/Ответы могут отсутствовать.*Что не работает.*Кого затронуло/)).toBeVisible();
  await page.getByRole("button", { name: /Ветвь 1/ }).click();
  const condition = page.getByRole("group", { name: "Если", exact: true });
  await expect(condition.getByRole("combobox", { name: /^Источник/ })).toHaveCount(3);
  expect(await condition.getByRole("combobox", { name: /^Источник/ }).evaluateAll(elements => elements.map(element => (element as HTMLSelectElement).value))).toEqual(["issue", "scope", "work"]);
  await condition.getByRole("button", { name: "Добавить группу ИЛИ", exact: true }).first().click();
  await condition.getByRole("button", { name: "Добавить отрицание", exact: true }).first().click();
  await expect(condition.getByRole("combobox", { name: /^Правило/ }).first()).toHaveValue("not");
  await evidence(page, info, "nested-rule-groups");
  // Keep the fixed simulation response aligned with the original three-answer fixture rule.
  await page.getByRole("button", { name: "Отменить изменение", exact: true }).click();
  await page.getByRole("button", { name: "Отменить изменение", exact: true }).click();
  await page.getByRole("combobox", { name: /^Направление обращения/ }).selectOption("support");
  await page.getByRole("combobox", { name: /^Профиль SLA ветки/ }).selectOption("urgent");
  await page.getByLabel("Приоритет ветви", { exact: true }).fill("5");
  await evidence(page, info, "nested-rule-branch");
  const save = page.getByRole("button", { name: "Сохранить черновик", exact: true }); if (await save.isEnabled()) await save.click();
  await expect.poll(() => state.definition().blocks?.find(block => block.id === "logic")?.transitions?.[0].priority).toBe(5);
  expect(state.definition().processing?.sla_profiles.urgent).toMatchObject({ resolution_minutes: 120, time_basis: "business", calendar_id: 8 });
  await page.getByRole("button", { name: "Тестировать", exact: true }).click(); await page.getByRole("button", { name: "Начать проверку", exact: true }).click();
  await simulationAnswers(page, "Весь отдел");
  await expect(page.getByText("Приоритет: P1", { exact: true })).toBeVisible(); await expect(page.getByText(/Ответить до:/)).toBeVisible();
  expect(await page.getByRole("complementary", { name: "Контекстный инспектор", exact: true }).evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await page.getByText(/Выбрать обработку · ветвь 1.*выбрана/).click();
  await expect(page.getByText("Все условия (И)", { exact: false })).toBeVisible();
  await expect(page.getByText("✓ Выполнено", { exact: true })).toHaveCount(4);
  await evidence(page, info, "condition-evaluation-matched");
  await page.getByRole("button", { name: "Сохранить результат и сравнить другой набор ответов", exact: true }).click();
  await simulationAnswers(page, "Один сотрудник");
  const compare = page.getByRole("region", { name: "Сравнение двух проверок" }); await expect(compare).toBeVisible();
  await expect(compare.getByText("Приоритет: P1", { exact: true })).toBeVisible(); await expect(compare.getByText("Приоритет: P3", { exact: true })).toBeVisible();
  await expect(compare.getByText("SLA: Срочный", { exact: true })).toBeVisible(); await expect(compare.getByText("SLA: Стандартный", { exact: true })).toBeVisible();
  await compare.evaluate(element => element.scrollIntoView({ block: "start" }));
  await evidence(page, info, "server-trace-comparison");
  await page.getByText(/Выбрать обработку · ветвь 1.*не выбрана/).click();
  await page.getByText("— Не выполнено", { exact: true }).last().scrollIntoViewIfNeeded();
  await expect(page.getByText("— Не выполнено", { exact: true })).toHaveCount(2);
  await evidence(page, info, "condition-evaluation-unmatched");
  expect(state.errors).toEqual([]); expect(state.unexpected).toEqual([]); expect(state.writes.every(write => ["draft", "simulate"].includes(write))).toBe(true);
 });
}
