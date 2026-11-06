import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { newKey } from "./scenario-builder-model";
import { setNavigationMode } from "./scenario-v4-model";
export function ScenarioNavigationEditor({ definition, block, disabled, onChange }: { definition: ScenarioDraftDefinition; block: ScenarioBlock; disabled: boolean; onChange: (next: ScenarioBlock) => void }) {
  const [error, setError] = useState("");
  const buttons = block.kind === "navigation" || block.transition_mode === "buttons";
  const routes = block.transitions ?? [], targets = definition.blocks?.filter(item => item.id !== block.id) ?? [];
  function mode(value: "automatic" | "buttons") { try { onChange(setNavigationMode(block, value)); setError(""); } catch (cause) { setError((cause as Error).message); } }
  return <fieldset disabled={disabled} className="space-y-3 rounded-xl border p-3" aria-label="Кнопки переходов">
    <legend className="font-semibold">Переходы к другим блокам</legend>
    {block.kind !== "navigation" && <label className="block">Способ перехода<Select value={buttons ? "buttons" : "automatic"} onChange={event => mode(event.target.value as "automatic" | "buttons")}><option value="automatic">Автоматически по маршруту</option><option value="buttons">Сотрудник выбирает кнопку</option></Select></label>}
    {error && <p role="alert">{error}</p>}
    {buttons ? <><p className="text-xs text-slate-500">До 10 кнопок. Выбор пути не сохраняется как ответ на вопрос.</p>{routes.map((edge, index) => <div key={edge.button?.key ?? index} className="space-y-2 rounded-lg border p-3">
      <label className="block">Текст кнопки {index + 1}<Input maxLength={300} value={edge.button?.label ?? ""} onChange={event => onChange({ ...block, transitions: routes.map((item, i) => i === index ? { ...item, button: { key: item.button?.key ?? newKey("action"), label: event.target.value } } : item) })} /></label>
      <label className="block">Куда перейти {index + 1}<Select value={edge.to} onChange={event => onChange({ ...block, transitions: routes.map((item, i) => i === index ? { ...item, to: event.target.value } : item) })}>{!targets.some(target => target.id === edge.to) && <option value={edge.to}>Блок недоступен</option>}{targets.map(target => <option key={target.id} value={target.id}>{target.title}</option>)}</Select></label>
      {edge.when && <p className="text-xs text-slate-500">Кнопка доступна по условию связи. Измените условие на карте.</p>}
      <Button variant="ghost" onClick={() => onChange({ ...block, transitions: routes.filter((_, i) => i !== index) })}>Удалить кнопку {index + 1}</Button>
    </div>)}<Button disabled={disabled || routes.length >= 10 || !targets.length} variant="outline" onClick={() => onChange({ ...block, transition_mode: "buttons", transitions: [...routes, { to: targets[0].id, button: { key: newKey("action"), label: targets[0].title } }] })}>Добавить кнопку перехода</Button></> : <p className="text-sm text-slate-500">Соедините блоки на карте. Условия редактируются на связях.</p>}
  </fieldset>;
}
