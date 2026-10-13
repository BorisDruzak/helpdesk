import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { conditionFields } from "./scenario-builder-model";
import { ScenarioConditionEditor } from "./scenario-condition-editor";
import { insertOnTransition, mapPalette, replaceTransitions } from "./scenario-map-model";

export function ScenarioEdgeInspector({ definition, source, index, disabled, onChange }: { definition: ScenarioDraftDefinition; source: string; index: number; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
  const [kind, setKind] = useState<ScenarioBlock["kind"]>("instruction");
  const [error, setError] = useState("");
  const block = definition.blocks?.find(item => item.id === source);
  const edge = block?.transitions?.[index];
  if (!block || !edge) return <p>Переход больше не существует. Выберите другой элемент.</p>;
  const edges = block.transitions!;
  const results = ({ resolution_check: ["yes", "no", "unknown"], instruction: ["acknowledged", "request_ticket"], diagnostic: ["unavailable", "denied", "timeout", "capability_absent"] } as Partial<Record<ScenarioBlock["kind"], string[]>>)[block.kind] ?? [];
  function perform(action: () => ScenarioDraftDefinition) { try { onChange(action()); setError(""); } catch (failure) { setError(failure instanceof Error ? failure.message : "Изменение не выполнено"); } }
  const update = (patch: Partial<typeof edge>) => perform(() => replaceTransitions(definition, source, edges.map((old, i) => i === index ? { ...old, ...patch } : old)));
  return <fieldset disabled={disabled} className="space-y-4">
    <legend className="text-lg font-semibold">Переход из «{block.title}»</legend>
    {error && <p role="alert">{error}</p>}
    <label className="block">Следующий блок<Select autoFocus value={edge.to} onChange={event => update({ to: event.target.value })}><option value="" disabled>Выберите блок</option>{definition.blocks?.filter(item => item.id !== source).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
    <ScenarioConditionEditor label="Условие перехода" value={edge.when} fields={conditionFields(definition, source)} resultValues={results} disabled={disabled} onChange={when => update({ when })} />
    <details><summary>Расширенные условия</summary><label className="block">Приоритет сопоставления<Input type="number" min={1} max={10000} value={edge.priority ?? ""} onChange={event => update({ priority: event.target.value ? Number(event.target.value) : null })} /></label></details>
    {!edge.when && <p className="text-sm text-slate-500">Резервный маршрут. Он должен идти после условных переходов.</p>}
    <Button variant="secondary" onClick={() => perform(() => replaceTransitions(definition, source, [...edges.filter((_, i) => i !== index), edge]))}>Переместить переход в конец</Button>
    <label className="block">Вставить блок на связь<Select value={kind} onChange={event => setKind(event.target.value as ScenarioBlock["kind"])}>{mapPalette.filter(item => !["decision", "resolution_check", "submit_ticket"].includes(item.kind)).map(item => <option key={item.kind} value={item.kind}>{item.label}</option>)}</Select></label>
    <Button variant="secondary" onClick={() => perform(() => insertOnTransition(definition, source, index, kind))}>Вставить между шагами</Button>
    <p className="text-xs text-slate-500">Условие сохраняется на первой связи. Второй переход продолжает прежний маршрут.</p>
    <Button variant="ghost" onClick={() => perform(() => replaceTransitions(definition, source, edges.filter((_, i) => i !== index)))}>Удалить выбранный переход</Button>
  </fieldset>;
}
