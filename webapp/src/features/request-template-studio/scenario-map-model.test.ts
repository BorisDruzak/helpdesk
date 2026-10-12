import { describe, expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { connectBlocks, insertOnTransition, positionBlock, reconnectTransition, deleteMapBlock } from "./scenario-map-model";

const draft = (): ScenarioDraftDefinition => ({ scenario_key: "test", title: "Карта", service_code: "it", offering_full_code: "it.print", entry_block_id: "q", process_binding: { request_template_key: "print" },
  entry_points: [{ key: "jam", title: "Замятие", target_block_id: "q" }], blocks: [
    { id: "q", kind: "resolution_check", title: "Решено?", transitions: [{ to: "done", when: { op: "eq", source: "current_result", value: "yes" } }, { to: "review" }] },
    { id: "done", kind: "finish", title: "Готово" }, { id: "review", kind: "review", title: "Сводка", transitions: [{ to: "ticket" }] }, { id: "ticket", kind: "submit_ticket", title: "Обращение" },
  ] });
describe("atomic map edits", () => {
  it("moves geometry without changing runtime graph", () => { const d = draft(); const next = positionBlock(d, "q", { x: 700, y: 200 }); expect(next.blocks).toEqual(d.blocks); expect(next.entry_points).toEqual(d.entry_points); expect(next.editor_layout?.positions?.q).toEqual({ x: 700, y: 200 }); });
  it("reconnects only the selected transition and retains its condition", () => { const d = draft(); const next = reconnectTransition(d, "q", 0, "review"); expect(next.blocks?.[0].transitions?.[0]).toEqual({ ...d.blocks![0].transitions![0], to: "review" }); expect(next.blocks?.[0].transitions?.[1]).toEqual(d.blocks![0].transitions![1]); });
  it("inserts a normal continuation and preserves the original condition", () => { const d = draft(); const next = insertOnTransition(d, "q", 0, "instruction"); const added = next.blocks!.find(b => !d.blocks!.some(old => old.id === b.id))!; expect(next.blocks![0].transitions![0]).toEqual({ ...d.blocks![0].transitions![0], to: added.id }); expect(added.transitions).toEqual([{ to: "done" }]); expect(d.blocks).toHaveLength(4); });
  it("rejects terminal insertion and cycles atomically", () => { const d = draft(); expect(() => insertOnTransition(d, "q", 0, "finish")).toThrow(); expect(() => connectBlocks(d, "review", "q")).toThrow(/цикл/); expect(d).toEqual(draft()); });
  it("requires explicit entrance resolution before deleting its target", () => { const d = draft(); expect(() => deleteMapBlock(d, "q", "review")).toThrow(/точк/); const next = deleteMapBlock(d, "q", "review", "reassign"); expect(next.entry_points![0].target_block_id).toBe("review"); expect(next.entry_block_id).toBe("review"); expect(next.blocks!.some(b => b.id === "q")).toBe(false); });
  it("can explicitly remove draft entrances atomically", () => { const next = deleteMapBlock(draft(), "q", "review", "remove"); expect(next.entry_points).toEqual([]); });
});
