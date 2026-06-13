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
        id: node.stable_key,
        position: { x: node.x, y: node.y },
        selected: node.stable_key === selectedStableKey,
        style: {
          background: node.stable_key === selectedStableKey ? "#f0fdf4" : "#ffffff",
          border: `2px solid ${nodeBorder(node, selectedStableKey)}`,
          borderRadius: 8,
          color: "#0f172a",
          fontSize: 12,
          fontWeight: 700,
          minWidth: 160,
          padding: 10,
        },
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

  useEffect(() => {
    setLocalNodes(flowNodes);
  }, [flowNodes]);

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

  return (
    <div className="overflow-hidden rounded-md border border-slate-200 bg-slate-950" data-testid="knowledge-react-flow-canvas">
      <div className="flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-4 py-2 text-xs font-semibold text-slate-200">
        <span>React Flow canvas</span>
        <span>{nodes.length ? `${nodes.length} узлов, ${flowEdges.length} связей` : "Нет узлов для отображения"}</span>
      </div>
      <div className="h-[560px]">
        <ReactFlow
          edges={flowEdges}
          fitView
          minZoom={0.35}
          nodes={localNodes}
          onConnect={handleConnect}
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
