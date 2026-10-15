import { fieldLabels } from "./scenario-builder-model";
import { useEffect, useMemo, useRef } from "react";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, useNodesState, useUpdateNodeInternals, type Edge, type Node, type NodeProps, type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { mapKindLabel, stableMapPositions, terminal } from "./scenario-map-model";
import "./scenario-map.css";
import { ScenarioMapEdge } from "./scenario-map-edge";
import { scenarioMapHints } from "./scenario-map-hints";

type MapData = { title: string; subtitle: string; entries: string[]; transitions: number; terminal: boolean; system: boolean; issue: boolean; current: boolean; visited: boolean; entrance?: boolean; hint?: string; add?: () => void };
export type MapNode = Node<MapData, "scenario">;
export const metadataNodeId = "studio:metadata";
export const entranceEdgeId = (key: string | null) => key === null ? "studio:primary" : `studio:entry-point:${encodeURIComponent(key)}`;
function MapBlock({ id, data, selected }: NodeProps<MapNode>) {
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => { updateNodeInternals(id); }, [id, data.transitions, data.terminal, updateNodeInternals]);
  return <div className={`studio-map-node ${selected ? "is-selected" : ""} ${data.system ? "is-system" : ""} ${data.issue ? "has-issue" : ""} ${data.current ? "is-current" : ""} ${data.visited ? "is-visited" : ""}`}>
    {!data.system && !data.entrance && <Handle type="target" position={Position.Left} aria-label={`Вход блока «${data.title}»`} title="Перетащите сюда связь другого блока" />}
    {data.entrance && <Handle type="source" position={Position.Bottom} aria-label={`Начало «${data.title}»: соединить с первым шагом`} />}
    {data.system && <Handle id="entrance" type="source" position={Position.Right} aria-label="Начало: создать связь с точкой входа" />}
    <div className="studio-map-node__kind">{data.subtitle}</div><strong>{data.title}</strong>
    {data.entries.map((title, index) => <span key={index} className="studio-map-node__entry">↳ {title}</span>)}
    {data.hint && <span className="studio-map-node__hint">{data.hint}</span>}
    {data.add && <button type="button" className="studio-node-add nodrag nopan" aria-label={`Добавить следующий шаг после «${data.title}»`} onClick={event => { event.stopPropagation(); data.add?.(); }}>+ Добавить следующий шаг</button>}
    {!data.system && !data.terminal && <><Handle id="new" type="source" position={Position.Right} className="studio-handle-new" aria-label={`Соединить «${data.title}» с другим блоком`} title="Перетащите к входу другого блока" style={{ top: 20 }} />{Array.from({ length: data.transitions }, (_, index) => <Handle key={index} id={`route-${index}`} type="source" position={Position.Right} style={{ top: 45 + index * 13 }} />)}</>}
  </div>;
}
const nodeTypes = { scenario: MapBlock };
const edgeTypes = { scenario: ScenarioMapEdge };
const emptyPath: string[] = [];
export const transitionId = (source: string, index: number) => `${source}:${index}`;
export function ScenarioMapCanvas({ definition, selected, selectedEdge, disabled, issueBlockId, path = emptyPath, current, onSelect, onEdge, onMove, onConnect, onReconnect, onDropBlock, onReady, onEntrance, onEntranceReconnect, onEntranceTitle, onAdd }: {
  definition: ScenarioDraftDefinition; selected: string; selectedEdge: string | null; disabled: boolean; issueBlockId?: string; path?: string[]; current?: string;
  onSelect: (id: string) => void; onEdge: (source: string, index: number) => void;
  onMove: (id: string, position: { x: number; y: number }) => void;
  onConnect: (source: string, target: string, handle: string | null) => void;
  onReconnect: (source: string, index: number, target: string) => void;
  onDropBlock: (kind: string, point: { x: number; y: number }, edgeId?: string) => void;
  onEntrance: (key: string | null, target: string) => void;
  onEntranceReconnect: (key: string | null, target: string) => void;
  onReady: (instance: ReactFlowInstance<MapNode>) => void;
  onEntranceTitle?: (key:string,title:string)=>void;
  onAdd?: (source: string | null, index?: number) => void;
}) {
  const hints = scenarioMapHints(definition);
  const positions = stableMapPositions(definition);
  const entrances = [...(definition.entry_points ?? []).map(entry => ({ key: entry.key as string | null, title: entry.title, target: entry.target_block_id, enabled: entry.enabled !== false })), ...(!definition.entry_points?.some(entry => entry.target_block_id === definition.entry_block_id) ? [{ key: null, title: "Начало маршрута", target: definition.entry_block_id ?? "", enabled: true }] : [])];
  const initial = useMemo<MapNode[]>(() => [{ id: metadataNodeId, type: "scenario", position: definition.editor_layout?.positions?.system_start ?? { x: -320, y: 0 }, selected: selected === metadataNodeId, data: { title: "Начало", subtitle: "Входы из каталога", entries: [], transitions: 0, terminal: true, system: true, issue: false, current: false, visited: false } }, ...(definition.blocks ?? []).map((block): MapNode => ({
    id: block.id, type: "scenario", position: positions[block.id], selected: selected === block.id,
    data: { title: block.kind === "form_page" && block.fields.length === 1 ? block.fields[0].label : block.title, subtitle: block.kind === "form_page" && block.fields.length === 1 ? `Вопрос · ${fieldLabels[block.fields[0].type]}` : mapKindLabel(block.kind), entries: [], transitions: block.transitions?.length ?? 0, terminal: terminal(block.kind), system: false, issue: issueBlockId === block.id || hints.some(hint => hint.blockId === block.id && hint.level === "required"), hint: hints.find(hint => hint.blockId === block.id)?.text, current: current === block.id, visited: path.includes(block.id), add: !disabled && !terminal(block.kind) && onAdd ? () => onAdd(block.id) : undefined },
  }))], [definition, selected, selectedEdge, issueBlockId, path, current, disabled, onAdd]);
  const [nodes, setNodes, onNodesChange] = useNodesState<MapNode>(initial);
  const dragging = useRef(false);
  const flow = useRef<ReactFlowInstance<MapNode> | null>(null);
  const previousCount = useRef(definition.blocks?.length ?? 0);
  useEffect(() => { const count = definition.blocks?.length ?? 0; const firstStep = previousCount.current === 0 && count > 0; previousCount.current = count; if (firstStep) { const frame = requestAnimationFrame(() => void flow.current?.fitView({ padding: 0.18, maxZoom: 1 })); return () => cancelAnimationFrame(frame); } }, [definition.blocks?.length]);
  useEffect(() => setNodes(previous => initial.map(node => { const old = previous.find(item => item.id === node.id); return { ...node, measured: old?.measured, ...(dragging.current && old ? { position: old.position, dragging: old.dragging } : {}) }; })), [initial, setNodes]);
  const routeEdges = useMemo<Edge[]>(() => (definition.blocks ?? []).flatMap(block => (block.transitions ?? []).map((edge, index) => ({
    id: transitionId(block.id, index), source: block.id, target: edge.to, sourceHandle: `route-${index}`, type: "scenario", reconnectable: "target", selected: selectedEdge === transitionId(block.id, index), markerEnd: { type: MarkerType.ArrowClosed }, label: edge.when && "source" in edge.when && edge.when.source === "current_result" && "value" in edge.when ? ({ yes: "Да", no: "Нет", unknown: "Не знаю" }[String(edge.when.value)] ?? `Условие ${index + 1}`) : edge.when ? `Условие ${index + 1}` : block.kind === "resolution_check" ? "Не знаю / иначе" : block.kind === "decision" ? "Иначе" : "Продолжить", data: { labelOffset: (index - ((block.transitions?.length ?? 1) - 1) / 2) * 46, select: () => onEdge(block.id, index), add: !disabled && onAdd ? () => onAdd(block.id, index) : undefined, addLabel: `Добавить шаг между «${block.title}» и «${definition.blocks?.find(target => target.id === edge.to)?.title ?? "следующим блоком"}»` }, style: { stroke: selectedEdge === transitionId(block.id, index) ? "#087443" : "#94a3b8", strokeWidth: 2 },
  }))), [definition.blocks, selectedEdge, disabled, onAdd, onEdge]);
  const entranceEdges: Edge[] = (definition.entry_points ?? []).filter(entry => nodes.some(node => node.id === entry.target_block_id)).map(entry => ({
    id: entranceEdgeId(entry.key), source: metadataNodeId, sourceHandle: "entrance", target: entry.target_block_id, type: "scenario", reconnectable: "target",
    data: { entrance: true, key: entry.key, labelOffset: (definition.entry_points!.indexOf(entry))*30, select:()=>onEntrance(entry.key,entry.target_block_id), rename: !disabled && onEntranceTitle ? (title:string)=>onEntranceTitle(entry.key,title) : undefined }, selected: selectedEdge === entranceEdgeId(entry.key), markerEnd: { type: MarkerType.ArrowClosed },
    label: entry.title, style: { stroke: "#0d9488", strokeWidth: 2, strokeDasharray: "6 4", opacity: entry.enabled === false ? 0.45 : 1 },
  }));
  if (definition.schema_version !== 2 && definition.entry_block_id && !definition.entry_points?.some(entry => entry.target_block_id === definition.entry_block_id) && nodes.some(node => node.id === definition.entry_block_id)) entranceEdges.push({
    id: entranceEdgeId(null), source: metadataNodeId, sourceHandle: "entrance", target: definition.entry_block_id, type: "smoothstep", reconnectable: "target",
    data: { entrance: true, key: null }, selected: selectedEdge === entranceEdgeId(null), label: "Основной вход", style: { stroke: "#0d9488", strokeDasharray: "6 4" },
  });
  const edges = [...routeEdges, ...entranceEdges];
  return <div className="studio-map-canvas" aria-label="Визуальная карта сценария" onDragOver={event => { if (!disabled) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }} onDrop={event => {
    if (disabled) return; event.preventDefault(); const kind = event.dataTransfer.getData("application/x-scenario-kind");
    if (kind) onDropBlock(kind, { x: event.clientX, y: event.clientY }, (event.target as Element).closest(".react-flow__edge")?.getAttribute("data-id") ?? undefined);
  }}>
    <button type="button" className="studio-map-settings" onClick={() => onSelect(metadataNodeId)}>Настройки карты</button>
    {!definition.blocks?.length && <div className="studio-map-empty"><strong>Начните с первого шага</strong><p>Добавьте вопрос или инструкцию. Затем продолжайте маршрут через +.</p>{!disabled && <button type="button" onClick={() => onAdd?.(null)}>+ Добавить первый шаг</button>}</div>}
    <ReactFlow<MapNode> nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={changes => { onNodesChange(changes.filter(change=>change.type!=="select")); if (!disabled && !dragging.current) for (const change of changes) if (change.type === "position" && change.position && change.dragging === false && !change.id.startsWith("studio:entry") && change.id !== `${entranceEdgeId(null)}:node`) onMove(change.id, change.position); }} onInit={instance=>{flow.current=instance;onReady(instance);}} fitView fitViewOptions={{ padding: 0.18, maxZoom: 1 }} minZoom={0.15} maxZoom={2} nodesDraggable={!disabled} nodesConnectable={!disabled} edgesReconnectable={!disabled} deleteKeyCode={null} multiSelectionKeyCode={null} selectionKeyCode={null} selectNodesOnDrag={false}
      onNodeClick={(_, node) => { const entry = entrances.find(item => `${entranceEdgeId(item.key)}:node` === node.id); if (entry) onEntrance(entry.key, entry.target); else onSelect(node.id); }} onPaneClick={() => onSelect(metadataNodeId)} onEdgeClick={(_, edge) => { if (edge.data?.entrance) { onEntrance(edge.data.key as string | null, edge.target); return; } const [source, index] = edge.id.split(":"); onEdge(source, Number(index)); }}
      onNodeDragStart={() => { dragging.current = true; }} onNodeDragStop={(_, node) => { dragging.current = false; onMove(node.id, node.position); }}
      onConnect={connection => { if (!connection.source || !connection.target) return; const entry = entrances.find(item => `${entranceEdgeId(item.key)}:node` === connection.source); if (entry) onEntranceReconnect(entry.key, connection.target); else onConnect(connection.source, connection.target, connection.sourceHandle ?? null); }}
      onReconnect={(edge, connection) => { if (!connection.target) return; if (edge.data?.entrance) onEntranceReconnect(edge.data.key as string | null, connection.target); else onReconnect(edge.source, Number(edge.id.split(":")[1]), connection.target); }}>
      <Background gap={22} color="#dbe4ef" /><Controls showInteractive={false} />
    </ReactFlow>
  </div>;
}
