import { useEffect, useMemo, useRef } from "react";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, useNodesState, useUpdateNodeInternals, type Edge, type Node, type NodeProps, type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { mapKindLabel, terminal } from "./scenario-map-model";
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
    {!data.system && !data.entrance && <Handle type="target" position={Position.Left} />}
    {data.entrance && <Handle type="source" position={Position.Bottom} />}
    {data.system && <Handle id="entrance" type="source" position={Position.Bottom} aria-label="Начало: создать связь с точкой входа" />}
    <div className="studio-map-node__kind">{data.subtitle}</div><strong>{data.title}</strong>
    {data.entries.map((title, index) => <span key={index} className="studio-map-node__entry">↳ {title}</span>)}
    {data.hint && <span className="studio-map-node__hint">{data.hint}</span>}
    {data.add && <button type="button" className="studio-node-add nodrag nopan" aria-label={`Добавить следующий шаг после «${data.title}»`} onClick={event => { event.stopPropagation(); data.add?.(); }}>+ Добавить следующий шаг</button>}
    {!data.system && !data.terminal && <><Handle id="new" type="source" position={Position.Right} style={{ top: 20 }} />{Array.from({ length: data.transitions }, (_, index) => <Handle key={index} id={`route-${index}`} type="source" position={Position.Right} style={{ top: 45 + index * 13 }} />)}</>}
  </div>;
}
const nodeTypes = { scenario: MapBlock };
const edgeTypes = { scenario: ScenarioMapEdge };
export const transitionId = (source: string, index: number) => `${source}:${index}`;
export function ScenarioMapCanvas({ definition, selected, selectedEdge, disabled, issueBlockId, path = [], current, onSelect, onEdge, onMove, onConnect, onReconnect, onDropBlock, onReady, onEntrance, onEntranceReconnect, onAdd }: {
  definition: ScenarioDraftDefinition; selected: string; selectedEdge: string | null; disabled: boolean; issueBlockId?: string; path?: string[]; current?: string;
  onSelect: (id: string) => void; onEdge: (source: string, index: number) => void;
  onMove: (id: string, position: { x: number; y: number }) => void;
  onConnect: (source: string, target: string, handle: string | null) => void;
  onReconnect: (source: string, index: number, target: string) => void;
  onDropBlock: (kind: string, point: { x: number; y: number }, edgeId?: string) => void;
  onEntrance: (key: string | null, target: string) => void;
  onEntranceReconnect: (key: string | null, target: string) => void;
  onReady: (instance: ReactFlowInstance<MapNode>) => void;
  onAdd?: (source: string | null, index?: number) => void;
}) {
  const hints = scenarioMapHints(definition);
  const entrances = [...(definition.entry_points ?? []).map(entry => ({ key: entry.key as string | null, title: entry.title, target: entry.target_block_id, enabled: entry.enabled !== false })), ...(definition.entry_block_id && !definition.entry_points?.some(entry => entry.target_block_id === definition.entry_block_id) ? [{ key: null, title: "Основной пункт каталога", target: definition.entry_block_id, enabled: true }] : [])];
  const initial = useMemo<MapNode[]>(() => [{ id: metadataNodeId, type: "scenario", hidden: true, position: definition.editor_layout?.positions?.system_start ?? { x: -320, y: 0 }, selected: selected === metadataNodeId, data: { title: "Настройки карты", subtitle: "Системные настройки", entries: [], transitions: 0, terminal: true, system: true, issue: false, current: false, visited: false } }, ...(definition.blocks ?? []).map((block, index): MapNode => ({
    id: block.id, type: "scenario", position: definition.editor_layout?.positions?.[block.id] ?? { x: (index % 3) * 310, y: Math.floor(index / 3) * 200 }, selected: selected === block.id,
    data: { title: block.kind === "form_page" && block.fields.length === 1 ? block.fields[0].label : block.title, subtitle: mapKindLabel(block.kind), entries: [], transitions: block.transitions?.length ?? 0, terminal: terminal(block.kind), system: false, issue: issueBlockId === block.id || hints.some(hint => hint.blockId === block.id && hint.level === "required"), hint: hints.find(hint => hint.blockId === block.id)?.text, current: current === block.id, visited: path.includes(block.id), add: !disabled && !terminal(block.kind) && onAdd ? () => onAdd(block.id) : undefined },
  })), ...entrances.map((entry, index): MapNode => {
    const targetIndex = definition.blocks?.findIndex(block => block.id === entry.target) ?? -1;
    const target = definition.editor_layout?.positions?.[entry.target] ?? { x: Math.max(0, targetIndex % 3) * 310, y: Math.floor(Math.max(0, targetIndex) / 3) * 200 };
    return { id: `${entranceEdgeId(entry.key)}:node`, type: "scenario", position: { x: target.x - index * 260, y: target.y - 170 }, draggable: false, selected: selectedEdge === entranceEdgeId(entry.key), data: { title: entry.title, subtitle: entry.enabled ? "Пункт каталога · точка входа" : "Пункт каталога · отключён", entries: [], transitions: 0, terminal: true, system: false, entrance: true, issue: targetIndex < 0, hint: targetIndex < 0 ? "Выберите начальный блок" : undefined, current: false, visited: false } };
  })], [definition, selected, selectedEdge, issueBlockId, path, current, disabled, onAdd]);
  const [nodes, setNodes, onNodesChange] = useNodesState<MapNode>(initial);
  const dragging = useRef(false);
  useEffect(() => setNodes(initial), [initial, setNodes]);
  const routeEdges = useMemo<Edge[]>(() => (definition.blocks ?? []).flatMap(block => (block.transitions ?? []).map((edge, index) => ({
    id: transitionId(block.id, index), source: block.id, target: edge.to, sourceHandle: `route-${index}`, type: "scenario", reconnectable: "target", selected: selectedEdge === transitionId(block.id, index), markerEnd: { type: MarkerType.ArrowClosed }, label: edge.when && "source" in edge.when && edge.when.source === "current_result" && "value" in edge.when ? ({ yes: "Да", no: "Нет", unknown: "Не знаю" }[String(edge.when.value)] ?? `Условие ${index + 1}`) : edge.when ? `Условие ${index + 1}` : block.kind === "resolution_check" ? "Не знаю / иначе" : "Продолжить", data: { labelOffset: (index - ((block.transitions?.length ?? 1) - 1) / 2) * 46, select: () => onEdge(block.id, index), add: !disabled && onAdd ? () => onAdd(block.id, index) : undefined, addLabel: `Добавить шаг между «${block.title}» и «${definition.blocks?.find(target => target.id === edge.to)?.title ?? "следующим блоком"}»` }, style: { stroke: selectedEdge === transitionId(block.id, index) ? "#087443" : "#94a3b8", strokeWidth: 2 },
  }))), [definition.blocks, selectedEdge, disabled, onAdd]);
  const entranceEdges: Edge[] = (definition.entry_points ?? []).filter(entry => nodes.some(node => node.id === entry.target_block_id)).map(entry => ({
    id: entranceEdgeId(entry.key), source: `${entranceEdgeId(entry.key)}:node`, target: entry.target_block_id, type: "smoothstep", reconnectable: "target",
    data: { entrance: true, key: entry.key }, selected: selectedEdge === entranceEdgeId(entry.key), markerEnd: { type: MarkerType.ArrowClosed },
    label: entry.title, style: { stroke: "#0d9488", strokeWidth: 2, strokeDasharray: "6 4", opacity: entry.enabled === false ? 0.45 : 1 },
  }));
  if (definition.entry_block_id && !definition.entry_points?.some(entry => entry.target_block_id === definition.entry_block_id) && nodes.some(node => node.id === definition.entry_block_id)) entranceEdges.push({
    id: entranceEdgeId(null), source: `${entranceEdgeId(null)}:node`, target: definition.entry_block_id, type: "smoothstep", reconnectable: "target",
    data: { entrance: true, key: null }, selected: selectedEdge === entranceEdgeId(null), label: "Основной вход", style: { stroke: "#0d9488", strokeDasharray: "6 4" },
  });
  const edges = [...routeEdges, ...entranceEdges];
  return <div className="studio-map-canvas" aria-label="Визуальная карта сценария" onDragOver={event => { if (!disabled) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }} onDrop={event => {
    if (disabled) return; event.preventDefault(); const kind = event.dataTransfer.getData("application/x-scenario-kind");
    if (kind) onDropBlock(kind, { x: event.clientX, y: event.clientY }, (event.target as Element).closest(".react-flow__edge")?.getAttribute("data-id") ?? undefined);
  }}>
    <button type="button" className="studio-map-settings" onClick={() => onSelect(metadataNodeId)}>Настройки карты</button>
    {!definition.blocks?.length && <div className="studio-map-empty"><strong>Начните с первого шага</strong><p>Добавьте вопрос или инструкцию. Затем продолжайте маршрут через +.</p>{!disabled && <button type="button" onClick={() => onAdd?.(null)}>+ Добавить первый шаг</button>}</div>}
    <ReactFlow<MapNode> nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={changes => { onNodesChange(changes); if (!disabled && !dragging.current) for (const change of changes) if (change.type === "position" && change.position && change.dragging === false && !change.id.startsWith("studio:entry") && change.id !== `${entranceEdgeId(null)}:node`) onMove(change.id, change.position); }} onInit={onReady} fitView fitViewOptions={{ padding: 0.18, maxZoom: 1 }} minZoom={0.15} maxZoom={2} nodesDraggable={!disabled} nodesConnectable={!disabled} edgesReconnectable={!disabled} deleteKeyCode={null}
      onNodeClick={(_, node) => { const entry = entrances.find(item => `${entranceEdgeId(item.key)}:node` === node.id); if (entry) onEntrance(entry.key, entry.target); else onSelect(node.id); }} onPaneClick={() => onSelect(metadataNodeId)} onEdgeClick={(_, edge) => { if (edge.data?.entrance) { onEntrance(edge.data.key as string | null, edge.target); return; } const [source, index] = edge.id.split(":"); onEdge(source, Number(index)); }}
      onNodeDragStart={() => { dragging.current = true; }} onNodeDragStop={(_, node) => { onMove(node.id, node.position); dragging.current = false; }}
      onConnect={connection => { if (!connection.source || !connection.target) return; const entry = entrances.find(item => `${entranceEdgeId(item.key)}:node` === connection.source); if (entry) onEntranceReconnect(entry.key, connection.target); else onConnect(connection.source, connection.target, connection.sourceHandle ?? null); }}
      onReconnect={(edge, connection) => { if (!connection.target) return; if (edge.data?.entrance) onEntranceReconnect(edge.data.key as string | null, connection.target); else onReconnect(edge.source, Number(edge.id.split(":")[1]), connection.target); }}>
      <Background gap={22} color="#dbe4ef" /><Controls showInteractive={false} />
    </ReactFlow>
  </div>;
}
