import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "@xyflow/react";
import { useEffect, useState, type ReactNode } from "react";
import { ScenarioResizableEditor, useScenarioEditorOffset, type ScenarioEditorOffset } from "./scenario-editor-size";

export function ScenarioMapEdge(props: EdgeProps) {
  const rename = props.data?.rename as ((title:string)=>void)|undefined;
  const [title,setTitle]=useState(String(props.label??""));
  useEffect(()=>setTitle(String(props.label??"")),[props.label]);
  const [path, x, pathY] = getSmoothStepPath(props);
  const y = pathY + Number(props.data?.labelOffset ?? 0);
  const add = props.data?.add as (() => void) | undefined;
  const select = props.data?.select as (() => void) | undefined;
  const editor = props.data?.editor as ReactNode;
  const preferenceKey = String(props.data?.preferenceKey ?? `edge:${props.id}`);
  const [savedOffset, saveOffset] = useScenarioEditorOffset(preferenceKey);
  const offset = (props.data?.editorOffset as ScenarioEditorOffset | undefined) ?? savedOffset;
  const changeOffset = (next: ScenarioEditorOffset) => { saveOffset(next); (props.data?.onEditorOffsetChange as ((value: ScenarioEditorOffset) => void) | undefined)?.(next); };
  const titleControl = rename ? <input className="studio-entry-name nodrag nopan" aria-label={`${props.data?.button ? "Текст кнопки" : "Название входа"} «${props.label}»`} onClick={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()} onPointerDown={event => event.stopPropagation()} maxLength={300} value={title} onChange={event=>setTitle(event.target.value)} onBlur={()=>{if(title.trim())rename(title.trim());else setTitle(String(props.label??""));}} onKeyDown={event=>{if(event.key==="Enter")event.currentTarget.blur();}}/> : <button type="button" className="studio-route-button nodrag nopan" title={String(props.data?.context ?? props.label ?? "")} onClick={event => { event.stopPropagation(); select?.(); }}>{props.label}</button>;
  const labelControls = <div className="studio-route-label__controls">{titleControl}{select && !editor && <button type="button" className="studio-route-edit nodrag nopan" onClick={event => { event.stopPropagation(); select(); }}>Редактировать переход</button>}{add && <button type="button" className="studio-step-plus nodrag nopan" aria-label={String(props.data?.addLabel)} onClick={event => { event.stopPropagation(); add(); }}>+</button>}</div>;
  return <><BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} />
    <EdgeLabelRenderer><div data-scenario-edge={props.id} className={`studio-route-label nodrag nopan${editor ? " is-expanded" : ""}`} style={{ transform: `translate(-50%, -50%) translate(${x + (editor ? 0 : offset.x)}px, ${y + (editor ? 0 : offset.y)}px)` }} onClick={event => { event.stopPropagation(); select?.(); }} onDoubleClick={event => { event.stopPropagation(); if (!(event.target instanceof Element && event.target.closest("input,textarea,select,[contenteditable]"))) select?.(); }}>
      {editor ? <ScenarioResizableEditor preferenceKey={preferenceKey} label="Размер редактора перехода" context="inline" dragMode="offset" getZoom={props.data?.getZoom as (() => number) | undefined} offset={offset} onOffsetChange={changeOffset}>{labelControls}{editor}</ScenarioResizableEditor> : labelControls}
    </div></EdgeLabelRenderer></>;
}
