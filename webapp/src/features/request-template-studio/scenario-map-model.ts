import type { ScenarioBlock, ScenarioDraftDefinition, ScenarioTransition } from "./scenario-contract";
import { addBlock, newBlock, newKey, removeBlock } from "./scenario-builder-model";

export const mapPalette: { kind: ScenarioBlock["kind"]; label: string }[] = [
  { kind: "form_page", label: "Вопрос" }, { kind: "instruction", label: "Инструкция" },
  { kind: "decision", label: "Условие" }, { kind: "resolution_check", label: "Проверка результата" },
  { kind: "diagnostic", label: "Диагностика" }, { kind: "review", label: "Сводка" }, { kind: "submit_ticket", label: "Результат" },
];
export const mapKindLabel = (kind: ScenarioBlock["kind"]) => kind === "finish" ? "Результат" : mapPalette.find(item => item.kind === kind)?.label ?? kind;
export const terminal = (kind: ScenarioBlock["kind"]) => kind === "finish" || kind === "submit_ticket";

export function connectStart(definition: ScenarioDraftDefinition, target: string) {
  const block = definition.blocks?.find(item => item.id === target);
  if (!block) throw new Error("Выберите существующий начальный блок");
  const entries = definition.entry_points ?? [];
  if (entries.some(entry => entry.target_block_id === target)) return definition.entry_block_id ? definition : { ...definition, entry_block_id: target };
  if (entries.length >= 64) throw new Error("Достигнут лимит 64 точек входа");
  return { ...definition, entry_block_id: definition.entry_block_id ?? target, entry_points: [...entries, {
    key: newKey("entry"), title: block.title, target_block_id: target, category_id: null, visibility: "public" as const, enabled: true,
  }] };
}
export function reconnectStart(definition: ScenarioDraftDefinition, key: string | null, target: string) {
  if (!definition.blocks?.some(item => item.id === target)) throw new Error("Выберите существующий начальный блок");
  if (key === null) return { ...definition, entry_block_id: target };
  if (!definition.entry_points?.some(entry => entry.key === key)) throw new Error("Точка входа не найдена");
  return { ...definition, entry_points: definition.entry_points.map(entry => entry.key === key ? { ...entry, target_block_id: target } : entry) };
}

export function positionBlock(definition: ScenarioDraftDefinition, id: string, position: { x: number; y: number }): ScenarioDraftDefinition {
  if (![position.x, position.y].every(value => Number.isFinite(value) && Math.abs(value) <= 100000)) throw new Error("Координаты должны быть конечными числами от −100000 до 100000");
  return { ...definition, editor_layout: { ...definition.editor_layout, positions: { ...definition.editor_layout?.positions, [id]: position } } };
}
export function requireAcyclic(definition: ScenarioDraftDefinition) {
  const blocks = new Map((definition.blocks ?? []).map(block => [block.id, block]));
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
  return requireAcyclic({ ...definition, blocks: definition.blocks?.map(block => block.id === id ? { ...block, transitions } : block) });
}
export function reconnectTransition(definition: ScenarioDraftDefinition, source: string, index: number, target: string) {
  const block = definition.blocks?.find(item => item.id === source);
  if (!block?.transitions?.[index] || !definition.blocks?.some(item => item.id === target)) throw new Error("Выберите существующий переход и целевой блок");
  return replaceTransitions(definition, source, block.transitions.map((edge, i) => i === index ? { ...edge, to: target } : edge));
}
export function connectBlocks(definition: ScenarioDraftDefinition, source: string, target: string) {
  const block = definition.blocks?.find(item => item.id === source);
  if (!block || terminal(block.kind) || !definition.blocks?.some(item => item.id === target)) throw new Error("Этот блок нельзя соединить с выбранной целью");
  if ((block.transitions?.length ?? 0) >= 30) throw new Error("Достигнут лимит переходов");
  return replaceTransitions(definition, source, [...block.transitions ?? [], { to: target }]);
}
export function insertOnTransition(definition: ScenarioDraftDefinition, source: string, index: number, kind: ScenarioBlock["kind"], position?: { x: number; y: number }) {
  if (terminal(kind) || kind === "resolution_check" || kind === "decision") throw new Error("Для этого типа нужны явные маршруты; добавьте его отдельно и настройте связи");
  const from = definition.blocks?.find(item => item.id === source);
  const edge = from?.transitions?.[index];
  if (!edge || (definition.blocks?.length ?? 0) >= 256) throw new Error("Переход не найден или достигнут лимит блоков");
  const block = newBlock(kind);
  block.transitions = [{ to: edge.to }];
  let next: ScenarioDraftDefinition = { ...definition, blocks: [...definition.blocks ?? [], block].map(old => old.id === source ? { ...old, transitions: old.transitions?.map((item, i) => i === index ? { ...item, to: block.id } : item) } : old) };
  if (position) next = positionBlock(next, block.id, position);
  return requireAcyclic(next);
}
export function addMapBlock(definition: ScenarioDraftDefinition, kind: ScenarioBlock["kind"], position: { x: number; y: number }) {
  const next = addBlock(definition, kind, null);
  return positionBlock(next, next.blocks![next.blocks!.length - 1].id, position);
}
export function deleteMapBlock(definition: ScenarioDraftDefinition, id: string, replacement: string | null, entranceAction?: "remove" | "reassign") {
  const entrances = definition.entry_points ?? [];
  if (entrances.some(entry => entry.target_block_id === id) && !entranceAction) throw new Error("Блок используется точкой входа. Выберите явное переназначение или удаление привязок из черновика.");
  if (entranceAction === "reassign" && (!replacement || replacement === id || !definition.blocks?.some(block => block.id === replacement))) throw new Error("Выберите другой начальный блок для точек входа");
  const entry_points = entranceAction === "remove" ? entrances.filter(entry => entry.target_block_id !== id) : entrances.map(entry => entry.target_block_id === id ? { ...entry, target_block_id: replacement! } : entry);
  const next = removeBlock({ ...definition, entry_points }, id, replacement);
  const positions = { ...next.editor_layout?.positions }; delete positions[id];
  return requireAcyclic({ ...next, editor_layout: { ...next.editor_layout, positions } });
}
