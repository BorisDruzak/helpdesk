import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioRoute, ScenarioSlaProfile } from "./scenario-contract";
import type { ScenarioSimulation } from "./scenario-api";

export type TerminalSlaSelection = { kind: "profile" | "policy" | "server"; key?: string; source: string };
export type TerminalSlaAlternative = { route: string[]; conditional: boolean; selection: TerminalSlaSelection; profile?: ScenarioSlaProfile; routing?: ScenarioRoute & { key: string; source: string } };
export type TerminalSlaPaths = { alternatives: TerminalSlaAlternative[]; truncated: boolean; cyclic: boolean; explored: number };
const MAX_STATES = 256, MAX_ALTERNATIVES = 64;

/** Structural alternatives only. The server remains authoritative for conditions and policy evaluation. */
export function summarizeTerminalSla(definition: ScenarioDraftDefinition, blockId: string, options: { inheritOnly?: boolean } = {}): TerminalSlaPaths {
 const result: TerminalSlaPaths = { alternatives: [], truncated: false, cyclic: false, explored: 0 };
 const blocks = new Map((definition.blocks ?? []).map(block => [block.id, block]));
 if (blocks.get(blockId)?.kind !== "submit_ticket") return result;
 const initial: TerminalSlaSelection = definition.processing
  ? { kind: "profile", key: definition.processing.defaults.sla_profile, source: "настройки карты по умолчанию" }
  : definition.process_binding.policy_refs?.sla
   ? { kind: "policy", key: definition.process_binding.policy_refs.sla, source: "правило обработки услуги" }
   : { kind: "server", source: "действующая серверная политика услуги" };
 type Pending = { id: string; visited: string[]; route: string[]; conditional: boolean; selection: TerminalSlaSelection; routing?: string; routingSource?: string };
 const entrances = [
  ...(definition.entry_block_id ? [{ id: definition.entry_block_id, title: "Начало карты" }] : []),
  ...(definition.entry_points ?? []).filter(entry => entry.enabled !== false).map(entry => ({ id: entry.target_block_id, title: entry.title })),
 ];
 const pending: Pending[] = entrances.reverse().map(entry => ({ id: entry.id, visited: [], route: [entry.title], conditional: false, selection: initial, routing: definition.processing?.defaults.route, routingSource: "настройки карты по умолчанию" }));
 while (pending.length && result.explored < MAX_STATES && result.alternatives.length < MAX_ALTERNATIVES) {
  const current = pending.pop()!; result.explored++;
  if (current.visited.includes(current.id)) { result.cyclic = true; continue; }
  const block = blocks.get(current.id); if (!block) continue;
  const route = [...current.route, block.title], visited = [...current.visited, block.id];
  let selection = current.selection;
  if (block.kind === "sla") {
   if (definition.processing && block.sla_profile) selection = { kind: "profile", key: block.sla_profile, source: `блок SLA «${block.title}»` };
   if (!definition.processing && block.policy_ref) selection = { kind: "policy", key: block.policy_ref, source: `блок SLA «${block.title}»` };
  }
  if (block.id === blockId && block.kind === "submit_ticket") {
   if (definition.schema_version === 4 && !options.inheritOnly) {
    if (definition.processing && block.sla_profile) selection = { kind: "profile", key: block.sla_profile, source: `завершение «${block.title}»` };
    if (!definition.processing && block.policy_ref) selection = { kind: "policy", key: block.policy_ref, source: `завершение «${block.title}»` };
   }
   const routing = current.routing ? definition.processing?.routes[current.routing] : undefined;
   result.alternatives.push({ route, conditional: current.conditional, selection, ...(selection.kind === "profile" ? { profile: definition.processing?.sla_profiles[selection.key ?? ""] } : {}), ...(routing ? { routing: { ...routing, key: current.routing!, source: current.routingSource! } } : {}) });
   continue;
  }
  if (block.kind === "finish" || block.kind === "submit_ticket") continue;
  const edges = block.transitions ?? [];
  for (let index = edges.length - 1; index >= 0; index--) {
   const edge = edges[index];
   const next = definition.processing && edge.processing?.sla_profile
    ? { kind: "profile" as const, key: edge.processing.sla_profile, source: `переход «${block.title}», ветвь ${index + 1}` } : selection;
   const conditional = current.conditional || !!edge.when || block.transition_mode === "buttons" || edges.length > 1;
   pending.push({ id: edge.to, visited, route: edges.length > 1 || edge.button ? [...route, edge.button?.label ?? `Ветвь ${index + 1}`] : route, conditional, selection: next, routing: edge.processing?.route ?? current.routing, routingSource: edge.processing?.route ? `переход «${block.title}», ветвь ${index + 1}` : current.routingSource });
  }
 }
 result.truncated = pending.length > 0;
 return result;
}

type ActualSla = { first_response_min?: number; resolution_min?: number; time_basis?: "business" | "calendar"; source?: { kind: string; block_id?: string; transition_index?: number }; selection?: { kind: string; key: string; source?: { kind: string; block_id?: string; transition_index?: number } } };
export function terminalActualSla(definition: ScenarioDraftDefinition, block: ScenarioBlock, result?: ScenarioSimulation) {
 if (block.kind !== "submit_ticket" || !result?.processing || result.processing_error || (result.current_step?.id ?? result.current_block?.id ?? result.state.current_block_id) !== block.id) return null;
 const sla: ActualSla = result.processing.sla;
 const map = result.map_processing ?? result.processing.map_processing;
 const source = sla.source ?? sla.selection?.source ?? map?.sla_profile.source;
 const title = definition.blocks?.find(item => item.id === source?.block_id)?.title ?? "Шаг сценария";
 const sourceLabel = source?.kind === "terminal" ? `завершение «${title}»` : source?.kind === "transition" ? `переход «${title}», ветвь ${(source.transition_index ?? 0) + 1}` : source?.kind === "block" ? `блок SLA «${title}»` : source?.kind === "default" ? "настройки карты по умолчанию" : "серверная политика услуги";
 return { sla, source: sourceLabel, route: [...(result.state.history ?? []), block.id].map(id => definition.blocks?.find(item => item.id === id)?.title ?? "Шаг сценария"), queue: result.processing.routing.queue_title ?? result.processing.routing.queue_code ?? map?.route.title };
}

export function terminalSlaSummary(definition: ScenarioDraftDefinition, block: ScenarioBlock, simulation?: ScenarioSimulation): string {
 if (block.kind === "finish") return "Завершение без обращения · SLA не применяется";
 if (block.kind !== "submit_ticket") return "";
 const actual = terminalActualSla(definition, block, simulation);
 if (actual) return `Очередь: ${actual.queue ?? "не определена"} · SLA проверенного пути: ответ ${actual.sla.first_response_min == null ? "не определён" : `${actual.sla.first_response_min} мин.`}, решение ${actual.sla.resolution_min == null ? "не определено" : `${actual.sla.resolution_min} мин.`} · ${actual.sla.time_basis === "business" ? "рабочее время" : actual.sla.time_basis === "calendar" ? "календарное время" : "режим времени не указан"}`;
 const result = summarizeTerminalSla(definition, block.id);
 if (!result.alternatives.length) return "SLA: путь к завершению не найден";
 const choices = new Set(result.alternatives.map(item => `${item.selection.kind}:${item.selection.key ?? ""}`));
 const queues = new Set(result.alternatives.map(item => item.routing?.key ?? ""));
 const queue = queues.size > 1 ? "Очередь зависит от пути" : result.alternatives[0].routing ? `Очередь: ${result.alternatives[0].routing!.title}` : "Очередь по правилам услуги";
 if (choices.size > 1) return `${queue} · SLA зависит от пути · проверьте варианты${result.truncated || result.cyclic ? " · обзор неполный" : ""}`;
 const first = result.alternatives[0];
 const label = first.profile ? `SLA: ${first.profile.title} · ответ ${first.profile.first_response_minutes} мин., решение ${first.profile.resolution_minutes} мин. · ${first.profile.time_basis === "business" ? "рабочее" : "календарное"} время`
  : first.selection.kind === "profile" ? "SLA: выбранный профиль недоступен" : "SLA по политике · сроки в проверке пути";
 return `${queue} · ${label}${result.truncated || result.cyclic ? " · обзор неполный" : ""}`;
}
