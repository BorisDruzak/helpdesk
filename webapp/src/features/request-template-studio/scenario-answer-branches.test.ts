import { describe, expect, it } from "vitest";
import type { ScenarioBlock, ScenarioCondition, ScenarioDraftDefinition, ScenarioField } from "./scenario-contract";

const load = () => import("./scenario-answer-branches");
const checkbox: ScenarioField = { key: "can_work", label: "Можно продолжать работу?", type: "checkbox" };
const yes: ScenarioCondition = { source: "answer", field: checkbox.key, op: "eq", value: true };
const no: ScenarioCondition = { source: "answer", field: checkbox.key, op: "eq", value: false };
const draft = (): ScenarioDraftDefinition => ({ schema_version: 3, scenario_key: "answer_branches", title: "Проверка", service_code: "it", offering_full_code: "it.support", entry_block_id: "question", process_binding: { request_template_key: "support" }, blocks: [
  { id: "question", kind: "form_page", title: "Вопрос", fields: [checkbox], transitions: [{ to: "decision" }] },
  { id: "decision", kind: "decision", title: "Условие", transitions: [] },
  { id: "other", kind: "instruction", title: "Другой шаг", content: { body: "Проверка" } },
  { id: "result", kind: "submit_ticket", title: "Обращение" },
] });

describe("explicit answer branch edits", () => {
  it("uses booleans for checkbox answers and strings for each declared choice", async () => {
    const { answerBranchChoices } = await load();
    expect(answerBranchChoices(checkbox).map(({ label, when }) => ({ label, when }))).toEqual([{ label: "Да", when: yes }, { label: "Нет", when: no }]);
    for (const type of ["radio", "select", "multi_select"] as const) {
      const values = answerBranchChoices({ key: "issue", label: "Что случилось?", type, options: [{ value: "printer", label: "Принтер" }] });
      expect(values).toHaveLength(1);
      expect(values[0]).toMatchObject({ label: "Принтер", when: { source: "answer", field: "issue", op: type === "multi_select" ? "in" : "eq", value: type === "multi_select" ? ["printer"] : "printer" } });
      expect(values[0].key).toBe(answerBranchChoices({ key: "issue", label: "Changed label", type, options: [{ value: "printer", label: "New label" }] })[0].key);
    }
    expect(answerBranchChoices({ key: "text", label: "Описание", type: "text" })).toEqual([]);
    expect(answerBranchChoices({ key: "empty", label: "Список", type: "select" })).toEqual([]);
  });

  it("offers available enumerated fields and prefers the nearest incoming question", async () => {
    const { answerBranchFields, defaultAnswerBranchField } = await load();
    const d = draft();
    d.blocks!.unshift({ id: "earlier", kind: "form_page", title: "Сначала", fields: [{ key: "first", label: "Первый", type: "radio", options: [{ value: "a", label: "А" }] }, { key: "description", label: "Текст", type: "text" }], transitions: [{ to: "question" }] });
    d.blocks!.push({ id: "unrelated", kind: "form_page", title: "Другая ветка", fields: [{ key: "hidden", label: "Недоступный", type: "checkbox" }] });
    expect(answerBranchFields(d, "decision").map(field => field.key)).toEqual(["first", "can_work"]);
    expect(defaultAnswerBranchField(d, "decision")?.key).toBe("can_work");
    expect(defaultAnswerBranchField(d, "decision", "first")?.key).toBe("first");
    expect(defaultAnswerBranchField(d, "decision", "hidden")?.key).toBe("can_work");
    expect(defaultAnswerBranchField(d, "question")?.key).toBe("can_work");
    expect(defaultAnswerBranchField(d, "missing")).toBeUndefined();
  });

  it("adds exactly one conditional connection from an empty question", async () => {
    const { connectAnswerBranch } = await load();
    const d = draft();
    d.blocks![0].transitions = [];
    const before = structuredClone(d);
    const next = connectAnswerBranch(d, "question", "decision", yes);
    expect(next.blocks![0].transitions).toEqual([{ to: "decision", when: yes }]);
    expect(next.blocks![1].transitions).toEqual([]);
    expect(d).toEqual(before);
  });

  it("creates yes and no steps as independent siblings without inserting into the first branch", async () => {
    const { appendAnswerBranchStep } = await load();
    const d = draft();
    const yesDraft = appendAnswerBranchStep(d, "decision", "instruction", yes);
    const yesStep = yesDraft.blocks!.at(-1)!;
    const next = appendAnswerBranchStep(yesDraft, "decision", "instruction", no);
    const noStep = next.blocks!.at(-1)!;
    expect(yesStep.id).not.toBe(noStep.id);
    expect(next.blocks!.find(block => block.id === "decision")!.transitions).toEqual([{ to: yesStep.id, when: yes }, { to: noStep.id, when: no }]);
    expect(next.blocks!.find(block => block.id === yesStep.id)!.transitions).toEqual([]);
    expect(noStep.transitions).toEqual([]);
    expect(d.blocks).toHaveLength(4);
    expect(next.editor_layout?.positions?.[yesStep.id]).not.toEqual(next.editor_layout?.positions?.[noStep.id]);
  });

  it("reconnects only an exact simple condition and retains all branch metadata", async () => {
    const { connectAnswerBranch, findAnswerBranch } = await load();
    const d = draft();
    const condition: ScenarioCondition = { op: "and", conditions: [yes] };
    d.blocks![1].transitions = [{ to: "result", when: condition, priority: 2 }, { to: "other", when: yes, priority: 7, processing: { route: "network", sla_profile: "urgent" }, processing_facts: { urgency: "blocked" } }, { to: "result" }];
    const original = structuredClone(d);
    expect(findAnswerBranch(d.blocks![1], { op: "eq", value: true, source: "answer", field: "can_work" })).toBe(1);
    expect(findAnswerBranch({ ...d.blocks![1], transitions: [{ to: "result", when: condition }] }, yes)).toBe(-1);
    const next = connectAnswerBranch(d, "decision", "result", yes);
    expect(next.blocks![1].transitions![1]).toEqual({ ...d.blocks![1].transitions![1], to: "result" });
    expect(next.blocks![1].transitions![0]).toEqual(d.blocks![1].transitions![0]);
    expect(next.blocks![1].transitions![2]).toEqual(d.blocks![1].transitions![2]);
    expect(d).toEqual(original);
  });

  it("matches singleton multi-select membership only, preserving custom sets and current-result conditions", async () => {
    const { findAnswerBranch } = await load();
    const when: ScenarioCondition = { source: "answer", field: "issue", op: "in", value: ["printer"] };
    const block: ScenarioBlock = { id: "d", kind: "decision", title: "Условие", transitions: [{ to: "x", when: { ...when, value: ["printer", "scanner"] } }, { to: "y", when }, { to: "z", when: { source: "current_result", op: "eq", value: true } }] };
    expect(findAnswerBranch(block, when)).toBe(1);
    expect(findAnswerBranch(block, { source: "answer", field: "other", op: "in", value: ["printer"] })).toBe(-1);
    expect(findAnswerBranch(block, { source: "current_result", op: "eq", value: true })).toBe(-1);
  });

  it("inserts new branches before fallback and rejects stale, unsupported or unreachable answers", async () => {
    const { connectAnswerBranch } = await load();
    const d = draft();
    d.blocks![1].transitions = [{ to: "other", priority: 12, processing: { sla_profile: "standard" } }];
    expect(connectAnswerBranch(d, "decision", "result", yes).blocks![1].transitions).toEqual([{ to: "result", when: yes }, ...d.blocks![1].transitions!]);
    expect(() => connectAnswerBranch(d, "decision", "result", { source: "answer", field: "can_work", op: "eq", value: "true" })).toThrow();
    expect(() => connectAnswerBranch(d, "decision", "result", { source: "answer", field: "future", op: "eq", value: true })).toThrow();
    expect(() => connectAnswerBranch(d, "decision", "result", { op: "not", condition: yes })).toThrow();
  });

  it("rejects cycles and terminal or resolution-check sources without mutating the draft", async () => {
    const { connectAnswerBranch, appendAnswerBranchStep } = await load();
    const d = draft(), before = structuredClone(d);
    expect(() => connectAnswerBranch(d, "decision", "question", yes)).toThrow(/цикл/);
    expect(() => connectAnswerBranch(d, "result", "other", yes)).toThrow();
    d.blocks!.push({ id: "resolution", kind: "resolution_check", title: "Решено?" });
    expect(() => connectAnswerBranch(d, "resolution", "other", yes)).toThrow();
    expect(() => appendAnswerBranchStep(d, "decision", "instruction", { source: "answer", field: "missing", op: "eq", value: true })).toThrow();
    expect(d.blocks!.slice(0, 4)).toEqual(before.blocks);
    expect(d.editor_layout).toBeUndefined();
  });

  it("allows reconnect at the transition limit but rejects a new branch and excess blocks", async () => {
    const { connectAnswerBranch, appendAnswerBranchStep } = await load();
    const d = draft();
    d.blocks![1].transitions = [{ to: "other", when: yes }, ...Array.from({ length: 29 }, () => ({ to: "result" }))];
    expect(connectAnswerBranch(d, "decision", "result", yes).blocks![1].transitions).toHaveLength(30);
    expect(() => connectAnswerBranch(d, "decision", "result", no)).toThrow(/лимит/i);
    d.blocks!.push(...Array.from({ length: 252 }, (_, index): ScenarioBlock => ({ id: `extra_${index}`, kind: "decision", title: "Шаг" })));
    expect(() => appendAnswerBranchStep(d, "decision", "instruction", yes)).toThrow(/256/);
    expect(d.blocks).toHaveLength(256);
  });
});
