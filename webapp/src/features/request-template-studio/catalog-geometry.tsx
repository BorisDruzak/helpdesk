import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
const key = "pc_client.studio.catalog.geometry.v1";
export function useCatalogGeometry(ref: RefObject<HTMLDivElement | null>) {
  const [widths, setWidths] = useState(() => { try { const value = JSON.parse(localStorage.getItem(key) ?? "{}"); return { left: Number.isFinite(value.left) ? value.left : 250, right: Number.isFinite(value.right) ? value.right : 380 }; } catch { return { left: 250, right: 380 }; } });
  const [width, setWidth] = useState(1200);
  useLayoutEffect(() => { const element = ref.current; if (!element) return; const measure = () => setWidth(element.getBoundingClientRect().width); measure(); const observer = new ResizeObserver(measure); observer.observe(element); return () => observer.disconnect(); }, [ref]);
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(widths)); } catch { /* Panels still resize without storage. */ } }, [widths]);
  const left = Math.max(200, Math.min(widths.left, 420, width - 300 - 340 - 16));
  const right = Math.max(300, Math.min(widths.right, 600, width - left - 340 - 16));
  function handle(side: "left" | "right") { return <CatalogResize side={side} value={side === "left" ? left : right} max={Math.max(side === "left" ? 200 : 300, width - (side === "left" ? right : left) - 340 - 16)} onChange={value => setWidths(old => ({ ...old, [side]: value }))} />; }
  return { style: { "--catalog-left": `${left}px`, "--catalog-right": `${right}px` } as CSSProperties, handle };
}
function CatalogResize({side, value, max, onChange}: {side:"left"|"right";value:number;max:number;onChange:(value:number)=>void}) {
  const start = useRef<{x:number;value:number}|null>(null), min = side === "left" ? 200 : 300, direction = side === "left" ? 1 : -1;
  const change = (next:number) => onChange(Math.max(min,Math.min(next,max,side==="left"?420:600)));
  return <div role="separator" tabIndex={0} aria-label={side==="left"?"Ширина структуры каталога":"Ширина настроек услуги"} aria-orientation="vertical" aria-valuenow={Math.round(value)} aria-valuemin={min} aria-valuemax={Math.round(max)} className="studio-map-resizer catalog-resizer"
    onPointerDown={event=>{if(event.button!==0)return;event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);start.current={x:event.clientX,value};}}
    onPointerMove={event=>{if(start.current)change(start.current.value+(event.clientX-start.current.x)*direction);}}
    onPointerUp={()=>{start.current=null;}} onPointerCancel={()=>{start.current=null;}} onLostPointerCapture={()=>{start.current=null;}}
    onKeyDown={event=>{if(!["ArrowRight","ArrowLeft","Home","End"].includes(event.key))return;event.preventDefault();change(event.key==="Home"?min:event.key==="End"?max:value+(event.key==="ArrowRight"?1:-1)*direction*(event.shiftKey?40:20));}} />;
}
