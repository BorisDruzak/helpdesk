import type { ScenarioBlock, ScenarioCondition, ScenarioDraftDefinition, ScenarioField, ScenarioScalar } from "./scenario-contract";
import { conditionFields } from "./scenario-builder-model";
import { addMapBlock, freeMapPosition, replaceTransitions, terminal } from "./scenario-map-model";

export type AnswerBranchChoice = { key: string; label: string; when: ScenarioCondition };

export function answerBranchChoices(field: ScenarioField): AnswerBranchChoice[] {
  if (field.type === "checkbox") return [true, false].map(value => ({ key: `${field.key}:${value}`, label: value ? "Да" : "Нет", when: { source: "answer", field: field.key, op: "eq", value } }));
  if (!["radio", "select", "multi_select"].includes(field.type)) return [];
  return (field.options ?? []).map(option => ({ key: `${field.key}:${option.value}`, label: option.label, when: field.type === "multi_select"
    ? { source: "answer", field: field.key, op: "in", value: [option.value] }
    : { source: "answer", field: field.key, op: "eq", value: option.value } }));
}

export function answerBranchFields(definition: ScenarioDraftDefinition, blockId: string): ScenarioField[] {
  if (!definition.blocks?.some(block => block.id === blockId)) return [];
  return conditionFields(definition, blockId).filter(field => ["checkbox", "radio", "select", "multi_select"].includes(field.type));
}

export function defaultAnswerBranchField(definition: ScenarioDraftDefinition, blockId: string, requestedKey?: string): ScenarioField | undefined {
  const available = answerBranchFields(definition, blockId);
  const requested = available.find(field => field.key === requestedKey);
  if (requested) return requested;
  // Reverse breadth-first traversal prefers the question immediately preceding
  // a decision rather than whichever question happens to be first in storage.
  const pending = [blockId], visited = new Set<string>();
  while (pending.length) {
    const id = pending.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    const block = definition.blocks?.find(item => item.id === id);
    if (block?.kind === "form_page") {
      const field = block.fields.find(item => available.some(candidate => candidate.key === item.key) && answerBranchChoices(item).length > 0);
      if (field) return field;
    }
    pending.push(...definition.blocks?.filter(item => item.transitions?.some(edge => edge.to === id)).map(item => item.id) ?? []);
  }
  return undefined;
}

function simpleAnswer(condition?: ScenarioCondition | null): { field: string; op: "eq" | "in"; value: ScenarioScalar } | undefined {
  if (!condition || !("source" in condition) || condition.source !== "answer") return undefined;
  if (condition.op === "eq") return { field: condition.field, op: "eq", value: condition.value };
  if (condition.op === "in" && condition.value.length === 1) return { field: condition.field, op: "in", value: condition.value[0] };
  return undefined;
}

function sameAnswer(left: ScenarioCondition | null | undefined, right: ScenarioCondition): boolean {
  const candidate = simpleAnswer(left), requested = simpleAnswer(right);
  return !!candidate && !!requested && candidate.field === requested.field && candidate.op === requested.op && candidate.value === requested.value;
}

export function findAnswerBranch(block: ScenarioBlock, when: ScenarioCondition): number {
  return block.transitions?.findIndex(edge => sameAnswer(edge.when, when)) ?? -1;
}

function requireAnswerChoice(definition: ScenarioDraftDefinition, source: string, when: ScenarioCondition): ScenarioBlock {
  const block = definition.blocks?.find(item => item.id === source);
  if (!block || terminal(block.kind) || block.kind === "resolution_check") throw new Error("Выберите шаг, который может ветвиться по ответу на вопрос");
  const value = simpleAnswer(when);
  const field = value && answerBranchFields(definition, source).find(item => item.key === value.field);
  if (!field || !answerBranchChoices(field).some(choice => sameAnswer(choice.when, when))) {
    throw new Error("Выберите доступный вопрос и существующий вариант ответа");
  }
  return block;
}

export function connectAnswerBranch(definition: ScenarioDraftDefinition, source: string, target: string, when: ScenarioCondition): ScenarioDraftDefinition {
  const block = requireAnswerChoice(definition, source, when);
  if (!definition.blocks?.some(item => item.id === target)) throw new Error("Выберите существующий целевой шаг");
  const transitions = [...block.transitions ?? []];
  const index = findAnswerBranch(block, when);
  if (index >= 0) transitions[index] = { ...transitions[index], to: target };
  else {
    if (transitions.length >= 30) throw new Error("Достигнут лимит 30 переходов");
    const fallback = transitions.findIndex(edge => edge.when == null);
    transitions.splice(fallback < 0 ? transitions.length : fallback, 0, { to: target, when: structuredClone(when) });
  }
  return replaceTransitions(definition, source, transitions);
}

export function appendAnswerBranchStep(definition: ScenarioDraftDefinition, source: string, kind: ScenarioBlock["kind"], when: ScenarioCondition): ScenarioDraftDefinition {
  requireAnswerChoice(definition, source, when);
  const next = addMapBlock(definition, kind, freeMapPosition(definition));
  return connectAnswerBranch(next, source, next.blocks!.at(-1)!.id, when);
}
