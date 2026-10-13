import type { ScenarioDraftDefinition } from "./scenario-contract";
import { terminal } from "./scenario-map-model";
export type MapHint = { code: string; text: string; level: "required" | "suggestion"; target?: "catalog" | "blocks"; blockId?: string };
/** Authoring guidance only; canonical publication remains the complete readiness check. */
export function scenarioMapHints(definition: ScenarioDraftDefinition): MapHint[] {
  const hints: MapHint[] = [], blocks = definition.blocks ?? [], ids = new Set(blocks.map(block => block.id));
  const add = (code: string, text: string, blockId?: string) => hints.push({ code, text, blockId, level: "required" });
  if (!definition.offering_full_code) hints.push({ code: "offering", text: "Выберите услугу в каталоге слева.", target: "catalog", level: "required" });
  else if (!definition.process_binding.request_template_key) add("template", "Привяжите к услуге шаблон обработки обращения.");
  if (!definition.title.trim()) add("title", "Укажите название карты в «Начало».");
  if (!blocks.length) hints.push({ code: "blocks", text: "Добавьте вопрос или инструкцию из библиотеки блоков.", target: "blocks", level: "required" });
  else {
    if (!definition.entry_block_id || !ids.has(definition.entry_block_id)) add("start", "Выберите основной вход карты в «Начало».");
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
  }
  if (!(definition.entry_points ?? []).length) hints.push({ code: "catalog_entrances", text: "Для отдельных пунктов каталога добавьте точки входа в инспекторе блока. Основной вход карты продолжает работать.", level: "suggestion" });
  return hints;
}
