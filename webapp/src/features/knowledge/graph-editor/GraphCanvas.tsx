import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type OnNodeDrag,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CheckCircle2, Crosshair, GitBranchPlus, LassoSelect, Link2, LocateFixed, MousePointer2, Move, RotateCcw, RotateCw, Save, Wand2 } from "lucide-react";

import type { KnowledgeGraphEdge, KnowledgeGraphNode } from "../api";
import { edgeStableKeys } from "./graphValidation";
import { GraphEdge, type GraphEdgeData } from "./GraphEdge";
import { GraphNode, type GraphNodeData } from "./GraphNode";
import { nodeTypeColor, relationTypeColor, relationTypeLabel, type GraphEditorMode, type GraphNodePosition, type PositionedGraphNode } from "./graphTypes";

type GraphCanvasProps = {
  activeRelationType: string;
  canRedo: boolean;
  canUndo: boolean;
  edges: KnowledgeGraphEdge[];
  layoutDirty: boolean;
  mode: GraphEditorMode;
  nodes: PositionedGraphNode[];
  nodesById: Map<string, KnowledgeGraphNode>;
  onArchiveNode: (stableKey: string) => void;
  onAutoLayout: () => void;
  onConnectNodes: (connection: { source_stable_key: string; target_stable_key: string }) => void;
  onDuplicateNode: (node: KnowledgeGraphNode) => void;
  onFitView: () => void;
  onLayoutCommit: (positions: Record<string, GraphNodePosition>) => void;
  onModeChange: (mode: GraphEditorMode) => void;
  onOpenArticle: (node: KnowledgeGraphNode) => void;
  onRequestAddNode: (position: GraphNodePosition) => void;
  onSaveLayout: () => void;
  onSelectEdge: (edgeId: string) => void;
  onSelectNode: (stableKey: string) => void;
  onStartConnect: (stableKey: string) => void;
  onUndo: () => void;
  onRedo: () => void;
  onValidate: () => void;
  savingLayout: boolean;
  selectedEdgeId: string;
  selectedStableKey: string;
};

const nodeTypes = { graphNode: GraphNode };
const edgeTypes = { graphEdge: GraphEdge };

type FlowNode = Node<GraphNodeData>;
type FlowEdge = Edge<GraphEdgeData>;

function positionsFromFlowNodes(nodes: Node[]) {
  return Object.fromEntries(nodes.map((node) => [node.id, { x: Math.round(node.position.x), y: Math.round(node.position.y) }]));
}

function modeButtonClass(mode: GraphEditorMode, activeMode: GraphEditorMode) {
  return `inline-flex h-9 items-center gap-2 rounded-pill px-3 text-xs font-semibold transition-colors ${
    mode === activeMode ? "bg-brand-600 text-white shadow-soft" : "border border-slate-200 bg-white text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
  }`;
}

export function GraphCanvas({
  activeRelationType,
  canRedo,
  canUndo,
  edges,
  layoutDirty,
  mode,
  nodes,
  nodesById,
  onArchiveNode,
  onAutoLayout,
  onConnectNodes,
  onDuplicateNode,
  onFitView,
  onLayoutCommit,
  onModeChange,
  onOpenArticle,
  onRequestAddNode,
  onRedo,
  onSaveLayout,
  onSelectEdge,
  onSelectNode,
  onStartConnect,
  onUndo,
  onValidate,
  savingLayout,
  selectedEdgeId,
  selectedStableKey,
}: GraphCanvasProps) {
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance<FlowNode, FlowEdge> | null>(null);

  const flowNodes = useMemo<FlowNode[]>(
    () =>
      nodes.map((node) => ({
        id: node.stable_key,
        type: "graphNode",
        position: { x: node.x, y: node.y },
        data: {
          node,
          onArchiveNode,
          onDuplicateNode,
          onEditNode: onSelectNode,
          onOpenArticle,
          onStartConnect,
        },
        selected: selectedStableKey === node.stable_key,
      })),
    [nodes, onArchiveNode, onDuplicateNode, onOpenArticle, onSelectNode, onStartConnect, selectedStableKey],
  );

  const flowEdges = useMemo<FlowEdge[]>(
    () =>
      edges.reduce<FlowEdge[]>((result, edge) => {
        if (edge.status === "archived") {
          return result;
        }
        const stableKeys = edgeStableKeys(edge, nodesById);
        if (!nodes.some((node) => node.stable_key === stableKeys.sourceStableKey) || !nodes.some((node) => node.stable_key === stableKeys.targetStableKey)) {
          return result;
        }
        result.push({
          id: edge.edge_id,
          source: stableKeys.sourceStableKey,
          target: stableKeys.targetStableKey,
          type: "graphEdge",
          selected: selectedEdgeId === edge.edge_id,
          data: { edge, onSelectEdge, selectedEdgeId },
          style: { stroke: relationTypeColor(edge.relation_type) },
        });
        return result;
      }, []),
    [edges, nodes, nodesById, onSelectEdge, selectedEdgeId],
  );

  const [localNodes, setLocalNodes, onNodesChange] = useNodesState(flowNodes);
  const [localEdges, setLocalEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setLocalNodes(flowNodes);
  }, [flowNodes, setLocalNodes]);

  useEffect(() => {
    setLocalEdges(flowEdges);
  }, [flowEdges, setLocalEdges]);

  const fitView = useCallback(() => {
    flowInstance?.fitView({ duration: 250, padding: 0.18 });
    onFitView();
  }, [flowInstance, onFitView]);

  function handleConnect(connection: Connection) {
    if (!connection.source || !connection.target) {
      return;
    }
    onConnectNodes({ source_stable_key: connection.source, target_stable_key: connection.target });
  }

  function handlePaneClick(event: React.MouseEvent) {
    if (mode !== "add_node") {
      return;
    }
    const position = flowInstance?.screenToFlowPosition({ x: event.clientX, y: event.clientY }) ?? { x: 420, y: 260 };
    onRequestAddNode({ x: Math.round(position.x), y: Math.round(position.y) });
  }

  const handleNodeDragStop: OnNodeDrag<FlowNode> = (_event, node) => {
    const nextNodes = localNodes.map((current) => (current.id === node.id ? node : current));
    onLayoutCommit(positionsFromFlowNodes(nextNodes));
  };

  return (
    <section className="surface-panel min-w-0 p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-slate-950">Холст</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">Все операции выполняются прямо на графе: выбор, перетаскивание, связь, проверка и сохранение схемы.</p>
        </div>
        <div className="rounded-pill border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600">
          Текущая связь: {relationTypeLabel(activeRelationType)}
        </div>
      </div>
      <div className="h-[620px] overflow-hidden rounded-xl border border-slate-900 bg-slate-950" data-testid="knowledge-react-flow-canvas">
        <ReactFlow<FlowNode, FlowEdge>
          colorMode="dark"
          edges={localEdges}
          edgeTypes={edgeTypes}
          fitView
          minZoom={0.25}
          nodeTypes={nodeTypes}
          nodes={localNodes}
          nodesDraggable={mode !== "connect"}
          onConnect={handleConnect}
          onEdgeClick={(_event, edge) => onSelectEdge(edge.id)}
          onEdgesChange={onEdgesChange}
          onInit={setFlowInstance}
          onNodeClick={(_event, node) => onSelectNode(node.id)}
          onNodeDragStop={handleNodeDragStop}
          onNodesChange={onNodesChange}
          onPaneClick={handlePaneClick}
          panOnDrag={mode === "pan"}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#1e3a5f" gap={24} />
          <Panel className="!m-4" position="top-left">
            <div className="flex max-w-[760px] flex-wrap gap-2 rounded-xl border border-slate-700 bg-slate-900/95 p-2 shadow-soft">
              <button className={modeButtonClass("select", mode)} onClick={() => onModeChange("select")} type="button">
                <MousePointer2 className="h-4 w-4" />
                Выбрать
              </button>
              <button className={modeButtonClass("connect", mode)} onClick={() => onModeChange("connect")} type="button">
                <Link2 className="h-4 w-4" />
                Связать
              </button>
              <button className={modeButtonClass("add_node", mode)} onClick={() => onModeChange("add_node")} type="button">
                <GitBranchPlus className="h-4 w-4" />
                Добавить узел
              </button>
              <button className={modeButtonClass("pan", mode)} onClick={() => onModeChange("pan")} type="button">
                <Move className="h-4 w-4" />
                Перемещение
              </button>
              <button className={modeButtonClass("lasso", mode)} onClick={() => onModeChange("lasso")} type="button">
                <LassoSelect className="h-4 w-4" />
                Область
              </button>
              <button className="inline-flex h-9 items-center gap-2 rounded-pill border border-slate-700 bg-slate-800 px-3 text-xs font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-50" disabled={!canUndo} onClick={onUndo} type="button">
                <RotateCcw className="h-4 w-4" />
                Отменить
              </button>
              <button className="inline-flex h-9 items-center gap-2 rounded-pill border border-slate-700 bg-slate-800 px-3 text-xs font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-50" disabled={!canRedo} onClick={onRedo} type="button">
                <RotateCw className="h-4 w-4" />
                Повторить
              </button>
              <button className="inline-flex h-9 items-center gap-2 rounded-pill border border-slate-700 bg-slate-800 px-3 text-xs font-semibold text-slate-100 hover:bg-slate-700" onClick={fitView} type="button">
                <LocateFixed className="h-4 w-4" />
                Показать всё
              </button>
              <button className="inline-flex h-9 items-center gap-2 rounded-pill border border-slate-700 bg-slate-800 px-3 text-xs font-semibold text-slate-100 hover:bg-slate-700" onClick={onValidate} type="button">
                <CheckCircle2 className="h-4 w-4" />
                Проверить
              </button>
              <button className="inline-flex h-9 items-center gap-2 rounded-pill border border-slate-700 bg-slate-800 px-3 text-xs font-semibold text-slate-100 hover:bg-slate-700" onClick={onAutoLayout} type="button">
                <Wand2 className="h-4 w-4" />
                Авто-схема
              </button>
            </div>
          </Panel>
          <Panel className="!m-4" position="top-right">
            <div className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold shadow-soft ${layoutDirty ? "border-amber-200 bg-amber-50 text-amber-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
              <span>{layoutDirty ? "Есть несохранённые изменения схемы" : "Схема сохранена"}</span>
              <button
                className="inline-flex h-8 items-center gap-1 rounded-pill bg-brand-600 px-3 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                disabled={savingLayout || !nodes.length}
                onClick={onSaveLayout}
                type="button"
              >
                <Save className="h-3.5 w-3.5" />
                Сохранить схему
              </button>
            </div>
          </Panel>
          <Panel className="!m-4" position="bottom-left">
            <div className="rounded-lg border border-slate-700 bg-slate-900/95 px-3 py-2 text-xs leading-5 text-slate-200 shadow-soft">
              {mode === "connect" ? "Связь: перетащите handle источника на цель или заполните черновик справа." : null}
              {mode === "add_node" ? "Добавление: кликните по свободному месту холста и заполните быстрые поля справа." : null}
              {mode === "select" ? "Выбор: кликните по узлу или подписи связи для инспектора." : null}
              {mode === "pan" ? "Перемещение: двигайте холст, затем вернитесь в режим выбора." : null}
              {mode === "lasso" ? "Область: подготовлено для группового выбора, основные действия остаются в инспекторе." : null}
            </div>
          </Panel>
          {flowEdges.length ? (
            <Panel className="!m-4" position="bottom-center">
              <div className="flex max-h-20 max-w-[560px] flex-wrap gap-2 overflow-y-auto rounded-lg border border-slate-700 bg-slate-900/95 p-2 shadow-soft">
                {flowEdges.map((edge) => (
                  <button
                    aria-label={`Выбрать связь ${relationTypeLabel(edge.data?.edge.relation_type)}`}
                    className={`rounded-pill px-3 py-1.5 text-xs font-semibold transition-colors ${
                      selectedEdgeId === edge.id ? "bg-brand-600 text-white" : "border border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700"
                    }`}
                    key={edge.id}
                    onClick={() => onSelectEdge(edge.id)}
                    type="button"
                  >
                    {relationTypeLabel(edge.data?.edge.relation_type)}
                  </button>
                ))}
              </div>
            </Panel>
          ) : null}
          <Controls position="bottom-left" showInteractive={false} />
          <MiniMap
            nodeColor={(node) => {
              const graphNode = nodes.find((item) => item.stable_key === node.id);
              return node.id === selectedStableKey ? "#22c55e" : nodeTypeColor(graphNode?.node_type);
            }}
            pannable
            position="bottom-right"
            zoomable
          />
          <Panel className="!m-4" position="bottom-right">
            <div className="rounded-lg border border-slate-700 bg-slate-900/90 px-3 py-2 text-xs font-semibold text-slate-200">
              Узлов: {nodes.length} · Связей: {localEdges.length}
            </div>
          </Panel>
          {mode === "add_node" ? (
            <Panel className="!m-4" position="top-center">
              <div className="flex items-center gap-2 rounded-xl border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-900 shadow-soft">
                <Crosshair className="h-4 w-4" />
                Кликните по холсту, чтобы выбрать место нового узла
              </div>
            </Panel>
          ) : null}
        </ReactFlow>
      </div>
    </section>
  );
}
