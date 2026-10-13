import { useState } from "react";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { scenarioMapHints, type MapHint } from "./scenario-map-hints";
export function ScenarioMapGuidance({ definition, onHint, onCheck }: { definition: ScenarioDraftDefinition; onHint: (hint: MapHint) => void; onCheck?: () => void }) {
  const [open, setOpen] = useState(!definition.blocks?.length);
  const hints = scenarioMapHints(definition);
  return <section className="studio-map-guidance" aria-label="Подсказки по карте">
    <button type="button" className="w-full p-3 text-left text-sm font-semibold" aria-expanded={open} onClick={() => setOpen(!open)}>Что ещё настроить · {hints.filter(hint => hint.level === "required").length} {open ? "▴" : "▾"}</button>
    {open && <div className="space-y-2 px-3 pb-3"><ul className="space-y-2">{hints.map((hint, index) => <li key={`${hint.code}:${index}`}><button type="button" className="text-left text-xs leading-5 hover:underline" onClick={() => onHint(hint)}>{hint.level === "required" ? "• " : "Совет: "}{hint.text}</button></li>)}</ul>{!hints.some(hint => hint.level === "required") && <p className="text-xs">Основные настройки заполнены.</p>}<p className="text-xs text-slate-500">Полную проверку маршрутов и политик выполните перед публикацией.</p>{onCheck && <button type="button" className="text-xs font-semibold text-blue-700 underline" onClick={onCheck}>Проверить готовность</button>}</div>}
  </section>;
}
