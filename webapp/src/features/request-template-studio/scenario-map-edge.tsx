import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "@xyflow/react";

export function ScenarioMapEdge(props: EdgeProps) {
  const [path, x, pathY] = getSmoothStepPath(props);
  const y = pathY + Number(props.data?.labelOffset ?? 0);
  const add = props.data?.add as (() => void) | undefined;
  return <><BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} />
    <EdgeLabelRenderer><div className="studio-route-label nodrag nopan" style={{ transform: `translate(-50%, -50%) translate(${x}px, ${y}px)` }} onClick={event => { event.stopPropagation(); (props.data?.select as (() => void) | undefined)?.(); }}>
      <span>{props.label}</span>{add && <button type="button" className="studio-step-plus" aria-label={String(props.data?.addLabel)} onClick={event => { event.stopPropagation(); add(); }}>+</button>}
    </div></EdgeLabelRenderer></>;
}
