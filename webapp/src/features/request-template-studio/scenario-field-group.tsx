import { useState } from "react";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { Button } from "../../components/ui/button";
import type { ScenarioField } from "./scenario-contract";
import { newKey } from "./scenario-builder-model";

export function ScenarioFieldGroup({ field, fields, disabled, onChange }: { field: ScenarioField; fields: ScenarioField[]; disabled: boolean; onChange: (fields: ScenarioField[]) => void }) {
  const [title, setTitle] = useState("");
  const groups = [...new Map(fields.filter(item => item.group).map(item => [item.group!, item.group_title || "Дополнительные вопросы"])).entries()];
  return <fieldset disabled={disabled} className="min-w-0 space-y-3 rounded border p-3"><legend className="font-medium">Раздел вопроса</legend>
    <label className="block">Раздел<Select value={field.group || ""} onChange={event => {
      const group = event.target.value || null;
      const groupTitle = groups.find(([key]) => key === group)?.[1] || null;
      onChange(fields.map(item => item.key === field.key ? { ...item, group, group_title: groupTitle } : item));
    }}><option value="">Общие вопросы</option>{groups.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></label>
    {field.group && <label className="block">Название раздела<Input maxLength={300} value={field.group_title || ""} onChange={event => onChange(fields.map(item => item.group === field.group ? { ...item, group_title: event.target.value || null } : item))} /></label>}
    <label className="block">Новый раздел<Input maxLength={300} value={title} onChange={event => setTitle(event.target.value)} /></label>
    <Button variant="secondary" disabled={!title.trim()} onClick={() => { const group = newKey("group"); onChange(fields.map(item => item.key === field.key ? { ...item, group, group_title: title.trim() } : item)); setTitle(""); }}>Создать раздел для вопроса</Button>
  </fieldset>;
}
