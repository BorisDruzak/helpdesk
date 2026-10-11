import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioField } from "./scenario-contract";
import { fieldUses, mapCondition, newField, newKey } from "./scenario-builder-model";
import { ScenarioFieldEditor } from "./scenario-field-editor";

type FormPage = Extract<ScenarioBlock, { kind: "form_page" }>;
type Props = { block: FormPage; definition: ScenarioDraftDefinition; disabled: boolean; onChange: (value: FormPage) => void };
export function ScenarioFormPageEditor({ block, definition, disabled, onChange }: Props) {
  const [selected, setSelected] = useState(block.fields[0]?.key);
  const [message, setMessage] = useState("");
  const field = block.fields.find(item => item.key === selected) ?? block.fields[0];
  const index = block.fields.findIndex(item => item.key === field?.key);
  const update = (fields: ScenarioField[]) => { setMessage(""); onChange({ ...block, fields }); };
  function insert(copy = false) {
    const next = copy && field ? { ...structuredClone(field), key: newKey("field"), aliases: [], label: `${field.label.slice(0, 290)} — копия`, process_mapping: { ...field.process_mapping, fact_key: field.process_mapping?.fact_key ? newKey("fact") : null } } : newField();
    if (copy && field) {
      next.visible_when = mapCondition(next.visible_when, { [field.key]: next.key });
      next.required_when = mapCondition(next.required_when, { [field.key]: next.key });
    }
    const fields = [...block.fields]; fields.splice(index + 1, 0, next);
    update(fields); setSelected(next.key);
  }
  function move(delta: number) {
    const fields = [...block.fields]; const target = index + delta;
    if (target < 0 || target >= fields.length) return;
    [fields[index], fields[target]] = [fields[target], fields[index]]; update(fields);
  }
  return <div className="min-w-0 space-y-4">
    <label className="block">Расположение вопросов<Select disabled={disabled} value={block.layout ?? "group"} onChange={event => onChange({ ...block, layout: event.target.value as FormPage["layout"] })}>
      <option value="single" disabled={block.fields.length !== 1}>Один вопрос</option><option value="group">Группа вопросов</option><option value="section">Разделы</option>
    </Select></label>
    <ul aria-label="Вопросы страницы" className="space-y-1">{block.fields.map(item => <li key={item.key}><Button className="max-w-full whitespace-normal text-left" variant={item.key === field?.key ? "secondary" : "ghost"} aria-pressed={item.key === field?.key} onClick={() => setSelected(item.key)}>{item.label}</Button></li>)}</ul>
    <div className="flex flex-wrap gap-2">
      <Button disabled={disabled || block.fields.length >= 100 || block.layout === "single"} onClick={() => insert()}>Добавить вопрос</Button>
      <Button variant="ghost" disabled={disabled || block.fields.length >= 100 || block.layout === "single"} onClick={() => insert(true)}>Копировать вопрос</Button>
      <Button variant="ghost" disabled={disabled || index <= 0} onClick={() => move(-1)}>Вопрос вверх</Button>
      <Button variant="ghost" disabled={disabled || index >= block.fields.length - 1} onClick={() => move(1)}>Вопрос вниз</Button>
      <Button variant="ghost" disabled={disabled || block.fields.length <= 1} onClick={() => {
        const uses = fieldUses(definition, field.key);
        if (uses.length) { setMessage(`Сначала измените зависимости: ${uses.join("; ")}`); return; }
        update(block.fields.filter(item => item.key !== field.key));
      }}>Удалить вопрос</Button>
    </div>
    {message && <p role="alert">{message}</p>}
    {field && <ScenarioFieldEditor key={field.key} field={field} definition={definition} disabled={disabled} onChange={next => update(block.fields.map(old => old.key === field.key ? next : old))} />}
  </div>;
}
