import type { ScenarioConditionEvaluation, ScenarioSimulation } from "./scenario-api";
import type { ScenarioDraftDefinition, ScenarioField } from "./scenario-contract";

const operatorLabels: Record<string, string> = { and: "Все условия (И)", or: "Любое условие (ИЛИ)", not: "Не выполняется (НЕ)", eq: "равно", neq: "не равно", gt: "больше", gte: "не меньше", lt: "меньше", lte: "не больше", exists: "ответ задан", in: "один из", otherwise: "Иначе" };
function Evaluation({ item, fields }: { item: ScenarioConditionEvaluation; fields: ScenarioField[] }) {
 const field = fields.find(field => field.key === item.field);
 const display = (value: unknown): string => Array.isArray(value) ? value.map(display).join(", ") : field?.options?.find(option => option.value === value)?.label ?? (value === null ? "Не знаю" : value === true ? "Да" : value === false ? "Нет" : typeof value === "string" || typeof value === "number" ? String(value) : "");
 return <li className={`min-w-0 rounded border p-2 text-sm ${item.matched ? "border-emerald-300 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}>
  <span className="font-medium">{item.matched ? "✓ Выполнено" : "— Не выполнено"}</span>{" · "}{field?.label ?? (item.source === "current_result" ? "Результат шага" : "")}{" "}{operatorLabels[item.op] ?? "Проверка"}{"value" in item ? `: ${display(item.value)}` : ""}
  {item.present === false ? <p>Ответ отсутствует</p> : "actual" in item ? <p>Ответ: {display(item.actual)}</p> : null}
  {!!item.children?.length && <ul className="mt-2 space-y-2 border-l pl-2">{item.children.map((child, index) => <Evaluation key={index} item={child} fields={fields} />)}</ul>}
 </li>;
}
export function ScenarioSimulationTrace({ result, definition }: { result: ScenarioSimulation; definition?: ScenarioDraftDefinition }) {
 const processing = result.map_processing ?? result.processing?.map_processing;
 if (!processing) return null;
 const fields = definition?.blocks?.flatMap(block => block.kind === "form_page" ? block.fields : []) ?? [];
 const title = (id: string) => definition?.blocks?.find(block => block.id === id)?.title ?? "Шаг сценария";
 const source = (value: { kind: "default" | "transition"; block_id?: string; transition_index?: number }) => value.kind === "default" ? "настройка карты по умолчанию" : `«${title(value.block_id ?? "") }», ветвь ${(value.transition_index ?? 0) + 1}`;
 return <section aria-label="Почему выбран этот результат" className="min-w-0 space-y-3">
  <h4 className="font-semibold">Почему выбран этот результат</h4>
  <p>Направление «{processing.route.title}»: {source(processing.route.source)}.</p>
  <p>Профиль SLA «{processing.sla_profile.title}»: {source(processing.sla_profile.source)}. {processing.sla_profile.time_basis === "business" ? "Рабочее время" : "Календарное время"}.</p>
  <p className="text-xs text-slate-500">Показаны решения сервера. Последнее явное назначение очереди, SLA и согласования заменяет соответствующее предыдущее значение.</p>
  <ol className="space-y-2">{processing.trace.map((step, index) => <li key={index} className="rounded border p-2 text-sm">{title(step.block_id)} → {title(step.to)}{step.assignments.route ? ` · направление: ${definition?.processing?.routes[step.assignments.route]?.title ?? step.assignments.route}` : ""}{step.assignments.sla_profile ? ` · SLA: ${definition?.processing?.sla_profiles[step.assignments.sla_profile]?.title ?? step.assignments.sla_profile}` : ""}{step.assignments.approval_required != null ? step.assignments.approval_required ? " · согласование требуется" : " · без согласования" : ""}</li>)}</ol>
  {processing.condition_trace?.map((step, index) => <details key={index}><summary className="text-sm">{title(step.block_id)} · ветвь {step.transition_index + 1} → {title(step.to)} · {step.selected ? "выбрана" : "не выбрана"}</summary><ul className="mt-2 space-y-2"><Evaluation item={step.condition_evaluation} fields={fields} /></ul></details>)}
 </section>;
}

export function ScenarioSimulationComparison({ first, second, definition }: { first: ScenarioSimulation; second: ScenarioSimulation; definition?: ScenarioDraftDefinition }) {
 const fields = definition?.blocks?.flatMap(block => block.kind === "form_page" ? block.fields : []) ?? [];
 function answers(result: ScenarioSimulation) { return Object.entries(result.state.answers).map(([key, value]) => { const field = fields.find(field => field.key === key); return `${field?.label ?? "Ответ"}: ${field?.options?.find(option => option.value === value)?.label ?? (value === null ? "Не знаю" : value === true ? "Да" : value === false ? "Нет" : String(value))}`; }).join("; "); }
 return <section aria-label="Сравнение двух проверок" className="min-w-0 space-y-2"><h4 className="font-semibold">Сравнение двух проверок</h4><div className="grid min-w-0 gap-3 sm:grid-cols-2">{[first, second].map((result, index) => <div key={index} className="min-w-0 space-y-2 break-words rounded border p-3"><h5 className="font-medium">{index === 0 ? "Сохранённая проверка" : "Текущая проверка"}</h5><p>{answers(result)}</p><p>Очередь: {result.processing?.routing.queue_title ?? result.processing?.routing.queue_code ?? "Не определена"}</p><p>SLA: {result.processing?.map_processing?.sla_profile.title ?? "Действующая политика"}</p><p>Первый ответ: {result.processing?.sla.first_response_min ?? "—"} мин. · решение: {result.processing?.sla.resolution_min ?? "—"} мин.</p><p>Приоритет: {result.processing?.priority.priority_class ?? "—"}</p><p>{result.processing?.approval.required ? "Согласование требуется" : "Без согласования"}</p></div>)}</div></section>;
}
