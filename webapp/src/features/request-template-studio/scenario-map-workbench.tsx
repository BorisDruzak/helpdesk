import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ReactFlowInstance } from "@xyflow/react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioCatalog } from "./scenario-api";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioPolicyKind } from "./scenario-contract";
import { duplicateBlock, fieldUses } from "./scenario-builder-model";
import { ScenarioBlockEditor } from "./scenario-block-editor";
import { ScenarioPurpose } from "./scenario-purpose";
import { ScenarioProcessing } from "./scenario-processing";
import { ScenarioEntryInspector } from "./scenario-entry-inspector";
import { ScenarioEdgeInspector } from "./scenario-edge-inspector";
import { ScenarioMapCanvas, transitionId, metadataNodeId, type MapNode } from "./scenario-map-canvas";
import { addMapBlock, connectBlocks, deleteMapBlock, insertOnTransition, mapPalette, positionBlock, reconnectTransition, requireAcyclic, terminal } from "./scenario-map-model";
import { useWorkbenchGeometry } from "./scenario-workbench-geometry";
import { ScenarioMapGuidance } from "./scenario-map-guidance";
import { ScenarioWorkbenchCatalog, type WorkbenchCatalogProps } from "./scenario-workbench-catalog";

type Props = { definition: ScenarioDraftDefinition; catalog: ScenarioCatalog; existing: boolean; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void; issueBlockId?: string; issueTransitions?: boolean; issuePolicy?: ScenarioPolicyKind; path?: string[]; current?: string; inspectorPanel?: ReactNode; catalogPanel?: WorkbenchCatalogProps; explorerTab?: "catalog" | "blocks"; onExplorerTab?: (tab: "catalog" | "blocks") => void; onCheck?: () => void; onInspect?: () => void; onCategoryDirty?: (dirty: boolean) => void; onCategoryOpen?: (open: boolean) => void; onCategoryCreated?: () => Promise<void> };
export function ScenarioMapWorkbench({ definition, catalog, existing, disabled, onChange, issueBlockId, issueTransitions, issuePolicy, path, current, inspectorPanel, catalogPanel, explorerTab = "blocks", onExplorerTab, onCheck, onInspect, ...categoryProps }: Props) {
  const [selected, setSelected] = useState(metadataNodeId);
  const [edge, setEdge] = useState<{ source: string; index: number } | null>(null);
  const [search, setSearch] = useState("");
  const [past, setPast] = useState<ScenarioDraftDefinition[]>([]), [future, setFuture] = useState<ScenarioDraftDefinition[]>([]);
  const [error, setError] = useState("");
  const [removing, setRemoving] = useState(false), [replacement, setReplacement] = useState("");
  const [entranceAction, setEntranceAction] = useState<"remove" | "reassign" | "">("");
  const [pendingInsert, setPendingInsert] = useState<{ kind: ScenarioBlock["kind"]; source: string; index: number; position: { x: number; y: number } } | null>(null);
  const flow = useRef<ReactFlowInstance<MapNode> | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const geometry = useWorkbenchGeometry(gridRef);
  const emitted = useRef(definition);
  const blocks = definition.blocks ?? [];
  const block = blocks.find(item => item.id === selected);
  useEffect(() => { if (issueBlockId) { setSelected(issueBlockId); setEdge(issueTransitions && definition.blocks?.find(item => item.id === issueBlockId)?.transitions?.length ? { source: issueBlockId, index: 0 } : null); } else if (issuePolicy) { setSelected(metadataNodeId); setEdge(null); } }, [issueBlockId, issueTransitions, issuePolicy]);
  useEffect(() => { if (emitted.current.scenario_key !== definition.scenario_key) { setPast([]); setFuture([]); setSelected(metadataNodeId); setEdge(null); setPendingInsert(null); setRemoving(false); setError(""); } emitted.current = definition; }, [definition]);
  function choose(id: string) { setSelected(id); setEdge(null); setRemoving(false); setError(""); }
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
    perform(() => { const next = addMapBlock(definition, kind, position); const id = next.blocks![next.blocks!.length - 1].id; choose(id); requestAnimationFrame(() => void flow.current?.fitView({ nodes: [{ id }], maxZoom: 1 })); return next; });
  }
  const entrances = definition.entry_points ?? [];
  const linkedEntries = entrances.filter(entry => entry.target_block_id === selected);
  return <div className="min-w-0 space-y-3" onKeyDown={event => {
    if ((event.ctrlKey || event.metaKey) && !/INPUT|TEXTAREA|SELECT/.test((event.target as HTMLElement).tagName)) {
      if (event.key.toLowerCase() === "z") { event.preventDefault(); history(event.shiftKey); }
      if (event.key.toLowerCase() === "y") { event.preventDefault(); history(true); }
    }
  }}>
    <div className="flex flex-wrap gap-2"><Button disabled={disabled || !past.length} variant="ghost" onClick={() => history(false)}>Отменить изменение</Button><Button disabled={disabled || !future.length} variant="ghost" onClick={() => history(true)}>Повторить изменение</Button><Button variant="ghost" onClick={() => void flow.current?.fitView({ padding: 0.2 })}>Вся карта</Button><Button variant="ghost" onClick={geometry.reset}>Сбросить размеры панелей</Button><p className="self-center text-xs text-slate-500">Связи определяют маршрут. Границы панелей можно перетаскивать.</p></div>
    {error && <p role="alert" className="rounded border border-amber-300 bg-amber-50 p-3">{error}</p>}
    {pendingInsert && <div className="rounded border p-3"><p>Вставить новый блок между выбранными шагами, сохранив условие?</p><Button disabled={disabled} onClick={() => { perform(() => insertOnTransition(definition, pendingInsert.source, pendingInsert.index, pendingInsert.kind, pendingInsert.position)); setPendingInsert(null); }}>Вставить между шагами</Button><Button variant="ghost" onClick={() => setPendingInsert(null)}>Отмена вставки</Button></div>}
    <div ref={gridRef} className="studio-map-workbench" style={geometry.style}>
      <aside className="studio-map-explorer space-y-4" aria-label="Библиотека блоков">
        {catalogPanel && <div role="tablist" aria-label="Содержимое левой панели" className="flex gap-1">{(["catalog", "blocks"] as const).map(tab=><button key={tab} type="button" role="tab" aria-selected={explorerTab===tab} className={`rounded px-3 py-2 text-sm ${explorerTab===tab?"bg-blue-50 font-semibold":"hover:bg-slate-100"}`} onClick={()=>onExplorerTab?.(tab)}>{tab==="catalog"?"Каталог":"Блоки"}</button>)}</div>}
        {catalogPanel && explorerTab === "catalog" ? <ScenarioWorkbenchCatalog {...catalogPanel} /> : <>
        <h3 className="font-semibold">Блоки</h3>
        <div className="space-y-1">{mapPalette.map(item => <button key={item.kind} type="button" className="w-full rounded-lg border px-3 py-2 text-left text-sm hover:bg-blue-50 disabled:opacity-50" disabled={disabled || blocks.length >= 256} draggable={!disabled} onDragStart={event => event.dataTransfer.setData("application/x-scenario-kind", item.kind)} onClick={() => add(item.kind)}>+ {item.label}</button>)}</div>
        <label className="block text-sm">Найти блок<Input value={search} onChange={event => setSearch(event.target.value)} /></label>
        <Button variant="ghost" onClick={() => choose(metadataNodeId)}>Начало</Button>
        <ul aria-label="Блоки сценария" className="space-y-1">{blocks.filter(item => item.title.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(item => <li key={item.id}><button type="button" className="w-full rounded p-2 text-left text-sm hover:bg-slate-100" aria-pressed={selected === item.id} onClick={() => { choose(item.id); void flow.current?.fitView({ nodes: [{ id: item.id }], maxZoom: 1 }); }}>{item.title}</button></li>)}</ul>
        <h3 className="font-semibold">Точки входа · {entrances.length}</h3>
        {entrances.map(entry => <button className="block w-full break-words rounded p-2 text-left text-xs text-blue-700 hover:bg-blue-50" key={entry.key} onClick={() => choose(entry.target_block_id)}>{entry.title}</button>)}
        {!entrances.length && <p className="text-xs text-slate-500">Совместимый вход: {blocks.find(item => item.id === definition.entry_block_id)?.title ?? "не выбран"}. Добавьте пункты через инспектор блока.</p>}
        </>}
      </aside>
      {geometry.handle("left")}
      <div className="studio-map-main">
      <ScenarioMapGuidance key={definition.scenario_key} definition={definition} onCheck={onCheck} onHint={hint=>{onInspect?.();if(hint.target)onExplorerTab?.(hint.target);else choose(hint.blockId??metadataNodeId);}} />
      <ScenarioMapCanvas definition={definition} disabled={disabled} selected={edge ? "" : selected} selectedEdge={edge ? transitionId(edge.source, edge.index) : null} issueBlockId={issueBlockId} path={path} current={current} onReady={instance => { flow.current = instance; }} onSelect={choose} onEdge={(source, index) => { setEdge({ source, index }); setRemoving(false); }}
        onMove={(id, point) => perform(() => positionBlock(definition, id === metadataNodeId ? "system_start" : id, point))}
        onConnect={(source, target, handle) => perform(() => handle?.startsWith("route-") ? reconnectTransition(definition, source, Number(handle.slice(6)), target) : connectBlocks(definition, source, target))}
        onReconnect={(source, index, target) => perform(() => reconnectTransition(definition, source, index, target))}
        onDropBlock={(value, point, edgeId) => { const kind = mapPalette.find(item => item.kind === value)?.kind; if (!kind) return; const position = flow.current?.screenToFlowPosition(point) ?? point; if (edgeId) { const [source, index] = edgeId.split(":"); setPendingInsert({ kind, source, index: Number(index), position }); } else add(kind, position); }} />
      </div>
      {geometry.handle("right")}
      <aside className="studio-map-inspector space-y-4" aria-label="Контекстный инспектор">
        {inspectorPanel ? inspectorPanel : edge ? <ScenarioEdgeInspector key={`${edge.source}:${edge.index}`} definition={definition} source={edge.source} index={edge.index} disabled={disabled} onChange={next => perform(() => next)} /> : !block ? <><h2 className="text-lg font-semibold">Начало</h2><p className="text-xs text-slate-500">Общие настройки карты. Системный элемент не исполняется и не удаляется.</p><ScenarioPurpose definition={definition} catalog={catalog} disabled={disabled} existing={existing} onChange={change} {...categoryProps} /><label className="block text-sm">Основной вход карты<Select disabled={disabled} value={definition.entry_block_id??""} onChange={event=>change({...definition,entry_block_id:event.target.value||null})}><option value="">Выберите начальный блок</option>{blocks.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</Select></label><details open={issuePolicy ? true : undefined}><summary className="cursor-pointer font-semibold">Политики и наследование</summary><ScenarioProcessing definition={definition} disabled={disabled} onChange={change} focusPolicy={issuePolicy} /></details></> : <>
          <h2 className="text-lg font-semibold">{block.title}</h2>
          {terminal(block.kind) && <><label className="block">Режим результата<Select disabled={disabled} value={block.kind} onChange={event => change({ ...definition, blocks: blocks.map(item => item.id === block.id ? { id: item.id, title: item.title, kind: event.target.value as "finish" | "submit_ticket", transitions: [], ...(event.target.value === "finish" ? { message: "Проблема решена без обращения" } : {}) } : item) })}><option value="submit_ticket">Создать обращение</option><option value="finish">Завершить без обращения</option></Select></label><p className="text-xs text-slate-500">Общий контекст услуги и шаблона. Приоритет и SLA рассчитывает сервер по собранным ответам.</p></>}
          {block.kind === "submit_ticket" && <details><summary>Политики обработки и согласование</summary><ScenarioProcessing definition={definition} disabled={disabled} onChange={change} /></details>}
          <ScenarioBlockEditor key={block.id} block={block} definition={definition} disabled={disabled} focusTitle={block.id === issueBlockId && !issueTransitions} hideTransitions onChange={next => change({ ...definition, blocks: blocks.map(item => item.id === block.id ? next : item) })} />
          {!terminal(block.kind) && <section className="space-y-2"><h3 className="font-semibold">Переходы</h3>{block.transitions?.map((item, index) => <Button key={index} className="h-auto w-full whitespace-normal" variant="ghost" onClick={() => setEdge({ source: block.id, index })}>{item.when ? "Условие" : "Продолжить"} → {blocks.find(target => target.id === item.to)?.title ?? "Блок не найден"}</Button>)}<label className="block text-sm">Соединить с блоком<Select disabled={disabled} value="" onChange={event => perform(() => connectBlocks(definition, block.id, event.target.value))}><option value="">Выберите следующий шаг</option>{blocks.filter(item => item.id !== block.id).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label></section>}
          <ScenarioEntryInspector definition={definition} blockId={block.id} catalog={catalog} disabled={disabled} onChange={change} />
          <details><summary>Расположение и стабильные параметры</summary><div className="flex gap-2">{(["x", "y"] as const).map(axis => <label key={axis}>{axis.toUpperCase()}<Input disabled={disabled} type="number" value={definition.editor_layout?.positions?.[block.id]?.[axis] ?? 0} onChange={event => perform(() => positionBlock(definition, block.id, { ...definition.editor_layout?.positions?.[block.id] ?? { x: 0, y: 0 }, [axis]: Number(event.target.value) }))} /></label>)}</div></details>
          <div className="flex flex-wrap gap-2"><Button disabled={disabled || blocks.length >= 256} variant="ghost" onClick={() => perform(() => { const next = duplicateBlock(definition, block.id); const copy = next.blocks!.find(item => !blocks.some(old => old.id === item.id))!; choose(copy.id); return positionBlock(next, copy.id, { x: (definition.editor_layout?.positions?.[block.id]?.x ?? 0) + 40, y: (definition.editor_layout?.positions?.[block.id]?.y ?? 0) + 120 }); })}>Копировать блок</Button><Button disabled={disabled} variant="ghost" onClick={() => { setRemoving(true); setReplacement(""); setEntranceAction(""); }}>Удалить блок</Button></div>
          {removing && <fieldset disabled={disabled} className="space-y-3 rounded border border-amber-300 p-3"><legend>Удаление блока</legend><p className="text-sm">Входящие связи: {blocks.filter(item => item.transitions?.some(t => t.to === block.id)).map(item => item.title).join(", ") || "нет"}. Исходящие: {block.transitions?.length ?? 0}. Точки входа: {linkedEntries.map(entry => entry.title).join(", ") || "нет"}.</p>{block.kind === "form_page" && <p>{block.fields.flatMap(field => fieldUses(definition, field.key, block.id)).join("; ")}</p>}<label>Перенаправить на<Select value={replacement} onChange={event => setReplacement(event.target.value)}><option value="">Выберите блок</option>{blocks.filter(item => item.id !== block.id).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</Select></label>{!!linkedEntries.length && <label>Привязанные точки входа<Select value={entranceAction} onChange={event => setEntranceAction(event.target.value as typeof entranceAction)}><option value="">Выберите явное действие</option><option value="reassign">Переназначить выбранному блоку</option><option value="remove">Убрать из черновика</option></Select></label>}<Button onClick={() => perform(() => { const next = deleteMapBlock(definition, block.id, replacement || null, entranceAction || undefined); choose(metadataNodeId); return next; })}>Подтвердить удаление блока</Button><Button variant="ghost" onClick={() => setRemoving(false)}>Отмена удаления</Button></fieldset>}
        </>}
      </aside>
    </div>
    {geometry.handle("height")}
  </div>;
}
