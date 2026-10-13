import { catalogEntries } from "./offering-card";
import type { OfferingCard, ScenarioCatalog, ScenarioItem } from "./scenario-api";
import type { ScenarioEntryPoint } from "./scenario-contract";

export type CatalogService = {
  key: string; card: OfferingCard; title: string; description: string; categoryId: string | null;
  synonyms: string[]; scenario?: ScenarioItem; entry?: ScenarioEntryPoint; activeEntry?: ScenarioEntryPoint;
  available: boolean; mode: "form" | "scenario"; draft: boolean; removedInDraft?: boolean;
};
function entrySettings(entry: ScenarioEntryPoint) { return { key:entry.key,title:entry.title,description:entry.description??"",category_id:entry.category_id??null,synonyms:entry.synonyms??[],visibility:entry.visibility??"public",enabled:entry.enabled??true,target_block_id:entry.target_block_id,reported_symptom:entry.reported_symptom??"" }; }
export function catalogServices(data: ScenarioCatalog): CatalogService[] {
  return catalogEntries(data).flatMap(card => {
    const maps = card.scenarios.filter(map => !map.archived && map.status !== "archived");
    const active = maps.find(map => map.id === card.active_scenario_id);
    const metadata = card.offering.metadata?.studio_catalog;
    const rows: CatalogService[] = [];
    const editingMap=active??maps[0];
    const matchingDraft=!editingMap?.published_entry_points?.length?editingMap?.entry_points?.find(entry=>entry.title.trim().toLocaleLowerCase()===card.offering.public_title.trim().toLocaleLowerCase()):undefined;
    // The ordinary form remains a real service while new entrances are only drafts.
    if (!active?.published_entry_points?.length) rows.push({ key: matchingDraft?`${editingMap!.id}:${matchingDraft.key}`:card.offering.full_code, card, title: card.offering.public_title,
      description: card.offering.short_description ?? "", categoryId: metadata && "category_id" in metadata ? metadata.category_id ?? null : card.category_ids[0] ?? null,
      synonyms: [...(metadata?.synonyms ?? []),...(matchingDraft?.synonyms??[])], available: card.requester_available !== false, mode: card.active_mode,
      scenario: editingMap, entry:matchingDraft, draft:!!matchingDraft });
    for (const map of maps) {
      const points = new Map((map.published_entry_points ?? []).map(entry => [entry.key, entry]));
      for (const entry of map.entry_points ?? []) points.set(entry.key, entry);
      for (const entry of points.values()) {
        if(matchingDraft&&map.id===editingMap!.id&&entry.key===matchingDraft.key)continue;
        const published = map.published_entry_points?.find(item => item.key === entry.key);
        const draftEntry = map.entry_points?.find(item => item.key === entry.key);
        const available = card.requester_available !== false && card.active_scenario_id === map.id && !!published && (map.published_public_entry_keys ?? []).includes(entry.key);
        const shown = available ? published! : entry;
        rows.push({ key: `${map.id}:${entry.key}`, card, title: shown.title, description: shown.description ?? "",
          categoryId: shown.category_id ?? map.category_id ?? null, synonyms: [...(shown.synonyms ?? []), ...(entry.synonyms ?? [])],
          scenario: map, entry, activeEntry: published, available, mode: "scenario", removedInDraft:!!published&&!draftEntry,
          draft: !published || !draftEntry || JSON.stringify(entrySettings(entry)) !== JSON.stringify(entrySettings(published)) });
      }
    }
    return rows;
  });
}
export function catalogServiceLocation(data: ScenarioCatalog, row: CatalogService) {
  const titles: string[] = [], seen = new Set<string>();
  let id = row.categoryId;
  while (id && !seen.has(id)) {
    seen.add(id); const node = data.categories.find(item => item.id === id && item.service_code === row.card.offering.service_code);
    if (!node) break;
    titles.unshift(node.title); id = node.parent_id;
  }
  titles.unshift(data.services.find(service => service.code === row.card.offering.service_code)?.public_title ?? "Раздел недоступен");
  return titles.join(" → ");
}
