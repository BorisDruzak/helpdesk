import type { ScenarioCondition, ScenarioField, ScenarioScalar } from "./scenario-contract";

// Labels only: conditions are still evaluated exclusively by the server.
export function conditionSummary(condition: ScenarioCondition, fields: ScenarioField[], depth = 0): string {
  if (depth >= 3) return "Составное условие";
  if (condition.op === "and" || condition.op === "or") {
    const parts = condition.conditions.slice(0, 2).map(item => `(${conditionSummary(item, fields, depth + 1)})`);
    return parts.join(condition.op === "and" ? " и " : " или ") + (condition.conditions.length > 2 ? " …" : "");
  }
  if (condition.op === "not") return `Не (${conditionSummary(condition.condition, fields, depth + 1)})`;
  if (!("source" in condition)) return "Составное условие";
  const field = condition.source === "answer" ? fields.find(item => item.key === condition.field) : undefined;
  const source = condition.source === "current_result" ? "Результат проверки" : field?.label || "Вопрос недоступен";
  if (condition.op === "exists") return `${source}: ответ задан`;
  const label = (value: ScenarioScalar) => {
    if (condition.source === "current_result") return ({ yes: "Да", no: "Нет", unknown: "Не знаю" }[String(value)] ?? "Другой результат");
    if (field?.options?.length) return field.options.find(item => item.value === value)?.label ?? "Вариант недоступен";
    if (value === null) return "Не задано";
    if (typeof value === "boolean") return value ? "Да" : "Нет";
    return String(value);
  };
  const operator = { eq: "равно", neq: "не равно", gt: "больше", gte: "не меньше", lt: "меньше", lte: "не больше", in: "один из" }[condition.op];
  const values = condition.op === "in" ? condition.value.slice(0, 3).map(label).join(", ") + (condition.value.length > 3 ? " …" : "") : label(condition.value);
  return `${source} ${operator} «${values}»`;
}
