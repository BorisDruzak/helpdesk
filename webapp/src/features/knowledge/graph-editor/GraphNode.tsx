import { Handle, NodeToolbar as FlowNodeToolbar, Position, type NodeProps } from "@xyflow/react";

import type { KnowledgeGraphNode } from "../api";
import { nodeTypeClassName, nodeTypeShortLabel } from "./graphTypes";
import { NodeInlineToolbar } from "./NodeToolbar";

export type GraphNodeData = {
  node: KnowledgeGraphNode;
  onArchiveNode: (stableKey: string) => void;
  onDuplicateNode: (node: KnowledgeGraphNode) => void;
  onEditNode: (stableKey: string) => void;
  onOpenArticle: (node: KnowledgeGraphNode) => void;
  onStartConnect: (stableKey: string) => void;
};

export function GraphNode({ data, selected }: NodeProps) {
  const graphData = data as GraphNodeData;
  const node = graphData.node;
  const canOpenArticle = Boolean(node.linked_item_id);
  return (
    <div
      className={`relative min-h-[92px] w-[230px] rounded-lg border-2 bg-white px-4 py-3 shadow-sm transition-colors ${
        selected ? "border-brand-500 bg-brand-50" : "border-slate-300"
      }`}
      style={{ borderColor: selected ? "#157243" : undefined }}
    >
      <FlowNodeToolbar isVisible={selected} offset={12} position={Position.Top}>
        <NodeInlineToolbar
          canOpenArticle={canOpenArticle}
          onArchive={() => graphData.onArchiveNode(node.stable_key)}
          onConnect={() => graphData.onStartConnect(node.stable_key)}
          onDuplicate={() => graphData.onDuplicateNode(node)}
          onEdit={() => graphData.onEditNode(node.stable_key)}
          onOpenArticle={() => graphData.onOpenArticle(node)}
        />
      </FlowNodeToolbar>
      <Handle className="!h-3 !w-3 !border-2 !border-white !bg-emerald-500" id="target" position={Position.Left} type="target" />
      <Handle className="!h-3 !w-3 !border-2 !border-white !bg-emerald-500" id="source" position={Position.Right} type="source" />
      <div className="space-y-2">
        <p className="line-clamp-2 text-sm font-semibold leading-5 text-slate-950">{node.label}</p>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-pill border px-2 py-0.5 text-[11px] font-semibold ${nodeTypeClassName(node.node_type)}`}>
            {nodeTypeShortLabel(node.node_type)}
          </span>
          {node.status === "archived" ? <span className="rounded-pill bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700">Архив</span> : null}
        </div>
      </div>
    </div>
  );
}
