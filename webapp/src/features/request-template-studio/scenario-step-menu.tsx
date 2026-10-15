import { useEffect, useRef } from "react";
import { Button } from "../../components/ui/button";
import type { ScenarioBlock } from "./scenario-contract";

const choices: { kind: ScenarioBlock["kind"]; title: string; hint: string }[] = [
  { kind: "form_page", title: "Спросить сотрудника", hint: "Вопрос и варианты ответа" },
  { kind: "instruction", title: "Показать инструкцию", hint: "Помочь выполнить действие" },
  { kind: "resolution_check", title: "Проверить результат", hint: "Да, нет или не знаю" },
  { kind: "decision", title: "Добавить условие", hint: "Выбрать маршрут по ответу" },
  { kind: "submit_ticket", title: "Создать обращение", hint: "Передать в поддержку" },
  { kind: "finish", title: "Завершить без обращения", hint: "Только после подтверждения решения" },
];
export function ScenarioStepMenu({ inserting, onChoose, onClose }: { inserting: boolean; onChoose: (kind: ScenarioBlock["kind"]) => void; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.querySelector<HTMLButtonElement>("button")?.focus(); }, []);
  return <div ref={ref} className="studio-step-menu" role="dialog" aria-label="Что добавить дальше?" onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); onClose(); } }}>
    <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">Что добавить дальше?</h3><Button variant="ghost" aria-label="Закрыть меню шагов" onClick={onClose}>×</Button></div>
    <p className="mb-2 text-xs text-slate-500">{inserting ? "Шаг будет вставлен в выбранную стрелку с сохранением условия." : "Новый шаг подключится автоматически."}</p>
    {choices.map(item => <button type="button" key={item.kind} className="studio-step-menu__choice" onClick={() => onChoose(item.kind)}><strong>{item.title}</strong><span>{item.hint}</span></button>)}
    {inserting && <p className="mt-2 border-t pt-2 text-xs text-slate-500">У нового условия прежнее продолжение станет ветвью «Иначе». Проверки результата и завершающие шаги добавляются отдельно.</p>}
  </div>;
}
