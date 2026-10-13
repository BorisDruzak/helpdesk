import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ReactFlowInstance } from "@xyflow/react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioPolicyKind } from "./scenario-contract";
import { duplicateBlock } from "./scenario-builder-model";
import { ScenarioBlockEditor } from "./scenario-block-editor";
import { ScenarioPurpose } from "./scenario-purpose";
import { ScenarioProcessing } from "./scenario-processing";
import { ScenarioEntryInspector } from "./scenario-entry-inspector";
import { ScenarioEdgeInspector } from "./scenario-edge-inspector";
import { ScenarioMapCanvas, transitionId, entranceEdgeId, metadataNodeId, type MapNode } from "./scenario-map-canvas";
import { addMapBlock, appendMapStep, connectBlocks, connectStart, reconnectStart, insertOnTransition, mapPalette, positionBlock, reconnectTransition, requireAcyclic, stableMapPositions, terminal } from "./scenario-map-model";
import { ScenarioDeleteDialog } from "./scenario-delete-dialog";
import { ScenarioBlockRoutes } from "./scenario-block-routes";
import { ScenarioStepMenu } from "./scenario-step-menu";
import { ScenarioResultBinding } from "./scenario-result-binding";
import { useWorkbenchGeometry } from "./scenario-workbench-geometry";
import { ScenarioMapGuidance } from "./scenario-map-guidance";
import { ScenarioRequesterPreview, ScenarioPagePreview } from "./scenario-requester-preview";
import { ScenarioWorkbenchCatalog, type WorkbenchCatalogProps } from "./scenario-workbench-catalog";

type Props = { definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; existing: boolean; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void; issueBlockId?: string; issueTransitions?: boolean; issuePolicy?: ScenarioPolicyKind; path?: string[]; current?: string; inspectorPanel?: ReactNode; catalogPanel?: WorkbenchCatalogProps; explorerTab?: "catalog" | "blocks"; onExplorerTab?: (tab: "catalog" | "blocks") => void; onTest?: () => void; onCheck?: () => void; onInspect?: () => void; onCategoryDirty?: (dirty: boolean) => void; onCategoryOpen?: (open: boolean) => void; onCategoryCreated?: () => Promise<void> };
export function ScenarioMapWorkbench({ definition, catalog, existing, disabled, onChange, issueBlockId, issueTransitions, issuePolicy, path, current, inspectorPanel, catalogPanel, explorerTab = "blocks", onExplorerTab, onTest, onCheck, onInspect, ...categoryProps }: Props) {
  const [selected, setSelected] = useState(!existing ? definition.blocks?.[0]?.id ?? metadataNodeId : metadataNodeId);
  const [stepMenu, setStepMenu] = useState<{ source: string | null; index?: number } | null>(null);
  const [bindingFocus, setBindingFocus] = useState(false);
  const [separateStep, setSeparateStep] = useState<ScenarioBlock["kind"] | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(false), [rightCollapsed, setRightCollapsed] = useState(false);
  const [edge, setEdge] = useState<{ source: string; index: number } | null>(null);
  const [entranceLink,setEntranceLink]=useState<{key:string|null;target:string}|null>(null);
  const [inspectorTab,setInspectorTab]=useState<"settings"|"preview">("settings");
  const [fullPreview,setFullPreview]=useState(false);
  const [search, setSearch] = useState("");
  const [past, setPast] = useState<ScenarioDraftDefinition[]>([]), [future, setFuture] = useState<ScenarioDraftDefinition[]>([]);
  const [error, setError] = useState("");
  const [removing, setRemoving] = useState(false);
  const [pendingInsert, setPendingInsert] = useState<{ kind: ScenarioBlock["kind"]; source: string; index: number; position: { x: number; y: number } } | null>(null);
  const flow = useRef<ReactFlowInstance<MapNode> | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const geometry = useWorkbenchGeometry(gridRef);
  const emitted = useRef(definition);
  const blocks = definition.blocks ?? [];
  const block = blocks.find(item => item.id === selected);
  const positions = stableMapPositions(definition);
  const hasInspectorPanel = !!inspectorPanel;
  useEffect(() => { if (hasInspectorPanel) setRightCollapsed(false); }, [hasInspectorPanel]);
  useEffect(() => { if (issueBlockId) { setSelected(issueBlockId); setEntranceLink(null); setInspectorTab("settings"); setEdge(issueTransitions && definition.blocks?.find(item => item.id === issueBlockId)?.transitions?.length ? { source: issueBlockId, index: 0 } : null); } else if (issuePolicy) { setSelected(metadataNodeId); setEdge(null); setEntranceLink(null); setInspectorTab("settings"); } }, [issueBlockId, issueTransitions, issuePolicy]);
  useEffect(() => { if (emitted.current.scenario_key !== definition.scenario_key) { setPast([]); setFuture([]); setSelected(metadataNodeId); setEdge(null); setPendingInsert(null); setRemoving(false); setError(""); setEntranceLink(null); setFullPreview(false); setInspectorTab("settings"); } emitted.current = definition; }, [definition]);
  useEffect(()=>{if(!entranceLink)return;const target=entranceLink.key===null?definition.entry_block_id:definition.entry_points?.find(entry=>entry.key===entranceLink.key)?.target_block_id;
    if(!target||(entranceLink.key===null&&definition.entry_points?.some(entry=>entry.target_block_id===target))){setEntranceLink(null);return;}
    if(target!==entranceLink.target){setEntranceLink({...entranceLink,target});setSelected(target);}
  },[definition,entranceLink]);
  function choose(id: string) { setSelected(id); setEdge(null); setEntranceLink(null); setRemoving(false); setError(""); setStepMenu(null); setSeparateStep(null); setRightCollapsed(false); setBindingFocus(false); }
  function change(next: ScenarioDraftDefinition) {
    if (disabled || JSON.stringify(next) === JSON.stringify(definition)) return;
    try { requireAcyclic(next); setPast(items => [...items.slice(-99), structuredClone(definition)]); setFuture([]); setError(""); emitted.current = next; onChange(next); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Изменение не выполнено"); }
  }
  function perform(action: () => ScenarioDraftDefinition) { try { change(action()); } catch (failure) { setError(failure instanceof Error ? failure.message : "Изменение не выполнено"); } }
  function history(redo: boolean) {
    const next = redo ? future[0] : past[past.length - 1]; if (!next || disabled) return;
    if (redo) { setFuture(future.slice(1)); setPast([...past, structuredClone(definition)]); }
    else { setPast(past.slice(0, -1)); setFuture([structuredClone(definition), ...future]); }
    emitted.current = next; onChange(next); setError("");
  }
  function add(kind: ScenarioBlock["kind"], point?: { x: number; y: number }) {
    const position = point ?? { x: (blocks.length % 3) * 310, y: Math.floor(blocks.length / 3) * 200 };
    perform(() => { const next = addMapBlock(definition, kind, position); const id = next.blocks![next.blocks!.length - 1].id; choose(id); return next; });
  }
  function addContextStep(kind: ScenarioBlock["kind"]) {
    if (!stepMenu || disabled) return;
    try {
      const next = stepMenu.index !== undefined && stepMenu.source ? insertOnTransition(definition, stepMenu.source, stepMenu.index, kind) : appendMapStep(definition, stepMenu.source, kind);
      change(next); choose(next.blocks!.at(-1)!.id); setInspectorTab("settings"); onInspect?.();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Не удалось добавить шаг"); setSeparateStep(kind); }
  }
  const entrances = definition.entry_points ?? [];
  return <div className="min-w-0 space-y-3" onKeyDown={event => {
    if (fullPreview) return;
    if ((event.ctrlKey || event.metaKey) && !/INPUT|TEXTAREA|SELECT/.test((event.target as HTMLElement).tagName)) {
      if (event.key.toLowerCase() === "z") { event.preventDefault(); history(event.shiftKey); }
      if (event.key.toLowerCase() === "y") { event.preventDefault(); history(true); }
    }
  }}>
    <div className="studio-map-toolbar flex flex-wrap gap-2"><Button disabled={disabled || !past.length} variant="ghost" onClick={() => history(false)}>Отменить изменение</Button><Button disabled={disabled || !future.length} variant="ghost" onClick={() => history(true)}>Повторить изменение</Button><Button variant="ghost" onClick={() => void flow.current?.fitView({ padding: 0.2 })}>Вся карта</Button><Button variant="ghost" onClick={()=>{choose(definition.entry_block_id??metadataNodeId);setInspectorTab("settings");onInspect?.();void flow.current?.fitView({nodes:flow.current.getNodes().filter(node=>node.data.entrance||node.id===definition.entry_block_id),padding:0.25,maxZoom:1});}}>Начало маршрута</Button><Button variant="outline" onClick={()=>setFullPreview(true)}>Предпросмотр страницы</Button><Button variant="ghost" aria-expanded={!leftCollapsed} onClick={() => setLeftCollapsed(!leftCollapsed)}>{leftCollapsed ? "Показать библиотеку" : "Свернуть библиотеку"}</Button><Button variant="ghost" aria-expanded={!rightCollapsed} onClick={() => setRightCollapsed(!rightCollapsed)}>{rightCollapsed ? "Показать настройки" : "Свернуть настройки"}</Button><details className="self-center"><summary className="cursor-pointer text-xs text-slate-500">Как работать с картой</summary><p className="studio-toolbar-help">Кнопка + добавляет и соединяет шаг. Перемещение блоков меняет только расположение. Стрелки задают маршрут; границы панелей можно перетаскивать.</p></details></div>
    {error && <div role="alert" className="rounded border border-amber-300 bg-amber-50 p-3"><p>{error}</p>{separateStep && <Button variant="outline" onClick={() => { add(separateStep); setStepMenu(null); onInspect?.(); }}>Добавить отдельно и настроить ветви</Button>}</div>}
    {pendingInsert && <div className="rounded border p-3"><p>Вставить новый блок между выбранными шагами, сохранив условие?</p><Button disabled={disabled} onClick={() => { perform(() => insertOnTransition(definition, pendingInsert.source, pendingInsert.index, pendingInsert.kind, pendingInsert.position)); setPendingInsert(null); }}>Вставить между шагами</Button><Button variant="ghost" onClick={() => setPendingInsert(null)}>Отмена вставки</Button></div>}

    <div ref={gridRef} className={`studio-map-workbench ${leftCollapsed ? "is-left-collapsed" : ""} ${rightCollapsed ? "is-right-collapsed" : ""}`} style={geometry.style}>
      <aside className="studio-map-explorer space-y-4" aria-label="Библиотека блоков">
        {catalogPanel && <div role="tablist" aria-label="Содержимое левой панели" className="flex gap-1">{(["catalog", "blocks"] as const).map(tab=><button key={tab} type="button" role="tab" aria-selected={explorerTab===tab} className={`rounded px-3 py-2 text-sm ${explorerTab===tab?"bg-blue-50 font-semibold":"hover:bg-slate-100"}`} onClick={()=>onExplorerTab?.(tab)}>{tab==="catalog"?"Каталог":"Блоки"}</button>)}</div>}
        {catalogPanel && explorerTab === "catalog" ? <ScenarioWorkbenchCatalog {...catalogPanel} /> : <>
        <h3 className="font-semibold">Библиотека блоков</h3>
        <div className="space-y-1">{mapPalette.map(item => <button key={item.kind} type="button" className="w-full rounded-lg border px-3 py-2 text-left text-sm hover:bg-blue-50 disabled:opacity-50" disabled={disabled || blocks.length >= 256} draggable={!disabled} onDragStart={event => event.dataTransfer.setData("application/x-scenario-kind", item.kind)} onClick={() => add(item.kind)}>+ {item.label}</button>)}</div>
        <details><summary className="cursor-pointer text-sm">Найти шаг · расположение панелей</summary><Button variant="ghost" onClick={geometry.reset}>Сбросить размеры панелей</Button><label className="block text-sm">Найти блок<Input value={search} onChange={event => setSearch(event.target.value)} /></label>
        </details><Button variant="ghost" onClick={() => choose(metadataNodeId)}>Настройки карты</Button>
        <ul aria-label="Блоки сценария" className="space-y-1">{blocks.filter(item => item.title.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(item => <li key={item.id}><button type="button" className="w-full rounded p-2 text-left text-sm hover:bg-slate-100" aria-pressed={selected === item.id} onClick={() => { choose(item.id); void flow.current?.fitView({ nodes: [{ id: item.id }], maxZoom: 1 }); }}>{item.title}</button></li>)}</ul>
        <h3 className="font-semibold">Точки входа · {entrances.length}</h3>
        {entrances.map(entry => <button className="block w-full break-words rounded p-2 text-left text-xs text-blue-700 hover:bg-blue-50" key={entry.key} onClick={() => choose(entry.target_block_id)}>{entry.title}</button>)}
        {!entrances.length && <p className="text-xs text-slate-500">Совместимый вход: {blocks.find(item => item.id === definition.entry_block_id)?.title ?? "не выбран"}. Добавьте пункты через инспектор блока.</p>}
        </>}
      </aside>
      {geometry.handle("left")}
      <div className="studio-map-main">
      <ScenarioMapGuidance key={definition.scenario_key} definition={definition} onCheck={onCheck} onHint={hint=>{setInspectorTab("settings");setEntranceLink(null);onInspect?.();choose(hint.blockId??metadataNodeId);if((hint.code==="offering"||hint.code==="template")&&!hint.blockId)setBindingFocus(true);if(hint.code==="entry_target"){const entry=entrances.find(item=>item.target_block_id===hint.blockId);if(entry)setEntranceLink({key:entry.key,target:entry.target_block_id});}if(hint.code==="blocks"||hint.code==="result")setStepMenu({source:null});}} />
      {stepMenu && <ScenarioStepMenu inserting={stepMenu.index !== undefined || !!blocks.find(item => item.id === stepMenu.source)?.transitions?.length} onChoose={addContextStep} onClose={() => setStepMenu(null)} />}
      {geometry.measured && <ScenarioMapCanvas definition={definition} disabled={disabled} selected={edge||entranceLink ? "" : selected} selectedEdge={entranceLink?entranceEdgeId(entranceLink.key):edge ? transitionId(edge.source, edge.index) : null} issueBlockId={issueBlockId} path={path} current={current} onReady={instance => { flow.current = instance; }} onSelect={id=>{choose(id);setInspectorTab("settings");onInspect?.();}} onEdge={(source, index) => { choose(source); setEdge({ source, index }); setInspectorTab("settings"); }}
        onAdd={(source,index)=>{setStepMenu({source,index});setError("");setSeparateStep(null);}}
        onEntrance={(key,target)=>{choose(target||metadataNodeId);setEntranceLink(target?{key,target}:null);setInspectorTab("settings");}} onEntranceReconnect={(key,target)=>perform(()=>reconnectStart(definition,key,target))}
        onMove={(id, point) => perform(() => positionBlock(definition, id === metadataNodeId ? "system_start" : id, point))}
        onConnect={(source, target, handle) => perform(() => source===metadataNodeId ? (()=>{const next=connectStart(definition,target);choose(target);setInspectorTab("settings");return next;})() : handle?.startsWith("route-") ? reconnectTransition(definition, source, Number(handle.slice(6)), target) : connectBlocks(definition, source, target))}
        onReconnect={(source, index, target) => perform(() => reconnectTransition(definition, source, index, target))}
        onDropBlock={(value, point, edgeId) => { const kind = mapPalette.find(item => item.kind === value)?.kind; if (!kind) return; const position = flow.current?.screenToFlowPosition(point) ?? point; if(edgeId?.startsWith("studio:")){setError("Связь с началом назначает точку входа. Новый шаг добавьте на карту и соедините обычным переходом.");return;} if (edgeId) { const [source, index] = edgeId.split(":"); setPendingInsert({ kind, source, index: Number(index), position }); } else add(kind, position); }} />}
      </div>
      {geometry.handle("right")}
      <aside className="studio-map-inspector space-y-4" aria-label="Контекстный инспектор">
        {!inspectorPanel && <div role="tablist" aria-label="Режим инспектора" className="flex flex-wrap gap-2">{(["settings","preview"] as const).map(tab=><button key={tab} type="button" role="tab" aria-selected={inspectorTab===tab} className={`rounded px-3 py-2 text-sm ${inspectorTab===tab?"bg-blue-50 font-semibold":"hover:bg-slate-100"}`} onClick={()=>setInspectorTab(tab)}>{tab==="settings"?"Настройки":"Как у сотрудника"}</button>)}</div>}
        {inspectorPanel ? inspectorPanel : inspectorTab==="preview" ? <><p className="text-xs text-slate-500">Оформление текущего черновика. Введённые здесь ответы не сохраняются.</p><ScenarioRequesterPreview key={`${definition.scenario_key}:${block?.id??"empty"}`} definition={definition} block={block??blocks.find(item=>item.id===definition.entry_block_id)??blocks[0]}/><Button variant="outline" onClick={()=>setFullPreview(true)}>Открыть полную страницу</Button></> : entranceLink ? <><h2 className="text-lg font-semibold">Пункт каталога</h2><p>Блок «{blocks.find(item=>item.id===entranceLink.target)?.title}» открывается из этого пункта каталога.</p>{entranceLink.key===null?<><p>Основной вход карты. Отдельный пункт каталога пока не создан.</p><Button disabled={disabled} onClick={()=>perform(()=>connectStart(definition,entranceLink.target))}>Создать пункт каталога для входа</Button><Button disabled={disabled} variant="ghost" onClick={()=>perform(()=>({...definition,entry_block_id:null}))}>Убрать основной вход из черновика</Button></>:<ScenarioEntryInspector definition={definition} blockId={entranceLink.target} catalog={catalog} disabled={disabled} onChange={change}/>}</> : edge ? <ScenarioEdgeInspector key={`${edge.source}:${edge.index}`} definition={definition} source={edge.source} index={edge.index} disabled={disabled} onChange={next => perform(() => next)} /> : !block ? <><h2 className="text-lg font-semibold">Настройки карты</h2><p className="text-xs text-slate-500">Название и раздел карты. Пункты каталога ведут сотрудника к вопросам и инструкциям.</p><label className="block text-sm">Добавить пункт каталога для блока<Select disabled={disabled} value="" onChange={event=>perform(()=>connectStart(definition,event.target.value))}><option value="">Выберите точку входа</option>{blocks.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</Select></label><ScenarioPurpose definition={definition} catalog={catalog} disabled={disabled} existing={existing} onChange={change} focusBinding={bindingFocus} {...categoryProps} /><label className="block text-sm">Основной вход карты<Select disabled={disabled} value={definition.entry_block_id??""} onChange={event=>change({...definition,entry_block_id:event.target.value||null})}><option value="">Выберите начальный блок</option>{blocks.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</Select></label><details open={issuePolicy ? true : undefined}><summary className="cursor-pointer font-semibold">Политики и наследование</summary><ScenarioProcessing definition={definition} disabled={disabled} onChange={change} focusPolicy={issuePolicy} /></details></> : <>
          <h2 className="text-lg font-semibold">{block.title}</h2>
          {definition.entry_block_id===block.id?<p className="text-xs font-semibold text-emerald-700">Начальный шаг маршрута</p>:<Button disabled={disabled} variant="ghost" onClick={()=>change({...definition,entry_block_id:block.id})}>Начать маршрут с этого блока</Button>}
          {terminal(block.kind) && <><label className="block">Действие по завершении<Select disabled={disabled} value={block.kind} onChange={event => change({ ...definition, blocks: blocks.map(item => item.id === block.id ? { id: item.id, title: item.title, kind: event.target.value as "finish" | "submit_ticket", transitions: [], ...(event.target.value === "finish" ? { message: "Проблема решена без обращения" } : {}) } : item) })}><option value="submit_ticket">Создать обращение</option><option value="finish">Завершить без обращения</option></Select></label><p className="text-xs text-slate-500">Привязка типа обращения общая для карты. Приоритет и SLA рассчитывает сервер по собранным ответам.</p></>}
          {block.kind === "submit_ticket" && <><ScenarioResultBinding definition={definition} catalog={catalog} existing={existing} disabled={disabled} onChange={change} onTest={onTest} onCheck={onCheck} /><details><summary>Политики обработки и согласование</summary><ScenarioProcessing definition={definition} disabled={disabled} onChange={change} /></details></>}
          <ScenarioBlockEditor key={block.id} block={block} definition={definition} disabled={disabled} focusTitle={block.id === issueBlockId && !issueTransitions} hideTransitions onChange={next => change({ ...definition, blocks: blocks.map(item => item.id === block.id ? next : item) })} />
          {(block.kind === "decision" || block.kind === "resolution_check") ? <ScenarioBlockRoutes definition={definition} block={block} disabled={disabled} onChange={next=>perform(()=>next)} /> : !terminal(block.kind) && <section className="space-y-2"><h3 className="font-semibold">Переходы</h3>{block.transitions?.map((item, index) => <Button key={index} className="h-auto w-full whitespace-normal" variant="ghost" onClick={() => setEdge({ source: block.id, index })}>{item.when ? "Условие" : "Продолжить"} → {blocks.find(target => target.id === item.to)?.title ?? "Блок не найден"}</Button>)}<label className="block text-sm">Соединить с блоком<Select disabled={disabled} value="" onChange={event => perform(() => connectBlocks(definition, block.id, event.target.value))}><option value="">Выберите следующий шаг</option>{blocks.filter(item => item.id !== block.id).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label></section>}
          <details><summary>Пункты каталога для этого шага</summary><ScenarioEntryInspector definition={definition} blockId={block.id} catalog={catalog} disabled={disabled} onChange={change} /></details>
          <details><summary>Расположение и стабильные параметры</summary><div className="flex gap-2">{(["x", "y"] as const).map(axis => <label key={axis}>{axis.toUpperCase()}<Input disabled={disabled} type="number" value={positions[block.id][axis]} onChange={event => perform(() => positionBlock(definition, block.id, { ...positions[block.id], [axis]: Number(event.target.value) }))} /></label>)}</div></details>
          <div className="flex flex-wrap gap-2"><Button disabled={disabled || blocks.length >= 256} variant="ghost" onClick={() => perform(() => { const next = duplicateBlock(definition, block.id); const copy = next.blocks!.find(item => !blocks.some(old => old.id === item.id))!; choose(copy.id); return positionBlock(next, copy.id, { x: positions[block.id].x + 40, y: positions[block.id].y + 120 }); })}>Копировать блок</Button><Button disabled={disabled} variant="ghost" onClick={() => setRemoving(true)}>Удалить блок</Button></div>

        </>}
      </aside>
    </div>
    {geometry.handle("height")}
    {removing && block && <ScenarioDeleteDialog definition={definition} block={block} disabled={disabled} onClose={()=>setRemoving(false)} onDelete={next=>{change(next);choose(metadataNodeId);}}/>}
    {fullPreview && <ScenarioPagePreview definition={definition} block={blocks.find(item=>item.id===definition.entry_block_id)??block??blocks[0]} onTest={()=>{setFullPreview(false);onTest?.();}} offeringTitle={catalog.offerings.find(item=>item.full_code===definition.offering_full_code)?.public_title??""} onClose={()=>setFullPreview(false)}/>}
  </div>;
}
