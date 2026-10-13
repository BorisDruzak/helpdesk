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
  return catalogEntries(data).map(card => {
    const maps=card.scenarios.filter(map=>!map.archived&&map.status!=="archived");
    const scenario=maps.find(map=>map.id===card.active_scenario_id)??maps[0];
    const metadata=card.offering.metadata?.studio_catalog;
    return {key:card.offering.full_code,card,title:scenario?.title??card.offering.public_title,
      description:scenario?.description??card.offering.short_description??"",categoryId:scenario?.category_id??metadata?.category_id??card.category_ids[0]??null,
      synonyms:[...(metadata?.synonyms??[]),...(scenario?.entry_points??[]).flatMap(entry=>[entry.title,...(entry.synonyms??[])])],
      available:card.requester_available!==false,mode:scenario?"scenario" as const:"form" as const,
      scenario,draft:!!scenario&&(scenario.status!=="published"||!!scenario.issues?.length||JSON.stringify((scenario.entry_points??[]).map(entrySettings))!==JSON.stringify((scenario.published_entry_points??[]).map(entrySettings)))};
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
