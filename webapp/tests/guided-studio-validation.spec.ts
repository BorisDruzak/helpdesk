import { expect, test } from "playwright/test";
import { installStudioV3Fixture } from "./fixtures/studio-v3";

for (const width of [1366, 1920]) {
  test(`explains Else and draft rejection without losing edits ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1366 ? 768 : 1080 });
    const state = await installStudioV3Fixture(page);
    const decision = state.definition().blocks!.find(block => block.id === "logic")!;
    decision.transitions = decision.transitions!.filter(edge => edge.when);
    let rejectSave = true;
    await page.route("**/scenarios/v3/draft", async route => {
      if (!rejectSave) return route.fallback();
      await route.fulfill({ status: 400, json: { status: "error", error_code: "VALIDATION_ERROR", issues: [
        { code: "string_too_long", path: "definition.blocks.3.decision.title", message: "Сократите текст: не более 300 символов." },
      ] } });
    });
    await page.route("**/scenarios/v3/simulate", route => route.fulfill({ status: 400, json: {
      status: "error", error_code: "SCENARIO_INVALID", issues: [{ code: "missing_fallback", path: "blocks.logic.transitions" }],
    } }));
    await page.goto("/app/admin/request-template-studio");
    await page.getByRole("region", { name: "Каталог услуг", exact: true }).getByRole("button", { name: "Настроить услугу Проблемы с печатью", exact: true }).click();
    await page.getByRole("button", { name: "Открыть карту сценария", exact: true }).click();
    await page.getByRole("button", { name: "Тестировать", exact: true }).click();
    await page.getByRole("button", { name: "Начать проверку", exact: true }).click();
    await expect(page.getByText(/Не настроен запасной переход «Иначе»/)).toBeVisible();
    await expect(page.getByText(/Ветки по ответам могут быть настроены/)).toBeVisible();
    await page.screenshot({ path: info.outputPath("missing-else.png") });
    await page.getByRole("button", { name: "Исправить шаг", exact: true }).click();
    await expect(page.getByText(/Ветки по ответам сохранятся/)).toBeVisible();
    const title = page.getByLabel("Название блока", { exact: true });
    await title.fill("Проверить настройки чата");
    await expect(page.getByRole("alert").filter({ hasText: "Черновик не сохранён" })).toContainText("Название шага: Сократите текст: не более 300 символов.");
    await expect(title).toHaveValue("Проверить настройки чата");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath("draft-reason.png") });
    rejectSave = false;
    await page.getByRole("button", { name: "Повторить автосохранение", exact: true }).click();
    await expect(page.getByText(/Черновик сохранён. Ревизия 2/)).toBeVisible();
    expect(state.definition().blocks![3].transitions).toHaveLength(1);
    expect(state.unexpected).toEqual([]);
    expect(state.errors.filter(error => !error.startsWith("400 ") && !error.includes("400 (Bad Request)"))).toEqual([]);
  });
}
