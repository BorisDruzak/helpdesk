import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioProcessingFacts } from "./scenario-contract";
import { newKey } from "./scenario-builder-model";
import { requireAcyclic, stableMapPositions } from "./scenario-map-model";
export const builtinFragments = [
  { key: "ola", title: "OLA: подтверждение и обработка" },
  { key: "details", title: "Описание проблемы со скриншотом" },
  { key: "instruction", title: "Инструкция → проверка результата" },
  { key: "impact", title: "Влияние на SLA — масштаб" },
  { key: "urgency", title: "Влияние на SLA — срочность" },
  { key: "navigation", title: "Меню без сохранения ответа" },
] as const;
export type BuiltinFragmentKey = typeof builtinFragments[number]["key"];
export function insertBuiltinFragment(definition: ScenarioDraftDefinition, key: BuiltinFragmentKey, position: { x: number; y: number }): ScenarioDraftDefinition {
  if (definition.schema_version !== 4) throw new Error("Включите новые возможности карты перед добавлением фрагментов.");
  const id = () => newKey("block"), fieldKey = newKey("field"), entry = id(), end = id();
  const ending: ScenarioBlock = { id: end, kind: "submit_ticket", title: "Создание обращения", transitions: [] };
  let blocks: ScenarioBlock[];
  if (key === "ola") blocks = [{id:entry,kind:"instruction",title:"Обработка группой",content:{body:"Опишите действия группы поддержки"},transitions:[{to:end}]}, ending, {id:id(),kind:"ola_attachment",title:"OLA группы",attached_to:entry,targets:{ack_minutes:15,processing_minutes:240}}];
  else if (key === "details") blocks = [{ id: entry, kind: "form_page", title: "Опишите проблему", layout: "single", fields: [{ key: fieldKey, type: "textarea", label: "Что произошло?", help_text: "Опишите действия и добавьте скриншот, если он поможет объяснить проблему.", required: true }], transitions: [{ to: end }] }, ending];
  else if (key === "navigation") blocks = [{ id: entry, kind: "navigation", title: "Выберите дальнейшее действие", transition_mode: "buttons", transitions: [{ to: end, button: { key: newKey("action"), label: "Обратиться в поддержку" } }] }, ending];
  else if (key === "instruction") {
    const check = id(), finish = id();
    blocks = [{ id: entry, kind: "instruction", title: "Попробуйте решение", content: { body: "Опишите последовательность действий", format: "plain" }, acknowledgment_required: true, transitions: [{ to: check }] }, { id: check, kind: "resolution_check", title: "Удалось решить проблему?", transitions: [{ to: finish, when: { source: "current_result", op: "eq", value: "yes" } }, { to: end }] }, { id: finish, kind: "finish", title: "Проблема решена", message: "Работа восстановлена, обращение не требуется", transitions: [] }, ending];
  } else {
    const check = id(), dimension: keyof ScenarioProcessingFacts = key;
    const choices = key === "impact" ? [{ value: "single_user", label: "Один пользователь" }, { value: "multiple_users", label: "Несколько пользователей" }, { value: "department", label: "Целое подразделение" }] : [{ value: "can_work", label: "Можно продолжать работу" }, { value: "degraded", label: "Работа затруднена" }, { value: "blocked", label: "Работа остановлена" }];
    const sla: ScenarioBlock[] = choices.map(choice => ({ id: id(), kind: "sla", title: `SLA · ${choice.label}`, processing_facts: { [dimension]: choice.value } as ScenarioProcessingFacts, transitions: [{ to: end }] }));
    blocks = [{ id: entry, kind: "form_page", title: key === "impact" ? "Кого затронула проблема?" : "Можно ли продолжать работу?", layout: "single", fields: [{ key: fieldKey, label: key === "impact" ? "Кого затронула проблема?" : "Можно ли продолжать работу?", type: "radio", required: true, options: choices }], transitions: [{ to: check }] }, { id: check, kind: "decision", title: "Влияние ответа на SLA", transitions: [...choices.map((choice, index) => ({ to: sla[index].id, when: { source: "answer" as const, field: fieldKey, op: "eq" as const, value: choice.value } })), { to: end }] }, ...sla, ending];
  }
  if ((definition.blocks?.length ?? 0) + blocks.length > 256) throw new Error("Фрагмент превысит лимит 256 блоков карты.");
  const positions = { ...stableMapPositions(definition), ...Object.fromEntries(blocks.map((block, index) => [block.id, { x: position.x + (index % 3) * 310, y: position.y + Math.floor(index / 3) * 210 }])) };
  return requireAcyclic({ ...definition, blocks: [...definition.blocks ?? [], ...blocks], editor_layout: { ...definition.editor_layout, positions }, ...(!definition.blocks?.length ? { entry_block_id: entry, entry_points: [{ key: newKey("entry"), title: definition.title, target_block_id: entry, category_id: definition.category_id ?? null, enabled: true, visibility: "public" as const }] } : {}) });
}
