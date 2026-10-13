import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** The shell's overflow boundary prevents CSS sticky reaching document scroll. */
export function ScenarioActionBar({ children, inline = false }: { children: ReactNode; inline?: boolean }) {
  const anchor = useRef<HTMLDivElement>(null);
  const [floating, setFloating] = useState(false);
  useEffect(() => {
    if (inline || !anchor.current || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => setFloating(entry.boundingClientRect.top < 80), { rootMargin: "-80px 0px 0px 0px", threshold: [0, 1] });
    observer.observe(anchor.current);
    return () => observer.disconnect();
  }, [inline]);
  return <div ref={anchor} className="min-h-11">
    {floating ? createPortal(<div className="fixed right-4 top-20 z-30 max-w-[calc(100vw-2rem)] rounded-xl border bg-white p-3 shadow-lg">{children}</div>, document.body) : children}
  </div>;
}
