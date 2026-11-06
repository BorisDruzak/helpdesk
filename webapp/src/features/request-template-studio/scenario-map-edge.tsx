import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "@xyflow/react";
import { useEffect, useState } from "react";

export function ScenarioMapEdge(props: EdgeProps) {
  const rename = props.data?.rename as ((title:string)=>void)|undefined;
  const [title,setTitle]=useState(String(props.label??""));
  useEffect(()=>setTitle(String(props.label??"")),[props.label]);
  const [path, x, pathY] = getSmoothStepPath(props);
  const y = pathY + Number(props.data?.labelOffset ?? 0);
  const add = props.data?.add as (() => void) | undefined;
  return <><BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} />
    <EdgeLabelRenderer><div data-scenario-edge={props.id} className="studio-route-label nodrag nopan" style={{ transform: `translate(-50%, -50%) translate(${x}px, ${y}px)` }} onClick={event => { event.stopPropagation(); (props.data?.select as (() => void) | undefined)?.(); }}>
      {rename ? <input className="studio-entry-name nodrag nopan" aria-label={`${props.data?.button ? "Текст кнопки" : "Название входа"} «${props.label}»`} onClick={event => event.stopPropagation()} onPointerDown={event => event.stopPropagation()} maxLength={300} value={title} onChange={event=>setTitle(event.target.value)} onBlur={()=>{if(title.trim())rename(title.trim());else setTitle(String(props.label??""));}} onKeyDown={event=>{if(event.key==="Enter")event.currentTarget.blur();}}/> : <button type="button" className="studio-route-button" title={String(props.data?.context ?? props.label ?? "")} onClick={event => { event.stopPropagation(); (props.data?.select as (() => void) | undefined)?.(); }}>{props.label}</button>}{add && <button type="button" className="studio-step-plus" aria-label={String(props.data?.addLabel)} onClick={event => { event.stopPropagation(); add(); }}>+</button>}
    </div></EdgeLabelRenderer></>;
}
