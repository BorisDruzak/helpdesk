import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { conditionFields } from "./scenario-builder-model";
import { ScenarioConditionEditor } from "./scenario-condition-editor";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioTransition } from "./scenario-contract";
import { replaceTransitions } from "./scenario-map-model";

export function ScenarioBlockRoutes({ definition, block, disabled, onChange }: { definition: ScenarioDraftDefinition; block: ScenarioBlock; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
  const transitions = block.transitions ?? [], fields = conditionFields(definition, block.id);
  const targets = definition.blocks?.filter(item => item.id !== block.id) ?? [];
  const [error, setError] = useState("");
  const update = (edges: ScenarioTransition[]) => { try { onChange(replaceTransitions(definition, block.id, edges)); setError(""); } catch (failure) { setError(failure instanceof Error ? failure.message : "Не удалось соединить блоки"); } };
  const options = targets.map(item => <option key={item.id} value={item.id}>{item.title}</option>);
  const fallback = transitions.find(edge => !edge.when);
  return <section className="space-y-3" aria-label="Ветви логического блока">
    <h3 className="font-semibold">Куда идти дальше</h3>
    {error && <p role="alert">{error}</p>}
    <p className="text-xs text-slate-500">Выберите следующий блок, затем вопрос и нужный ответ в поле «Если». Например: «Что не работает?» равно «Почта» → инструкция по почте. Сервер выбирает подходящую ветвь; если ни одна не подходит, используется путь «иначе».</p>
    {transitions.map((edge, index) => edge.when && <fieldset key={index} disabled={disabled} className="space-y-2 rounded-lg border p-3"><legend>Ветвь {index + 1}</legend>
      <label className="block">Следующий блок<Select value={edge.to} onChange={event => update(transitions.map((old, i) => i === index ? { ...old, to: event.target.value } : old))}>{options}</Select></label>
      <ScenarioConditionEditor label="Если" value={edge.when} fields={fields} resultValues={block.kind === "resolution_check" ? ["yes", "no", "unknown"] : []} disabled={disabled} onChange={when => update(transitions.map((old, i) => i === index ? { ...old, when } : old))} />
      <Button variant="ghost" onClick={() => update(transitions.filter((_, i) => i !== index))}>Удалить ветвь {index + 1}</Button>
    </fieldset>)}
    <label className="block">Добавить условную ветвь<Select disabled={disabled || (!fields.length && block.kind !== "resolution_check") || transitions.length >= 30} value="" onChange={event => {
      const field = fields[0];
      const when = block.kind === "resolution_check" ? { op: "eq" as const, source: "current_result" as const, value: "yes" } : field.type === "checkbox" || (["select", "radio"].includes(field.type) && field.options?.length) ? { op: "eq" as const, source: "answer" as const, field: field.key, value: field.type === "checkbox" ? true : field.options![0].value } : { op: "exists" as const, source: "answer" as const, field: field.key };
      update([...transitions.filter(edge => edge.when), { to: event.target.value, when }, ...transitions.filter(edge => !edge.when)]);
    }}><option value="">Выберите следующий блок</option>{options}</Select></label>
    {!fields.length && block.kind === "decision" && <p className="text-sm text-amber-700">Сначала соедините предыдущий вопрос с этим блоком. Его ответы появятся в условиях.</p>}
    <label className="block">Если ни одно условие не выполнено<Select disabled={disabled} value={fallback?.to ?? ""} onChange={event => update([...transitions.filter(edge => edge.when), ...(event.target.value ? [{ ...fallback, to: event.target.value, when: null }] : [])])}><option value="">Выберите запасной маршрут</option>{options}</Select></label>
    {transitions.filter(edge => !edge.when).length > 1 && <p role="alert">Есть несколько безусловных переходов. Выберите один запасной маршрут.</p>}
  </section>;
}
