import { useRef, useState, type DragEvent } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioField } from "./scenario-contract";
import { fieldUses, mapCondition, newField, newKey } from "./scenario-builder-model";
import { ScenarioFieldEditor } from "./scenario-field-editor";
import { ScenarioFieldGroup } from "./scenario-field-group";
import { ScenarioFields } from "../requester/scenario-fields";

type FormPage = Extract<ScenarioBlock, { kind: "form_page" }>;
type Props = { block: FormPage; definition: ScenarioDraftDefinition; disabled: boolean; onChange: (value: FormPage) => void };
export function ScenarioFormPageEditor({ block, definition, disabled, onChange }: Props) {
  const [message, setMessage] = useState("");
  const dragged = useRef<string | null>(null);
  // Match the requester's grouping before deriving move/count positions.
  const groups = new Map<string, ScenarioField[]>();
  for (const field of block.fields) { const key = field.group || ""; groups.set(key, [...groups.get(key) ?? [], field]); }
  const ordered = block.layout === "section" ? [...groups.values()].flat() : block.fields;
  function update(fields: ScenarioField[]) {
    setMessage("");
    onChange({ ...block, ...(block.layout === "single" && fields.length > 1 ? { layout: "group" as const } : {}), title: fields.length === 1 ? fields[0].label : block.title, fields });
  }
  function remove(keys: string[]) {
    const uses = keys.flatMap(key => fieldUses(definition, key));
    if (uses.length) { setMessage(`Сначала измените зависимости: ${uses.join("; ")}`); return; }
    update(ordered.filter(field => !keys.includes(field.key)));
  }
  function count(value: string) {
    const total = Number(value);
    if (!Number.isInteger(total) || total < 1 || total > 100) { setMessage("Укажите от 1 до 100 вопросов"); return; }
    if (total < ordered.length) remove(ordered.slice(total).map(field => field.key));
    else if (total > ordered.length) update([...ordered, ...Array.from({ length: total - ordered.length }, () => newField())]);
  }
  function insert(field?: ScenarioField) {
    if (disabled || ordered.length >= 100) return;
    const next = field ? { ...structuredClone(field), key: newKey("field"), aliases: [], label: `${field.label.slice(0, 290)} — копия`, process_mapping: { ...field.process_mapping, fact_key: field.process_mapping?.fact_key ? newKey("fact") : null } } : newField();
    if (field) { next.visible_when = mapCondition(next.visible_when, { [field.key]: next.key }); next.required_when = mapCondition(next.required_when, { [field.key]: next.key }); }
    const fields = [...ordered]; fields.splice(field ? ordered.indexOf(field) + 1 : fields.length, 0, next); update(fields);
  }
  function isQuestionDrag(event: DragEvent) {
    const types = Array.from(event.dataTransfer.types);
    return !disabled && !!dragged.current && types.includes("application/x-studio-question") && !types.includes("Files") && !event.dataTransfer.files.length;
  }
  function move(key: string, target: number) {
    if (disabled || target < 0 || target >= ordered.length) return;
    const fields = [...ordered], index = fields.findIndex(field => field.key === key);
    if (index < 0 || index === target) return;
    const neighbor = fields[target], [moving] = fields.splice(index, 1);
    fields.splice(target, 0, block.layout === "section" ? { ...moving, group: neighbor.group, group_title: neighbor.group_title } : moving);
    update(fields);
  }
  return <div className="studio-question-page min-w-0 space-y-4">
    <div className="studio-question-page__toolbar">
      <label>Количество вопросов<Input type="number" min={1} max={100} disabled={disabled} value={block.fields.length} onChange={event => count(event.target.value)} /></label>
      <Button disabled={disabled || block.fields.length >= 100} onClick={() => insert()}>Добавить вопрос</Button>
      <details><summary>Расположение страницы</summary><label className="block">Расположение вопросов<Select disabled={disabled} value={block.layout ?? "group"} onChange={event => onChange({ ...block, layout: event.target.value as FormPage["layout"] })}><option value="single" disabled={block.fields.length !== 1}>Один вопрос</option><option value="group">Группа вопросов</option><option value="section">Разделы</option></Select></label></details>
    </div>
    {message && <p role="alert">{message}</p>}
    {block.layout === "section" && <p className="text-xs text-slate-500">Порядок совпадает со страницей сотрудника. Перенос через границу раздела перемещает вопрос в соседний раздел.</p>}
    <div aria-label="Вопросы страницы" className="space-y-4"><ScenarioFields fields={block.fields.map(({ key, type, label, group, group_title }) => ({ key, type, label, group, group_title }))} layout={block.layout} renderField={projected => {
      const field = block.fields.find(item => item.key === projected.key)!;
      const index = ordered.findIndex(item => item.key === field.key);
      return <article className="studio-question-card" aria-label={`Вопрос ${index + 1}`} onDragOverCapture={event => { if (!isQuestionDrag(event)) return; event.preventDefault(); event.stopPropagation(); event.dataTransfer.dropEffect = "move"; }} onDropCapture={event => { if (!isQuestionDrag(event)) return; event.preventDefault(); event.stopPropagation(); const key = dragged.current!; dragged.current = null; move(key, index); }}>
        <div className="studio-question-card__actions">
          <button type="button" className="studio-question-drag nodrag nopan" draggable={!disabled} disabled={disabled} aria-label={`Переместить вопрос ${index + 1}`} title="Перетащите или используйте стрелки клавиатуры" onDragStart={event => { dragged.current = field.key; event.dataTransfer.setData("application/x-studio-question", field.key); event.dataTransfer.effectAllowed = "move"; event.stopPropagation(); }} onDragEnd={() => { dragged.current = null; }} onKeyDown={event => { if (event.key === "ArrowUp" || event.key === "ArrowDown") { event.preventDefault(); event.stopPropagation(); move(field.key, index + (event.key === "ArrowUp" ? -1 : 1)); } }}>⠿ Вопрос {index + 1}</button>
          <Button size="sm" variant="ghost" aria-label={`Вопрос ${index + 1} вверх`} disabled={disabled || index === 0} onClick={() => move(field.key, index - 1)}>↑</Button>
          <Button size="sm" variant="ghost" aria-label={`Вопрос ${index + 1} вниз`} disabled={disabled || index === ordered.length - 1} onClick={() => move(field.key, index + 1)}>↓</Button>
          <Button size="sm" variant="ghost" disabled={disabled || ordered.length >= 100} onClick={() => insert(field)}>Копировать вопрос</Button>
          <Button size="sm" variant="ghost" disabled={disabled || ordered.length <= 1} onClick={() => remove([field.key])}>Удалить вопрос</Button>
        </div>
        <ScenarioFieldEditor field={field} definition={definition} disabled={disabled} onChange={next => update(block.fields.map(old => old.key === field.key ? next : old))} />
        {block.layout === "section" && <details><summary>Раздел вопроса</summary><ScenarioFieldGroup field={field} fields={block.fields} disabled={disabled} onChange={update} /></details>}
      </article>;
    }} /></div>
  </div>;
}
