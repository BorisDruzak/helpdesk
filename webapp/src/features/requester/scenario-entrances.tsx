import { useEffect, useState } from "react";
import type { ServiceCatalogOffering } from "./types";
import { ScenarioSession } from "./scenario-session";

export function ScenarioEntrances({ offering, owner, deviceId, initialEntryPointKey, onBrowse }: { offering: ServiceCatalogOffering; owner: string; deviceId: string; initialEntryPointKey?: string; onBrowse?:()=>void }) {
  const selectionKey = owner ? `pc_client.scenario.selection:${owner}:${offering.full_code}` : null;
  const [entry, setEntry] = useState<string | undefined>(() => { if (initialEntryPointKey) return initialEntryPointKey; if (onBrowse) return undefined; try { return selectionKey ? sessionStorage.getItem(selectionKey) || undefined : undefined; } catch { return undefined; } });
  useEffect(() => { if (initialEntryPointKey && selectionKey) { try { sessionStorage.setItem(selectionKey, initialEntryPointKey); } catch { /* Server session remains authoritative. */ } } }, [initialEntryPointKey, selectionKey]);
  function choose(value: string | undefined) { setEntry(value); if (selectionKey) { try { if (value) sessionStorage.setItem(selectionKey, value); else sessionStorage.removeItem(selectionKey); } catch { /* Server session is authoritative. */ } } }
  const items = offering.catalog_items ?? [];
  if (!items.length) return <ScenarioSession offering={offering.full_code} owner={owner} deviceId={deviceId} />;
  if (entry) return <div className="grid gap-3"><button type="button" className="text-left underline" onClick={() => {choose(undefined);onBrowse?.();}}>Другой пункт каталога</button><ScenarioSession key={entry} offering={offering.full_code} owner={owner} deviceId={deviceId} entryPointKey={entry} /></div>;
  if(onBrowse) return null;
  return <section className="grid gap-3" aria-label="Пункты каталога">{items.map(item => <button key={item.key} type="button" className="rounded-xl border bg-white p-4 text-left" onClick={() => choose(item.entry_point_key)}><span className="block font-semibold">{item.title}</span><span className="block text-sm">{item.description}</span></button>)}</section>;
}
