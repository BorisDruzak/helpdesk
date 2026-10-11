import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "../../components/ui/button";
import type { ScenarioBlock } from "./scenario-contract";
import { ScenarioBlockPreview } from "./scenario-block-preview";

export function ScenarioPreviewPanel({ block, onClose }: { block: ScenarioBlock; onClose: () => void }) {
  const [wide, setWide] = useState(() => window.matchMedia("(min-width: 1440px)").matches);
  const controlsRef = useRef<HTMLDivElement>(null);
  const focusClose = () => controlsRef.current?.querySelector("button")?.focus();
  useEffect(() => {
    const query = window.matchMedia("(min-width: 1440px)");
    const change = () => setWide(query.matches);
    query.addEventListener("change", change);
    return () => query.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    if (wide) return;
    const previous = document.activeElement;
    focusClose();
    return () => { if (previous instanceof HTMLElement && previous.isConnected) previous.focus(); };
  }, [wide]);
  if (wide) return <aside aria-label="Предпросмотр выбранного шага" className="min-w-0"><ScenarioBlockPreview block={block} /></aside>;
  return createPortal(<div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section role="dialog" aria-modal="true" aria-label="Предпросмотр выбранного шага" className="h-full w-full max-w-md space-y-4 overflow-y-auto bg-white p-5 shadow-xl" onKeyDown={event => {
      if (event.key === "Escape") { event.stopPropagation(); onClose(); }
      // The drawer has one interactive control; keep keyboard focus inside it.
      if (event.key === "Tab") { event.preventDefault(); focusClose(); }
    }}>
      <div ref={controlsRef}><Button variant="secondary" onClick={onClose}>Закрыть предпросмотр</Button></div>
      <ScenarioBlockPreview block={block} />
    </section>
  </div>, document.body);
}
