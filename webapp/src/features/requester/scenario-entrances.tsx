import { useEffect, useMemo } from "react";
import type { ServiceCatalogOffering } from "./types";
import { ScenarioSession } from "./scenario-session";

export function ScenarioEntrances({ offering, owner, deviceId, initialEntryPointKey }: { offering: ServiceCatalogOffering; owner: string; deviceId: string; initialEntryPointKey?: string }) {
  const selectionKey = owner ? `pc_client.scenario.selection:${owner}:${offering.full_code}` : null;
  const items = offering.catalog_items ?? [];
  const storedEntry = useMemo(() => { try { return selectionKey ? sessionStorage.getItem(selectionKey) || undefined : undefined; } catch { return undefined; } }, [selectionKey]);
  const requestedEntry = initialEntryPointKey ?? storedEntry;
  const hasPinnedSession = useMemo(() => {
    try { return !!(owner && requestedEntry && sessionStorage.getItem(`pc_client.scenario.session:${owner}:${offering.full_code}:entry:${encodeURIComponent(requestedEntry)}`)); }
    catch { return false; }
  }, [owner, offering.full_code, requestedEntry]);
  const entry = items.some(item => item.entry_point_key === requestedEntry) || hasPinnedSession ? requestedEntry : undefined;
  useEffect(() => { if (entry && selectionKey) { try { sessionStorage.setItem(selectionKey, entry); } catch { /* Server session remains authoritative. */ } } }, [entry, selectionKey]);
  if (entry) return <ScenarioSession key={entry} offering={offering.full_code} owner={owner} deviceId={deviceId} entryPointKey={entry} />;
  if (!items.length) return <ScenarioSession offering={offering.full_code} owner={owner} deviceId={deviceId} />;
  return <p className="text-sm text-slate-600">Выберите проблему в поиске выше, чтобы начать пошаговую помощь.</p>;
}
