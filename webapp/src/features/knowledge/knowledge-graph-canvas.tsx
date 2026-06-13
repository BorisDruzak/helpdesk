import { useEffect, useMemo, useState } from "react";
import {
  applyNodeChanges,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { KnowledgeGraphEdge, KnowledgeGraphNode } from "./api";

export type KnowledgeGraphCanvasPosition = {
  x: number;
  y: number;
};

export type KnowledgeGraphCanvasNode = KnowledgeGraphNode & KnowledgeGraphCanvasPosition;

type GraphCanvasProps = {
  edges: KnowledgeGraphEdge[];
  nodes: KnowledgeGraphCanvasNode[];
  nodesById: Map<string, KnowledgeGraphNode>;
  onConnectNodes: (connection: { source_stable_key: string; target_stable_key: string }) => void;
  onLayoutChange: (positions: Record<string, KnowledgeGraphCanvasPosition>) => void;
  onSelectNode: (stableKey: string) => void;
  selectedStableKey?: string;
};

type FlowGraphNode = Node<Record<string, unknown>>;

const GRAPH_NODE_WIDTH = 220;
const GRAPH_NODE_HEIGHT = 84;

function nodeBorder(node: KnowledgeGraphCanvasNode, selectedStableKey?: string) {
  if (node.stable_key === selectedStableKey) {
    return "#157243";
  }
  if (node.node_type === "knowledge_item") {
    return "#2563eb";
  }
  if (node.node_type === "service" || node.node_type === "offering") {
    return "#0f766e";
  }
  return "#64748b";
}

function edgeStableKey(nodeId: string, nodesById: Map<string, KnowledgeGraphNode>) {
  return nodesById.get(nodeId)?.stable_key ?? nodeId;
}

function layoutPositions(nodes: Node[]): Record<string, KnowledgeGraphCanvasPosition> {
  return Object.fromEntries(nodes.map((node) => [node.id, { x: Math.round(node.position.x), y: Math.round(node.position.y) }]));
}

export function KnowledgeGraphCanvas({ edges, nodes, nodesById, onConnectNodes, onLayoutChange, onSelectNode, selectedStableKey }: GraphCanvasProps) {
  const flowNodes = useMemo<FlowGraphNode[]>(
    () =>
      nodes.map((node) => ({
        data: {
          label: node.label,
          nodeType: node.node_type,
          stableKey: node.stable_key,
        },
        ariaLabel: node.label,
        height: GRAPH_NODE_HEIGHT,
        id: node.stable_key,
        initialHeight: GRAPH_NODE_HEIGHT,
        initialWidth: GRAPH_NODE_WIDTH,
        measured: { height: GRAPH_NODE_HEIGHT, width: GRAPH_NODE_WIDTH },
        position: { x: node.x, y: node.y },
        selected: node.stable_key === selectedStableKey,
        style: {
          background: node.stable_key === selectedStableKey ? "#f0fdf4" : "#ffffff",
          border: `2px solid ${nodeBorder(node, selectedStableKey)}`,
          borderRadius: 8,
          color: "#0f172a",
          fontSize: 12,
          fontWeight: 700,
          height: GRAPH_NODE_HEIGHT,
          lineHeight: 1.35,
          maxWidth: GRAPH_NODE_WIDTH,
          overflow: "hidden",
          padding: 10,
          textOverflow: "ellipsis",
          whiteSpace: "normal",
          width: GRAPH_NODE_WIDTH,
          wordBreak: "break-word",
        },
        width: GRAPH_NODE_WIDTH,
      })),
    [nodes, selectedStableKey],
  );

  const flowEdges = useMemo<Edge[]>(
    () =>
      edges.reduce<Edge[]>((result, edge) => {
          const source = edgeStableKey(edge.source_node_id, nodesById);
          const target = edgeStableKey(edge.target_node_id, nodesById);
          if (!nodes.some((node) => node.stable_key === source) || !nodes.some((node) => node.stable_key === target)) {
            return result;
          }
          result.push({
            animated: edge.status !== "archived",
            data: { relationType: edge.relation_type },
            id: edge.edge_id,
            label: edge.relation_type,
            source,
            style: { stroke: "#157243", strokeWidth: 2 },
            target,
            type: "smoothstep",
          });
          return result;
        }, []),
    [edges, nodes, nodesById],
  );

  const [localNodes, setLocalNodes] = useState(flowNodes);
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance | null>(null);

  useEffect(() => {
    setLocalNodes(flowNodes);
  }, [flowNodes]);

  useEffect(() => {
    if (!flowInstance || !localNodes.length) {
      return;
    }
    const requestFrame = window.requestAnimationFrame ?? ((callback: FrameRequestCallback) => window.setTimeout(callback, 0));
    const cancelFrame = window.cancelAnimationFrame ?? window.clearTimeout;
    const animationFrame = requestFrame(() => {
      flowInstance.fitView({ duration: 250, padding: 0.18 });
    });
    return () => cancelFrame(animationFrame);
  }, [flowEdges.length, flowInstance, localNodes.length, selectedStableKey]);

  function handleNodesChange(changes: NodeChange[]) {
    setLocalNodes((currentNodes) => {
      const nextNodes = applyNodeChanges(changes, currentNodes) as FlowGraphNode[];
      onLayoutChange(layoutPositions(nextNodes));
      return nextNodes;
    });
  }

  function handleConnect(connection: Connection) {
    if (!connection.source || !connection.target) {
      return;
    }
    onConnectNodes({ source_stable_key: connection.source, target_stable_key: connection.target });
  }

  function fitVisibleGraph() {
    flowInstance?.fitView({ duration: 250, padding: 0.18 });
  }

  return (
    <div className="overflow-hidden rounded-md border border-slate-200 bg-slate-950" data-testid="knowledge-react-flow-canvas">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-4 py-2 text-xs font-semibold text-slate-200">
        <div className="min-w-0">
          <span>React Flow canvas</span>
          <span className="ml-3 text-slate-400">
            {nodes.length ? `${nodes.length} узлов, ${flowEdges.length} связей` : "Нет узлов для отображения"}
          </span>
        </div>
        <button
          className="rounded-pill border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-100 transition-colors hover:border-slate-400 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!nodes.length}
          onClick={fitVisibleGraph}
          type="button"
        >
          Показать весь граф
        </button>
      </div>
      <div className="h-[560px]">
        <ReactFlow
          edges={flowEdges}
          fitView
          minZoom={0.35}
          nodes={localNodes}
          onConnect={handleConnect}
          onInit={setFlowInstance}
          onNodeClick={(_event, node) => onSelectNode(node.id)}
          onNodesChange={handleNodesChange}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#334155" gap={22} />
          <Controls />
          <MiniMap nodeColor={(node) => (node.id === selectedStableKey ? "#157243" : "#94a3b8")} pannable zoomable />
        </ReactFlow>
      </div>
    </div>
  );
}
