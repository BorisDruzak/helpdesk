import { useState } from "react";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { scenarioMapHints, type MapHint } from "./scenario-map-hints";
export function ScenarioMapGuidance({ definition, onHint, onCheck }: { definition: ScenarioDraftDefinition; onHint: (hint: MapHint) => void; onCheck?: () => void }) {
  const [open, setOpen] = useState(false);
  const hints = scenarioMapHints(definition);
  return <section className="studio-map-guidance" aria-label="Подсказки по карте">
    <button type="button" className="w-full p-3 text-left text-xs font-semibold" aria-expanded={open} onClick={() => setOpen(!open)}>{hints.find(hint => hint.level === "required")?.text ?? "Маршрут настроен · проверить перед публикацией"} {open ? "▴" : "▾"}</button>
    {open && <div className="space-y-2 px-3 pb-3"><ul className="space-y-2">{hints.map((hint, index) => <li key={`${hint.code}:${index}`} className="text-xs leading-5"><span>{hint.text}</span> <button type="button" className="font-semibold text-emerald-700 underline" aria-label={`Исправить: ${hint.text}`} onClick={() => onHint(hint)}>Исправить</button></li>)}</ul>{!hints.some(hint => hint.level === "required") && <p className="text-xs">Основные настройки заполнены.</p>}<p className="text-xs text-slate-500">Полную проверку маршрутов и политик выполните перед публикацией.</p>{onCheck && <button type="button" className="text-xs font-semibold text-emerald-700 underline" onClick={onCheck}>Проверить готовность</button>}</div>}
  </section>;
}
