import type { ScenarioBlock, ScenarioCondition, ScenarioDraftDefinition, ScenarioField, ScenarioFieldType, ScenarioRole } from "./scenario-contract";

export const blockLabels: Record<ScenarioBlock["kind"], string> = {
  form_page: "Страница вопросов", instruction: "Инструкция", decision: "Условие",
  resolution_check: "Проверка результата", diagnostic: "Диагностика",
  review: "Просмотр ответов", submit_ticket: "Создание обращения", finish: "Завершение без обращения",
};
export const fieldLabels: Record<ScenarioFieldType, string> = {
  text: "Короткий текст", textarea: "Длинный текст", select: "Список", multi_select: "Несколько вариантов",
  radio: "Один вариант", checkbox: "Да / нет", number: "Число", date: "Дата", datetime: "Дата и время",
  phone: "Телефон", email: "Email", url: "Ссылка", user_picker: "Пользователь", department_picker: "Подразделение",
  location_picker: "Расположение", device_picker: "Устройство", service_picker: "Услуга",
};
export const roleLabels: Record<ScenarioRole, string> = {
  display_only: "Показать ответ", priority_impact: "Влияние на приоритет", priority_urgency: "Срочность",
  priority_importance: "Важность", routing_field: "Маршрутизация", diagnostic_input: "Вход диагностики",
  approval_subject: "Участник согласования", closure_evidence: "Подтверждение закрытия",
  reporting_dimension: "Отчётность", passport_fact: "Факт паспорта", visibility_public: "Публичный ответ",
};
export const newKey = (prefix: string) => `${prefix}_${crypto.randomUUID().replaceAll("-", "")}`;
export const newField = (): ScenarioField => ({ key: newKey("field"), type: "text", label: "Новый вопрос" });
export const isChoice = (type: ScenarioFieldType) => ["select", "radio", "multi_select"].includes(type);
export function compatibleRole(type: ScenarioFieldType, role: ScenarioRole) {
  if (role.startsWith("priority_")) return ["select", "radio", "number", "checkbox"].includes(type);
  return role !== "approval_subject" || ["user_picker", "department_picker"].includes(type);
}
export function changeFieldType(field: ScenarioField, type: ScenarioFieldType): ScenarioField {
  const validation = { ...field.validation };
  if (type !== "number") { delete validation.min_value; delete validation.max_value; }
  if (["number", "checkbox", "multi_select"].includes(type)) { delete validation.min_length; delete validation.max_length; }
  return { ...field, type, validation, options: isChoice(type) ? field.options?.length ? field.options : [{ value: "yes", label: "Да" }, { value: "no", label: "Нет" }] : [],
    process_mapping: { ...field.process_mapping, roles: (field.process_mapping?.roles ?? []).filter(role => compatibleRole(type, role)),
      effects: field.type === type || isChoice(field.type) && isChoice(type) ? field.process_mapping?.effects : [] } };
}
export function editFieldOption(field: ScenarioField, index: number, value: string | null): ScenarioField {
  const old = field.options?.[index];
  if (!old) return field;
  return { ...field, options: value === null ? field.options!.filter((_, i) => i !== index) : field.options!.map((option, i) => i === index ? { ...option, value } : option),
    process_mapping: { ...field.process_mapping, effects: (field.process_mapping?.effects ?? []).flatMap(effect => effect.value !== old.value ? [effect] : value === null ? [] : [{ ...effect, value }]) } };
}
export function newBlock(kind: ScenarioBlock["kind"]): ScenarioBlock {
  const base = { id: newKey("block"), title: blockLabels[kind], transitions: [] };
  switch (kind) {
    case "form_page": return { ...base, kind, layout: "group", fields: [newField()] };
    case "instruction": return { ...base, kind, content: { format: "plain", body: "Опишите шаги решения" }, acknowledgment_required: true };
    case "diagnostic": return { ...base, kind, capability: "endpoint.context.diagnostic.collect", require_consent: true, execution_mode: "unavailable", timeout_seconds: 30 };
    case "finish": return { ...base, kind, message: "Проблема решена без обращения" };
    default: return { ...base, kind };
  }
}
export function addBlock(definition: ScenarioDraftDefinition, kind: ScenarioBlock["kind"], after: string | null) {
  const blocks = [...(definition.blocks ?? [])];
  const block = newBlock(kind);
  const index = blocks.findIndex(item => item.id === after);
  blocks.splice(index < 0 ? blocks.length : index + 1, 0, block);
  return { ...definition, blocks, entry_block_id: definition.entry_block_id ?? block.id };
}
export function mapCondition(condition: ScenarioCondition | null | undefined, map: Record<string, string>): ScenarioCondition | null | undefined {
  if (!condition) return condition;
  if (condition.op === "and" || condition.op === "or") return { ...condition, conditions: condition.conditions.map(item => mapCondition(item, map)!) };
  if (condition.op === "not") return { ...condition, condition: mapCondition(condition.condition, map)! };
  if ("source" in condition && condition.source === "answer") return { ...condition, field: map[condition.field] ?? condition.field };
  return condition;
}
export function duplicateBlock(definition: ScenarioDraftDefinition, id: string) {
  const blocks = [...(definition.blocks ?? [])];
  const index = blocks.findIndex(item => item.id === id);
  if (index < 0 || blocks.length >= 256) throw new Error("Блок не найден или достигнут лимит");
  const copy = structuredClone(blocks[index]);
  copy.id = newKey("block"); copy.title = `${copy.title.slice(0, 290)} — копия`;
  if (copy.kind === "form_page") {
    const map = Object.fromEntries(copy.fields.map(field => [field.key, newKey("field")]));
    copy.fields = copy.fields.map(field => ({ ...field, key: map[field.key], aliases: [],
      process_mapping: { ...field.process_mapping, fact_key: field.process_mapping?.fact_key ? newKey("fact") : null },
      visible_when: mapCondition(field.visible_when, map), required_when: mapCondition(field.required_when, map) }));
    copy.transitions = copy.transitions?.map(edge => ({ ...edge, when: mapCondition(edge.when, map) }));
  }
  blocks.splice(index + 1, 0, copy);
  return { ...definition, blocks };
}
export function moveBlock(definition: ScenarioDraftDefinition, id: string, before: string) {
  const blocks = [...(definition.blocks ?? [])];
  const source = blocks.findIndex(item => item.id === id);
  if (source < 0 || id === before || !blocks.some(item => item.id === before)) return definition;
  const [block] = blocks.splice(source, 1);
  blocks.splice(blocks.findIndex(item => item.id === before), 0, block);
  return { ...definition, blocks };
}
function refers(condition: ScenarioCondition | null | undefined, key: string): boolean {
  if (!condition) return false;
  if (condition.op === "and" || condition.op === "or") return condition.conditions.some(item => refers(item, key));
  if (condition.op === "not") return refers(condition.condition, key);
  return "source" in condition && condition.source === "answer" && condition.field === key;
}
export function fieldUses(definition: ScenarioDraftDefinition, key: string, excludingBlock?: string) {
  const uses: string[] = [];
  for (const block of definition.blocks ?? []) {
    if (block.id === excludingBlock) continue;
    block.transitions?.forEach((edge, index) => { if (refers(edge.when, key)) uses.push(`${block.title}: переход ${index + 1}`); });
    if (block.kind === "form_page") for (const field of block.fields) {
      if (refers(field.visible_when, key)) uses.push(`${field.label}: видимость`);
      if (refers(field.required_when, key)) uses.push(`${field.label}: обязательность`);
    }
  }
  return uses;
}
/** Picker scope only; server graph validation/execution remains authoritative. */
export function conditionFields(definition: ScenarioDraftDefinition, blockId: string, excludeKey?: string) {
  const allowed = new Set([blockId]);
  const pending = [blockId];
  while (pending.length) {
    const target = pending.pop()!;
    for (const block of definition.blocks ?? []) if (!allowed.has(block.id) && block.transitions?.some(edge => edge.to === target)) {
      allowed.add(block.id); pending.push(block.id);
    }
  }
  return (definition.blocks ?? []).flatMap(block => allowed.has(block.id) && block.kind === "form_page" ? block.fields : []).filter(field => field.key !== excludeKey);
}
/** Structural availability hint only; conditions and visibility are evaluated by the server. */
export function conditionFieldAvailability(definition: ScenarioDraftDefinition, blockId: string) {
  const blocks = definition.blocks ?? [];
  const entrances = [...new Set([definition.entry_block_id, ...definition.entry_points?.filter(entry => entry.enabled !== false).map(entry => entry.target_block_id) ?? []].filter((id): id is string => !!id))];
  function bypasses(avoiding: string) {
    const pending = [...entrances], seen = new Set<string>();
    while (pending.length) {
      const id = pending.pop()!;
      if (id === avoiding || seen.has(id)) continue;
      if (id === blockId) return true;
      seen.add(id); pending.push(...blocks.find(block => block.id === id)?.transitions?.map(edge => edge.to) ?? []);
    }
    return false;
  }
  return conditionFields(definition, blockId).map(field => {
    const owner = blocks.find(block => block.kind === "form_page" && block.fields.some(item => item.key === field.key));
    return { field, mayBeMissing: !field.required || !!field.allow_unknown || !!field.visible_when || !!field.required_when || !!owner && bypasses(owner.id) };
  });
}
export function removeBlock(definition: ScenarioDraftDefinition, id: string, replacement: string | null) {
  const block = definition.blocks?.find(item => item.id === id);
  if (!block) return definition;
  const remaining = definition.blocks!.filter(item => item.id !== id);
  if (block.kind === "form_page" && block.fields.some(field => fieldUses(definition, field.key, id).length)) throw new Error("Ответ используется другим блоком. Сначала измените зависимости.");
  const linked = definition.entry_block_id === id || remaining.some(item => item.transitions?.some(edge => edge.to === id));
  if (replacement && !remaining.some(item => item.id === replacement)) throw new Error("Выберите существующий блок");
  if (linked && remaining.length && !replacement) throw new Error("Переназначьте входящие переходы и начало сценария");
  return { ...definition, entry_block_id: definition.entry_block_id === id ? replacement : definition.entry_block_id,
    blocks: remaining.map(item => ({ ...item, transitions: item.transitions?.map(edge => edge.to === id ? { ...edge, to: replacement! } : edge) })) };
}
