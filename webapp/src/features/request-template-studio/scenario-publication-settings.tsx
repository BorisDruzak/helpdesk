import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { fetchWebSettingsPayload } from "../settings/api";
import type { ScenarioDraftDefinition, ScenarioPolicyKind } from "./scenario-contract";
import { ScenarioPublicationDefinitions } from "./scenario-publication-definitions";
import { ScenarioProcessing } from "./scenario-processing";
import { scenarioQueueSettings, type ScenarioProcessingRegistry } from "./scenario-policy-settings";

type Props = { definition: ScenarioDraftDefinition; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void; requestId: number; focus?: "route" | "sla"; focusPolicy?: ScenarioPolicyKind };
export function ScenarioPublicationSettings({ definition, disabled, onChange, requestId, focus, focusPolicy }: Props) {
 const sectionRef = useRef<HTMLElement>(null), routeRef = useRef<HTMLSelectElement>(null), slaRef = useRef<HTMLSelectElement>(null);
 const [registry, setRegistry] = useState<ScenarioProcessingRegistry | null>(null);
 const [failed, setFailed] = useState(false), [attempt, setAttempt] = useState(0);
 const processing = definition.processing;
 const optionalFallback = definition.schema_version === 4;
 useEffect(() => { if (requestId && !focusPolicy) { const target = focus === "route" ? routeRef.current : focus === "sla" ? slaRef.current : sectionRef.current; target?.focus(); target?.scrollIntoView?.({ block: "nearest" }); } }, [requestId, focus, focusPolicy]);
 useEffect(() => { if (!processing) return; let active = true; setFailed(false); void fetchWebSettingsPayload().then(value => { if (active) setRegistry(value); }).catch(() => { if (active) setFailed(true); }); return () => { active = false; }; }, [attempt, !!processing]);
 const { queues, defaultCode } = scenarioQueueSettings(registry);
 const common = queues.find(queue => queue.code === defaultCode);
 const missingRoutes = processing ? Object.entries(processing.routes).filter(([, route]) => !route.queue_code || (!!registry && !registry.queues.some(queue => queue.is_active && queue.code === route.queue_code))) : [];
 return <section ref={sectionRef} tabIndex={-1} aria-label="Обработка услуги" className="scenario-publication-section space-y-4">
  <h2>Обработка услуги</h2>
  <p className="text-sm text-slate-600">Общие правила действуют для всей услуги. Блоки маршрута и сроков на карте уточняют их для пройденного пути. Приоритет и сроки рассчитываются по ответам и действующим правилам.</p>
  <ScenarioProcessing definition={definition} disabled={disabled} onChange={onChange} serviceWide focusPolicy={focusPolicy} focusRequestId={requestId} />
  {processing && <details aria-label="Резервные настройки карты" className="space-y-3" open={!optionalFallback || Boolean(requestId && focus && !focusPolicy)}>
   <summary className="cursor-pointer font-semibold">Дополнительные настройки карты{optionalFallback ? " (необязательно)" : ""}</summary>
   <p className="text-sm text-slate-600">Применяются, если на пройденном пути нет явного назначения. {optionalFallback ? "Дополнительный профиль сроков для сотрудника не нужен, когда сроки определены блоками или действующими правилами услуги. Проверка публикации проверяет каждый путь." : "В этой версии карты направление и профиль сроков для сотрудника по умолчанию обязательны."}</p>
   <label className="block">Резервное направление<Select ref={routeRef} disabled={disabled} value={processing.defaults.route} onChange={event => onChange({ ...definition, processing: { ...processing, defaults: { ...processing.defaults, route: event.target.value } } })}><option value="">{optionalFallback ? "Рассчитать по правилам услуги/пройденному пути" : "Выберите резервную настройку"}</option>{processing.defaults.route && !processing.routes[processing.defaults.route] && <option value={processing.defaults.route}>Направление больше не найдено</option>}{Object.entries(processing.routes).map(([key, route]) => <option key={key} value={key}>{route.title}</option>)}</Select></label>
   <label className="block">Резервный профиль сроков для сотрудника<Select ref={slaRef} disabled={disabled} value={processing.defaults.sla_profile} onChange={event => onChange({ ...definition, processing: { ...processing, defaults: { ...processing.defaults, sla_profile: event.target.value } } })}><option value="">{optionalFallback ? "Рассчитать по правилам услуги/пройденному пути" : "Выберите резервную настройку"}</option>{processing.defaults.sla_profile && !processing.sla_profiles[processing.defaults.sla_profile] && <option value={processing.defaults.sla_profile}>Профиль больше не найден</option>}{Object.entries(processing.sla_profiles).map(([key, profile]) => <option key={key} value={key}>{profile.title}</option>)}</Select></label>
   {failed && <div role="alert"><p>Не удалось проверить общую очередь.</p><Button variant="outline" onClick={() => setAttempt(value => value + 1)}>Повторить загрузку общей очереди</Button></div>}
   {missingRoutes.map(([key, route]) => <div key={key} className="rounded border p-3 space-y-2"><p>В направлении «{route.title}» не выбрана действующая очередь. Настройте направление ниже{common ? " или используйте настроенную общую очередь." : "."}</p>{common && <Button disabled={disabled} variant="outline" onClick={() => onChange({ ...definition, processing: { ...processing, routes: { ...processing.routes, [key]: { ...route, queue_code: common.code } } } })}>Использовать общую очередь «{common.name}»</Button>}</div>)}
   <ScenarioPublicationDefinitions definition={definition} disabled={disabled} onChange={onChange} />
  </details>}

 </section>;
}
