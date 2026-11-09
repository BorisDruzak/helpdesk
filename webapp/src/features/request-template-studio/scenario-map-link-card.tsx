import { useEffect, useState, type ReactNode } from "react";
import { Handle, Position } from "@xyflow/react";
import { ScenarioResizableEditor } from "./scenario-editor-size";

export type MapLinkCard = {
  edgeId: string; positionKey: string; title: string; context: string; targetTitle: string;
  route?: { source: string; index: number }; entrance?: { key: string | null; target: string; pending?:boolean };
  disabled: boolean; rename?: (title: string) => void; select: () => void;
  add?: () => void; addLabel?: string;
};
export function ScenarioMapLinkCard({ link, selected, editor, preferenceKey, getZoom, onOriginChange, onResize, onMinimumFit }: {
  link: MapLinkCard; selected?: boolean; editor?: ReactNode; preferenceKey: string; getZoom?: () => number;
  onOriginChange?: (delta: {x:number;y:number},commit:boolean)=>void; onResize?:()=>void; onMinimumFit?:()=>void;
}) {
  const [title,setTitle]=useState(link.title);
  useEffect(()=>setTitle(link.title),[link.title]);
  return <div data-scenario-edge={link.edgeId} className={`studio-map-node studio-map-link-card${selected ? " is-selected" : ""}${editor ? " is-expanded" : ""}`} onDoubleClick={event=>{event.stopPropagation();if(!(event.target instanceof Element && event.target.closest("input,textarea,select,[contenteditable]")))link.select();}}>
    {!link.entrance && <Handle type="target" id="in" position={Position.Left} isConnectable={false}/>}
    <Handle type="source" id="out" position={Position.Right} isConnectable={!link.disabled} aria-label={`Изменить назначение «${link.title}»`}/>
    <div className="studio-map-node__kind">{link.entrance ? "Вход из каталога" : "Переход"}</div>
    <p className="studio-map-link-card__context">{link.context}</p>
    {link.rename ? <input className="studio-entry-name nodrag nopan" aria-label={`${link.entrance ? "Название входа" : "Текст кнопки"} «${link.title}»`} disabled={link.disabled} maxLength={300} value={title} onChange={event=>setTitle(event.target.value)} onClick={event=>event.stopPropagation()} onDoubleClick={event=>event.stopPropagation()} onBlur={()=>{if(title.trim())link.rename?.(title.trim());else setTitle(link.title);}} onKeyDown={event=>{event.stopPropagation();if(event.key==="Enter")event.currentTarget.blur();}}/> : <button type="button" className="studio-route-button nodrag nopan" onClick={event=>{event.stopPropagation();link.select();}}>{link.title}</button>}
    <button type="button" className="studio-node-edit nodrag nopan" onClick={event=>{event.stopPropagation();link.select();}}>{editor ? "Свернуть редактор" : link.entrance ? "Редактировать вход" : "Редактировать переход"}</button>
    {editor && <ScenarioResizableEditor preferenceKey={preferenceKey} label={link.entrance ? "Размер редактора входа" : "Размер редактора перехода"} getZoom={getZoom} onOriginChange={onOriginChange} onResize={onResize} onMinimumFit={onMinimumFit}><div className="studio-inline-editor nopan nowheel">{editor}</div></ScenarioResizableEditor>}
    <p className="studio-map-link-card__target">{link.entrance?.pending?"Тяните связь справа к первому блоку →":`→ ${link.targetTitle}`}</p>
    {link.add && <button type="button" className="studio-node-add nodrag nopan" aria-label={link.addLabel} onClick={event=>{event.stopPropagation();link.add?.();}}>+ Вставить шаг</button>}
  </div>;
}
