import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "@xyflow/react";

import type { KnowledgeGraphEdge } from "../api";
import { relationTypeLabel } from "./graphTypes";
import { EdgeToolbar } from "./EdgeToolbar";

export type GraphEdgeData = {
  edge: KnowledgeGraphEdge;
  onSelectEdge: (edgeId: string) => void;
  selectedEdgeId: string;
};

export function GraphEdge(props: EdgeProps) {
  const data = props.data as GraphEdgeData | undefined;
  const edge = data?.edge;
  const selected = Boolean(edge && data?.selectedEdgeId === edge.edge_id);
  const [edgePath, labelX, labelY] = getSmoothStepPath(props);
  const label = relationTypeLabel(edge?.relation_type);
  return (
    <>
      <BaseEdge
        markerEnd={props.markerEnd}
        path={edgePath}
        style={{
          ...props.style,
          strokeWidth: selected ? 4 : 2.5,
        }}
      />
      {edge ? (
        <EdgeLabelRenderer>
          <div
            className="absolute"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "all",
            }}
          >
            <EdgeToolbar label={label} onSelect={() => data?.onSelectEdge(edge.edge_id)} selected={selected} />
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}
