import type { ScenarioDraftDefinition, ScenarioOlaTargets } from "./scenario-contract";
import { isPolicyAttachment, policyAttachmentsFor } from "./scenario-policy-attachments-model";
export type OlaValue = { targets?: ScenarioOlaTargets | null; policy_ref?: string | null };
type OlaAlternative = OlaValue & { route: string[]; source: string };

/** Bounded structural alternatives; actual condition/priority checks remain server-owned. */
export function summarizeTerminalOla(definition: ScenarioDraftDefinition, blockId: string, inheritOnly = false) {
 const alternatives: OlaAlternative[] = [], blocks = new Map(definition.blocks?.map(block => [block.id, block]));
 const initial = definition.process_binding.policy_refs?.ola;
 const entries = [definition.entry_block_id, ...(definition.entry_points ?? []).filter(entry => entry.enabled !== false).map(entry => entry.target_block_id)].filter((id): id is string => !!id);
 const pending = [...new Set(entries)].map(id => ({ id, visited: [] as string[], selection: { ...(initial ? { policy_ref: initial } : {}), source: "действующие правила услуги" } as Omit<OlaAlternative, "route">, route: [] as string[] }));
 let explored = 0, cyclic = false;
 while (pending.length && explored++ < 256 && alternatives.length < 64) {
  const current = pending.pop()!, block = blocks.get(current.id);
  if (!block || isPolicyAttachment(block)) continue;
  if (current.visited.includes(block.id)) { cyclic = true; continue; }
  const route = [...current.route, block.title]; let selection = current.selection;
  if (definition.schema_version === 4) {
   for (const setting of policyAttachmentsFor(definition, block.id)) {
    const value = setting.kind === "ola_attachment" ? setting : setting.kind === "sla_attachment" ? {targets:setting.ola_targets,policy_ref:setting.ola_policy_ref} : {};
    if (value.targets || value.policy_ref) selection = { targets:value.targets,policy_ref:value.policy_ref,source:`блок «${setting.title}» у «${block.title}»` };
   }
   if (block.id === blockId && block.kind === "submit_ticket" && !inheritOnly && (block.ola_targets || block.ola_policy_ref)) selection = { targets: block.ola_targets, policy_ref: block.ola_policy_ref, source: "настройка завершающего блока" };
  }
  if (block.id === blockId) { alternatives.push({ ...selection, route }); continue; }
  for (const edge of block.transitions ?? []) pending.push({ id: edge.to, visited: [...current.visited, block.id], selection, route });
 }
 return { alternatives, truncated: !!pending.length, cyclic };
}
