import { useEffect, useRef, useState, type ReactNode } from "react";

type Size = { width: number; height: number };
type Props = { preferenceKey: string; label: string; children: ReactNode; getZoom?: () => number; context?: "inline" | "popover" | "full"; onResize?: () => void; onMinimumFit?: () => void };
const storageKey = (key: string) => `studio-editor-size:v1:${key}`;
function savedSize(key: string, context: Props["context"]): Size {
  const fallback = context === "full" ? { width: 900, height: 650 } : { width: 460, height: 340 };
  try { const value = JSON.parse(localStorage.getItem(storageKey(key)) || "null"); return value && Number.isFinite(value.width) && Number.isFinite(value.height) ? value : fallback; } catch { return fallback; }
}
/** UI preference only: resizing never touches the scenario definition/history. */
export function ScenarioResizableEditor({ preferenceKey, label, children, getZoom, context = "inline", onResize, onMinimumFit }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const [preferred, setPreferred] = useState(() => savedSize(preferenceKey, context));
  const [size, setSize] = useState(preferred);
  const drag = useRef<{ x: number; y: number; size: Size; zoom: number } | null>(null);
  function limits() {
    const zoom = getZoom?.() || 1;
    const bounds = context === "full" ? null : root.current?.closest(context === "inline" ? ".studio-map-canvas" : ".studio-map-main")?.getBoundingClientRect();
    const width = Math.max(1, Math.min(window.innerWidth - 48, bounds?.width || window.innerWidth - 48) / zoom - (context === "inline" ? 48 : 32));
    const height = Math.max(1, Math.min(window.innerHeight - 48, bounds?.height || window.innerHeight - 48) / zoom - (context === "inline" ? 140 : 32));
    return { width, height };
  }
  function bound(next: Size): Size {
    const available = limits();
    // Inline nodes can fit/pan their viewport; never collapse the usable editor.
    const max = context === "inline" ? { width: Math.max(280, available.width), height: Math.max(160, available.height) } : available;
    return { width: Math.round(Math.max(Math.min(280, max.width), Math.min(max.width, next.width))), height: Math.round(Math.max(Math.min(160, max.height), Math.min(max.height, next.height))) };
  }
  function resize(next: Size, persist = true) {
    const desired = { width: Math.max(280, next.width), height: Math.max(160, next.height) };
    setPreferred(desired); setSize(bound(desired));
    if (persist) try { localStorage.setItem(storageKey(preferenceKey), JSON.stringify(desired)); } catch { /* Storage may be unavailable. */ }
    onResize?.();
  }
  useEffect(() => {
    const clamp = () => {
      const available = limits(), next = bound(preferred);
      setSize(current => next.width === current.width && next.height === current.height ? current : next);
      if (context === "inline" && (available.width < 280 || available.height < 160)) onMinimumFit?.();
    };
    clamp(); window.addEventListener("resize", clamp);
    const surface = root.current?.closest(context === "inline" ? ".studio-map-canvas" : ".studio-map-main");
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(clamp) : null;
    if (surface) observer?.observe(surface);
    return () => { window.removeEventListener("resize", clamp); observer?.disconnect(); };
  }, [preferenceKey, context, getZoom, preferred.width, preferred.height]);
  return <div ref={root} className={`studio-resizable-editor is-${context} nodrag nopan nowheel`} style={{ width: size.width, height: size.height }} onClick={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()}>
    <div className="studio-resizable-editor__body">{children}</div>
    <button type="button" className="studio-editor-resize nodrag nopan" aria-label={label} title="Потяните за угол. Стрелки меняют размер; Shift — крупный шаг." onPointerDown={event => {
      if (event.button !== 0) return;
      event.preventDefault(); event.stopPropagation(); event.currentTarget.setPointerCapture?.(event.pointerId);
      drag.current = { x: event.clientX, y: event.clientY, size, zoom: getZoom?.() || 1 };
    }} onPointerMove={event => { const start = drag.current; if (!start) return; event.preventDefault(); event.stopPropagation(); resize({ width: start.size.width + (event.clientX - start.x) / start.zoom, height: start.size.height + (event.clientY - start.y) / start.zoom }); }} onPointerUp={event => { event.stopPropagation(); drag.current = null; if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }} onPointerCancel={() => { drag.current = null; }} onKeyDown={event => {
      const delta = event.shiftKey ? 60 : 20;
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
      event.preventDefault(); event.stopPropagation(); resize({ width: size.width + (event.key === "ArrowRight" ? delta : event.key === "ArrowLeft" ? -delta : 0), height: size.height + (event.key === "ArrowDown" ? delta : event.key === "ArrowUp" ? -delta : 0) });
    }}>↘ <span>{Math.round(size.width)} × {Math.round(size.height)}</span></button>
  </div>;
}
