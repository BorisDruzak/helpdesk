import { expect, it } from "vitest";
import { scenarioMapHints } from "./scenario-map-hints";
import type { ScenarioDraftDefinition } from "./scenario-contract";
const base: ScenarioDraftDefinition = { scenario_key: "test", title: "Карта", service_code: "it", offering_full_code: "it.printer", process_binding: { request_template_key: "printer" }, entry_block_id: "a", blocks: [{ id: "a", title: "Инструкция", kind: "instruction", content: { body: "Шаг" }, transitions: [{ to: "end" }] }, { id: "end", title: "Обращение", kind: "submit_ticket" }] };
it("points an empty map to service selection and blocks without claiming readiness", () => {
 const hints = scenarioMapHints({ ...base, offering_full_code: "", blocks: [], entry_block_id: null });
 expect(hints).toEqual(expect.arrayContaining([expect.objectContaining({ code: "offering" }), expect.objectContaining({ target: "blocks" })]));
});
it("locates unfinished and disconnected steps, counting configured entrances as graph starts", () => {
 const definition = { ...base, blocks: [...base.blocks!, { id: "extra", title: "Дополнительный шаг", kind: "instruction" as const, content: { body: "" }, transitions: [] }] };
 expect(scenarioMapHints(definition)).toEqual(expect.arrayContaining([expect.objectContaining({ code: "disconnected", blockId: "extra" }), expect.objectContaining({ code: "missing_route", blockId: "extra" }), expect.objectContaining({ code: "instruction_empty", blockId: "extra" })]));
 expect(scenarioMapHints({ ...definition, entry_points: [{ key: "special", title: "Другой вход", target_block_id: "extra" }] }).some(hint => hint.code === "disconnected")).toBe(false);
});
it("allows legacy single entrance and does not invent policy readiness", () => {
 expect(scenarioMapHints(base).filter(hint => hint.level === "required")).toEqual([]);
 expect(scenarioMapHints(base).some(hint => hint.code === "catalog_entrances")).toBe(true);
});
it("recognizes a positive check inside a compound condition but detects bypass entrances",()=>{
 const definition: ScenarioDraftDefinition = {...base,entry_block_id:"check",blocks:[{id:"check",title:"Решено?",kind:"resolution_check",transitions:[{to:"done",when:{op:"and",conditions:[{source:"current_result",op:"eq",value:"yes"}]}},{to:"ticket"}]},{id:"done",title:"Готово",kind:"finish"},{id:"ticket",title:"Обращение",kind:"submit_ticket"}]};
 expect(scenarioMapHints(definition).some(hint=>hint.code==="unconfirmed_finish")).toBe(false);
 expect(scenarioMapHints({...definition,entry_points:[{key:"bypass",title:"Отдельный вход",target_block_id:"done"}]})).toEqual(expect.arrayContaining([expect.objectContaining({code:"unconfirmed_finish",blockId:"done"})]));
});
