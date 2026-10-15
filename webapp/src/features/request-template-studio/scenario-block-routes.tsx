import { useId, useState, type ReactNode } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { conditionFields, conditionFieldAvailability } from "./scenario-builder-model";
import { newAnswerCondition, ScenarioConditionEditor } from "./scenario-condition-editor";
import { conditionSummary } from "./scenario-condition-summary";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioTransition } from "./scenario-contract";
import { replaceTransitions } from "./scenario-map-model";
import { ScenarioBranchProcessingEditor, ProcessingFactsEditor } from "./scenario-branch-processing";

function BranchCard({ title, description, target, expanded, onToggle, children }: {
  title: string; description: string; target: string; expanded: boolean; onToggle: () => void; children: ReactNode;
}) {
  const id = useId();
  return <div className="studio-branch-card">
    <button type="button" className="studio-branch-card__summary" aria-expanded={expanded} aria-controls={id} onClick={onToggle}>
      <span className="flex items-center gap-2 font-semibold"><span aria-hidden="true">{expanded ? "▾" : "▸"}</span>{title}</span>
      <span className="studio-branch-card__condition" title={description}>{description}</span>
      <span className="studio-branch-card__target" title={target}>→ {target}</span>
    </button>
    <div id={id} hidden={!expanded}>{expanded && <div className="space-y-3 border-t p-3">{children}</div>}</div>
  </div>;
}

export function ScenarioBlockRoutes({ definition, block, disabled, onChange }: { definition: ScenarioDraftDefinition; block: ScenarioBlock; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
  const transitions = block.transitions ?? [], fields = conditionFields(definition, block.id);
  const targets = definition.blocks?.filter(item => item.id !== block.id) ?? [];
  const [expanded, setExpanded] = useState<number[]>([]);
  const [fallbackExpanded, setFallbackExpanded] = useState(false);
  const [error, setError] = useState("");
  const update = (edges: ScenarioTransition[]) => {
    try { onChange(replaceTransitions(definition, block.id, edges)); setError(""); return true; }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Не удалось соединить блоки"); return false; }
  };
  const toggle = (index: number) => setExpanded(current => current.includes(index) ? current.filter(item => item !== index) : [...current, index]);
  const options = targets.map(item => <option key={item.id} value={item.id}>{item.title}</option>);
  const targetTitle = (id: string) => targets.find(item => item.id === id)?.title ?? "Выберите следующий шаг";
  const fallback = transitions.find(edge => !edge.when);
  const conditionalIndices = transitions.flatMap((edge, index) => edge.when ? [index] : []);
  const maybeMissing = conditionFieldAvailability(definition, block.id).filter(item => item.mayBeMissing);
  const processingSummary = (edge: ScenarioTransition) => [edge.processing?.route ? definition.processing?.routes[edge.processing.route]?.title ?? "Направление не найдено" : null, edge.processing?.sla_profile ? `SLA: ${definition.processing?.sla_profiles[edge.processing.sla_profile]?.title ?? "профиль не найден"}` : null, edge.processing?.approval_required === true ? "согласование" : edge.processing?.approval_required === false ? "без согласования" : null].filter(Boolean).join(" · ");
  return <section className="space-y-3" aria-label="Ветви логического блока">
    <h3 className="font-semibold">Куда идти дальше</h3>
    {error && <p role="alert">{error}</p>}
    <p className="text-xs text-slate-500">Каждая ветвь — ответ и следующий шаг. Нажмите на неё, чтобы изменить. Следующим шагом может быть другое условие. Если ни одна ветвь не подходит, сервер использует «Иначе».</p>
    <p className="text-xs text-slate-500">Если подходят несколько ветвей, сервер выбирает первую по приоритету: меньшее число раньше, без числа — после заданных приоритетов; при равенстве действует порядок в списке. Расположение на карте на выбор не влияет.</p>
    {!!maybeMissing.length && <p role="status" className="rounded border border-amber-300 p-2 text-sm">Ответы могут отсутствовать из-за специализированного входа, необязательного или скрытого вопроса: {maybeMissing.map(item => item.field.label).join(", ")}. Используйте «Ответ задан» и резервную ветку. Отсутствующий ответ не равен «Нет».</p>}
    {conditionalIndices.length > 0 && <div className="flex flex-wrap gap-1">
      <Button variant="ghost" onClick={() => { setExpanded(conditionalIndices); setFallbackExpanded(true); }}>Развернуть все ветви</Button>
      <Button variant="ghost" onClick={() => { setExpanded([]); setFallbackExpanded(false); }}>Свернуть все ветви</Button>
    </div>}
    {transitions.map((edge, index) => edge.when && <BranchCard key={index} title={`Ветвь ${conditionalIndices.indexOf(index) + 1}`} description={`${conditionSummary(edge.when, fields)}${edge.priority != null ? ` · приоритет ${edge.priority}` : ""}`} target={[targetTitle(edge.to), processingSummary(edge)].filter(Boolean).join(" · ")} expanded={expanded.includes(index)} onToggle={() => toggle(index)}>
      <fieldset disabled={disabled} className="space-y-3">
        <label className="block">Следующий блок<Select value={edge.to} onChange={event => update(transitions.map((old, i) => i === index ? { ...old, to: event.target.value } : old))}>{options}</Select></label>
        <ScenarioConditionEditor label="Если" value={edge.when} fields={fields} resultValues={block.kind === "resolution_check" ? ["yes", "no", "unknown"] : []} disabled={disabled} onChange={when => update(transitions.map((old, i) => i === index ? { ...old, when } : old))} />
        <ScenarioBranchProcessingEditor definition={definition} value={edge.processing} disabled={disabled} onChange={processing => update(transitions.map((old, i) => i === index ? { ...old, processing } : old))} />
        {(definition.schema_version ?? 1) >= 2 && <details><summary>Масштаб, срочность и важность</summary><ProcessingFactsEditor value={edge.processing_facts} disabled={disabled} onChange={processing_facts => update(transitions.map((old, i) => i === index ? { ...old, processing_facts } : old))} /></details>}
        <label className="block">Приоритет ветви<input className="field-base block w-full" type="number" min={1} max={10000} value={edge.priority ?? ""} onChange={event => update(transitions.map((old, i) => i === index ? { ...old, priority: event.target.value ? Number(event.target.value) : null } : old))} /></label>
        <Button variant="outline" disabled={conditionalIndices.indexOf(index) === 0} onClick={() => { const previous = conditionalIndices[conditionalIndices.indexOf(index) - 1]; const next = [...transitions]; [next[index], next[previous]] = [next[previous], next[index]]; if (update(next)) setExpanded([previous]); }}>Передвинуть ветвь выше</Button>
        <Button variant="ghost" onClick={() => {
          if (update(transitions.filter((_, i) => i !== index))) setExpanded(current => current.filter(item => item !== index).map(item => item > index ? item - 1 : item));
        }}>Удалить ветвь {conditionalIndices.indexOf(index) + 1}</Button>
      </fieldset>
    </BranchCard>)}
    <label className="block">Добавить условную ветвь<Select disabled={disabled || (!fields.length && block.kind !== "resolution_check") || transitions.length >= 30} value="" onChange={event => {
      const field = fields[0];
      const when = block.kind === "resolution_check" ? { op: "eq" as const, source: "current_result" as const, value: "yes" } : newAnswerCondition(field);
      if (update([...transitions.filter(edge => edge.when), { to: event.target.value, when }, ...transitions.filter(edge => !edge.when)])) setExpanded([conditionalIndices.length]);
    }}><option value="">Выберите следующий блок</option>{options}</Select></label>
    {!fields.length && block.kind === "decision" && <p className="text-sm text-amber-700">Сначала соедините предыдущий вопрос с этим блоком. Его ответы появятся в условиях.</p>}
    <BranchCard title="Иначе" description="Если ни одно условие не выполнено" target={fallback ? targetTitle(fallback.to) : "Выберите запасной маршрут"} expanded={fallbackExpanded} onToggle={() => setFallbackExpanded(value => !value)}>
      <label className="block">Если ни одно условие не выполнено<Select disabled={disabled} value={fallback?.to ?? ""} onChange={event => update([...transitions.filter(edge => edge.when), ...(event.target.value ? [{ ...fallback, to: event.target.value, when: null }] : [])])}><option value="">Выберите запасной маршрут</option>{options}</Select></label>
      <p className="text-xs text-slate-500">Сюда сотрудник перейдёт, если ни один ответ выше не подошёл. Можно выбрать ещё одно условие.</p>
      {fallback && <ScenarioBranchProcessingEditor definition={definition} value={fallback.processing} disabled={disabled} onChange={processing => update(transitions.map(edge => edge === fallback ? { ...edge, processing } : edge))} />}
    </BranchCard>
    {transitions.filter(edge => !edge.when).length > 1 && <p role="alert">Есть несколько безусловных переходов. Выберите один запасной маршрут.</p>}
  </section>;
}
