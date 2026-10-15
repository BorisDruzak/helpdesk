import { expect, it } from "vitest";
import { conditionSummary } from "./scenario-condition-summary";
import type { ScenarioCondition, ScenarioField } from "./scenario-contract";
const fields: ScenarioField[] = [{ key: "secret", label: "Проблема", type: "select", options: [{ value: "mail_key", label: "Почта" }] }];
it("uses option labels inside nested conditions without exposing keys", () => {
  expect(conditionSummary({ op: "and", conditions: [{ op: "eq", source: "answer", field: "secret", value: "mail_key" }, { op: "not", condition: { op: "eq", source: "current_result", value: "yes" } }] }, fields)).toBe('(Проблема равно «Почта») и (Не (Результат проверки равно «Да»))');
  expect(conditionSummary({ op: "in", source: "answer", field: "secret", value: ["mail_key", "removed_key"] }, fields)).toBe('Проблема один из «Почта, Вариант недоступен»');
});
it("bounds deeply nested summaries and identifies missing questions", () => {
  let condition: ScenarioCondition = { op: "exists", source: "answer", field: "removed" };
  expect(conditionSummary(condition, fields)).toBe("Вопрос недоступен: ответ задан");
  for (let i = 0; i < 10; i++) condition = { op: "not", condition };
  expect(conditionSummary(condition, fields).length).toBeLessThan(100);
});
