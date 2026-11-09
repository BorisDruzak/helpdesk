import { useState } from "react";
import { Select } from "../../components/ui/select";
import { Button } from "../../components/ui/button";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import type { ScenarioSimulation } from "./scenario-api";
import { usePublishedScenarioPolicies } from "./scenario-policy-attachments";
import { terminalActualSla } from "./scenario-terminal-sla-model";

import { summarizeTerminalOla, type OlaValue } from "./scenario-ola-model";
export { summarizeTerminalOla } from "./scenario-ola-model";

/** Durations are calendar minutes, matching the existing OLA runtime. */
export function ScenarioOlaEditor({ value, disabled, onChange, inherit = false }: { value: OlaValue; disabled: boolean; onChange: (value: OlaValue) => void; inherit?: boolean }) {
 const [emptyMode, setEmptyMode] = useState("inherit");
 const mode = value.targets ? "targets" : value.policy_ref ? "policy" : emptyMode;
 const { policies, error, retry } = usePublishedScenarioPolicies(mode === "policy");
 const choices = policies?.ola ?? [];
 return <fieldset disabled={disabled} className="min-w-0 space-y-3" aria-label="Настройка внутренних сроков">
  <label className="block">Способ задания внутренних сроков<Select value={mode} onChange={event => {
   const next = event.target.value; setEmptyMode(next);
   onChange(next === "targets" ? { targets: { ack_minutes: 15, processing_minutes: 240 } } : {});
  }}><option value="inherit">{inherit ? "Получить внутренние сроки из пути заявки" : "Сохранить действующие внутренние сроки"}</option><option value="targets">Задать сроки вручную</option><option value="policy">Опубликованное правило внутренних сроков</option></Select></label>
  {mode === "targets" && <div className="grid gap-3 sm:grid-cols-2">{(["ack_minutes", "processing_minutes"] as const).map(key => <label className="block text-sm" key={key}>{key === "ack_minutes" ? "Назначение исполнителя, мин." : "Обработка группой, мин."}<input className="field-base mt-1 w-full" type="number" min={1} max={525600} step={1} required value={value.targets?.[key] ?? ""} onChange={event => onChange({ targets: { ack_minutes: value.targets?.ack_minutes ?? 15, processing_minutes: value.targets?.processing_minutes ?? 240, [key]: event.target.value === "" ? 0 : Number(event.target.value) } })} /></label>)}</div>}
  {mode === "policy" && <><label className="block">Правило внутренних сроков<Select value={value.policy_ref ?? ""} onChange={event => onChange(event.target.value ? { policy_ref: event.target.value } : {})}><option value="">Выберите опубликованное правило</option>{value.policy_ref && !choices.some(item => item.code === value.policy_ref) && <option value={value.policy_ref}>Сохранённое правило недоступно</option>}{choices.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}</Select></label>{error ? <div role="alert"><p>Не удалось загрузить правила внутренних сроков. Сохранённый выбор не изменён.</p><Button variant="outline" onClick={retry}>Повторить загрузку внутренних сроков</Button></div> : !policies ? <p role="status">Загрузка правил внутренних сроков…</p> : !choices.length ? <p>Нет опубликованных правил внутренних сроков.</p> : null}</>}
  <p className="text-xs text-slate-500">Внутренние сроки группы поддержки: назначение исполнителя и обработка обращения. Назначение исполнителя останавливает первый таймер, решение — второй. Ручные сроки считаются в календарных минутах. Последняя настройка на пройденном пути заменяет предыдущую; завершение может уточнить её.</p>
 </fieldset>;
}

function OlaValues({ value }: { value: OlaValue }) {
 return <p>{value.targets ? `Назначение исполнителя: ${value.targets.ack_minutes} мин. · обработка группой: ${value.targets.processing_minutes} мин. · календарное время.` : value.policy_ref ? "Опубликованное правило внутренних сроков: сроки определит сервер по приоритету." : "Сроки определяются действующими правилами услуги или очереди."}</p>;
}

export function ScenarioTerminalOla({ block, definition, disabled, onChange, result }: { block: ScenarioBlock; definition: ScenarioDraftDefinition; disabled: boolean; onChange: (next: ScenarioBlock) => void; result?: ScenarioSimulation }) {
 if (block.kind !== "submit_ticket") return null;
 const inherited = summarizeTerminalOla(definition, block.id, true);
 const actual = terminalActualSla(definition, block, result) ? result?.processing?.ola : undefined;
 return <section className="min-w-0 space-y-3 rounded-xl border p-3" aria-label="Внутренние сроки завершения"><h3 className="font-semibold">Внутренние сроки поддержки</h3>
  {definition.schema_version === 4 && <ScenarioOlaEditor key={block.id} value={{ targets: block.ola_targets, policy_ref: block.ola_policy_ref }} disabled={disabled} inherit onChange={value => { const next = { ...block }; delete next.ola_targets; delete next.ola_policy_ref; if (value.targets) next.ola_targets = value.targets; if (value.policy_ref) next.ola_policy_ref = value.policy_ref; onChange(next); }} />}
  {actual && <div className="rounded border border-emerald-300 bg-emerald-50 p-2 text-sm"><h4>{actual.enabled === false ? "Настроенные внутренние сроки (учёт отключён)" : "Проверенные внутренние сроки этого пути"}</h4>{actual.enabled === false && <p role="alert">Учёт внутренних сроков отключён на сервере. Таймеры назначения исполнителя и обработки не будут запущены.</p>}<p>Назначение исполнителя: {actual.ack_min == null ? "срок не задан" : `${actual.ack_min} мин.`} · обработка группой: {actual.processing_min == null ? "срок не задан" : `${actual.processing_min} мин.`}.</p></div>}
  <details open={inherited.alternatives.length <= 1}><summary>Внутренние сроки по пути заявки</summary><p className="text-xs text-slate-500">Варианты связей на карте; ответы и условия проверяет сервер в тестировании.</p>{inherited.alternatives.map((item, index) => <div key={index} className="mt-2 rounded border p-2 text-sm"><p>{item.route.join(" → ")}</p><OlaValues value={item}/><p>Источник: {item.source}.</p></div>)}{!inherited.alternatives.length && <p>Путь к этому завершению не найден.</p>}{(inherited.truncated || inherited.cyclic) && <p>Обзор ограничен. Проверьте конкретный путь в тестировании.</p>}</details>
 </section>;
}
