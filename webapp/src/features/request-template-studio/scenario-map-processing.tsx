import { useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import { fetchWebSettingsPayload, type WebSettingsPayload } from "../settings/api";
import { newKey } from "./scenario-builder-model";
import type { ScenarioDraftDefinition, ScenarioProcessing, ScenarioSlaProfile } from "./scenario-contract";

export const emptyMapProcessing = (): ScenarioProcessing => ({ routes: {}, sla_profiles: {}, defaults: { route: "", sla_profile: "" }, assignment_mode: "last_matching_branch" });
function DurationInput({ label, value, disabled, onChange }: { label: string; value: number; disabled: boolean; onChange: (minutes: number) => void }) {
 const [unit, setUnit] = useState(1);
 return <div className="grid min-w-0 grid-cols-2 gap-2"><label>{label}<Input disabled={disabled} type="number" min={1 / unit} max={525600 / unit} step="any" value={value / unit || ""} onChange={event => onChange(Number(event.target.value) * unit)} /></label><label>Единица {label === "Первый ответ" ? "первого ответа" : "срока решения"}<Select disabled={disabled} value={unit} onChange={event => setUnit(Number(event.target.value))}><option value={1}>Минуты</option><option value={60}>Часы</option><option value={1440}>Дни</option></Select></label></div>;
}
export function ScenarioMapProcessing({ definition, disabled, onChange }: { definition: ScenarioDraftDefinition; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
 const [registry, setRegistry] = useState<Pick<WebSettingsPayload, "queues" | "calendars"> | null>(null);
 const [error, setError] = useState(false), [attempt, setAttempt] = useState(0);
 const processing = definition.processing ?? emptyMapProcessing();
 const change = (next: ScenarioProcessing) => onChange({ ...definition, processing: next });
 useEffect(() => { let active = true; setError(false); setRegistry(null); void fetchWebSettingsPayload().then(data => { if (active) setRegistry({ queues: data.queues, calendars: data.calendars }); }).catch(() => { if (active) setError(true); }); return () => { active = false; }; }, [attempt]);
 const queues = registry?.queues.filter(item => item.is_active) ?? [], calendars = registry?.calendars.filter(item => item.is_active) ?? [];
 const profile = (key: string, patch: Partial<ScenarioSlaProfile>) => change({ ...processing, sla_profiles: { ...processing.sla_profiles, [key]: { ...processing.sla_profiles[key], ...patch } } });
 const uses = (type: "route" | "sla_profile", key: string) => processing.defaults[type] === key || definition.blocks?.some(block => block.transitions?.some(edge => edge.processing?.[type] === key));
 return <section aria-label="Обработка этой карты" className="min-w-0 space-y-4">
  <h3 className="font-semibold">Куда направлять обращения</h3>
  <p className="text-sm">Направления и сроки принадлежат этой карте. На ветках можно менять их независимо. Последнее явное назначение в пройденном маршруте заменяет предыдущее; иначе действуют выбранные ниже значения по умолчанию.</p>
  {error ? <div role="alert"><p>Не удалось загрузить очереди и рабочие календари.</p><Button variant="outline" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку справочников</Button></div> : !registry ? <p role="status">Загрузка очередей и календарей…</p> : null}
  <fieldset disabled={disabled} className="min-w-0 space-y-3">
   {Object.entries(processing.routes).map(([key, route]) => <fieldset key={key} className="min-w-0 space-y-2 rounded border p-3"><legend className="px-1">{route.title || "Направление"}</legend>
    <label className="block">Название направления<Input maxLength={300} value={route.title} onChange={event => change({ ...processing, routes: { ...processing.routes, [key]: { ...route, title: event.target.value } } })} /></label>
    <label className="block">Очередь Helpdesk<Select disabled={!registry} value={route.queue_code} onChange={event => change({ ...processing, routes: { ...processing.routes, [key]: { ...route, queue_code: event.target.value } } })}><option value="">Выберите действующую очередь</option>{route.queue_code && !queues.some(item => item.code === route.queue_code) && <option value={route.queue_code}>Выбранная очередь недоступна</option>}{queues.map(item => <option key={item.code} value={item.code}>{item.name}</option>)}</Select></label>
    <Button variant="ghost" disabled={uses("route", key)} onClick={() => change({ ...processing, routes: Object.fromEntries(Object.entries(processing.routes).filter(([id]) => id !== key)) })}>Удалить направление</Button>{uses("route", key) && <p className="text-xs text-slate-500">Используется на ветке или по умолчанию. Сначала измените назначение.</p>}
   </fieldset>)}
   <Button variant="outline" disabled={!registry || Object.keys(processing.routes).length >= 32} onClick={() => change({ ...processing, routes: { ...processing.routes, [newKey("route")]: { title: "Новое направление", queue_code: "" } } })}>Добавить направление</Button>
   <label className="block">Направление по умолчанию<Select value={processing.defaults.route} onChange={event => change({ ...processing, defaults: { ...processing.defaults, route: event.target.value } })}><option value="">Выберите направление</option>{processing.defaults.route && !processing.routes[processing.defaults.route] && <option value={processing.defaults.route}>Направление больше не найдено</option>}{Object.entries(processing.routes).map(([key, route]) => <option key={key} value={key}>{route.title}</option>)}</Select></label>
   <h3 className="font-semibold">Сроки обработки</h3>
   <p className="text-sm">Задайте сроки явно. Профиль не зависит от класса приоритета. Рабочее время рассчитывается по выбранному календарю Helpdesk.</p>
   {Object.entries(processing.sla_profiles).map(([key, item]) => <fieldset key={key} className="min-w-0 space-y-2 rounded border p-3"><legend className="px-1">{item.title || "Профиль SLA"}</legend>
    <label className="block">Название профиля<Input maxLength={300} value={item.title} onChange={event => profile(key, { title: event.target.value })} /></label>
    <DurationInput label="Первый ответ" value={item.first_response_minutes} disabled={disabled} onChange={first_response_minutes => profile(key, { first_response_minutes })} />
    <DurationInput label="Срок решения" value={item.resolution_minutes} disabled={disabled} onChange={resolution_minutes => profile(key, { resolution_minutes })} />
    <label className="block">Учёт времени<Select value={item.time_basis ?? "calendar"} onChange={event => profile(key, { time_basis: event.target.value as "calendar" | "business", calendar_id: null })}><option value="calendar">Календарное время</option><option value="business">Рабочее время</option></Select></label>
    {item.time_basis === "business" && <label className="block">Рабочий календарь<Select disabled={!registry} value={item.calendar_id ?? ""} onChange={event => profile(key, { calendar_id: event.target.value ? Number(event.target.value) : null })}><option value="">Выберите календарь</option>{item.calendar_id && !calendars.some(calendar => calendar.id === item.calendar_id) && <option value={item.calendar_id}>Выбранный календарь недоступен</option>}{calendars.map(calendar => <option key={calendar.id} value={calendar.id}>{calendar.name}</option>)}</Select></label>}
    <Button variant="ghost" disabled={uses("sla_profile", key)} onClick={() => change({ ...processing, sla_profiles: Object.fromEntries(Object.entries(processing.sla_profiles).filter(([id]) => id !== key)) })}>Удалить профиль</Button>{uses("sla_profile", key) && <p className="text-xs text-slate-500">Используется на ветке или по умолчанию. Сначала измените назначение.</p>}
   </fieldset>)}
   <Button variant="outline" disabled={Object.keys(processing.sla_profiles).length >= 32} onClick={() => change({ ...processing, sla_profiles: { ...processing.sla_profiles, [newKey("sla")]: { title: "Новый профиль", first_response_minutes: 0, resolution_minutes: 0, time_basis: "calendar", calendar_id: null } } })}>Добавить профиль SLA</Button>
   <label className="block">Профиль SLA по умолчанию<Select value={processing.defaults.sla_profile} onChange={event => change({ ...processing, defaults: { ...processing.defaults, sla_profile: event.target.value } })}><option value="">Выберите профиль</option>{processing.defaults.sla_profile && !processing.sla_profiles[processing.defaults.sla_profile] && <option value={processing.defaults.sla_profile}>Профиль больше не найден</option>}{Object.entries(processing.sla_profiles).map(([key, item]) => <option key={key} value={key}>{item.title}</option>)}</Select></label>
   {(!processing.defaults.route || !processing.defaults.sla_profile) && <p role="alert">Для публикации выберите направление и профиль SLA по умолчанию. Новые профили требуют явных сроков.</p>}
  </fieldset>
 </section>;
}
