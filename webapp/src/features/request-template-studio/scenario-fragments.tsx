import { isPolicyAttachment } from "./scenario-policy-attachments-model";
import { useEffect, useRef, useState } from "react";
import { fetchHelpdeskModelRegistry, type AdminHelpdeskPolicyItem } from "../forms-builder/api";
import { fetchWebSettingsPayload } from "../settings/api";
import { ScenarioApiError, type ScenarioDetail } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { builtinFragments, insertBuiltinFragment, type BuiltinFragmentKey } from "./scenario-fragment-model";
import { newKey } from "./scenario-builder-model";
import { archiveScenarioFragment, createScenarioFragment, emptyFragmentMappings, fetchScenarioFragment, fetchScenarioFragments, insertSavedScenarioFragment, type FragmentDetail, type FragmentMappings, type FragmentSummary } from "./scenario-fragment-api";

type Props = { definition: ScenarioDraftDefinition; detail: ScenarioDetail | null; dirty: boolean; selectedBlockId?: string; disabled: boolean; position: {x:number;y:number}; onLocalInsert: (next: ScenarioDraftDefinition) => void; onInserted: (detail: ScenarioDetail & {inserted_block_ids?:string[]}) => void; onBusy?: (busy:boolean) => void };
const mappingNames = {attachment_target:"blocks",field:"fields",route:"routes",sla_profile:"sla_profiles",policy_ref:"policy_refs",sla_policy_ref:"sla_policy_refs",routing_policy_ref:"routing_policy_refs",ola_policy_ref:"ola_policy_refs",calendar:"calendars",fact:"facts"} as const;
const kindLabels: Record<string,string> = {attachment_target:"Блок для настройки",field:"Поле",route:"Маршрут",sla_profile:"Профиль сроков для сотрудника",policy_ref:"Правило сроков для сотрудника",sla_policy_ref:"Правило сроков для сотрудника",routing_policy_ref:"Правило маршрутизации",ola_policy_ref:"Правило внутренних сроков",calendar:"Календарь",fact:"Назначение ответа"};
export function ScenarioFragments({ definition, detail, dirty, selectedBlockId, disabled, position, onLocalInsert, onInserted, onBusy }: Props) {
 const [list,setList] = useState<FragmentSummary[]>([]), [chosen,setChosen] = useState<FragmentDetail|null>(null), [builtin,setBuiltin] = useState<BuiltinFragmentKey|null>(null);
 const [selected,setSelected] = useState<string[]>(selectedBlockId ? [selectedBlockId] : []), [title,setTitle] = useState(""), [mappings,setMappings] = useState<FragmentMappings>(emptyFragmentMappings);
 const [policies,setPolicies] = useState<Record<"sla"|"ola"|"routing",AdminHelpdeskPolicyItem[]>>({sla:[],ola:[],routing:[]}), [calendars,setCalendars] = useState<{id:number;name:string}[]>([]), [message,setMessage] = useState(""), [busy,setBusy] = useState(false);
 const generation = useRef(0), selectedRequest = useRef(0), busyCallback = useRef(onBusy); busyCallback.current = onBusy;
 const scope = `${detail?.scenario.id ?? "new"}:${disabled}`;
 useEffect(() => { const current = ++generation.current; selectedRequest.current++; setChosen(null); setList([]); setMappings(emptyFragmentMappings()); setMessage(""); setBusy(false);
   void fetchScenarioFragments().then(result => { if (generation.current === current) setList(result.items); }).catch(() => { if (generation.current === current) setMessage("Не удалось загрузить библиотеку фрагментов."); });
   return () => { generation.current++; selectedRequest.current++; busyCallback.current?.(false); };
 }, [scope]);
 useEffect(() => { setSelected(selectedBlockId ? [selectedBlockId] : []); }, [selectedBlockId, scope]);
 useEffect(() => { if (!chosen) return; let active = true;
   if (chosen.external_dependencies.some(d => ["policy_ref", "sla_policy_ref", "ola_policy_ref", "routing_policy_ref"].includes(d.kind))) void fetchHelpdeskModelRegistry().then(data => {if(active) setPolicies({ola:(data.policies.ola ?? []).filter(p => p.is_active && !!p.published_at),sla:(data.policies.sla ?? []).filter(p => p.is_active && !!p.published_at), routing:(data.policies.routing ?? []).filter(p => p.is_active && !!p.published_at)});}).catch(() => {if(active) setMessage("Не удалось загрузить правила сроков и маршрутизации.");});
   if (chosen.external_dependencies.some(d => d.kind === "calendar")) void fetchWebSettingsPayload().then(data => {if(active) setCalendars(data.calendars.filter(c => c.is_active));}).catch(() => {if(active) setMessage("Не удалось загрузить календари.");});
   return () => {active = false;};
 }, [chosen]);
 async function selectFragment(id:string) { const scopeGeneration = generation.current, requestId = ++selectedRequest.current; setChosen(null); setBuiltin(null); setMappings(emptyFragmentMappings()); setMessage("");
   try { const data = await fetchScenarioFragment(id); if (scopeGeneration === generation.current && requestId === selectedRequest.current) setChosen(data); } catch { if(scopeGeneration === generation.current && requestId === selectedRequest.current) setMessage("Не удалось открыть фрагмент."); }
 }
 async function run(action: () => Promise<void>) { const current = generation.current; setBusy(true); busyCallback.current?.(true); setMessage(""); try { await action(); } catch (error) { if (generation.current === current) setMessage(error instanceof ScenarioApiError && error.dependencies.length ? `Проверьте сопоставление: ${error.dependencies.map(d => d.label).join(", ")}` : "Не удалось выполнить действие. Проверьте актуальность черновика и повторите попытку."); } finally {if(generation.current === current) {setBusy(false);busyCallback.current?.(false);} } }
 const live = useRef({detail,dirty,disabled}); live.current = {detail,dirty,disabled};
 function canPersist() { return !!live.current.detail && !live.current.dirty && !live.current.disabled; }
 const fields = (definition.blocks ?? []).flatMap(block => block.kind === "form_page" ? block.fields : []);
 const usedFacts = new Set(fields.flatMap(field => [field.key, ...(field.aliases ?? []), field.process_mapping?.fact_key || field.key]));
 const options = (kind:string): {value:string;label:string}[] => {
  if(kind === "attachment_target") return (definition.blocks ?? []).filter(block => !isPolicyAttachment(block)).map(block => ({value:block.id,label:block.title}));
  if(kind === "field") return fields.map(f => ({value:f.key,label:`${f.label} (${f.type})`}));
  if(kind === "route") return Object.entries(definition.processing?.routes ?? {}).map(([key,v]) => ({value:key,label:v.title}));
  if(kind === "sla_profile") return Object.entries(definition.processing?.sla_profiles ?? {}).map(([key,v]) => ({value:key,label:v.title}));
  if(kind === "policy_ref" || kind === "sla_policy_ref") return policies.sla.map(p => ({value:p.code,label:p.title}));
  if(kind === "ola_policy_ref") return policies.ola.map(p => ({value:p.code,label:p.title}));
  if(kind === "routing_policy_ref") return policies.routing.map(p => ({value:p.code,label:p.title}));
  if(kind === "calendar") return calendars.map(c => ({value:String(c.id),label:c.name}));
  return [];
 };
 const dependencies = chosen?.external_dependencies ?? [];
 const factValues = Object.values(mappings.facts).filter(Boolean);
 const missing = dependencies.some(d => d.kind !== "block" && (!(Object.hasOwn(mappingNames, d.kind)) || !mappings[mappingNames[d.kind as keyof typeof mappingNames]][d.key])) || factValues.some(value => usedFacts.has(value)) || new Set(factValues).size !== factValues.length;
 let preview: ScenarioDraftDefinition | null = null;
 if (builtin) { try { preview = insertBuiltinFragment({...definition, blocks:[], entry_block_id:null, entry_points:[]}, builtin, position); } catch { /* insertion explains unsupported schema */ } }
 return <section aria-label="Библиотека фрагментов" className="space-y-4">
  <h3>Библиотека фрагментов</h3>
  <div><h4>Готовые шаблоны</h4><div className="flex flex-wrap gap-2">{builtinFragments.map(item => <button type="button" key={item.key} disabled={disabled || busy} onClick={() => {setBuiltin(item.key);setChosen(null);selectedRequest.current++;setMessage("");}}>{item.title}</button>)}</div></div>
  {builtin && <div><h4>Предпросмотр шаблона</h4><ul>{preview?.blocks?.map(b => <li key={b.id}>{b.title}</li>)}</ul><button type="button" disabled={disabled || busy} onClick={() => {try {onLocalInsert(insertBuiltinFragment(definition,builtin,position));setMessage("Шаблон добавлен на карту.");} catch (e) {setMessage(e instanceof Error ? e.message : "Не удалось добавить шаблон.");}}}>Добавить шаблон</button></div>}
  <div><h4>Сохранённые фрагменты</h4>{list.length === 0 && <p>Сохранённых фрагментов нет.</p>}{list.map(item => <button type="button" key={item.id} onClick={() => void selectFragment(item.id)}>{item.title} · {item.block_count} блоков · {item.source_title}</button>)}</div>
  {(!detail || dirty) && <p>Сначала сохраните услугу и её изменения для работы с сохранёнными фрагментами.</p>}
  {chosen && <div className="space-y-2"><h4>Предпросмотр: {chosen.fragment.title}</h4><ul>{chosen.definition.blocks?.map(block => <li key={block.id}>{block.title} ({block.kind})</li>)}</ul>
   {definition.schema_version !== 4 && <p>Сначала включите новые возможности карты, чтобы вставить сохранённый фрагмент.</p>}
   {dependencies.filter(d => d.kind === "block").length > 0 && <p role="status">Внешние переходы не копируются. После вставки соедините блоки на карте.</p>}
   {dependencies.filter(d => d.kind !== "block").map(dep => dep.kind === "fact" ? <label className="block" key={`fact:${dep.key}`}>Назначение ответа: {dep.label}<select value={!mappings.facts[dep.key] ? "" : mappings.facts[dep.key] === dep.key ? "original" : "new"} onChange={event => {const value = event.target.value === "original" ? dep.key : event.target.value === "new" ? newKey("fact") : ""; setMappings(previous => ({...previous, facts:{...previous.facts,[dep.key]:value}}));}}><option value="">Выберите назначение</option>{!usedFacts.has(dep.key) && !Object.entries(mappings.facts).some(([key,value]) => key !== dep.key && value === dep.key) && <option value="original">Сохранить исходное назначение</option>}<option value="new">Новое независимое поле</option></select><span> Новое поле не наследует правила обработки исходной услуги.</span></label> : <label className="block" key={`${dep.kind}:${dep.key}`}>{kindLabels[dep.kind] ?? "Неизвестная зависимость"}: {dep.label}<select value={Object.hasOwn(mappingNames, dep.kind) ? String(mappings[mappingNames[dep.kind as keyof typeof mappingNames]][dep.key] ?? "") : ""} onChange={event => {const name = mappingNames[dep.kind as keyof typeof mappingNames]; if (!name) return; const value = event.target.value; setMappings(previous => ({...previous,[name]:{...previous[name],[dep.key]:name === "calendars" ? Number(value) : value}}));}}><option value="">Выберите значение</option>{options(dep.kind).map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>)}
   <button type="button" disabled={disabled || busy || !detail || dirty || missing || definition.schema_version !== 4} onClick={() => void run(async () => {const current = generation.current; const target = live.current.detail; if (!target || !canPersist()) return; const result = await insertSavedScenarioFragment(target.scenario.id, chosen.fragment.id, target.draft.revision, chosen.fragment.revision, position, mappings); if (generation.current === current && canPersist()) onInserted(result);})}>Вставить фрагмент</button>
   <button type="button" disabled={disabled || busy} onClick={() => void run(async () => {const current = generation.current; await archiveScenarioFragment(chosen.fragment.id, chosen.fragment.revision); if(generation.current === current && !live.current.disabled) {setList(items => items.filter(i => i.id !== chosen.fragment.id));setChosen(null);setMessage("Фрагмент архивирован.");}})}>Архивировать фрагмент</button>
  </div>}
  <fieldset disabled={disabled || busy || !detail || dirty}><legend>Сохранить блоки как фрагмент</legend><label>Название фрагмента <input value={title} maxLength={300} onChange={e => setTitle(e.target.value)} /></label><p>Выберите один или несколько блоков:</p>{definition.blocks?.map(block => <label className="block" key={block.id}><input type="checkbox" checked={selected.includes(block.id)} onChange={e => setSelected(current => e.target.checked ? [...current,block.id] : current.filter(id => id !== block.id))} /> {block.title}</label>)}
   <p>Предпросмотр: {selected.map(id => definition.blocks?.find(b => b.id === id)?.title).filter(Boolean).join(", ") || "блоки не выбраны"}</p>
   <button type="button" disabled={!title.trim() || !selected.length} onClick={() => void run(async () => {const current = generation.current; const source = live.current.detail; if(!source || !canPersist()) return; const result = await createScenarioFragment(title.trim(),source.scenario.id,selected,source.draft.revision); if(generation.current === current && canPersist()) {setList(items => [...items,result.fragment]); setChosen(result);setBuiltin(null);setMappings(emptyFragmentMappings());setMessage("Фрагмент сохранён.");}})}>Сохранить фрагмент</button>
  </fieldset>{message && <p role="status">{message}</p>}
 </section>;
}
