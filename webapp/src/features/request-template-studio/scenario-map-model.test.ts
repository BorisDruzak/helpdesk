import { describe, expect, it } from "vitest";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { connectStart, reconnectStart, connectBlocks, insertOnTransition, positionBlock, reconnectTransition, deleteMapBlock } from "./scenario-map-model";

const draft = (): ScenarioDraftDefinition => ({ scenario_key: "test", title: "Карта", service_code: "it", offering_full_code: "it.print", entry_block_id: "q", process_binding: { request_template_key: "print" },
  entry_points: [{ key: "jam", title: "Замятие", target_block_id: "q" }], blocks: [
    { id: "q", kind: "resolution_check", title: "Решено?", transitions: [{ to: "done", when: { op: "eq", source: "current_result", value: "yes" } }, { to: "review" }] },
    { id: "done", kind: "finish", title: "Готово" }, { id: "review", kind: "review", title: "Сводка", transitions: [{ to: "ticket" }] }, { id: "ticket", kind: "submit_ticket", title: "Обращение" },
  ] });
describe("atomic map edits", () => {
  it("freezes legacy default positions before deletion so other blocks do not follow", () => {
    const next = deleteMapBlock(draft(), "done", null, undefined, "detach");
    expect(next.blocks![0].transitions).toEqual([{ to: "review" }]);
    expect(next.editor_layout?.positions?.review).toEqual({ x: 620, y: 0 });
    expect(next.editor_layout?.positions?.ticket).toEqual({ x: 0, y: 200 });
  });
  it("removes an entrance and its main start explicitly without requiring a replacement", () => {
    const next = deleteMapBlock(draft(), "q", null, "remove", "detach");
    expect(next.entry_block_id).toBeNull(); expect(next.entry_points).toEqual([]);
  });
  it("moves geometry without changing runtime graph", () => { const d = draft(); const next = positionBlock(d, "q", { x: 700, y: 200 }); expect(next.blocks).toEqual(d.blocks); expect(next.entry_points).toEqual(d.entry_points); expect(next.editor_layout?.positions?.q).toEqual({ x: 700, y: 200 }); });
  it("reconnects only the selected transition and retains its condition", () => { const d = draft(); const next = reconnectTransition(d, "q", 0, "review"); expect(next.blocks?.[0].transitions?.[0]).toEqual({ ...d.blocks![0].transitions![0], to: "review" }); expect(next.blocks?.[0].transitions?.[1]).toEqual(d.blocks![0].transitions![1]); });
  it("inserts a normal continuation and preserves the original condition", () => { const d = draft(); const next = insertOnTransition(d, "q", 0, "instruction"); const added = next.blocks!.find(b => !d.blocks!.some(old => old.id === b.id))!; expect(next.blocks![0].transitions![0]).toEqual({ ...d.blocks![0].transitions![0], to: added.id }); expect(added.transitions).toEqual([{ to: "done" }]); expect(d.blocks).toHaveLength(4); });
  it("honors a deliberate drop position without mutating its input", () => { const d = draft(), point = { x: 0, y: 0 }; const next = insertOnTransition(d, "q", 0, "instruction", point); expect(next.editor_layout?.positions?.[next.blocks!.at(-1)!.id]).toEqual(point); expect(point).toEqual({ x: 0, y: 0 }); });
  it("rejects terminal insertion and cycles atomically", () => { const d = draft(); expect(() => insertOnTransition(d, "q", 0, "finish")).toThrow(); expect(() => connectBlocks(d, "review", "q")).toThrow(/цикл/); expect(d).toEqual(draft()); });
  it("requires explicit entrance resolution before deleting its target", () => { const d = draft(); expect(() => deleteMapBlock(d, "q", "review")).toThrow(/точк/); const next = deleteMapBlock(d, "q", "review", "reassign"); expect(next.entry_points![0].target_block_id).toBe("review"); expect(next.entry_block_id).toBe("review"); expect(next.blocks!.some(b => b.id === "q")).toBe(false); });
  it("can explicitly remove draft entrances atomically", () => { const next = deleteMapBlock(draft(), "q", "review", "remove"); expect(next.entry_points).toEqual([]); });
});

describe("start connections", () => {
 it("adds an entrance atomically without adding a runtime block or changing the main entrance",()=>{const d=draft();const next=connectStart(d,"review");expect(next.entry_points).toHaveLength(2);expect(next.entry_points?.[1]).toMatchObject({title:"Сводка",target_block_id:"review",enabled:true});expect(next.blocks).toEqual(d.blocks);expect(next.entry_block_id).toBe("q");expect(connectStart(next,"review")).toBe(next);});
 it("preserves entrance metadata during reconnect and validates targets and limits",()=>{const d=draft();d.entry_points![0].synonyms=["бумага"];expect(reconnectStart(d,"jam","review").entry_points?.[0]).toMatchObject({key:"jam",synonyms:["бумага"],target_block_id:"review"});expect(reconnectStart(d,null,"review").entry_block_id).toBe("review");expect(()=>connectStart(d,"missing")).toThrow();d.entry_points=Array.from({length:64},(_,i)=>({key:`e${i}`,title:"Вход",target_block_id:"q"}));expect(()=>connectStart(d,"review")).toThrow(/64/);});
 it("chooses the first start only when no main entrance exists",()=>{const d=draft();d.entry_block_id=null;expect(connectStart(d,"review").entry_block_id).toBe("review");});
});
