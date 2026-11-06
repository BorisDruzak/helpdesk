import { useMemo, useState } from "react";
import type { ScenarioTransition } from "./scenario-contract";

export type MapPoint = { x: number; y: number };
const keyFor = (scenario: string) => `studio-map-link-positions:v1:${scenario}`;
const valid = (point: MapPoint) => Number.isFinite(point?.x) && Number.isFinite(point?.y) && Math.abs(point.x) <= 100000 && Math.abs(point.y) <= 100000;
function read(scenario: string): Record<string, MapPoint> {
  try { const value = JSON.parse(localStorage.getItem(keyFor(scenario)) ?? "{}"); return Object.fromEntries(Object.entries(value).filter((entry): entry is [string, MapPoint] => valid(entry[1] as MapPoint))); } catch { return {}; }
}
/** Local layout only. Stable action/entry identities keep geometry through reordering. */
export function entranceLayoutKey(key: string | null) {
  return key === null ? "entry:implicit" : `entry:named:${key}`;
}
export function routeLayoutKey(source: string, edge: ScenarioTransition, occurrence = 0) {
  return edge.button ? `route:${source}:action:${edge.button.key}` : `route:${source}:${JSON.stringify([edge.to, canonical(edge.when ?? null)])}:${occurrence}`;
}
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  return value && typeof value === "object" ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)])) : value;
}
export function useMapLinkLayout(scenario: string) {
  const [state, setState] = useState(() => ({ scenario, positions: read(scenario) }));
  const positions = useMemo(() => state.scenario === scenario ? state.positions : read(scenario), [scenario, state]);
  function move(key: string, point: MapPoint) {
    if (!valid(point)) return;
    setState(current => {
      const next = { ...(current.scenario === scenario ? current.positions : read(scenario)), [key]: point };
      try { localStorage.setItem(keyFor(scenario), JSON.stringify(next)); } catch { /* Layout stays usable when storage is unavailable. */ }
      return { scenario, positions: next };
    });
  }
  return { positions, move };
}
