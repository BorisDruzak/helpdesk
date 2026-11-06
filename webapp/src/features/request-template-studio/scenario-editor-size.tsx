import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

type Size = { width: number; height: number };
export type ScenarioEditorOffset = { x: number; y: number };
type Direction = "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw";
type Props = {
  preferenceKey: string; label: string; children: ReactNode; getZoom?: () => number;
  context?: "inline" | "popover" | "full"; onResize?: () => void; onMinimumFit?: () => void;
  /** Node mode delegates blank-space dragging to ReactFlow's native node movement. */
  dragMode?: "node" | "offset" | "none";
  offset?: ScenarioEditorOffset; onOffsetChange?: (offset: ScenarioEditorOffset) => void;
  /** Total origin delta from the gesture start; commit persists a native node's final position. */
  onOriginChange?: (delta: ScenarioEditorOffset, commit: boolean) => void;
};
const storageKey = (key: string) => `studio-editor-size:v1:${key}`;
const offsetKey = (key: string) => `studio-editor-offset:v1:${key}`;
const directions: Record<Direction, string> = { n: "верхняя граница", ne: "верхний правый угол", e: "правая граница", se: "нижний правый угол", s: "нижняя граница", sw: "нижний левый угол", w: "левая граница", nw: "верхний левый угол" };
const controls = "input,textarea,select,button,a,[contenteditable],summary,label,[data-editor-control],.studio-question-answer,.studio-rich-toolbar,.field-base";
function control(target: EventTarget | null) { return target instanceof Element ? target.closest(controls) : null; }
function savedSize(key: string, context: Props["context"]): Size {
  const fallback = context === "full" ? { width: 900, height: 650 } : { width: 460, height: 340 };
  try { const value = JSON.parse(localStorage.getItem(storageKey(key)) || "null"); return value && Number.isFinite(value.width) && Number.isFinite(value.height) ? value : fallback; } catch { return fallback; }
}
function savedOffset(key: string): ScenarioEditorOffset {
  try { const value = JSON.parse(localStorage.getItem(offsetKey(key)) || "null"); if (value && Number.isFinite(value.x) && Number.isFinite(value.y)) return value; } catch { /* Storage may be unavailable. */ }
  return { x: 0, y: 0 };
}
/** Shared by edge labels and editors; never writes scenario JSON/history. */
export function useScenarioEditorOffset(preferenceKey: string) {
  const [stored, setStored] = useState(() => ({ key: preferenceKey, value: savedOffset(preferenceKey) }));
  const value = stored.key === preferenceKey ? stored.value : savedOffset(preferenceKey);
  function change(next: ScenarioEditorOffset) {
    setStored({ key: preferenceKey, value: next });
    try { localStorage.setItem(offsetKey(preferenceKey), JSON.stringify(next)); } catch { /* Storage may be unavailable. */ }
  }
  return [value, change] as const;
}
/** UI preferences only: resizing/offsets never touch the scenario definition/history. */
export function ScenarioResizableEditor({ preferenceKey, label, children, getZoom, context = "inline", onResize, onMinimumFit, dragMode = context === "inline" ? "node" : "offset", offset: controlledOffset, onOffsetChange, onOriginChange }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const [preferred, setPreferred] = useState(() => savedSize(preferenceKey, context));
  const [size, setSize] = useState(preferred);
  const [localOffset, saveOffset] = useScenarioEditorOffset(preferenceKey);
  const offset = controlledOffset ?? localOffset;
  // Keep the preference intact when a smaller viewport temporarily limits placement.
  const [displayOffset, setDisplayOffset] = useState(offset);
  const renderedOffset = useRef(displayOffset); renderedOffset.current = displayOffset;
  const [grabbing, setGrabbing] = useState(false);
  const drag = useRef<{ x: number; y: number; size: Size; offset: ScenarioEditorOffset; zoom: number; direction?: Direction; origin?: ScenarioEditorOffset } | null>(null);
  const originChange = useRef(onOriginChange); originChange.current = onOriginChange;
  const zoom = () => { const value = getZoom?.() ?? 1; return Number.isFinite(value) && value > 0 ? value : 1; };
  function limits() {
    const scale = zoom();
    const bounds = context === "full" ? null : root.current?.closest(context === "inline" ? ".studio-map-canvas" : ".studio-map-main")?.getBoundingClientRect();
    return {
      width: Math.max(1, Math.min(window.innerWidth - 48, bounds?.width || window.innerWidth - 48) / scale - (context === "inline" ? 48 : 32)),
      height: Math.max(1, Math.min(window.innerHeight - 48, bounds?.height || window.innerHeight - 48) / scale - (context === "inline" ? 140 : 32)),
    };
  }
  function bound(next: Size): Size {
    const available = limits();
    const max = context === "inline" ? { width: Math.max(280, available.width), height: Math.max(160, available.height) } : available;
    return { width: Math.round(Math.max(Math.min(280, max.width), Math.min(max.width, next.width))), height: Math.round(Math.max(Math.min(160, max.height), Math.min(max.height, next.height))) };
  }
  function boundOffset(next: ScenarioEditorOffset) {
    if (dragMode === "offset" && root.current) {
      const rect = root.current.getBoundingClientRect(), scale = zoom();
      const surface = context === "full" ? null : root.current.closest(context === "inline" ? ".studio-map-canvas" : ".studio-map-main")?.getBoundingClientRect();
      if (context === "inline" && !surface) return next;
      const left = surface?.left ?? 0, top = surface?.top ?? 0;
      const right = surface?.right ?? window.innerWidth, bottom = surface?.bottom ?? window.innerHeight;
      const originX = rect.left - renderedOffset.current.x * scale, originY = rect.top - renderedOffset.current.y * scale;
      next = { x: Math.max((left + 8 - originX) / scale, Math.min((right - 8 - rect.width - originX) / scale, next.x)), y: Math.max((top + 8 - originY) / scale, Math.min((bottom - 8 - rect.height - originY) / scale, next.y)) };
    }
    return next;
  }
  function move(next: ScenarioEditorOffset) {
    const bounded = boundOffset(next);
    saveOffset(bounded); onOffsetChange?.(bounded);
  }
  function resize(next: Size) {
    const desired = { width: Math.max(280, next.width), height: Math.max(160, next.height) }, bounded = bound(desired);
    setPreferred(desired); setSize(bounded);
    try { localStorage.setItem(storageKey(preferenceKey), JSON.stringify(desired)); } catch { /* Storage may be unavailable. */ }
    onResize?.(); return bounded;
  }
  useEffect(() => { setPreferred(savedSize(preferenceKey, context)); }, [preferenceKey, context]);
  useLayoutEffect(() => {
    if (dragMode !== "offset") return;
    const clamp = () => {
      const next = boundOffset(offset);
      setDisplayOffset(current => current.x === next.x && current.y === next.y ? current : next);
    };
    clamp(); window.addEventListener("resize", clamp);
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(clamp) : null;
    const surface = root.current?.closest(context === "inline" ? ".studio-map-canvas" : ".studio-map-main");
    if (root.current) observer?.observe(root.current);
    if (surface) observer?.observe(surface);
    return () => { window.removeEventListener("resize", clamp); observer?.disconnect(); };
  }, [preferenceKey, context, dragMode, getZoom, size.width, size.height, offset.x, offset.y]);
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
  useEffect(() => {
    const stop = () => stopDrag();
    window.addEventListener("pointerup", stop); window.addEventListener("pointercancel", stop); window.addEventListener("blur", stop);
    return () => { window.removeEventListener("pointerup", stop); window.removeEventListener("pointercancel", stop); window.removeEventListener("blur", stop); };
  }, []);
  function stopDrag() {
    const origin = drag.current?.origin;
    drag.current = null; setGrabbing(false);
    if (origin) originChange.current?.(origin, true);
  }
  function applyResize(direction: Direction, start: Size, startOffset: ScenarioEditorOffset, dx: number, dy: number, commit = false) {
    const next = resize({ width: start.width + (direction.includes("w") ? -dx : direction.includes("e") ? dx : 0), height: start.height + (direction.includes("n") ? -dy : direction.includes("s") ? dy : 0) });
    if (direction.includes("w") || direction.includes("n")) {
      const delta = { x: direction.includes("w") ? start.width - next.width : 0, y: direction.includes("n") ? start.height - next.height : 0 };
      if (dragMode === "offset") move({ x: startOffset.x + delta.x, y: startOffset.y + delta.y });
      else if (dragMode === "node" && onOriginChange) {
        if (drag.current && !commit) drag.current.origin = delta;
        onOriginChange(delta, commit);
      }
    }
  }
  return <div ref={root} className={`studio-resizable-editor is-${context} ${dragMode === "node" ? "" : "nodrag"} nopan nowheel${dragMode !== "none" ? " is-grabbable" : ""}${grabbing ? " is-grabbing" : ""}`} style={{ width: size.width, height: size.height, "--studio-resize-hit": `${20 / zoom()}px`, "--studio-resize-corner": `${28 / zoom()}px`, "--studio-resize-grip": `${10 / zoom()}px`, "--studio-resize-stroke": `${2 / zoom()}px`, ...(dragMode === "offset" ? { transform: `translate(${displayOffset.x}px, ${displayOffset.y}px)` } : {}) } as CSSProperties} onClick={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()}
    onMouseDownCapture={event => { control(event.target)?.classList.add("nodrag"); }}
    onMouseDown={event => { if (control(event.target)) event.stopPropagation(); }}
    onPointerDown={event => {
      if (control(event.target)) { event.stopPropagation(); return; }
      if (event.button !== 0 || dragMode === "none") return;
      if (event.target instanceof HTMLElement && event.target.scrollHeight > event.target.clientHeight && event.target.clientWidth > 0) {
        const rect = event.target.getBoundingClientRect(); if (event.clientX >= rect.left + event.target.clientWidth) return;
      }
      setGrabbing(true);
      if (dragMode === "node") return;
      event.preventDefault(); event.stopPropagation(); event.currentTarget.setPointerCapture?.(event.pointerId);
      drag.current = { x: event.clientX, y: event.clientY, size, offset: displayOffset, zoom: zoom() };
    }}
    onPointerMove={event => {
      const start = drag.current; if (!start) return;
      event.preventDefault(); event.stopPropagation();
      const dx = (event.clientX - start.x) / start.zoom, dy = (event.clientY - start.y) / start.zoom;
      if (start.direction) applyResize(start.direction, start.size, start.offset, dx, dy);
      else move({ x: start.offset.x + dx, y: start.offset.y + dy });
    }} onPointerUp={stopDrag} onPointerCancel={stopDrag} onLostPointerCapture={stopDrag}>
    <div className="studio-resizable-editor__body">{children}</div>
    {(Object.entries(directions) as [Direction, string][]).map(([direction, name]) => <button key={direction} type="button" data-resize-direction={direction} className={`studio-editor-resize is-${direction} nodrag nopan`} aria-label={direction === "se" ? label : `${label}: ${name}`} title={`${name}. Потяните за границу; стрелки меняют размер, Shift — крупный шаг.`} onPointerDown={event => {
      if (event.button !== 0) return;
      event.preventDefault(); event.stopPropagation(); event.currentTarget.setPointerCapture?.(event.pointerId);
      drag.current = { x: event.clientX, y: event.clientY, size, offset: displayOffset, zoom: zoom(), direction };
    }} onKeyDown={event => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
      event.preventDefault(); event.stopPropagation(); const step = event.shiftKey ? 60 : 20;
      applyResize(direction, size, displayOffset, event.key === "ArrowRight" ? step : event.key === "ArrowLeft" ? -step : 0, event.key === "ArrowDown" ? step : event.key === "ArrowUp" ? -step : 0, true);
    }} />)}
  </div>;
}
