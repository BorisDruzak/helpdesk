import { isPolicyAttachment } from "./scenario-policy-attachments-model";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { conditionFields, conditionFieldAvailability } from "./scenario-builder-model";
import { ScenarioConditionEditor } from "./scenario-condition-editor";
import { replaceTransitions } from "./scenario-map-model";
import { setNavigationMode } from "./scenario-v4-model";
import { useState } from "react";


export function ScenarioEdgeInspector({ definition, source, index, disabled, onChange }: { definition: ScenarioDraftDefinition; source: string; index: number; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
  const [modeError,setModeError]=useState("");
  const block = definition.blocks?.find(item => item.id === source);
  const edge = block?.transitions?.[index];
  if (!block || !edge) return <p>Переход больше не существует. Выберите другой элемент.</p>;
  const edges = block.transitions!;
  const maybeMissing = conditionFieldAvailability(definition, source).filter(item => item.mayBeMissing);
  const results = ({ resolution_check: ["yes", "no", "unknown"], instruction: ["acknowledged", "request_ticket"], diagnostic: ["unavailable", "denied", "timeout", "capability_absent"] } as Partial<Record<ScenarioBlock["kind"], string[]>>)[block.kind] ?? [];
  function perform(action: () => ScenarioDraftDefinition) { onChange(action()); }
  function changeMode(mode: "automatic"|"buttons") {
    try {
      const next={...definition,blocks:definition.blocks?.map(item=>item.id===source?setNavigationMode(item,mode,id=>definition.blocks?.find(target=>target.id===id)?.title??"Продолжить"):item)};
      onChange(next);setModeError("");
    } catch(failure) { setModeError(failure instanceof Error?failure.message:"Не удалось изменить способ перехода. Связи сохранены."); }
  }
  const update = (patch: Partial<typeof edge>) => perform(() => replaceTransitions(definition, source, edges.map((old, i) => i === index ? { ...old, ...patch } : old)));
  return <fieldset disabled={disabled} className="space-y-4">
    <legend className="text-lg font-semibold">Переход из «{block.title}»</legend>
    {definition.schema_version === 4 && ["form_page", "instruction", "review"].includes(block.kind) && <><label className="block">Как сотрудник переходит дальше<Select value={block.transition_mode ?? "automatic"} onChange={event=>changeMode(event.target.value as "automatic"|"buttons")}><option value="automatic">Автоматически по условию</option><option value="buttons" disabled={edges.length>10}>Выбирает кнопку перехода</option></Select></label>{edges.length>10&&<p className="text-sm text-slate-500">Для выбора кнопками нужно не более 10 связей. Разделите маршрут на несколько блоков; существующие переходы сохранены.</p>}</>}
    {block.kind==="navigation"&&<p className="text-sm text-slate-500">Блок переходов всегда показывает кнопки сотруднику.</p>}
    {modeError&&<p role="alert">{modeError}</p>}
    {edge.button && <label className="block">Текст кнопки перехода<Input disabled={disabled} maxLength={300} value={edge.button.label} onChange={event => update({ button: { ...edge.button!, label: event.target.value } })} /></label>}
    <label className="block">Следующий блок<Select autoFocus value={edge.to} onChange={event => update({ to: event.target.value })}><option value="" disabled>Выберите блок</option>{definition.blocks?.filter(item => item.id !== source && !isPolicyAttachment(item)).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>
    {block.transition_mode !== "buttons" && !edge.button && <label className="block">Приоритет перехода<Input type="number" min={1} max={10000} value={edge.priority ?? ""} onChange={event => update({ priority: event.target.value ? Number(event.target.value) : null })} /></label>}
    <ScenarioConditionEditor label="Условие перехода" value={edge.when} fields={conditionFields(definition, source)} resultValues={results} disabled={disabled} onChange={when => update({ when })} />
    {!!maybeMissing.length && <p role="status" className="text-sm text-amber-800">При специализированном входе или скрытом вопросе могут отсутствовать ответы: {maybeMissing.map(item => item.field.label).join(", ")}. Проверяйте «Ответ задан»; отсутствие ответа не означает «Нет». Настройте резервный маршрут.</p>}
    {!edge.when && <p className="text-sm text-slate-500">Резервный маршрут. Он должен идти после условных переходов.</p>}
  </fieldset>;
}
