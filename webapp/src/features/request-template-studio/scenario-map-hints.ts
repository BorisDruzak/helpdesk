import type { ScenarioCondition, ScenarioDraftDefinition } from "./scenario-contract";
import { terminal } from "./scenario-map-model";
export type MapHint = { code: string; text: string; level: "required" | "suggestion"; target?: "catalog" | "blocks"; blockId?: string };
function confirmsResolution(condition: ScenarioCondition | null | undefined): boolean {
  if (!condition) return false;
  if (condition.op === "and") return condition.conditions.some(confirmsResolution);
  if (condition.op === "or") return !!condition.conditions.length && condition.conditions.every(confirmsResolution);
  if (condition.op === "not") return "source" in condition.condition && condition.condition.source === "current_result" && condition.condition.op === "neq" && condition.condition.value === "yes";
  if (!("source" in condition) || condition.source !== "current_result") return false;
  return condition.op === "eq" && condition.value === "yes" || condition.op === "in" && !!condition.value.length && condition.value.every(value => value === "yes");
}
/** Authoring guidance only; canonical publication remains the complete readiness check. */
export function scenarioMapHints(definition: ScenarioDraftDefinition): MapHint[] {
  const hints: MapHint[] = [], blocks = definition.blocks ?? [], ids = new Set(blocks.map(block => block.id));
  const add = (code: string, text: string, blockId?: string) => hints.push({ code, text, blockId, level: "required" });
  const result = blocks.find(block => block.kind === "submit_ticket");
  if (definition.schema_version !== 2 && !definition.offering_full_code) add("offering", "Выберите тип обращения, чтобы сохранить черновик.", result?.id);
  else if (definition.schema_version !== 2 && !definition.process_binding.request_template_key) add("template", "Для обращения не выбран шаблон заявки.", result?.id);
  if (!definition.title.trim()) add("title", "Укажите название в настройках карты.");
  if (!blocks.length) hints.push({ code: "blocks", text: "Добавьте первый шаг: вопрос или инструкцию.", target: "blocks", level: "required" });
  else {
    if (!definition.entry_block_id || !ids.has(definition.entry_block_id)) add("start", "Соедините «Начало» с первым вопросом или инструкцией.");
    for (const entry of definition.entry_points ?? []) if (!ids.has(entry.target_block_id)) add("entry_target", `«${entry.title}»: пункт каталога не связан с блоком.`, entry.target_block_id);
    if (!blocks.some(block => terminal(block.kind))) hints.push({ code: "result", text: "Добавьте «Результат»: создание обращения или завершение без обращения.", target: "blocks", level: "required" });
    const reached = new Set<string>(), pending = [definition.entry_block_id, ...(definition.entry_points ?? []).map(entry => entry.target_block_id)].filter((id): id is string => !!id);
    while (pending.length) { const id = pending.pop()!; if (reached.has(id)) continue; reached.add(id); pending.push(...(blocks.find(block => block.id === id)?.transitions ?? []).map(edge => edge.to)); }
    for (const block of blocks) {
      if (!reached.has(block.id)) add("disconnected", `«${block.title}»: соедините с маршрутом или назначьте точку входа.`, block.id);
      if (!terminal(block.kind) && !block.transitions?.length) add("missing_route", `«${block.title}»: укажите следующий шаг.`, block.id);
      if (block.transitions?.some(edge => !ids.has(edge.to))) add("missing_target", `«${block.title}»: переход ведёт к удалённому блоку.`, block.id);
      if (block.kind === "instruction" && !block.content.body.trim()) add("instruction_empty", `«${block.title}»: заполните текст инструкции.`, block.id);
      if (block.kind === "form_page" && !block.fields.length) add("questions", `«${block.title}»: добавьте хотя бы один вопрос.`, block.id);
    }
    const visited = new Set<string>(), routes = [definition.entry_block_id, ...(definition.entry_points ?? []).map(entry => entry.target_block_id)].filter((id): id is string => !!id).map(id => ({ id, confirmed: false }));
    while (routes.length) {
      const state = routes.pop()!, key = `${state.id}:${state.confirmed}`;
      if (visited.has(key)) continue; visited.add(key);
      const block = blocks.find(item => item.id === state.id); if (!block) continue;
      if (block.kind === "finish" && !state.confirmed && !hints.some(hint => hint.code === "unconfirmed_finish" && hint.blockId === block.id)) add("unconfirmed_finish", `«${block.title}»: перед завершением нужна положительная проверка решения.`, block.id);
      for (const edge of block.transitions ?? []) routes.push({ id: edge.to, confirmed: state.confirmed || (block.kind === "resolution_check" && confirmsResolution(edge.when)) });
    }
  }
  if (!(definition.entry_points ?? []).length) hints.push({ code: "catalog_entrances", text: "Проведите линию от «Начала» к блоку, чтобы создать пункт каталога.", level: "suggestion" });
  return hints;
}
