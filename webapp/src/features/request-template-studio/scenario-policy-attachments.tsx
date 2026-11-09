import { useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { fetchHelpdeskModelRegistry, type AdminHelpdeskPolicyItem } from "../forms-builder/api";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { ProcessingFactsEditor } from "./scenario-processing-facts";
import { ScenarioMapProcessing } from "./scenario-map-processing";
import { connectPolicyAttachment, detachPolicyAttachment, isPolicyAttachment } from "./scenario-policy-attachments-model";

/** Shared published-registry chooser: never substitutes a made-up policy or duration. */
export function usePublishedScenarioPolicies(enabled: boolean) {
 const [policies, setPolicies] = useState<Record<string, AdminHelpdeskPolicyItem[]> | null>(null);
 const [error, setError] = useState(false), [attempt, setAttempt] = useState(0);
 useEffect(() => {
  if (!enabled) return;
  let active = true; setPolicies(null); setError(false);
  void fetchHelpdeskModelRegistry().then(data => {
   if (active) setPolicies(Object.fromEntries(Object.entries(data.policies).map(([kind, values]) => [kind, values.filter((item, index, all) => item.is_active && !!item.published_at && all.findIndex(other => other.code === item.code && other.is_active && !!other.published_at) === index)])));
  }).catch(() => { if (active) setError(true); });
  return () => { active = false; };
 }, [enabled, attempt]);
 return { policies, error, retry: () => setAttempt(value => value + 1) };
}

export function ScenarioPolicyAttachmentEditor({ block, definition, disabled, onChange }: { block: ScenarioBlock; definition: ScenarioDraftDefinition; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
 const { policies, error, retry } = usePublishedScenarioPolicies(!definition.processing && isPolicyAttachment(block));
 const [targetError, setTargetError] = useState<string | null>(null);
 if (!isPolicyAttachment(block)) return null;
 const isSla = block.kind === "sla_attachment", kind = isSla ? "sla" : "routing";
 const choices = policies?.[kind] ?? [];
 const selected = definition.processing ? (block.kind === "sla_attachment" ? block.sla_profile : block.route) ?? "" : block.policy_ref ?? "";
 const mapChoices = definition.processing ? isSla ? definition.processing.sla_profiles : definition.processing.routes : {};
 const available = definition.processing ? !!mapChoices[selected] : choices.some(item => item.code === selected);
 const profile = block.kind === "sla_attachment" && block.sla_profile ? definition.processing?.sla_profiles[block.sla_profile] : undefined;
 const route = block.kind === "routing_attachment" && block.route ? definition.processing?.routes[block.route] : undefined;
 const update = (next: ScenarioBlock) => onChange({ ...definition, blocks: definition.blocks?.map(item => item.id === block.id ? next : item) });
 function select(value: string) {
  if (!isPolicyAttachment(block)) return;
  if (block.kind === "sla_attachment") {
   const next = { ...block }; delete next.sla_profile; delete next.policy_ref;
   if (value) { if (definition.processing) next.sla_profile = value; else next.policy_ref = value; } update(next);
  } else {
   const next = { ...block }; delete next.route; delete next.policy_ref;
   if (value) { if (definition.processing) next.route = value; else next.policy_ref = value; } update(next);
  }
 }
 return <fieldset disabled={disabled} className="space-y-4" aria-label={isSla ? "Прикреплённая настройка SLA" : "Прикреплённая настройка маршрута"}>
  <p className="text-sm text-slate-500">Настройка применяется, когда путь проходит связанный блок. Отдельного шага для сотрудника нет. Последнее явное назначение заменяет предыдущее; настройка перехода применяется после настройки блока.</p>
  <label className="block">Применять к блоку<Select value={block.attached_to ?? ""} onChange={event => { try { const next = event.target.value ? connectPolicyAttachment(definition, block.id, event.target.value) : detachPolicyAttachment(definition, block.id); setTargetError(null); onChange(next); } catch (failure) { setTargetError(failure instanceof Error ? failure.message : "Не удалось прикрепить настройку"); } }}><option value="">Не прикреплено</option>
   {block.attached_to && !definition.blocks?.some(item => item.id === block.attached_to && !isPolicyAttachment(item)) && <option value={block.attached_to}>Связанный блок недоступен</option>}
   {definition.blocks?.filter(item => !isPolicyAttachment(item)).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
  </Select></label>
  {!block.attached_to && <p className="text-sm">Прикрепите настройку к шагу или результату перед публикацией.</p>}
  {targetError && <p role="alert">{targetError}</p>}
  {block.kind === "sla_attachment" && <ProcessingFactsEditor value={block.processing_facts} disabled={disabled} onChange={processing_facts => update({ ...block, processing_facts })} />}
  <label className="block">{definition.processing ? isSla ? "Профиль SLA" : "Маршрут обработки" : isSla ? "Правило SLA" : "Правило маршрутизации"}<Select value={selected} onChange={event => select(event.target.value)}><option value="">{isSla ? "Не менять сроки" : "Не менять маршрут"}</option>
   {selected && !available && <option value={selected}>{definition.processing ? "Сохранённая настройка недоступна" : "Сохранённое правило недоступно"}</option>}
   {definition.processing ? Object.entries(mapChoices).map(([key, item]) => <option key={key} value={key}>{item.title}</option>) : choices.map(item => <option key={item.code} value={item.code}>{item.title}</option>)}
  </Select></label>
  {!definition.processing && !policies && !error && <p role="status">Загрузка опубликованных правил…</p>}
  {!definition.processing && error && <div role="alert"><p>Не удалось загрузить правила. Сохранённый выбор не изменён.</p><Button variant="outline" onClick={retry}>Повторить загрузку правил</Button></div>}
  {!definition.processing && policies && !choices.length && <p>Нет опубликованных правил для выбора.</p>}
  {profile && <p className="text-sm">Первый ответ: {profile.first_response_minutes} мин. · решение: {profile.resolution_minutes} мин. · {profile.time_basis === "business" ? "Рабочее время" : "Календарное время"}.</p>}
  {route && <p className="text-sm">Очередь: {route.queue_code}.</p>}
  {definition.processing && selected && available && <div className="space-y-2">
   <p className="text-sm">{(isSla ? definition.processing.defaults.sla_profile : definition.processing.defaults.route) === selected ? "Эта настройка также применяется по умолчанию для карты." : "На остальных путях действуют текущие настройки карты по умолчанию."}</p>
   <Button variant="outline" disabled={(isSla ? definition.processing.defaults.sla_profile : definition.processing.defaults.route) === selected} onClick={() => onChange({ ...definition, processing: { ...definition.processing!, defaults: { ...definition.processing!.defaults, [isSla ? "sla_profile" : "route"]: selected } } })}>{isSla ? "Использовать профиль SLA по умолчанию" : "Использовать направление по умолчанию"}</Button>
  </div>}
  {definition.processing && <ScenarioMapProcessing key={`${block.id}:${selected}`} definition={definition} disabled={disabled} onChange={onChange} section={isSla ? "sla" : "route"} itemKey={selected} onCreated={(next, key) => onChange({ ...next, blocks: next.blocks?.map(item => item.id !== block.id ? item : item.kind === "sla_attachment" ? { ...item, sla_profile: key } : item.kind === "routing_attachment" ? { ...item, route: key } : item) })} />}
  {!definition.processing && <p className="text-sm">{isSla ? "Сроки" : "Очередь"} определит сервер по ответам и опубликованному правилу. Точные значения доступны в проверке пути.</p>}
 </fieldset>;
}
