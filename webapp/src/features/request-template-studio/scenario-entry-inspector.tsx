import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioDraftDefinition, ScenarioEntryPoint } from "./scenario-contract";
import { newKey } from "./scenario-builder-model";

function SearchPhrases({ value, onChange }: { value: string[]; onChange: (next: string[]) => void }) {
  const [text, setText] = useState(value.join("\n"));
  const emitted = useRef(JSON.stringify(value));
  useEffect(() => { const incoming = JSON.stringify(value); if (incoming !== emitted.current) { setText(value.join("\n")); emitted.current = incoming; } }, [value]);
  return <textarea className="field-base w-full" placeholder="Одна фраза на строку" value={text} onChange={event => {
    const raw = event.target.value; setText(raw);
    const next = raw.split("\n").map(line => line.trim()).filter(Boolean).slice(0, 20);
    emitted.current = JSON.stringify(next); onChange(next);
  }} />;
}

export function ScenarioEntryInspector({ definition, blockId, catalog, disabled, onChange }: { definition: ScenarioDraftDefinition; blockId: string; catalog: ScenarioCatalog; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
  const entries = definition.entry_points ?? [];
  function update(key: string, patch: Partial<ScenarioEntryPoint>) { onChange({ ...definition, entry_points: entries.map(entry => entry.key === key ? { ...entry, ...patch } : entry) }); }
  return <section className="space-y-3 border-t pt-4" aria-label="Точки входа выбранного блока">
    <h3 className="font-semibold">Точки входа из каталога</h3>
    <p className="text-xs text-slate-500">Пункты используют одну карту. Сообщённый симптом не становится проверенным фактом.</p>
    {entries.filter(entry => entry.target_block_id === blockId).map(entry => <fieldset key={entry.key} disabled={disabled} className="space-y-3 rounded-xl border p-3">
      <legend>{entry.title || "Новая точка входа"}</legend>
      <label className="block">Название пункта<Input maxLength={300} value={entry.title} onChange={event => update(entry.key, { title: event.target.value })} /></label>
      <label className="block">Краткое описание<textarea className="field-base w-full" maxLength={2000} value={entry.description ?? ""} onChange={event => update(entry.key, { description: event.target.value })} /></label>
      <label className="block">Категория пункта<Select value={entry.category_id ?? ""} onChange={event => update(entry.key, { category_id: event.target.value || null })}><option value="">Категория карты</option>{catalog.categories.filter(category => category.service_code === definition.service_code && category.lifecycle_status !== "archived").map(category => <option key={category.id} value={category.id}>{category.title}</option>)}</Select></label>
      <label className="block">Синонимы и поисковые фразы<SearchPhrases value={entry.synonyms ?? []} onChange={synonyms => update(entry.key, { synonyms })} /></label>
      <label className="block">Начальный блок<Select value={entry.target_block_id} onChange={event => update(entry.key, { target_block_id: event.target.value })}>{definition.blocks?.map(block => <option key={block.id} value={block.id}>{block.title}</option>)}</Select></label>
      <label className="block">Сообщённый симптом<Input maxLength={2000} value={entry.reported_symptom ?? ""} onChange={event => update(entry.key, { reported_symptom: event.target.value })} /></label>
      <label className="flex gap-2"><input type="checkbox" checked={entry.enabled ?? true} onChange={event => update(entry.key, { enabled: event.target.checked })} />Доступен в каталоге</label>
      <label className="block">Видимость<Select value={entry.visibility ?? "public"} onChange={event => update(entry.key, { visibility: event.target.value as ScenarioEntryPoint["visibility"] })}><option value="public">Для сотрудников</option><option value="internal">Внутренний</option><option value="restricted">Ограниченный</option></Select></label>
      <details><summary>Расширенные настройки пункта</summary><p className="break-all text-xs">Стабильный ключ: {entry.key}</p></details>
      <Button variant="ghost" onClick={() => onChange({ ...definition, entry_points: entries.filter(old => old.key !== entry.key) })}>Убрать точку входа из черновика</Button>
    </fieldset>)}
    <Button variant="secondary" disabled={disabled || entries.length >= 64} onClick={() => onChange({ ...definition, entry_points: [...entries, { key: newKey("entry"), title: definition.blocks?.find(block => block.id === blockId)?.title ?? "Новый пункт", target_block_id: blockId, category_id: null, visibility: "public", enabled: true }] })}>Добавить точку входа из каталога</Button>
  </section>;
}
