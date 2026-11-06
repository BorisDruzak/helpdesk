import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { usePublishedScenarioPolicies } from "./scenario-policy-attachments";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioSlaProfile } from "./scenario-contract";
import { summarizeTerminalSla, terminalActualSla } from "./scenario-terminal-sla-model";
import type { ScenarioSimulation } from "./scenario-api";

function ProfileValues({ profile }: { profile: ScenarioSlaProfile }) {
 return <p>Первый ответ: {profile.first_response_minutes} мин. · решение: {profile.resolution_minutes} мин. · {profile.time_basis === "business" ? "Рабочее время" : "Календарное время"}{profile.time_basis === "business" && !profile.calendar_id ? " · календарь не выбран" : ""}.</p>;
}

/** Final SLA belongs to the existing terminal; opening this editor never upgrades or rewrites it. */
export function ScenarioTerminalSla({ block, definition, disabled, onChange, onTestPath, result }: { block: ScenarioBlock; definition: ScenarioDraftDefinition; disabled: boolean; onChange: (next: ScenarioBlock) => void; onTestPath?: () => void; result?: ScenarioSimulation }) {
 const canChoosePolicy = block.kind === "submit_ticket" && definition.schema_version === 4 && !definition.processing;
 const { policies: registry, error, retry } = usePublishedScenarioPolicies(canChoosePolicy);
 const policies = registry?.sla ?? null, routingPolicies = registry?.routing ?? null;
 if (block.kind === "finish") return <section aria-label="SLA завершения"><h3 className="font-semibold">Завершение без обращения</h3><p className="text-sm">Обращение не создаётся. Обязательство поддержки по SLA здесь не возникает, даже если на пути выбирались сроки.</p></section>;
 if (block.kind !== "submit_ticket") return null;
 const inherited = summarizeTerminalSla(definition, block.id, { inheritOnly: true });
 const actual = terminalActualSla(definition, block, result);
 const selected = definition.processing ? block.sla_profile ?? "" : block.policy_ref ?? "";
 const profile = selected ? definition.processing?.sla_profiles[selected] : undefined;
 const policy = policies?.find(item => item.code === selected);
 const selectedRoute = definition.processing ? block.route ?? "" : block.routing_policy_ref ?? "";
 const route = selectedRoute ? definition.processing?.routes[selectedRoute] : undefined;
 const routingPolicy = routingPolicies?.find(item => item.code === selectedRoute);
 function select(value: string) {
  if (block.kind !== "submit_ticket") return;
  const next = { ...block }; delete next.sla_profile; delete next.policy_ref;
  if (value) { if (definition.processing) next.sla_profile = value; else next.policy_ref = value; }
  onChange(next);
 }
 function selectRoute(value: string) {
  if (block.kind !== "submit_ticket") return;
  const next = { ...block }; delete next.route; delete next.routing_policy_ref;
  if (value) { if (definition.processing) next.route = value; else next.routing_policy_ref = value; }
  onChange(next);
 }
 return <section className="min-w-0 space-y-3" aria-label="SLA завершения">
  <h3 className="font-semibold">Маршрут и SLA создаваемого обращения</h3>
  <p className="text-sm text-slate-500">Очередь и сроки наследуются по пройденному пути. Последнее явное назначение заменяет предыдущее; выбранные здесь настройки применяются в конце.</p>
  {actual && <section className="space-y-1 rounded border border-emerald-300 bg-emerald-50 p-3 text-sm"><h4 className="font-semibold">Проверенный SLA этого пути</h4><p>Путь: {actual.route.join(" → ")}</p><p>Очередь: {actual.queue ?? "не определена сервером"}</p><p>Первый ответ: {actual.sla.first_response_min == null ? "не определён" : `${actual.sla.first_response_min} мин.`} · решение: {actual.sla.resolution_min == null ? "не определено" : `${actual.sla.resolution_min} мин.`} · {actual.sla.time_basis === "business" ? "Рабочее время" : actual.sla.time_basis === "calendar" ? "Календарное время" : "Режим времени не указан сервером"}.</p><p>Источник: {actual.source}.</p><p>Источник очереди: {actual.routingSource}.</p></section>}
  {definition.schema_version === 4 ? <fieldset disabled={disabled} className="space-y-2"><label className="block">SLA при создании обращения<Select value={selected} onChange={event => select(event.target.value)}><option value="">Наследовать SLA пройденного пути</option>
   {selected && !(definition.processing ? definition.processing.sla_profiles[selected] : policy) && <option value={selected}>Выбранный {definition.processing ? "профиль" : "правило"} недоступен</option>}
   {definition.processing ? Object.entries(definition.processing.sla_profiles).map(([key, item]) => <option key={key} value={key}>{item.title}</option>) : policies?.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}
  </Select></label>
   {canChoosePolicy && !policies && !error && <p role="status" className="text-sm">Загрузка опубликованных правил SLA…</p>}
   {canChoosePolicy && error && <div role="alert" className="text-sm"><p>Не удалось загрузить правила SLA и маршрутизации. Сохранённый выбор не изменён.</p><Button variant="outline" onClick={retry}>Повторить загрузку правил</Button></div>}
   {canChoosePolicy && policies?.length === 0 && <p className="text-sm">Нет опубликованных правил SLA для выбора.</p>}
   {selected && <div className="rounded border p-2 text-sm"><p className="font-medium">Итоговое назначение: {profile?.title ?? policy?.title ?? "сохранённый выбор"}</p>{profile ? <ProfileValues profile={profile} /> : definition.processing ? <p role="alert">Профиль отсутствует в настройках карты. Выберите существующий профиль SLA.</p> : <><p>Сроки рассчитывает сервер по ответам и опубликованному правилу; точные значения покажет проверка пути.</p>{policies && !policy && <p role="alert">Выбранное правило SLA недоступно. Выберите опубликованное правило.</p>}</>}</div>}
   <label className="block">Маршрут при создании обращения<Select value={selectedRoute} onChange={event => selectRoute(event.target.value)}><option value="">Наследовать маршрут пройденного пути</option>
    {selectedRoute && !(definition.processing ? route : routingPolicy) && <option value={selectedRoute}>Выбранный маршрут недоступен</option>}
    {definition.processing ? Object.entries(definition.processing.routes).map(([key, item]) => <option key={key} value={key}>{item.title}</option>) : routingPolicies?.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}
   </Select></label>
   {canChoosePolicy && registry && !routingPolicies?.length && <p className="text-sm">Нет опубликованных правил маршрутизации для выбора.</p>}
   {selectedRoute && <div className="rounded border p-2 text-sm"><p>Итоговый маршрут: {route?.title ?? routingPolicy?.title ?? "сохранённый выбор"}</p>{route ? <p>Очередь: {route.queue_code}.</p> : definition.processing ? <p role="alert">Маршрут отсутствует в настройках карты.</p> : <p>Очередь определит сервер по ответам и опубликованному правилу.</p>}</div>}
  </fieldset> : <p className="text-sm">В этой версии карты действует наследование SLA и маршрута. Выбор в завершении доступен после явного обновления карты до версии 4.</p>}
  <details open={inherited.alternatives.length <= 1}><summary className="text-sm font-medium">Наследуемый SLA: {inherited.alternatives.length > 1 ? `${inherited.alternatives.length} вариантов пути` : "результат пути"}</summary>
   <p className="mt-2 text-xs text-slate-500">Это варианты связей на карте. Условия, ответы и доступность правил проверяет сервер; перечисленные пути могут оказаться недостижимыми при конкретных ответах.</p>
   {!inherited.alternatives.length && <p className="mt-2 text-sm">Путь от начала или действующей точки входа к этому завершению не найден.</p>}
   <ol className="mt-2 space-y-2">{inherited.alternatives.map((item, index) => <li key={index} className="min-w-0 break-words rounded border p-2 text-sm"><p>{item.route.join(" → ")}{item.conditional ? " · условия не проверены" : ""}</p><p>Очередь: {item.routing ? `${item.routing.title} (${item.routing.queue_code})` : "определяется сервером по правилам услуги"}</p><p className="font-medium">{item.profile?.title ?? (item.selection.kind === "profile" ? "Профиль не найден" : item.selection.kind === "policy" ? policies?.find(policy => policy.code === item.selection.key)?.title ?? "Выбранное правило SLA" : "Действующая политика услуги")}</p>{item.profile ? <ProfileValues profile={item.profile} /> : item.selection.kind === "profile" ? <p role="alert">Профиль отсутствует в настройках карты.</p> : <p>Сроки определит сервер по ответам. Точные значения доступны в проверке пути.</p>}<p className="text-xs text-slate-500">Источник SLA: {item.selection.source}.{` Источник очереди: ${item.routingSelection.source}.`}</p></li>)}</ol>
   {inherited.truncated && <p role="status" className="mt-2 text-sm">Обзор ограничен: показаны не все варианты. Проверьте нужный путь на сервере.</p>}
   {inherited.cyclic && <p role="alert" className="mt-2 text-sm">На карте найден цикл; обзор этого пути остановлен. Исправьте переходы и повторите проверку.</p>}
  </details>
  {onTestPath && <Button variant="outline" disabled={disabled} onClick={onTestPath}>Проверить путь</Button>}
 </section>;
}
