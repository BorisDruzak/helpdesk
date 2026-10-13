import { describe, expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { addBlock, duplicateBlock, moveBlock, removeBlock, fieldUses, changeFieldType, editFieldOption, conditionFields } from "./scenario-builder-model";

const draft = (): ScenarioDraftDefinition => ({
  scenario_key: "test", title: "Тест", service_code: "it", offering_full_code: "it.test",
  process_binding: { request_template_key: "test" }, entry_block_id: "questions",
  blocks: [
    { id: "questions", title: "Вопросы", kind: "form_page", fields: [{ key: "answer", type: "text", label: "Ответ" }], transitions: [{ to: "check" }] },
    { id: "check", title: "Проверка", kind: "resolution_check", transitions: [{ to: "done", when: { op: "eq", source: "answer", field: "answer", value: "ok" } }] },
    { id: "done", title: "Готово", kind: "finish" },
  ],
});

describe("safe scenario builder operations", () => {
  it("reconciles typed effects when choices are renamed, removed or replaced by a different answer type", () => {
    const field = { key: "scope", label: "Scope", type: "radio" as const, options: [{ value: "all", label: "All" }, { value: "one", label: "One" }], process_mapping: { effects: [{ value: "all", facts: { impact: "department" as const } }] } };
    expect(editFieldOption(field, 0, "team").process_mapping?.effects?.[0].value).toBe("team");
    expect(editFieldOption(field, 0, null).process_mapping?.effects).toEqual([]);
    expect(changeFieldType(field, "text").process_mapping?.effects).toEqual([]);
    expect(changeFieldType(field, "multi_select").process_mapping?.effects).toEqual(field.process_mapping.effects);
  });
  it("offers answers only from the current page and upstream blocks", () => {
    const definition = addBlock(draft(), "form_page", "done");
    expect(conditionFields(definition, "questions").map(field => field.key)).toEqual(["answer"]);
    expect(conditionFields(definition, "check").map(field => field.key)).toEqual(["answer"]);
    expect(conditionFields(definition, "questions", "answer")).toEqual([]);
  });
  it("inserts after selection and keeps existing transitions and source immutable", () => {
    const source = draft();
    const result = addBlock(source, "instruction", "questions");
    expect(result.blocks?.map(b => b.kind)).toEqual(["form_page", "instruction", "resolution_check", "finish"]);
    expect(result.blocks?.[0].transitions).toEqual([{ to: "check" }]);
    expect(source.blocks).toHaveLength(3);
  });
  it("creates a valid initial form field and sets the first entry", () => {
    const result = addBlock({ ...draft(), blocks: [], entry_block_id: null }, "form_page", null);
    expect(result.entry_block_id).toBe(result.blocks?.[0].id);
    expect(result.blocks?.[0]).toMatchObject({ kind: "form_page", fields: [{ type: "text", label: "Новый вопрос" }] });
  });
  it("duplicates with fresh identifiers and remaps local dependencies and facts", () => {
    const source = draft();
    const first = source.blocks![0];
    if (first.kind !== "form_page") throw Error();
    first.fields.push({ key: "dependent", type: "text", label: "Уточнение", visible_when: { op: "exists", source: "answer", field: "answer" }, process_mapping: { roles: ["reporting_dimension"], fact_key: "report" } });
    const result = duplicateBlock(source, "questions");
    const copy = result.blocks![1];
    if (copy.kind !== "form_page") throw Error();
    expect(copy.id).not.toBe(first.id);
    expect(copy.fields[0].key).not.toBe("answer");
    expect(copy.fields[1].visible_when).toMatchObject({ field: copy.fields[0].key });
    expect(copy.fields[1].process_mapping?.fact_key).not.toBe("report");
    expect(copy.transitions).toEqual([{ to: "check" }]);
  });
  it("reorders without rewriting explicit routes or entry", () => {
    const result = moveBlock(draft(), "done", "questions");
    expect(result.blocks?.map(b => b.id)).toEqual(["done", "questions", "check"]);
    expect(result.entry_block_id).toBe("questions");
    expect(result.blocks?.[1].transitions).toEqual([{ to: "check" }]);
  });
  it("requires reassignment for incoming links, rewires links and the entry safely", () => {
    expect(() => removeBlock(draft(), "check", null)).toThrow(/переход/i);
    const result = removeBlock(draft(), "check", "done");
    expect(result.blocks?.[0].transitions).toEqual([{ to: "done" }]);
    expect(() => removeBlock(draft(), "questions", "missing")).toThrow();
    const noUses = draft();
    noUses.blocks![1].transitions = [{ to: "done" }];
    expect(removeBlock(noUses, "questions", "check").entry_block_id).toBe("check");
  });
  it("blocks removal of referenced answers and reports transition and field uses", () => {
    expect(fieldUses(draft(), "answer")).toEqual(["Проверка: переход 1"]);
    expect(() => removeBlock(draft(), "questions", "check")).toThrow(/ответ/i);
  });
  it("normalizes constraints, options and incompatible roles when type changes", () => {
    const number = changeFieldType({ key: "a", label: "A", type: "text", validation: { min_length: 2 }, process_mapping: { roles: ["approval_subject", "reporting_dimension"] } }, "number");
    expect(number.validation).toEqual({});
    expect(number.process_mapping?.roles).toEqual(["reporting_dimension"]);
    const choice = changeFieldType(number, "select");
    expect(choice.options).toHaveLength(2);
    expect(changeFieldType(choice, "text").options).toEqual([]);
  });
});
