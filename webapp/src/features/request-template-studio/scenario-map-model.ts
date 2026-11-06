import { setNavigationMode, uniqueButtonLabel } from "./scenario-v4-model";
import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioTransition } from "./scenario-contract";
import { addBlock, newBlock, newKey, removeBlock } from "./scenario-builder-model";
import { isPolicyAttachment, reassignPolicyAttachments } from "./scenario-policy-attachments-model";

export const mapPalette: { kind: ScenarioBlock["kind"]; label: string }[] = [
  { kind: "form_page", label: "Вопрос" }, { kind: "instruction", label: "Инструкция" },
  { kind: "decision", label: "Условие" }, { kind: "resolution_check", label: "Проверка результата" },
  { kind: "submit_ticket", label: "Результат" },
  { kind: "navigation", label: "Переходы · кнопки" }, { kind: "sla_attachment", label: "SLA" }, { kind: "routing_attachment", label: "Маршрут" },
];
export const mapKindLabel = (kind: ScenarioBlock["kind"]) => kind === "finish" ? "Результат" : kind === "sla" ? "SLA · последовательный блок" : mapPalette.find(item => item.kind === kind)?.label ?? kind;
export const terminal = (kind: ScenarioBlock["kind"]) => kind === "finish" || kind === "submit_ticket";
export const catalogEntranceSourceId = "studio:metadata";

export function createCatalogEntrance(definition: ScenarioDraftDefinition, source: string, target: string, title: string) {
  if (source !== catalogEntranceSourceId) throw new Error("Вход из каталога подключается только к блоку «Начало».");
  const label = title.trim();
  if (!label || label.length > 300) throw new Error("Укажите название входа до 300 символов.");
  const block = definition.blocks?.find(item => item.id === target);
  if (!block) throw new Error("Выберите существующий начальный блок");
  if (isPolicyAttachment(block)) throw new Error("Настройка не может быть началом маршрута. Прикрепите её к шагу.");
  if ((definition.entry_points?.length ?? 0) + (definition.editor_layout?.pending_entrances?.length ?? 0) >= 64) throw new Error("Достигнут лимит 64 точек входа");
  return { ...definition, entry_block_id: definition.entry_block_id ?? target, entry_points: [...definition.entry_points ?? [], {
    key: newKey("entry"), title: label, target_block_id: target, category_id: definition.category_id ?? null, visibility: "public" as const, enabled: true,
  }] };
}

export function connectStart(definition: ScenarioDraftDefinition, target: string) {
  const block = definition.blocks?.find(item => item.id === target);
  if (!block) throw new Error("Выберите существующий начальный блок");
  if (isPolicyAttachment(block)) throw new Error("Настройка не может быть началом маршрута. Прикрепите её к шагу.");
  const entries = definition.entry_points ?? [];
  if (entries.some(entry => entry.target_block_id === target)) return definition.entry_block_id ? definition : { ...definition, entry_block_id: target };
  if (entries.length + (definition.editor_layout?.pending_entrances?.length ?? 0) >= 64) throw new Error("Достигнут лимит 64 точек входа");
  return { ...definition, entry_block_id: definition.entry_block_id ?? target, entry_points: [...entries, {
    key: newKey("entry"), title: block.title, target_block_id: target, category_id: definition.category_id ?? null, visibility: "public" as const, enabled: true,
  }] };
}
export function reconnectStart(definition: ScenarioDraftDefinition, key: string | null, target: string) {
  if (!definition.blocks?.some(item => item.id === target)) throw new Error("Выберите существующий начальный блок");
  if (isPolicyAttachment(definition.blocks.find(item => item.id === target)!)) throw new Error("Настройка не может быть началом маршрута. Прикрепите её к шагу.");
  if (key === null) return { ...definition, entry_block_id: target };
  if (!definition.entry_points?.some(entry => entry.key === key)) throw new Error("Точка входа не найдена");
  const movedPrimary = definition.entry_points.some(entry => entry.key === key && entry.enabled !== false && entry.target_block_id === definition.entry_block_id);
  const entry_points = definition.entry_points.map(entry => entry.key === key ? { ...entry, target_block_id: target } : entry);
  return { ...definition, entry_points, entry_block_id: movedPrimary && !entry_points.some(entry => entry.enabled !== false && entry.target_block_id === definition.entry_block_id) ? target : definition.entry_block_id };
}

export function positionBlock(definition: ScenarioDraftDefinition, id: string, position: { x: number; y: number }): ScenarioDraftDefinition {
  if (![position.x, position.y].every(value => Number.isFinite(value) && Math.abs(value) <= 100000)) throw new Error("Координаты должны быть конечными числами от −100000 до 100000");
  return { ...definition, editor_layout: { ...definition.editor_layout, positions: { ...stableMapPositions(definition), [id]: position } } };
}
// Freeze the fallback layout before changing block order. Geometry never follows graph links.
export function stableMapPositions(definition: ScenarioDraftDefinition): Record<string, { x: number; y: number }> {
  return { system_start: { x: -320, y: 0 }, ...Object.fromEntries((definition.blocks ?? []).map((block, index) => [block.id, { x: (index % 3) * 310, y: Math.floor(index / 3) * 200 }])), ...definition.editor_layout?.positions };
}
export function freeMapPosition(definition: ScenarioDraftDefinition) {
  const occupied = Object.values(stableMapPositions(definition));
  let slot = definition.blocks?.length ?? 0;
  let point = { x: (slot % 3) * 310, y: Math.floor(slot / 3) * 200 };
  while (occupied.some(old => Math.abs(old.x - point.x) < 260 && Math.abs(old.y - point.y) < 170)) {
    slot += 1; point = { x: (slot % 3) * 310, y: Math.floor(slot / 3) * 200 };
  }
  return point;
}
/** Place around the visible flow-space center; never search from the graph origin. */
export function nearMapPosition(definition: ScenarioDraftDefinition, center: { x: number; y: number }) {
  const occupied = Object.values(stableMapPositions(definition));
  const origin = { x: center.x - 115, y: center.y - 45 };
  for (let ring = 0; ring <= 8; ring++) {
    for (let dx = -ring; dx <= ring; dx++) for (let dy = -ring; dy <= ring; dy++) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) !== ring) continue;
      const point = { x: origin.x + dx * 280, y: origin.y + dy * 190 };
      if (occupied.every(old => Math.abs(old.x - point.x) >= 260 || Math.abs(old.y - point.y) >= 170)) return point;
    }
  }
  return origin;
}
export function requireAcyclic(definition: ScenarioDraftDefinition) {
  const blocks = new Map((definition.blocks ?? []).filter(block => !isPolicyAttachment(block)).map(block => [block.id, block]));
  const active = new Set<string>(), visited = new Set<string>();
  function visit(id: string) {
    if (active.has(id)) throw new Error("Соединение создаёт запрещённый цикл. Возврат к вопросу выполняется через навигацию сеанса.");
    if (visited.has(id)) return;
    active.add(id);
    blocks.get(id)?.transitions?.forEach(edge => visit(edge.to));
    active.delete(id); visited.add(id);
  }
  blocks.forEach(block => visit(block.id));
  return definition;
}
export function replaceTransitions(definition: ScenarioDraftDefinition, id: string, transitions: ScenarioTransition[]) {
  if (isPolicyAttachment(definition.blocks?.find(block => block.id === id)?.kind ?? "instruction") || transitions.some(edge => isPolicyAttachment(definition.blocks?.find(block => block.id === edge.to)?.kind ?? "instruction"))) throw new Error("Настройку нужно прикрепить к блоку отдельной связью, а не переходом маршрута.");
  return requireAcyclic({ ...definition, blocks: definition.blocks?.map(block => block.id === id ? { ...block, transitions } : block) });
}
export function reconnectTransition(definition: ScenarioDraftDefinition, source: string, index: number, target: string) {
  const block = definition.blocks?.find(item => item.id === source);
  if (!block?.transitions?.[index] || !definition.blocks?.some(item => item.id === target)) throw new Error("Выберите существующий переход и целевой блок");
  return replaceTransitions(definition, source, block.transitions.map((edge, i) => i === index ? { ...edge, to: target } : edge));
}
export function connectBlocks(definition: ScenarioDraftDefinition, source: string, target: string) {
  const block = definition.blocks?.find(item => item.id === source);
  if (isPolicyAttachment(block?.kind ?? "instruction") || isPolicyAttachment(definition.blocks?.find(item => item.id === target)?.kind ?? "instruction")) throw new Error("Настройку нужно прикрепить к блоку отдельной связью, а не переходом маршрута.");
  if (!block || terminal(block.kind) || !definition.blocks?.some(item => item.id === target)) throw new Error("Этот блок нельзя соединить с выбранной целью");
  if ((block.transitions?.length ?? 0) >= (block.transition_mode === "buttons" ? 10 : 30)) throw new Error("Достигнут лимит переходов");
  if (block.kind === "sla" && block.transitions?.length) throw new Error("У блока SLA может быть только один следующий шаг");
  let edge:ScenarioTransition={to:target};
  if (block.transition_mode === "buttons") edge.button = { key: newKey("action"), label: uniqueButtonLabel(definition.blocks?.find(item => item.id === target)?.title ?? "Продолжить", (block.transitions ?? []).map(edge => edge.button?.label ?? "")) };
  if((definition.schema_version??1)>=2&&block.kind==="resolution_check"){
    const used=(block.transitions??[]).map(item=>item.when&&"value" in item.when?item.when.value:null);
    const value=["yes","no","unknown"].find(item=>!used.includes(item));
    if(value)edge={to:target,when:{source:"current_result",op:"eq",value}};
  }
  const transitions = [...block.transitions ?? [], edge];
  const next = replaceTransitions(definition, source, transitions);
  // Only an explicit new edit creates a choice; loading old graphs never changes their semantics.
  if (definition.schema_version === 4 && ["form_page", "instruction", "review", "navigation"].includes(block.kind)
    && transitions.length > 1 && !transitions.some(item => item.when) && block.transition_mode !== "buttons") {
    return { ...next, blocks: next.blocks?.map(item => item.id === source ? setNavigationMode(item, "buttons", id => definition.blocks?.find(target => target.id === id)?.title ?? "Продолжить") : item) };
  }
  return next;
}
export function insertOnTransition(definition: ScenarioDraftDefinition, source: string, index: number, kind: ScenarioBlock["kind"], position?: { x: number; y: number }) {
  if (isPolicyAttachment(kind)) throw new Error("Добавьте настройку из библиотеки и прикрепите её к блоку. Настройки не вставляются в переходы.");
  if (["sla", "navigation"].includes(kind) && definition.schema_version !== 4) throw new Error("Сначала включите новые возможности карты. Существующие услуги сохраняют прежние правила.");
  if (terminal(kind) || kind === "resolution_check") throw new Error("Этот шаг завершает маршрут или требует отдельных ветвей. Добавьте его из библиотеки и явно настройте переходы.");
  const from = definition.blocks?.find(item => item.id === source);
  const edge = from?.transitions?.[index];
  if (!edge || (definition.blocks?.length ?? 0) >= 256) throw new Error("Переход не найден или достигнут лимит блоков");
  const block = newBlock(kind);
  block.transitions = [{ to: edge.to, ...(block.kind === "navigation" ? { button: { key: newKey("action"), label: "Продолжить" } } : {}) }];
  let next: ScenarioDraftDefinition = { ...definition, blocks: [...definition.blocks ?? [], block].map(old => old.id === source ? { ...old, transitions: old.transitions?.map((item, i) => i === index ? { ...item, to: block.id } : item) } : old) };
  const fromIndex = definition.blocks!.findIndex(item => item.id === source);
  const origin = definition.editor_layout?.positions?.[source] ?? { x: (fromIndex % 3) * 310, y: Math.floor(fromIndex / 3) * 200 };
  const point = position ? { ...position } : { x: origin.x, y: origin.y + 170 };
  while (!position && definition.blocks!.some((item, i) => { const old = definition.editor_layout?.positions?.[item.id] ?? { x: (i % 3) * 310, y: Math.floor(i / 3) * 200 }; return Math.abs(old.x - point.x) < 260 && Math.abs(old.y - point.y) < 145; })) point.y += 170;
  next = positionBlock(next, block.id, point);
  return requireAcyclic(next);
}
export function addMapBlock(definition: ScenarioDraftDefinition, kind: ScenarioBlock["kind"], position: { x: number; y: number }) {
  if (["sla", "navigation", "sla_attachment", "routing_attachment"].includes(kind) && definition.schema_version !== 4) throw new Error("Сначала включите новые возможности карты. Существующие услуги сохраняют прежние правила.");
  if ((definition.blocks?.length ?? 0) >= 256) throw new Error("Достигнут лимит 256 шагов карты");
  const next = isPolicyAttachment(kind) ? { ...definition, blocks: [...definition.blocks ?? [], { id: newKey("block"), title: kind === "sla_attachment" ? "SLA" : "Маршрут", kind } as ScenarioBlock] } : addBlock(definition, kind, null);
  return positionBlock(next, next.blocks![next.blocks!.length - 1].id, position);
}
/** Contextual addition is one undoable mutation. Existing branches are never guessed. */
export function appendMapStep(definition: ScenarioDraftDefinition, source: string | null, kind: ScenarioBlock["kind"]): ScenarioDraftDefinition {
  if (isPolicyAttachment(kind)) throw new Error("Добавьте настройку из библиотеки и прикрепите её к блоку. Настройки не являются следующим шагом.");
  const from = definition.blocks?.find(block => block.id === source);
  if (from && isPolicyAttachment(from)) throw new Error("Настройку нужно прикрепить к блоку. У неё нет следующего шага.");
  if (source && (!from || terminal(from.kind))) throw new Error("После результата маршрут завершён. Добавьте шаг перед результатом.");
  if (from?.transitions?.length) {
    if (from.transitions.length !== 1) throw new Error("У блока несколько ветвей. Нажмите «+» на нужной стрелке.");
    return insertOnTransition(definition, from.id, 0, kind);
  }
  const point = source ? definition.editor_layout?.positions?.[source] ?? { x: 0, y: 0 } : { x: 0, y: -170 };
  let next = addMapBlock(definition, kind, { x: point.x, y: point.y + 170 });
  const added = next.blocks!.at(-1)!;
  if (from) next = connectBlocks(next, from.id, added.id);
  else if (!definition.blocks?.length && definition.schema_version !== 2) { next = connectStart(next, added.id); next = { ...next, entry_points: [{ ...next.entry_points![0], title: definition.title, category_id: definition.category_id }] }; }
  return next;
}
export function deleteMapBlock(definition: ScenarioDraftDefinition, id: string, replacement: string | null, entranceAction?: "remove" | "reassign", referenceAction: "redirect" | "detach" = "redirect") {
  if (replacement && isPolicyAttachment(definition.blocks?.find(block => block.id === replacement)?.kind ?? "instruction")) throw new Error("Выберите шаг или результат: настройка не может заменить удаляемый блок.");
  definition = reassignPolicyAttachments(definition, id, referenceAction === "detach" ? null : replacement);
  const entrances = definition.entry_points ?? [];
  if (entrances.some(entry => entry.target_block_id === id) && !entranceAction) throw new Error("Блок используется точкой входа. Выберите явное переназначение или удаление привязок из черновика.");
  if (entranceAction === "reassign" && (!replacement || replacement === id || !definition.blocks?.some(block => block.id === replacement))) throw new Error("Выберите другой начальный блок для точек входа");
  const entry_points = entranceAction === "remove" ? entrances.filter(entry => entry.target_block_id !== id) : entrances.map(entry => entry.target_block_id === id ? { ...entry, target_block_id: replacement! } : entry);
  const prepared = referenceAction === "detach" ? { ...definition, entry_block_id: definition.entry_block_id === id ? (entranceAction === "reassign" ? replacement : null) : definition.entry_block_id, blocks: definition.blocks?.map(block => ({ ...block, transitions: block.transitions?.filter(edge => edge.to !== id) })) } : definition;
  const next = removeBlock({ ...prepared, entry_points }, id, referenceAction === "detach" ? null : replacement);
  const positions = stableMapPositions(definition); delete positions[id];
  return requireAcyclic({ ...next, editor_layout: { ...next.editor_layout, positions } });
}
