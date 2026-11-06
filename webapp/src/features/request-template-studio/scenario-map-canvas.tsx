import { ScenarioMapLinkCard, type MapLinkCard } from "./scenario-map-link-card";
import { entranceLayoutKey, routeLayoutKey, useMapLinkLayout } from "./scenario-map-link-layout";
import { ScenarioResizableEditor } from "./scenario-editor-size";
import { conditionFields, fieldLabels } from "./scenario-builder-model";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, useNodesState, useUpdateNodeInternals, type Edge, type Node, type NodeProps, type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ScenarioCondition, ScenarioDraftDefinition } from "./scenario-contract";
import { catalogEntranceSourceId, mapKindLabel, stableMapPositions, terminal } from "./scenario-map-model";
import "./scenario-map.css";
import { ScenarioMapEdge } from "./scenario-map-edge";
import { scenarioMapHints } from "./scenario-map-hints";
import { isPolicyAttachment } from "./scenario-policy-attachments-model";
import type { ScenarioSimulation } from "./scenario-api";
import { terminalActualSla, terminalSlaSummary } from "./scenario-terminal-sla-model";
import { answerBranchChoices, defaultAnswerBranchField, findAnswerBranch } from "./scenario-answer-branches";
import { conditionSummary } from "./scenario-condition-summary";

type AnswerRow = { key: string; label: string; transitionIndex: number; targetTitle?: string; add?: () => void };
type MapData = { link?: MapLinkCard; shiftOrigin?: (delta: {x:number;y:number},commit:boolean)=>void; policyAttachment?: boolean; terminalPath?: string[]; terminalSummary?: string; startActions?: { label: string; run: () => void }[]; fitEditor?: () => void; preferenceKey?: string; getZoom?: () => number; buttonLabels?: string[]; auxiliary?: boolean; editor?: ReactNode; edit?: () => void; expanded?: boolean; title: string; subtitle: string; entries: string[]; transitions: number; terminal: boolean; system: boolean; issue: boolean; current: boolean; visited: boolean; entrance?: boolean; hint?: string; add?: () => void; answerFieldLabel?: string; answerBranches?: AnswerRow[]; moreAnswerBranches?: boolean };
export type MapNode = Node<MapData, "scenario">;
export const metadataNodeId = catalogEntranceSourceId;
export const entranceEdgeId = (key: string | null) => key === null ? "studio:primary" : `studio:entry-point:${encodeURIComponent(key)}`;
function MapBlock({ id, data, selected }: NodeProps<MapNode>) {
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => { updateNodeInternals(id); }, [id, data.transitions, data.terminal, data.answerBranches, data.expanded, data.editor, updateNodeInternals]);
  if (data.link) return <ScenarioMapLinkCard link={data.link} selected={selected} editor={data.editor} preferenceKey={data.preferenceKey ?? id} getZoom={data.getZoom} onOriginChange={data.shiftOrigin} onResize={() => updateNodeInternals(id)} onMinimumFit={data.fitEditor}/>;
  const answerRoutes = new Set(data.answerBranches?.map(row => row.transitionIndex).filter(index => index >= 0));
  const otherRoutes = Array.from({ length: data.transitions }, (_, index) => index).filter(index => !answerRoutes.has(index));
  return <div onDoubleClick={event => { event.stopPropagation(); data.edit?.(); }} className={`studio-map-node ${data.expanded ? "is-expanded" : ""} ${selected ? "is-selected" : ""} ${data.system ? "is-system" : ""} ${data.issue ? "has-issue" : ""} ${data.current ? "is-current" : ""} ${data.visited ? "is-visited" : ""}`}>
    {!data.system && !data.entrance && !data.policyAttachment && <Handle type="target" isConnectable={!data.auxiliary} position={Position.Left} aria-label={`Вход блока «${data.title}»`} title="Перетащите сюда связь другого блока" />}
    {data.policyAttachment && <Handle id="policy" type="source" position={Position.Right} aria-label={`Подключить настройку «${data.title}» к блоку`} />}
    {data.entrance && <Handle type="source" position={Position.Bottom} aria-label={`Начало «${data.title}»: соединить с первым шагом`} />}
    {data.system && <Handle id="entrance" type="source" position={Position.Right} aria-label="Начало: создать связь с точкой входа" />}
    <div className="studio-map-node__kind">{data.subtitle}</div><strong>{data.title}</strong>
    {data.edit && <button type="button" className="studio-node-edit nodrag nopan" onClick={event => { event.stopPropagation(); data.edit?.(); }}>{data.expanded ? "Свернуть редактор" : "Редактировать"}</button>}
    {data.startActions && <div className="space-y-1 border-t pt-2" aria-label="Подпункты начала">{data.startActions.map(action => <button key={action.label} type="button" className="studio-node-edit nodrag nopan" aria-label={`Начало: ${action.label}`} onClick={event => { event.stopPropagation(); action.run(); }}>{action.label}</button>)}</div>}
    {data.editor && <ScenarioResizableEditor key={data.preferenceKey} preferenceKey={data.preferenceKey ?? id} label="Изменить размер редактора блока" getZoom={data.getZoom} onOriginChange={data.shiftOrigin} onMinimumFit={data.fitEditor} onResize={() => updateNodeInternals(id)}><div className="studio-inline-editor nopan nowheel" onClick={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()} onKeyDown={event => event.stopPropagation()}>{data.editor}</div></ScenarioResizableEditor>}
    {!!data.buttonLabels?.length && <div className="studio-node-buttons" aria-label="Кнопки сотрудника">{data.buttonLabels.map((label, index) => <span key={index}>{label}</span>)}</div>}
    {data.entries.map((title, index) => <span key={index} className="studio-map-node__entry">↳ {title}</span>)}
    {data.terminalSummary && <span className="studio-map-node__entry break-words" aria-label="Итог завершения">{data.terminalSummary}</span>}
    {data.terminalPath && <details className="nodrag nopan text-xs"><summary className="cursor-pointer">Пройденный маршрут</summary><p className="break-words">{data.terminalPath.join(" → ")}</p></details>}
    {data.hint && <span className="studio-map-node__hint">{data.hint}</span>}
    {!!data.answerBranches?.length && <div className="studio-node-answers">
      <span className="studio-node-answers__source" title={data.answerFieldLabel}>По ответу: {data.answerFieldLabel}</span>
      {data.answerBranches.map((row, index) => <div key={row.key} className="studio-node-answer">
        <span className="studio-node-answer__label" title={row.label}>{row.label}</span>
        {row.transitionIndex >= 0 ? <span className="studio-node-answer__target" title={row.targetTitle}>→ {row.targetTitle}</span> : <button type="button" disabled={!row.add} className="studio-node-answer__add nodrag nopan" aria-label={`Добавить шаг для «${row.label}» после «${data.title}»`} onClick={event => { event.stopPropagation(); row.add?.(); }}>+ Шаг</button>}
        <Handle id={row.transitionIndex >= 0 ? `route-${row.transitionIndex}` : `answer-${index}`} type="source" position={Position.Right} aria-label={`Ветка «${row.label}» блока «${data.title}»`} />
      </div>)}
      {data.moreAnswerBranches && <span className="studio-node-answers__more">Другие варианты — в настройках блока</span>}
    </div>}
    {data.add && <button type="button" className="studio-node-add nodrag nopan" aria-label={`Добавить следующий шаг после «${data.title}»`} onClick={event => { event.stopPropagation(); data.add?.(); }}>+ Добавить следующий шаг</button>}
    {!data.system && !data.terminal && !data.policyAttachment && <><Handle id="new" type="source" position={Position.Right} className="studio-handle-new" aria-label={`Соединить «${data.title}» с другим блоком`} title="Перетащите к входу другого блока" style={{ top: 20 }} />{!!data.answerBranches?.length ? <div className="studio-node-other-routes" style={{ height: otherRoutes.length * 16 }}>{otherRoutes.map((routeIndex, index) => <Handle key={routeIndex} id={`route-${routeIndex}`} type="source" position={Position.Right} style={{ top: 8 + index * 16 }} />)}</div> : otherRoutes.map(index => <Handle key={index} id={`route-${index}`} type="source" position={Position.Right} style={{ top: 45 + index * 13 }} />)}</>}
  </div>;
}
const nodeTypes = { scenario: MapBlock };
const edgeTypes = { scenario: ScenarioMapEdge };
const emptyPath: string[] = [];
const emptyAuxiliary: Record<string, ReactNode> = {};
export const transitionCardId = (source: string, index: number) => `studio:link:route:${encodeURIComponent(source)}:${index}`;
export const entranceCardId = (key: string | null) => key === null ? "studio:link:entry:implicit" : `studio:link:entry:named:${encodeURIComponent(key)}`;
export const transitionId = (source: string, index: number) => `${source}:${index}`;
export function ScenarioMapCanvas({ edgeEditor, entranceEditor, simulationResult, definition, selected, selectedEdge, disabled, issueBlockId, path = emptyPath, current, onSelect, onEdge, onMove, onConnect, onReconnect, onDropBlock, onReady, onEntrance, onEntranceReconnect, onEntranceTitle, onAdd, answerSources, onAnswerAdd, auxiliaryEditors = emptyAuxiliary, expandedId, inlineEditor, onEdit, onContext, onButtonTitle, onStartSection }: {
  edgeEditor?: ReactNode; entranceEditor?: ReactNode;
  simulationResult?: ScenarioSimulation;
  onStartSection?: (section: "service" | "catalog" | "entries" | "processing") => void;
  auxiliaryEditors?: Record<string, ReactNode>; expandedId?: string | null; inlineEditor?: ReactNode; onEdit?: (id: string) => void; onContext?: (point: { x: number; y: number }, nodeId?: string, edgeId?: string) => void;
  definition: ScenarioDraftDefinition; selected: string; selectedEdge: string | null; disabled: boolean; issueBlockId?: string; path?: string[]; current?: string;
  onSelect: (id: string) => void; onEdge: (source: string, index: number) => void;
  onMove: (id: string, position: { x: number; y: number }) => void;
  onConnect: (source: string, target: string, handle: string | null) => void;
  onReconnect: (source: string, index: number, target: string) => void;
  onDropBlock: (kind: string, point: { x: number; y: number }, edgeId?: string) => void;
  onEntrance: (key: string | null, target: string) => void;
  onEntranceReconnect: (key: string | null, target: string) => void;
  onReady: (instance: ReactFlowInstance<MapNode>) => void;
  onButtonTitle?: (source: string, index: number, title: string) => void;
  onEntranceTitle?: (key:string,title:string)=>void;
  onAdd?: (source: string | null, index?: number) => void;
  answerSources?: Record<string, string>;
  onAnswerAdd?: (source: string, when: ScenarioCondition) => void;
}) {
  const [viewportZoom, setViewportZoom] = useState(1);
  const linkLayout = useMapLinkLayout(definition.scenario_key);
  function fitEditor(id: string) {
    requestAnimationFrame(() => requestAnimationFrame(() => void flow.current?.fitView({ nodes: [{ id }], minZoom: 0.15, maxZoom: 1, padding: .12, duration: 150 })));
  }
  const hints = scenarioMapHints(definition);
  const positions = stableMapPositions(definition);
  const entrances = [...(definition.entry_points ?? []).map(entry => ({ key: entry.key as string | null, title: entry.title, target: entry.target_block_id, enabled: entry.enabled !== false })), ...(!definition.entry_points?.some(entry => entry.target_block_id === definition.entry_block_id) ? [{ key: null, title: "Начало маршрута", target: definition.entry_block_id ?? "", enabled: true }] : [])];
  const baseInitial = useMemo<MapNode[]>(() => [{ id: metadataNodeId, type: "scenario", position: definition.editor_layout?.positions?.system_start ?? { x: -320, y: 0 }, selected: selected === metadataNodeId, data: { shiftOrigin: (delta,commit)=>shiftOrigin(metadataNodeId,delta,commit), fitEditor: () => fitEditor(metadataNodeId), preferenceKey: `${definition.scenario_key}:system_start:inline`, getZoom: () => flow.current?.getZoom() ?? 1, expanded: expandedId === metadataNodeId, editor: expandedId === metadataNodeId ? inlineEditor : undefined, edit: onEdit ? () => onEdit(metadataNodeId) : undefined, title: "Начало", subtitle: "Услуга и точки входа", startActions: onStartSection ? ([ ["service", "Услуга и описание"], ["catalog", "Раздел и категория"], ["entries", "Входы в каталог"], ["processing", "Обработка и SLA"] ] as const).map(([section,label]) => ({ label, run: () => onStartSection(section) })) : undefined, entries: [], transitions: 0, terminal: true, system: true, issue: false, current: false, visited: false } }, ...(definition.blocks ?? []).map((block): MapNode => {
    const field = block.kind === "decision" ? defaultAnswerBranchField(definition, block.id, answerSources?.[block.id]) : undefined;
    const choices = field ? answerBranchChoices(field) : [];
    const answerBranches: AnswerRow[] = choices.slice(0, 6).map(choice => {
      const transitionIndex = findAnswerBranch(block, choice.when);
      return { key: choice.key, label: choice.label, transitionIndex, targetTitle: transitionIndex < 0 ? undefined : definition.blocks?.find(item => item.id === block.transitions?.[transitionIndex]?.to)?.title ?? "Шаг недоступен", add: !disabled && onAnswerAdd ? () => onAnswerAdd(block.id, choice.when) : undefined };
    });
    return {
    id: block.id, type: "scenario", position: positions[block.id], selected: selected === block.id,
    data: { shiftOrigin: (delta,commit)=>shiftOrigin(block.id,delta,commit), policyAttachment: isPolicyAttachment(block), terminalPath: terminalActualSla(definition, block, simulationResult)?.route, terminalSummary: terminal(block.kind) ? terminalSlaSummary(definition, block, simulationResult) : undefined, fitEditor: () => fitEditor(block.id), preferenceKey: `${definition.scenario_key}:${block.id}:inline`, getZoom: () => flow.current?.getZoom() ?? 1, buttonLabels: block.transition_mode === "buttons" || block.kind === "navigation" ? block.transitions?.map(edge => edge.button?.label ?? "Кнопка без названия") : undefined, expanded: expandedId === block.id, editor: expandedId === block.id ? inlineEditor : undefined, edit: onEdit ? () => onEdit(block.id) : undefined, title: block.kind === "form_page" && block.fields.length === 1 ? block.fields[0].label : block.title, subtitle: block.kind === "form_page" && block.fields.length === 1 ? `Вопрос · ${fieldLabels[block.fields[0].type]}` : mapKindLabel(block.kind), entries: [], transitions: block.transitions?.length ?? 0, terminal: terminal(block.kind), system: false, issue: issueBlockId === block.id || hints.some(hint => hint.blockId === block.id && hint.level === "required"), hint: hints.find(hint => hint.blockId === block.id)?.text, current: current === block.id, visited: path.includes(block.id), add: !disabled && !terminal(block.kind) && !isPolicyAttachment(block) && onAdd ? () => onAdd(block.id) : undefined, answerFieldLabel: field?.label, answerBranches, moreAnswerBranches: choices.length > 6 },
  }; })], [definition, selected, selectedEdge, issueBlockId, path, current, disabled, onAdd, answerSources, onAnswerAdd, auxiliaryEditors, expandedId, inlineEditor, onEdit, viewportZoom, onStartSection, simulationResult]);
  const auxiliaryNodes = useMemo<MapNode[]>(() => Object.entries(auxiliaryEditors).map(([source, content]) => ({ id: `studio:legacy-sla:${source}`, type: "scenario", position: { x: (positions[source]?.x ?? 0) + 320, y: (positions[source]?.y ?? 0) + 70 }, draggable: false, selected: selected === `studio:legacy-sla:${source}`, data: { fitEditor: () => fitEditor(`studio:legacy-sla:${source}`), preferenceKey: `${definition.scenario_key}:legacy-sla:${source}:inline`, getZoom: () => flow.current?.getZoom() ?? 1, auxiliary: true, title: "SLA по ответам и ветвям", subtitle: "Действующие правила", entries: [], transitions: 0, terminal: true, system: false, issue: false, current: false, visited: false, expanded: expandedId === `studio:legacy-sla:${source}`, editor: expandedId === `studio:legacy-sla:${source}` ? content : undefined, edit: onEdit ? () => onEdit(`studio:legacy-sla:${source}`) : undefined } })), [auxiliaryEditors, definition, selected, expandedId, onEdit, viewportZoom]);
  const linkNodes = useMemo<MapNode[]>(() => {
    const occupied = [...baseInitial, ...auxiliaryNodes].map(node => node.position);
    function placement(key: string, source: string, target: string, index: number) {
      const saved = linkLayout.positions[key]; if (saved) { occupied.push(saved); return saved; }
      const from = source === metadataNodeId ? definition.editor_layout?.positions?.system_start ?? {x:-320,y:0} : positions[source] ?? {x:0,y:0};
      const to = positions[target] ?? {x:from.x+600,y:from.y};
      const preferred={x:(from.x+to.x)/2,y:(from.y+to.y)/2+140+index*70};
      for(let ring=0;ring<=15;ring++)for(let dx=-ring;dx<=ring;dx++)for(let dy=-ring;dy<=ring;dy++){
        if(Math.max(Math.abs(dx),Math.abs(dy))!==ring)continue;
        const point={x:preferred.x+dx*280,y:preferred.y+dy*170};
        if(occupied.every(old=>Math.abs(old.x-point.x)>=260||Math.abs(old.y-point.y)>=150)){occupied.push(point);return point;}
      }
      occupied.push(preferred);return preferred;
    }
    function node(id: string, link: MapLinkCard): MapNode {
      const expanded=selectedEdge===link.edgeId;
      return {id,type:"scenario",position:placement(link.positionKey,link.route?.source??metadataNodeId,link.route?definition.blocks?.find(block=>block.id===link.route!.source)?.transitions?.[link.route.index]?.to??"":link.entrance!.target,link.route?.index??0),selected:expanded,data:{link,title:link.title,subtitle:link.entrance?"Вход из каталога":"Переход",entries:[],transitions:0,terminal:true,system:false,issue:false,current:false,visited:false,expanded,editor:expanded?(link.entrance?entranceEditor:edgeEditor):undefined,preferenceKey:`${definition.scenario_key}:link:${link.positionKey}:inline`,getZoom:()=>flow.current?.getZoom()??1,shiftOrigin:(delta,commit)=>shiftOrigin(id,delta,commit),fitEditor:()=>fitEditor(id)}};
    }
    const routes=(definition.blocks??[]).flatMap(block=>{
      const occurrences=new Map<string,number>();
      return(block.transitions??[]).map((edge,index)=>{
        const signature=routeLayoutKey(block.id,edge),occurrence=occurrences.get(signature)??0;occurrences.set(signature,occurrence+1);
        const targetTitle=definition.blocks?.find(target=>target.id===edge.to)?.title??"Следующий шаг";
        const title=edge.button?.label||(edge.when?conditionSummary(edge.when,conditionFields(definition,block.id)):block.kind==="resolution_check"?"Не знаю / иначе":block.kind==="decision"?"Иначе":`Продолжить → ${targetTitle}`);
        return node(transitionCardId(block.id,index),{edgeId:transitionId(block.id,index),positionKey:routeLayoutKey(block.id,edge,occurrence),title,targetTitle,context:`${block.title} → ${targetTitle}`,route:{source:block.id,index},disabled,select:()=>onEdge(block.id,index),rename:definition.schema_version===4&&edge.button&&!disabled&&onButtonTitle?title=>onButtonTitle(block.id,index,title):undefined,add:!disabled&&onAdd?()=>onAdd(block.id,index):undefined,addLabel:`Добавить шаг между «${block.title}» и «${targetTitle}»`});
      });
    });
    return [...routes,...entrances.filter(entry=>entry.target&&definition.blocks?.some(block=>block.id===entry.target)).map(entry=>node(entranceCardId(entry.key),{edgeId:entranceEdgeId(entry.key),positionKey:entranceLayoutKey(entry.key),title:entry.title,targetTitle:definition.blocks?.find(block=>block.id===entry.target)?.title??"Шаг недоступен",context:"Начало → вход из каталога",entrance:{key:entry.key,target:entry.target},disabled,select:()=>onEntrance(entry.key,entry.target),rename:entry.key!==null&&!disabled&&onEntranceTitle?title=>onEntranceTitle(entry.key!,title):undefined}))];
  },[definition,baseInitial,auxiliaryNodes,selectedEdge,edgeEditor,entranceEditor,disabled,onEdge,onEntrance,onButtonTitle,onEntranceTitle,onAdd,linkLayout.positions,viewportZoom]);
  const initial = useMemo(() => [...baseInitial, ...auxiliaryNodes, ...linkNodes], [baseInitial, auxiliaryNodes, linkNodes]);
  const [nodes, setNodes, onNodesChange] = useNodesState<MapNode>(initial);
  const dragging = useRef(false);
  const flow = useRef<ReactFlowInstance<MapNode> | null>(null);
  // A link editor changes its native node's dimensions just like a block editor.
  // Depend on identity, not editor content, so typing never keeps recentering the map.
  const expandedMapId = linkNodes.find(node => node.data.editor)?.id ?? expandedId;
  useEffect(() => {
    if (!expandedMapId) return;
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => void flow.current?.fitView({ nodes: [{ id: expandedMapId }], minZoom: 0.15, maxZoom: 1, padding: .12, duration: 150 })); });
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); };
  }, [expandedMapId]);
  const resizeOrigins = useRef<Record<string,{x:number;y:number}>>({});
  function shiftOrigin(id:string,delta:{x:number;y:number},commit:boolean) {
    const origin=resizeOrigins.current[id]??nodes.find(node=>node.id===id)?.position;
    if(!origin || disabled)return;
    resizeOrigins.current[id]=origin;
    const position={x:origin.x+delta.x,y:origin.y+delta.y};
    setNodes(previous=>previous.map(node=>node.id===id?{...node,position}:node));
    if(commit){delete resizeOrigins.current[id];persistPosition(id,position);}
  }
  function persistPosition(id:string,point:{x:number;y:number}){
    const link=nodes.find(node=>node.id===id)?.data.link;
    if(link)linkLayout.move(link.positionKey,point);else onMove(id,point);
  }
  const previousCount = useRef(definition.blocks?.length ?? 0);
  useEffect(() => { const count = definition.blocks?.length ?? 0; const firstStep = previousCount.current === 0 && count > 0; previousCount.current = count; if (firstStep) { const frame = requestAnimationFrame(() => void flow.current?.fitView({ padding: 0.18, maxZoom: 1 })); return () => cancelAnimationFrame(frame); } }, [definition.blocks?.length]);
  useEffect(() => setNodes(previous => initial.map(node => { const old = previous.find(item => item.id === node.id); return { ...node, measured: old?.measured, ...((dragging.current || resizeOrigins.current[node.id]) && old ? { position: old.position, dragging: old.dragging } : {}) }; })), [initial, setNodes]);
  const routeEdges: Edge[] = (definition.blocks??[]).flatMap(block=>(block.transitions??[]).flatMap((edge,index)=>{
    const id=transitionId(block.id,index),card=transitionCardId(block.id,index),selected=selectedEdge===id;
    const style={stroke:selected?"#087443":"#94a3b8",strokeWidth:2};
    const data={route:{source:block.id,index}};
    return [{id:`${id}:input`,source:block.id,sourceHandle:`route-${index}`,target:card,targetHandle:"in",type:"smoothstep",reconnectable:false,selectable:false,data,style},{id,source:card,sourceHandle:"out",target:edge.to,type:"smoothstep",reconnectable:"target" as const,selected,data,markerEnd:{type:MarkerType.ArrowClosed},style}];
  }));
  const entranceEdges: Edge[] = entrances.filter(entry=>entry.target&&nodes.some(node=>node.id===entry.target)).flatMap(entry=>{
    const id=entranceEdgeId(entry.key),card=entranceCardId(entry.key),data={entrance:true,key:entry.key,target:entry.target},style={stroke:"#0d9488",strokeWidth:2,strokeDasharray:"6 4",opacity:entry.enabled?1:.45};
    return [{id:`${id}:input`,source:metadataNodeId,sourceHandle:"entrance",target:card,targetHandle:"in",type:"smoothstep",reconnectable:false,selectable:false,data,style},{id,source:card,sourceHandle:"out",target:entry.target,type:"smoothstep",reconnectable:"target" as const,data,selected:selectedEdge===id,markerEnd:{type:MarkerType.ArrowClosed},style}];
  });
  const attachmentEdges: Edge[] = (definition.blocks ?? []).filter(isPolicyAttachment).flatMap(block => block.attached_to && nodes.some(node=>node.id===block.attached_to) ? [{ id: `studio:attachment:${block.id}`, source: block.id, sourceHandle:"policy", target:block.attached_to, type:"smoothstep", reconnectable:"target" as const, data:{attachment:true}, label: block.kind==="sla_attachment"?"Настройка SLA":"Настройка маршрута", style:{stroke:"#7c3aed",strokeDasharray:"5 5",strokeWidth:2} }] : []);
  const edges: Edge[] = [...routeEdges, ...entranceEdges, ...attachmentEdges, ...Object.keys(auxiliaryEditors).map(source => ({ id: `studio:sla-link:${source}`, source, target: `studio:legacy-sla:${source}`, sourceHandle: "new", type: "smoothstep", data: { auxiliary: true }, style: { stroke: "#c3984f", strokeDasharray: "3 5" }, selectable: false, reconnectable: false }))];
  return <div className="studio-map-canvas" aria-label="Визуальная карта сценария" onContextMenu={event => { if (onContext) { event.preventDefault(); onContext({ x: event.clientX, y: event.clientY }, (event.target as Element).closest("[data-scenario-edge]") ? undefined : (event.target as Element).closest(".react-flow__node")?.getAttribute("data-id") ?? undefined, (event.target as Element).closest("[data-scenario-edge], .react-flow__edge")?.getAttribute("data-scenario-edge") ?? (event.target as Element).closest(".react-flow__edge")?.getAttribute("data-id") ?? undefined); } }} onDragOver={event => { if (!disabled) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }} onDrop={event => {
    if (disabled) return; event.preventDefault(); const kind = event.dataTransfer.getData("application/x-scenario-kind");
    if (kind) onDropBlock(kind, { x: event.clientX, y: event.clientY }, (event.target as Element).closest(".react-flow__edge")?.getAttribute("data-id") ?? undefined);
  }}>
    <button type="button" className="studio-map-settings" onClick={() => onEdit ? onEdit(metadataNodeId) : onSelect(metadataNodeId)}>Настройки карты</button>
    {!definition.blocks?.length && <div className="studio-map-empty"><strong>Начните с первого шага</strong><p>Добавьте вопрос или инструкцию. Затем продолжайте маршрут через +.</p>{!disabled && <button type="button" onClick={() => onAdd?.(null)}>+ Добавить первый шаг</button>}</div>}
    <ReactFlow<MapNode> onMoveEnd={(_, viewport) => setViewportZoom(viewport.zoom)} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={changes => { onNodesChange(changes.filter(change=>change.type!=="select")); if (!disabled && !dragging.current) for (const change of changes) if (change.type === "position" && change.position && change.dragging === false && !change.id.startsWith("studio:legacy-sla:") && change.id !== `${entranceEdgeId(null)}:node`) persistPosition(change.id, change.position); }} zoomOnDoubleClick={false} onInit={instance=>{flow.current=instance;onReady(instance);}} fitView fitViewOptions={{ padding: 0.18, maxZoom: 1 }} minZoom={0.15} maxZoom={2} nodesDraggable={!disabled} nodesConnectable={!disabled} edgesReconnectable={!disabled} deleteKeyCode={null} multiSelectionKeyCode={null} selectionKeyCode={null} selectNodesOnDrag={false}
      onNodeClick={(_, node) => { if(node.data.link)node.data.link.select();else onSelect(node.id); }} onPaneClick={() => onSelect(metadataNodeId)} onEdgeClick={(_, edge) => { if (edge.data?.auxiliary) return; if(edge.data?.attachment){onSelect(edge.source);return;} if (edge.data?.entrance) { onEntrance(edge.data.key as string | null, String(edge.data.target)); return; } const route=edge.data?.route as {source:string;index:number}|undefined; if(route)onEdge(route.source,route.index); }}
      onNodeDragStart={() => { dragging.current = true; }} onNodeDragStop={(_, node) => { dragging.current = false; if (!node.data.auxiliary) persistPosition(node.id, node.position); }}
      onConnect={connection => { if (!connection.source || !connection.target || !definition.blocks?.some(block=>block.id===connection.target) || connection.source.startsWith("studio:legacy-sla:") || connection.target.startsWith("studio:legacy-sla:")) return; const link=nodes.find(node=>node.id===connection.source)?.data.link; if(link?.entrance)onEntranceReconnect(link.entrance.key,connection.target);else if(link?.route)onReconnect(link.route.source,link.route.index,connection.target);else if(!nodes.find(node=>node.id===connection.target)?.data.link)onConnect(connection.source, connection.target, connection.sourceHandle ?? null); }}
      onReconnect={(edge, connection) => { if (!connection.target || !definition.blocks?.some(block=>block.id===connection.target)) return; if(edge.data?.attachment) onConnect(edge.source,connection.target,"policy"); else if (edge.data?.entrance) onEntranceReconnect(edge.data.key as string | null, connection.target); else {const route=edge.data?.route as {source:string;index:number}|undefined;if(route)onReconnect(route.source,route.index,connection.target);} }}>
      <Background gap={22} color="#dbe4ef" /><Controls showInteractive={false} />
    </ReactFlow>
  </div>;
}
