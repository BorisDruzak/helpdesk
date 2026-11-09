import { summarizeTerminalOla } from "./scenario-ola-model";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioRoute, ScenarioSlaProfile } from "./scenario-contract";
import type { ScenarioSimulation } from "./scenario-api";
import { isPolicyAttachment, policyAttachmentsFor } from "./scenario-policy-attachments-model";

export type TerminalSlaSelection = { kind: "profile" | "policy" | "server"; key?: string; source: string };
export type TerminalSlaAlternative = { route: string[]; conditional: boolean; selection: TerminalSlaSelection; profile?: ScenarioSlaProfile; routingSelection: TerminalSlaSelection; routing?: ScenarioRoute & { key: string; source: string } };
export type TerminalSlaPaths = { alternatives: TerminalSlaAlternative[]; truncated: boolean; cyclic: boolean; explored: number };
const MAX_STATES = 256, MAX_ALTERNATIVES = 64;

/** Structural alternatives only. The server remains authoritative for conditions and policy evaluation. */
export function summarizeTerminalSla(definition: ScenarioDraftDefinition, blockId: string, options: { inheritOnly?: boolean } = {}): TerminalSlaPaths {
 const result: TerminalSlaPaths = { alternatives: [], truncated: false, cyclic: false, explored: 0 };
 const blocks = new Map((definition.blocks ?? []).map(block => [block.id, block]));
 if (blocks.get(blockId)?.kind !== "submit_ticket") return result;
 const initial: TerminalSlaSelection = definition.processing && (definition.processing.defaults.sla_profile || definition.schema_version !== 4)
  ? { kind: "profile", key: definition.processing.defaults.sla_profile, source: "настройки карты по умолчанию" }
  : definition.process_binding.policy_refs?.sla
   ? { kind: "policy", key: definition.process_binding.policy_refs.sla, source: "правило обработки услуги" }
   : { kind: "server", source: "действующая серверная политика услуги" };
 const initialRouting: TerminalSlaSelection = definition.processing && (definition.processing.defaults.route || definition.schema_version !== 4) ? { kind: "profile", key: definition.processing.defaults.route, source: "настройки карты по умолчанию" } : definition.process_binding.policy_refs?.routing ? { kind: "policy", key: definition.process_binding.policy_refs.routing, source: "правило маршрутизации услуги" } : { kind: "server", source: "действующая серверная политика услуги" };
 type Pending = { id: string; visited: string[]; route: string[]; conditional: boolean; selection: TerminalSlaSelection; routingSelection: TerminalSlaSelection };
 const entrances = [
  ...(definition.entry_block_id ? [{ id: definition.entry_block_id, title: "Начало карты" }] : []),
  ...(definition.entry_points ?? []).filter(entry => entry.enabled !== false).map(entry => ({ id: entry.target_block_id, title: entry.title })),
 ];
 const pending: Pending[] = entrances.reverse().map(entry => ({ id: entry.id, visited: [], route: [entry.title], conditional: false, selection: initial, routingSelection: initialRouting }));
 while (pending.length && result.explored < MAX_STATES && result.alternatives.length < MAX_ALTERNATIVES) {
  const current = pending.pop()!; result.explored++;
  if (current.visited.includes(current.id)) { result.cyclic = true; continue; }
  const block = blocks.get(current.id); if (!block || isPolicyAttachment(block)) continue;
  const route = [...current.route, block.title], visited = [...current.visited, block.id];
  let selection = current.selection, routingSelection = current.routingSelection;

  if (definition.schema_version === 4) for (const attachment of policyAttachmentsFor(definition, block.id)) {
   const source = `настройка «${attachment.title}» у блока «${block.title}»`;
   if (attachment.kind === "sla_attachment") {
    if (definition.processing && attachment.sla_profile) selection = { kind: "profile", key: attachment.sla_profile, source };
    if (!definition.processing && attachment.policy_ref) selection = { kind: "policy", key: attachment.policy_ref, source };
   } else if (attachment.kind === "routing_attachment") {
    if (definition.processing && attachment.route) routingSelection = { kind: "profile", key: attachment.route, source };
    if (!definition.processing && attachment.policy_ref) routingSelection = { kind: "policy", key: attachment.policy_ref, source };
   }
  }
  // Server replay applies target attachments, then the executable legacy block, then its edge.
  if (block.kind === "sla") {
   if (definition.processing && block.sla_profile) selection = { kind: "profile", key: block.sla_profile, source: `блок сроков «${block.title}»` };
   if (!definition.processing && block.policy_ref) selection = { kind: "policy", key: block.policy_ref, source: `блок сроков «${block.title}»` };
  }
  if (block.id === blockId && block.kind === "submit_ticket") {
   if (definition.schema_version === 4 && !options.inheritOnly) {
    if (definition.processing && block.sla_profile) selection = { kind: "profile", key: block.sla_profile, source: `завершение «${block.title}»` };
    if (!definition.processing && block.policy_ref) selection = { kind: "policy", key: block.policy_ref, source: `завершение «${block.title}»` };
    if (definition.processing && block.route) routingSelection = { kind: "profile", key: block.route, source: `завершение «${block.title}»` };
    if (!definition.processing && block.routing_policy_ref) routingSelection = { kind: "policy", key: block.routing_policy_ref, source: `завершение «${block.title}»` };
   }
   const routing = routingSelection.kind === "profile" ? definition.processing?.routes[routingSelection.key ?? ""] : undefined;
   result.alternatives.push({ route, conditional: current.conditional, selection, routingSelection, ...(selection.kind === "profile" ? { profile: definition.processing?.sla_profiles[selection.key ?? ""] } : {}), ...(routing ? { routing: { ...routing, key: routingSelection.key!, source: routingSelection.source } } : {}) });
   continue;
  }
  if (block.kind === "finish" || block.kind === "submit_ticket") continue;
  const edges = block.transitions ?? [];
  for (let index = edges.length - 1; index >= 0; index--) {
   const edge = edges[index];
   const next = definition.processing && edge.processing?.sla_profile
    ? { kind: "profile" as const, key: edge.processing.sla_profile, source: `переход «${block.title}», ветвь ${index + 1}` } : selection;
   const conditional = current.conditional || !!edge.when || block.transition_mode === "buttons" || edges.length > 1;
   pending.push({ id: edge.to, visited, route: edges.length > 1 || edge.button ? [...route, edge.button?.label ?? `Ветвь ${index + 1}`] : route, conditional, selection: next, routingSelection: definition.processing && edge.processing?.route ? { kind: "profile", key: edge.processing.route, source: `переход «${block.title}», ветвь ${index + 1}` } : routingSelection });
  }
 }
 result.truncated = pending.length > 0;
 return result;
}

type ActualSource = { kind: string; block_id?: string; attached_to?: string; transition_index?: number };
type ActualSla = { first_response_min?: number; resolution_min?: number; time_basis?: "business" | "calendar"; source?: ActualSource; selection?: { kind: string; key: string; source?: ActualSource } };
export function actualSourceLabel(definition?: ScenarioDraftDefinition, source?: ActualSource) {
 const title = definition?.blocks?.find(item => item.id === source?.block_id)?.title ?? "Шаг сценария";
 const target = definition?.blocks?.find(item => item.id === source?.attached_to)?.title ?? "Шаг сценария";
 return source?.kind === "attachment" ? `настройка «${title}» у блока «${target}»` : source?.kind === "terminal" ? `завершение «${title}»` : source?.kind === "transition" ? `переход «${title}», ветвь ${(source.transition_index ?? 0) + 1}` : source?.kind === "block" ? `блок сроков «${title}»` : source?.kind === "default" ? "настройки карты по умолчанию" : "серверная политика услуги";
}
export function terminalActualSla(definition: ScenarioDraftDefinition, block: ScenarioBlock, result?: ScenarioSimulation) {
 if (block.kind !== "submit_ticket" || !result?.processing || result.processing_error || (result.current_step?.id ?? result.current_block?.id ?? result.state.current_block_id) !== block.id) return null;
 const sla: ActualSla = result.processing.sla;
 const map = result.map_processing ?? result.processing.map_processing;
 const source = sla.source ?? sla.selection?.source ?? map?.sla_profile?.source;
 const routing = result.processing.routing;
 const routeIds = [...(result.state.history ?? [])]; if (routeIds.at(-1) !== block.id) routeIds.push(block.id);
 return { sla, source: actualSourceLabel(definition, source), routingSource: actualSourceLabel(definition, routing.source ?? routing.selection?.source ?? map?.route?.source), route: routeIds.filter(id => !isPolicyAttachment(definition.blocks?.find(item => item.id === id)?.kind ?? "instruction")).map(id => definition.blocks?.find(item => item.id === id)?.title ?? "Шаг сценария"), queue: routing.queue_title ?? routing.queue_code ?? map?.route?.title };
}

function slaSummary(definition: ScenarioDraftDefinition, block: ScenarioBlock, simulation?: ScenarioSimulation): string {
 if (block.kind === "finish") return "Завершение без обращения · сроки поддержки не применяются";
 if (block.kind !== "submit_ticket") return "";
 const actual = terminalActualSla(definition, block, simulation);
 if (actual) return `Очередь: ${actual.queue ?? "не определена"} · Сроки проверенного пути: ответ ${actual.sla.first_response_min == null ? "не определён" : `${actual.sla.first_response_min} мин.`}, решение ${actual.sla.resolution_min == null ? "не определено" : `${actual.sla.resolution_min} мин.`} · ${actual.sla.time_basis === "business" ? "рабочее время" : actual.sla.time_basis === "calendar" ? "календарное время" : "режим времени не указан"}`;
 const result = summarizeTerminalSla(definition, block.id);
 if (!result.alternatives.length) return "Сроки: путь к завершению не найден";
 const choices = new Set(result.alternatives.map(item => `${item.selection.kind}:${item.selection.key ?? ""}`));
 const queues = new Set(result.alternatives.map(item => `${item.routingSelection.kind}:${item.routingSelection.key ?? ""}`));
 const queue = queues.size > 1 ? "Очередь зависит от пути" : result.alternatives[0].routing ? `Очередь: ${result.alternatives[0].routing!.title}` : "Очередь по правилам услуги";
 if (choices.size > 1) return `${queue} · Сроки для сотрудника зависят от пути · проверьте варианты${result.truncated || result.cyclic ? " · обзор неполный" : ""}`;
 const first = result.alternatives[0];
 const label = first.profile ? `Сроки: ${first.profile.title} · ответ ${first.profile.first_response_minutes} мин., решение ${first.profile.resolution_minutes} мин. · ${first.profile.time_basis === "business" ? "рабочее" : "календарное"} время`
  : first.selection.kind === "profile" ? "Сроки: выбранный профиль недоступен" : "Сроки по правилу услуги · сроки в проверке пути";
 return `${queue} · ${label}${result.truncated || result.cyclic ? " · обзор неполный" : ""}`;
}

/** Existing cards keep their SLA text; an OLA assignment adds an independent summary. */
export function terminalSlaSummary(definition: ScenarioDraftDefinition, block: ScenarioBlock, simulation?: ScenarioSimulation): string {
 const sla = slaSummary(definition, block, simulation);
 if (block.kind !== "submit_ticket") return sla;
 const actual = terminalActualSla(definition, block, simulation) ? simulation?.processing?.ola : undefined;
 if (actual?.enabled === false) return `${sla} · учёт внутренних сроков отключён на сервере`;
 if (actual && (actual.ack_min != null || actual.processing_min != null)) return `${sla} · Внутренние сроки: назначение исполнителя ${actual.ack_min ?? "не задано"} мин., обработка ${actual.processing_min ?? "не задана"} мин.`;
 const paths = summarizeTerminalOla(definition, block.id);
 if (!paths.alternatives.some(item => item.targets || item.policy_ref)) return sla;
 const selections = new Set(paths.alternatives.map(item => JSON.stringify([item.targets, item.policy_ref])));
 if (selections.size !== 1 || paths.truncated || paths.cyclic) return `${sla} · Внутренние сроки зависят от пути · проверьте варианты`;
 const first = paths.alternatives[0];
 return `${sla} · ${first.targets ? `Внутренние сроки: назначение исполнителя ${first.targets.ack_minutes} мин., обработка ${first.targets.processing_minutes} мин.` : "Внутренние сроки по правилу · сроки в проверке пути"}`;
}
