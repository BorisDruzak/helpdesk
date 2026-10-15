import { describe, expect, it } from "vitest";
import { createScenarioStarter } from "./scenario-starter";
import { appendMapStep, insertOnTransition } from "./scenario-map-model";

describe("editable starter routes", () => {
  it("creates a simple request with a real entrance, question, review and ticket result", () => {
    const draft = createScenarioStarter("Выдать доступ", "simple", "access", null);
    expect(draft.blocks?.map(block => block.kind)).toEqual(["form_page", "review", "submit_ticket"]);
    expect(draft.entry_points?.[0]).toMatchObject({ title: "Выдать доступ", target_block_id: draft.blocks![0].id });
    expect(draft.blocks![0].transitions).toEqual([{ to: draft.blocks![1].id }]);
    expect(draft.blocks![1].transitions).toEqual([{ to: draft.blocks![2].id }]);
    expect(draft.offering_full_code).toBe("");
  });
  it("allows self-service completion only after yes, with a safe unknown route", () => {
    const draft = createScenarioStarter("Проблемы с печатью", "diagnostic", "it", null);
    const check = draft.blocks!.find(block => block.kind === "resolution_check")!;
    const finish = draft.blocks!.find(block => block.kind === "finish")!;
    const review = draft.blocks!.find(block => block.kind === "review")!;
    expect(check.transitions).toEqual([
      { to: finish.id, when: { source: "current_result", op: "eq", value: "yes" } },
      { to: review.id, when: { source: "current_result", op: "eq", value: "no" } },
      { to: review.id },
    ]);
    expect(draft.blocks!.filter(block => block.transitions?.some(edge => edge.to === finish.id))).toEqual([check]);
  });
  it("keeps an empty draft empty until its first executable step is added", () => {
    const draft = createScenarioStarter("Своя карта", "empty", "it", null);
    expect(draft.blocks).toEqual([]);
    const next = appendMapStep(draft, null, "form_page");
    expect(next.entry_points?.[0].target_block_id).toBe(next.blocks![0].id);
    expect(next.entry_block_id).toBe(next.blocks![0].id);
  });
  it("inserts into exactly the chosen edge and preserves its condition and priority", () => {
    const draft = createScenarioStarter("Печать", "diagnostic", "it", null);
    const check = draft.blocks!.find(block => block.kind === "resolution_check")!;
    check.transitions![1].priority = 9;
    const before = structuredClone(draft);
    const next = insertOnTransition(draft, check.id, 1, "form_page");
    const added = next.blocks!.at(-1)!;
    expect(next.blocks!.find(block => block.id === check.id)!.transitions![1]).toEqual({ ...check.transitions![1], to: added.id });
    expect(added.transitions).toEqual([{ to: check.transitions![1].to }]);
    expect(next.blocks!.find(block => block.id === check.id)!.transitions![0]).toEqual(check.transitions![0]);
    expect(draft).toEqual(before);
  });
  it("preserves a decision continuation and rejects terminal insertion", () => {
    const draft = createScenarioStarter("Доступ", "simple", "access", null);
    expect(() => insertOnTransition(draft, draft.blocks![0].id, 0, "submit_ticket")).toThrow(/маршрут/);
    const next = appendMapStep(draft, draft.blocks![0].id, "decision");
    expect(next.blocks!.at(-1)!.kind).toBe("decision");
    expect(next.blocks!.at(-1)!.transitions).toEqual([{ to: draft.blocks![0].transitions![0].to }]);
    expect(() => insertOnTransition(draft, draft.blocks![0].id, 0, "resolution_check")).toThrow(/ветв/);
  });
});
