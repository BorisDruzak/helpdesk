import { useEffect, useMemo, useRef } from "react";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, useNodesState, useUpdateNodeInternals, type Edge, type Node, type NodeProps, type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { mapKindLabel, terminal } from "./scenario-map-model";
import "./scenario-map.css";

type MapData = { title: string; subtitle: string; entries: string[]; transitions: number; terminal: boolean; system: boolean; issue: boolean; current: boolean; visited: boolean };
export type MapNode = Node<MapData, "scenario">;
export const metadataNodeId = "studio:metadata";
export const entranceEdgeId = (key: string | null) => key === null ? "studio:primary" : `studio:entry-point:${encodeURIComponent(key)}`;
function MapBlock({ id, data, selected }: NodeProps<MapNode>) {
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => { updateNodeInternals(id); }, [id, data.transitions, data.terminal, updateNodeInternals]);
  return <div className={`studio-map-node ${selected ? "is-selected" : ""} ${data.system ? "is-system" : ""} ${data.issue ? "has-issue" : ""} ${data.current ? "is-current" : ""} ${data.visited ? "is-visited" : ""}`}>
    {!data.system && <Handle type="target" position={Position.Left} />}
    {data.system && <Handle id="entrance" type="source" position={Position.Bottom} aria-label="Начало: создать связь с точкой входа" />}
    <div className="studio-map-node__kind">{data.subtitle}</div><strong>{data.title}</strong>
    {data.entries.map((title, index) => <span key={index} className="studio-map-node__entry">↳ {title}</span>)}
    {!data.system && !data.terminal && <><Handle id="new" type="source" position={Position.Right} style={{ top: 20 }} />{Array.from({ length: data.transitions }, (_, index) => <Handle key={index} id={`route-${index}`} type="source" position={Position.Right} style={{ top: 45 + index * 13 }} />)}</>}
  </div>;
}
const nodeTypes = { scenario: MapBlock };
export const transitionId = (source: string, index: number) => `${source}:${index}`;
export function ScenarioMapCanvas({ definition, selected, selectedEdge, disabled, issueBlockId, path = [], current, onSelect, onEdge, onMove, onConnect, onReconnect, onDropBlock, onReady, onEntrance, onEntranceReconnect }: {
  definition: ScenarioDraftDefinition; selected: string; selectedEdge: string | null; disabled: boolean; issueBlockId?: string; path?: string[]; current?: string;
  onSelect: (id: string) => void; onEdge: (source: string, index: number) => void;
  onMove: (id: string, position: { x: number; y: number }) => void;
  onConnect: (source: string, target: string, handle: string | null) => void;
  onReconnect: (source: string, index: number, target: string) => void;
  onDropBlock: (kind: string, point: { x: number; y: number }, edgeId?: string) => void;
  onEntrance: (key: string | null, target: string) => void;
  onEntranceReconnect: (key: string | null, target: string) => void;
  onReady: (instance: ReactFlowInstance<MapNode>) => void;
}) {
  const initial = useMemo<MapNode[]>(() => [{ id: metadataNodeId, type: "scenario", position: definition.editor_layout?.positions?.system_start ?? { x: -320, y: 0 }, selected: selected === metadataNodeId, data: { title: "Начало", subtitle: "Общие настройки карты", entries: [], transitions: 0, terminal: true, system: true, issue: false, current: false, visited: false } }, ...(definition.blocks ?? []).map((block, index): MapNode => ({
    id: block.id, type: "scenario", position: definition.editor_layout?.positions?.[block.id] ?? { x: (index % 3) * 310, y: Math.floor(index / 3) * 200 }, selected: selected === block.id,
    data: { title: block.title, subtitle: mapKindLabel(block.kind), entries: (definition.entry_points ?? []).filter(entry => entry.target_block_id === block.id).map(entry => entry.title), transitions: block.transitions?.length ?? 0, terminal: terminal(block.kind), system: false, issue: issueBlockId === block.id, current: current === block.id, visited: path.includes(block.id) },
  }))], [definition, selected, issueBlockId, path, current]);
  const [nodes, setNodes, onNodesChange] = useNodesState<MapNode>(initial);
  const dragging = useRef(false);
  useEffect(() => setNodes(initial), [initial, setNodes]);
  const routeEdges = useMemo<Edge[]>(() => (definition.blocks ?? []).flatMap(block => (block.transitions ?? []).map((edge, index) => ({
    id: transitionId(block.id, index), source: block.id, target: edge.to, sourceHandle: `route-${index}`, type: "smoothstep", reconnectable: "target", selected: selectedEdge === transitionId(block.id, index), markerEnd: { type: MarkerType.ArrowClosed }, label: edge.when ? `Условие ${index + 1}` : "Продолжить", style: { stroke: selectedEdge === transitionId(block.id, index) ? "#2563eb" : "#94a3b8", strokeWidth: 2 },
  }))), [definition.blocks, selectedEdge]);
  const entranceEdges: Edge[] = (definition.entry_points ?? []).filter(entry => nodes.some(node => node.id === entry.target_block_id)).map(entry => ({
    id: entranceEdgeId(entry.key), source: metadataNodeId, sourceHandle: "entrance", target: entry.target_block_id, type: "smoothstep", reconnectable: "target",
    data: { entrance: true, key: entry.key }, selected: selectedEdge === entranceEdgeId(entry.key), markerEnd: { type: MarkerType.ArrowClosed },
    label: entry.title, style: { stroke: "#0d9488", strokeWidth: 2, strokeDasharray: "6 4", opacity: entry.enabled === false ? 0.45 : 1 },
  }));
  if (definition.entry_block_id && !definition.entry_points?.some(entry => entry.target_block_id === definition.entry_block_id) && nodes.some(node => node.id === definition.entry_block_id)) entranceEdges.push({
    id: entranceEdgeId(null), source: metadataNodeId, sourceHandle: "entrance", target: definition.entry_block_id, type: "smoothstep", reconnectable: "target",
    data: { entrance: true, key: null }, selected: selectedEdge === entranceEdgeId(null), label: "Основной вход", style: { stroke: "#0d9488", strokeDasharray: "6 4" },
  });
  const edges = [...routeEdges, ...entranceEdges];
  return <div className="studio-map-canvas" aria-label="Визуальная карта сценария" onDragOver={event => { if (!disabled) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } }} onDrop={event => {
    if (disabled) return; event.preventDefault(); const kind = event.dataTransfer.getData("application/x-scenario-kind");
    if (kind) onDropBlock(kind, { x: event.clientX, y: event.clientY }, (event.target as Element).closest(".react-flow__edge")?.getAttribute("data-id") ?? undefined);
  }}>
    <ReactFlow<MapNode> nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={changes => { onNodesChange(changes); if (!disabled && !dragging.current) for (const change of changes) if (change.type === "position" && change.position && change.dragging === false) onMove(change.id, change.position); }} onInit={onReady} fitView minZoom={0.15} maxZoom={2} nodesDraggable={!disabled} nodesConnectable={!disabled} edgesReconnectable={!disabled} deleteKeyCode={null}
      onNodeClick={(_, node) => onSelect(node.id)} onPaneClick={() => onSelect(metadataNodeId)} onEdgeClick={(_, edge) => { if (edge.data?.entrance) { onEntrance(edge.data.key as string | null, edge.target); return; } const [source, index] = edge.id.split(":"); onEdge(source, Number(index)); }}
      onNodeDragStart={() => { dragging.current = true; }} onNodeDragStop={(_, node) => { onMove(node.id, node.position); dragging.current = false; }}
      onConnect={connection => { if (connection.source && connection.target) onConnect(connection.source, connection.target, connection.sourceHandle ?? null); }}
      onReconnect={(edge, connection) => { if (!connection.target) return; if (edge.data?.entrance) onEntranceReconnect(edge.data.key as string | null, connection.target); else onReconnect(edge.source, Number(edge.id.split(":")[1]), connection.target); }}>
      <Background gap={22} color="#dbe4ef" /><Controls showInteractive={false} />
    </ReactFlow>
  </div>;
}
