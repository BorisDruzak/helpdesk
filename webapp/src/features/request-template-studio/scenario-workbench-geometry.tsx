import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
const storageKey = "pc_client.studio.workbench.geometry.v1";
type Geometry = { left: number; right: number; height: number | null };
const defaults: Geometry = { left: 240, right: 360, height: null };
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, Math.max(min, max)));
function readGeometry(): Geometry {
  try { const saved = JSON.parse(localStorage.getItem(storageKey) ?? "null"); return { left: Number.isFinite(saved?.left) ? clamp(saved.left,180,480) : defaults.left, right: Number.isFinite(saved?.right) ? clamp(saved.right,280,640) : defaults.right, height: Number.isFinite(saved?.height) ? clamp(saved.height,280,1600) : null }; }
  catch { return { ...defaults }; }
}
function ResizeHandle({ axis, value, min, max, onChange }: { axis: keyof Geometry; value: number; min: number; max: number; onChange: (value: number) => void }) {
  const start = useRef<{ coordinate: number; value: number } | null>(null);
  const vertical = axis === "height", direction = axis === "right" ? -1 : 1;
  const label = axis === "left" ? "Ширина каталога и блоков" : axis === "right" ? "Ширина инспектора" : "Высота редактора";
  return <div role="separator" tabIndex={0} aria-label={label} aria-orientation={vertical ? "horizontal" : "vertical"} aria-valuenow={Math.round(value)} aria-valuemin={min} aria-valuemax={Math.round(Math.max(min,max))} className={`studio-map-resizer ${vertical ? "is-height" : ""}`} title={`${label}: перетащите или используйте клавиши со стрелками`}
    onPointerDown={event => { if(event.button!==0)return; event.preventDefault(); event.currentTarget.setPointerCapture?.(event.pointerId); start.current={coordinate: vertical?event.clientY:event.clientX,value}; }}
    onPointerMove={event => { if(start.current) onChange(clamp(start.current.value+((vertical?event.clientY:event.clientX)-start.current.coordinate)*direction,min,max)); }}
    onPointerUp={() => { start.current=null; }} onPointerCancel={() => { start.current=null; }} onLostPointerCapture={() => { start.current=null; }}
    onKeyDown={event => { const plus=vertical?"ArrowDown":"ArrowRight", minus=vertical?"ArrowUp":"ArrowLeft"; if(![plus,minus,"Home","End"].includes(event.key))return; event.preventDefault(); event.stopPropagation(); onChange(event.key==="Home"?min:event.key==="End"?max:clamp(value+(event.key===plus?1:-1)*direction*(event.shiftKey?40:20),min,max)); }} />;
}
export function useWorkbenchGeometry(grid: RefObject<HTMLDivElement | null>) {
  const [geometry,setGeometry]=useState(readGeometry);
  const [bounds,setBounds]=useState({width:1200,height:600,desktop:true});
  function measure(){const element=grid.current;if(!element)return;const next={width:element.getBoundingClientRect().width||window.innerWidth,height:Math.max(280,window.innerHeight-element.getBoundingClientRect().top-32),desktop:window.innerWidth>1100};setBounds(old=>old.width===next.width&&old.height===next.height&&old.desktop===next.desktop?old:next);}
  useLayoutEffect(measure);
  useEffect(()=>{window.addEventListener("resize",measure);const observer=new ResizeObserver(measure);if(grid.current)observer.observe(grid.current);return()=>{window.removeEventListener("resize",measure);observer.disconnect();};},[grid]);
  useEffect(()=>{try{localStorage.setItem(storageKey,JSON.stringify(geometry));}catch{/* Usable without browser storage. */}},[geometry]);
  const left=clamp(geometry.left,180,bounds.width-280-320-16),right=clamp(geometry.right,280,bounds.width-left-320-16),height=clamp(geometry.height??Math.min(720,bounds.height),280,bounds.height);
  const style={"--studio-explorer-width":`${left}px`,"--studio-inspector-width":`${right}px`,...(bounds.desktop?{height}:{} )} as CSSProperties;
  const handle=(axis:keyof Geometry)=><ResizeHandle axis={axis} value={axis==="left"?left:axis==="right"?right:height} min={axis==="left"?180:280} max={axis==="left"?Math.min(480,bounds.width-right-320-16):axis==="right"?Math.min(640,bounds.width-left-320-16):bounds.height} onChange={value=>setGeometry(old=>({...old,[axis]:value}))}/>;
  return {style,handle,reset:()=>setGeometry({...defaults})};
}
