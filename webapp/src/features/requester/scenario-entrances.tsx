import { useEffect, useState } from "react";
import type { ServiceCatalogOffering } from "./types";
import { ScenarioSession } from "./scenario-session";

export function ScenarioEntrances({ offering, owner, deviceId, initialEntryPointKey }: { offering: ServiceCatalogOffering; owner: string; deviceId: string; initialEntryPointKey?: string }) {
  const [query, setQuery] = useState("");
  const selectionKey = owner ? `pc_client.scenario.selection:${owner}:${offering.full_code}` : null;
  const [entry, setEntry] = useState<string | undefined>(() => { if (initialEntryPointKey) return initialEntryPointKey; try { return selectionKey ? sessionStorage.getItem(selectionKey) || undefined : undefined; } catch { return undefined; } });
  useEffect(() => { if (initialEntryPointKey && selectionKey) { try { sessionStorage.setItem(selectionKey, initialEntryPointKey); } catch { /* Server session remains authoritative. */ } } }, [initialEntryPointKey, selectionKey]);
  function choose(value: string | undefined) { setEntry(value); if (selectionKey) { try { if (value) sessionStorage.setItem(selectionKey, value); else sessionStorage.removeItem(selectionKey); } catch { /* Server session is authoritative. */ } } }
  const items = offering.catalog_items ?? [];
  if (!items.length) return <ScenarioSession offering={offering.full_code} owner={owner} deviceId={deviceId} />;
  if (entry) return <div className="grid gap-3"><button type="button" className="text-left underline" onClick={() => choose(undefined)}>Другой пункт каталога</button><ScenarioSession key={entry} offering={offering.full_code} owner={owner} deviceId={deviceId} entryPointKey={entry} /></div>;
  const visible = items.filter(item => [item.title, item.description, ...item.synonyms].join(" ").toLocaleLowerCase().includes(query.toLocaleLowerCase().trim()));
  return <section className="grid gap-3" aria-label="Пункты каталога"><label>Найти проблему<input className="field-base block w-full" value={query} onChange={event => setQuery(event.target.value)} /></label>{visible.length ? visible.map(item => <button key={item.key} type="button" className="rounded-xl border bg-white p-4 text-left" onClick={() => choose(item.entry_point_key)}><span className="block font-semibold">{item.title}</span><span className="block text-sm">{item.description}</span></button>) : <p>Пункты каталога не найдены.</p>}</section>;
}
